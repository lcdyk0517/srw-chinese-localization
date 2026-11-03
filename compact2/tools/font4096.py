# -*- coding: utf-8 -*-
"""WS2 4096-slot font expansion (E000-EFFF, 4 chunks of 1024 glyphs).

Font renderer: bank 0x3F, string loop + two-byte dispatcher + kanji setup.
Each chunk is stored in the free FF run of a separate bank; the cave switches
C2 to the chunk bank and computes the glyph address.
"""
from pathlib import Path
import subprocess, tempfile, os
from PIL import Image, ImageDraw, ImageFont
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"

CONFIG = {
    "D1": dict(
        rom="Super Robot Taisen Compact 2 - Dai-1-bu - Chijou Gekidou Hen (Japan).ws",
        strloop=0x3F55FE, dispatch=0x3F5677, dispatch_jmp=0x3F567B,
        exit=0x3F5917, setup=0x591A, setup_dx=0x5948, ret=0x5A86,
        cave=0xE018, tramp=0x1C64,
        chunks=[(0x3B,0x0000),(0x18,0x0000),(0x1A,0x7380),(0x04,0x0000)],
    ),
    "D2": dict(
        rom="Super Robot Taisen Compact 2 - Dai-2-bu - Uchuu Gekishin Hen (Japan) (Rev 4).ws",
        strloop=0x3F56EA, dispatch=0x3F5763, dispatch_jmp=0x3F5767,
        exit=0x3F5A03, setup=0x5A06, setup_dx=0x5A34, ret=0x5B72,
        cave=0xE4A6, tramp=0x1C94,
        chunks=[(0x3B,0x0000),(0x18,0x1A09),(0x27,0x3494),(0x39,0x5FC1)],
    ),
    "D3": dict(
        rom="Super Robot Taisen Compact 2 - Dai-3-bu - Ginga Kessen Hen (Japan) (Rev 2).ws",
        strloop=0x3F5726, dispatch=0x3F579F, dispatch_jmp=0x3F57A3,
        exit=0x3F5A3F, setup=0x5A42, setup_dx=0x5A70, ret=0x5BAE,
        cave=0xE6DE, tramp=0x1C94,
        chunks=[(0x27,0x3480),(0x18,0x376E),(0x3B,0x3E48),(0x21,0x70EC)],
    ),
}

CAVE_TMPL = r"""bits 16
org 0x{cave:04X}
start:
    cmp al, 0xF2
    jae orig
    mov bh, al
    mov al, ah
    xor ah, ah
    xor bl, bl
    sub bh, 0xE0
    add ax, bx
    mov cx, ax
    mov dx, ax
    and dx, 0x03FF
    mov bx, ax
    shr bx, 1
    shr bx, 1
    shr bx, 1
    shr bx, 1
    shr bx, 1
    shr bx, 1
    shr bx, 1
    shr bx, 1
    shr bx, 1
    shr bx, 1
    mov ax, bx
    shl bx, 1
    add bx, ax
    mov al, [cs:bx+chantab]
    mov si, [cs:bx+chantab+1]
    or al, 0xC0
    out 0xC2, al
    mov ax, dx
    and ax, 7
    shl ax, 4
    and dx, 0xFFF8
    shl dx, 5
    mov di, si
    add di, dx
    add di, ax
    mov si, [0x0206]
    mov dx, 0x2000
    mov es, dx
    jmp 0xF000:0x{setup_dx:04X}
orig:
    jmp 0xF000:0x{setup:04X}
chantab:
{chantab}
"""

TRAMP_TMPL = r"""bits 16
org 0x{tramp:04X}
    jmp 0xF000:0x{cave:04X}
times 0x0C-($-$$) db 0x90
restore:
    push ax
    mov al, 0xF0
    out 0xC2, al
    pop ax
    jmp 0xF000:0x{ret:04X}
"""

def asm(src, tag):
    p = TOOLS / f"_font4096_{tag}.asm"
    b = TOOLS / f"_font4096_{tag}.bin"
    p.write_text(src, encoding="utf-8")
    subprocess.run(["nasm", "-f", "bin", "-o", str(b), str(p)], check=True)
    return b.read_bytes()

def build(key, out_suffix="_test"):
    cfg = CONFIG[key]
    rom = bytearray((ROOT / cfg["rom"]).read_bytes())
    chantab = "\n".join(f"    db 0x{bank:02X}\n    dw 0x{base:04X}" for bank, base in cfg["chunks"])
    cave = asm(CAVE_TMPL.format(cave=cfg["cave"], setup=cfg["setup"], setup_dx=cfg["setup_dx"], chantab=chantab), key+"_cave")
    tramp = asm(TRAMP_TMPL.format(tramp=cfg["tramp"], cave=cfg["cave"], ret=cfg["ret"]), key+"_tramp")
    assert all(b == 0xFF for b in rom[0x3F0000+cfg["cave"]:0x3F0000+cfg["cave"]+len(cave)]), "cave not free"
    assert all(b == 0xFF for b in rom[0x3F0000+cfg["tramp"]:0x3F0000+cfg["tramp"]+len(tramp)]), "tramp not free"
    rom[0x3F0000+cfg["cave"]:0x3F0000+cfg["cave"]+len(cave)] = cave
    rom[0x3F0000+cfg["tramp"]:0x3F0000+cfg["tramp"]+len(tramp)] = tramp
    rom[cfg["strloop"]+1] = 0xE0
    rom[cfg["dispatch"]+1] = 0xE0
    rel = cfg["tramp"] - (cfg["dispatch_jmp"] + 3)
    rom[cfg["dispatch_jmp"]:cfg["dispatch_jmp"]+3] = b"\xE9" + (rel & 0xFFFF).to_bytes(2, "little")
    rel2 = (cfg["tramp"] + 0x0C) - (cfg["exit"] + 3)
    rom[cfg["exit"]:cfg["exit"]+3] = b"\xE9" + (rel2 & 0xFFFF).to_bytes(2, "little")
    out = ROOT / (cfg["rom"].replace(".ws", out_suffix + ".ws"))
    out.write_bytes(rom)
    print("wrote", out, "cave", hex(cfg["cave"]), "tramp", hex(cfg["tramp"]))
    return out, rom, cfg

def pack_glyph(ch, font_path=r"C:\Windows\Fonts\simsun.ttc", size=12, origin=(1, 2)):
    """Return 32 bytes: top16 (TL rows then TR rows) + bottom16 (BL then BR)."""
    font = ImageFont.truetype(font_path, size)
    im = Image.new("L", (16, 16), 0)
    ImageDraw.Draw(im).text(origin, ch, font=font, fill=255)
    a = (np.array(im) > 128).astype(np.uint8)
    def row(y, x0, x1):
        v = 0
        for x in range(x0, x1): v = (v << 1) | int(a[y, x])
        return v
    top = bytes([row(y, 0, 8) for y in range(8)] + [row(y, 8, 16) for y in range(8)])
    bot = bytes([row(y, 0, 8) for y in range(8, 16)] + [row(y, 8, 16) for y in range(8, 16)])
    return top + bot

def write_chars(rom, cfg, chars, start=0xE000):
    """chars: iterable of unique chars; allocate consecutive codes. Returns char->code."""
    mapping = {}
    for i, ch in enumerate(chars):
        code = start + i
        if code > 0xEFFF: raise ValueError("font overflow")
        write_glyph(rom, cfg, code, pack_glyph(ch))
        mapping[ch] = code
    return mapping

def write_glyph(rom, cfg, code, glyph):
    """glyph = 32 bytes: top16 (TL block + TR block) then bottom16 (BL block + BR block)."""
    n = code - 0xE000
    chunk = n >> 10
    local = n & 0x3FF
    bank, base = cfg["chunks"][chunk]
    k, r = local >> 3, local & 7
    di = base + k*0x100 + r*0x10
    addr = bank*0x10000 + di
    rom[addr:addr+16] = glyph[:16]
    rom[addr+0x80:addr+0x90] = glyph[16:]
    return addr

if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == "base":
        for k in sys.argv[2:]:
            out, rom, cfg = build(k, out_suffix="_base")
            dst = ROOT / "expanded" / f"{k}_4096.ws"
            dst.parent.mkdir(exist_ok=True)
            dst.write_bytes(rom)
            print("base", dst)
    else:
        for k in (sys.argv[1:] or ["D1"]):
            build(k)
