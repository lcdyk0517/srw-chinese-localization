# -*- coding: utf-8 -*-
"""WS2 trilogy text/code helpers (fonts verified at 0x300000/0x301000)."""
import json, struct, re, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(r"D:\WSC3\构建\assets")

HIRAGANA = "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
SMALL_HIRA = "ぁぃぅぇぉゃゅょっ"
PA_HIRA = "ぱぴぷぺぽ"
KATAKANA = "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン"
SMALL_KATA = "ァィゥェォャュョッ"
PA_KATA = "パピプペポ"
SINGLE = {}
_c = 0x01
for s in (HIRAGANA, SMALL_HIRA, PA_HIRA, KATAKANA, SMALL_KATA, PA_KATA):
    for ch in s:
        SINGLE[_c] = ch; _c += 1
for i, ch in enumerate("0123456789"): SINGLE[0x79+i] = ch
for i, ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"): SINGLE[0x83+i] = ch
for i, ch in enumerate("abcdefghijklmnopqrstuvwxyz"): SINGLE[0x9D+i] = ch
SINGLE.update({0xB7:"。",0xB8:"、",0xB9:"’",0xBA:",",0xBB:"・",0xBC:"‥",0xBD:"ー",
 0xBE:"+",0xBF:"±",0xC0:"=",0xC1:"％",0xC2:"/",0xC3:":",0xC4:"~",0xC5:"!",0xC6:"?",
 0xC7:"「",0xC8:"」",0xC9:"(",0xCA:")",0xCB:"Ⓟ",0xCC:"Ⓑ",0xCD:"㊂",0xCE:"⊕",
 0xCF:"（圈8）",0xD0:"▶",0xD1:"×",0xD2:"ν",0xD3:"Ⅰ",0xD4:"Ⅱ",0xD5:"Ⅲ",
 0xD6:"Ⅳ",0xD7:"Ⅴ",0xD8:"∧",0xD9:"◀",0xDA:"◀",0xDB:"▶",0xDC:"▶",0xDD:"[",0xDE:"]"})
SINGLE[0x00] = ""
for _c in range(0xDF, 0xF0): SINGLE[_c] = ""

F0_KANA = {0x06:"が",0x07:"ぎ",0x08:"ぐ",0x09:"げ",0x0A:"ご",0x0B:"ざ",0x0C:"じ",0x0D:"ず",0x0E:"ぜ",0x0F:"ぞ",
 0x10:"だ",0x11:"ぢ",0x12:"づ",0x13:"で",0x14:"ど",0x1A:"ば",0x1B:"び",0x1C:"ぶ",0x1D:"べ",0x1E:"ぼ",
 0x42:"ガ",0x43:"ギ",0x44:"グ",0x45:"ゲ",0x46:"ゴ",0x47:"ザ",0x48:"ジ",0x49:"ズ",0x4A:"ゼ",0x4B:"ゾ",
 0x4C:"ダ",0x4D:"ヂ",0x4E:"ヅ",0x4F:"デ",0x50:"ド",0x51:"パ",0x52:"ピ",0x53:"プ",0x54:"ペ",0x55:"ポ",
 0x56:"バ",0x57:"ビ",0x58:"ブ",0x59:"ベ",0x5A:"ボ"}

# Corrections found by glyph inspection in WS2 (WSC3 jsonl was wrong at these).
KANJI_OVERRIDES = {
    int(k, 16): v for k, v in
    json.loads((Path(__file__).resolve().parent / "assets" / "kanji_overrides.json").read_text(encoding="utf-8")).items()
}

def load_kanji():
    d = {}
    p = DATA / "verified_kanji.jsonl"
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line); d[int(r["code"],16)] = r["char"]
    d.update(KANJI_OVERRIDES)
    return d

KANJI = load_kanji()

def read_string(rom, off, limit=600):
    """Return (tokens, hexdump, bad, kana, ctrl). Stops at FF."""
    i = off; out=[]; hx=[]; bad=0; kana=0; ctrl=0
    while i < len(rom) and i-off < limit:
        c = rom[i]
        if c == 0xFF: break
        if 0xF0 <= c <= 0xF9:
            if i+1 >= len(rom): break
            n = rom[i+1]; code = (c<<8)|n; hx.append(rom[i:i+2].hex())
            i += 2
            if c == 0xF0:
                ch = F0_KANA.get(n)
                if ch: out.append(ch); kana += 1
                else: out.append(f"{{F0:{n:02X}}}"); bad += 1
            elif c == 0xF1:
                out.append(f"{{F1:{n:02X}}}"); ctrl += 1
            else:
                ch = KANJI.get(code)
                if ch and not ch.startswith("（"):
                    out.append(ch)
                else:
                    out.append(f"{{K:{code:04X}}}"); bad += 1
        elif c in (0xFC, 0xFD):
            if i+1 >= len(rom): break
            n=rom[i+1]; hx.append(rom[i:i+2].hex()); i+=2
            out.append(f"{{{c:02X}:{n:02X}}}"); ctrl += 1
        elif c == 0xFE:
            hx.append("fe"); i+=1; out.append("/")
        else:
            hx.append(f"{c:02x}")
            ch = SINGLE.get(c)
            if c == 0: pass
            elif ch is None: out.append(f"{{{c:02X}}}"); bad += 1
            else:
                out.append(ch)
                if 0x01 <= c <= 0x78: kana += 1
            i += 1
    return "".join(out), " ".join(hx), bad, kana, ctrl

def split_speaker(text):
    pos = text.find("「")
    if pos <= 0: return "", text
    pre = text[:pos]
    stripped = re.sub(r"\{[A-Za-z0-9:]+\}", "", pre)
    if len(stripped) <= 16 and not any(ch in stripped for ch in "。、!?」/"):
        return pre, text[pos:]
    return "", text

def parse_table(rom, bank, toff=0, count=None):
    base = bank*0x10000
    first = struct.unpack_from("<H", rom, base+toff)[0]
    if count is None:
        count = (first-toff)//2
    return [struct.unpack_from("<H", rom, base+toff+2*k)[0] for k in range(count)], first

def glyph16_kanji(rom, code, base=0x301000):
    lead, sec = code>>8, code&0xFF
    n = (lead-0xF2)*256+sec; k=n>>3; r=n&7; di=k*0x100+r*0x10
    return rom[base+di:base+di+16] + rom[base+di+0x80:base+di+0x90]

PLACEHOLDER_GLYPH = bytes.fromhex(
    "0000007f5f5f6f77000000f0d0d0b0705858776f5f5f7f00d0d070b0d0d0f000")

def glyph_bytes(rom, code, base=0x301000):
    lead, sec = code >> 8, code & 0xFF
    n = (lead - 0xF2) * 256 + sec
    k, r = n >> 3, n & 7
    di = k * 0x100 + r * 0x10
    return rom[base + di: base + di + 16] + rom[base + di + 0x80: base + di + 0x90]

def measure(rom, off, limit=600):
    """Return (max_line_px, line_count, placeholder_count, raw_bytes)."""
    i = off; line = 0; mx = 0; lines = 1; ph = 0
    while i < len(rom) and i - off < limit:
        c = rom[i]
        if c == 0xFF:
            break
        if 0xF0 <= c <= 0xF9:
            n = rom[i + 1]; i += 2
            if c == 0xF0:
                line += 8
            elif c == 0xF1:
                line += 16
            else:
                line += 16
                if glyph_bytes(rom, (c << 8) | n) == PLACEHOLDER_GLYPH:
                    ph += 1
        elif c in (0xFC, 0xFD):
            i += 2
        elif c == 0xFE:
            mx = max(mx, line); line = 0; lines += 1; i += 1
        else:
            if 1 <= c <= 0xDE:
                line += 8
            i += 1
    mx = max(mx, line)
    return mx, lines, ph

# ---------------------------------------------------------------------------
# WS2 build helpers
# ---------------------------------------------------------------------------
import zlib, hashlib
import openpyxl
from openpyxl.styles import Font as _Font, PatternFill as _Fill
from PIL import Image, ImageDraw, ImageFont
import numpy as np

BUILD = Path(__file__).resolve().parent
ASSETS = BUILD / "assets"
# WS2_FONT=fusion 时用融合像素字体生成第二套字模；默认宋体。
FONT_CHOICE = os.environ.get("WS2_FONT", "simsun").strip().lower()
FONT_PATH = ASSETS / "fonts" / (
    "fusion-pixel-12px-monospaced-zh_hans.ttf"
    if FONT_CHOICE == "fusion" else "simsun.ttc")
SINGLE_FONT_PATH = ASSETS / "fonts" / "zpix.ttf"

ADDR = {
    "D1": dict(strloop=0x3F55FE, strloop_dlg=0x3F547D, dispatch=0x3F5677, dispatch_jmp=0x3F567B, exit=0x3F5917, f1loop=0x3F5AC6,
               inc20a=0x5A81, ret=0x5A86, c2stub=0x1C80),
    "D2": dict(strloop=0x3F56EA, strloop_dlg=0x3F5569, dispatch=0x3F5763, dispatch_jmp=0x3F5767, exit=0x3F5A03, f1loop=0x3F5BB2,
               inc20a=0x5B6D, ret=0x5B72, c2stub=0x1CB0),
    "D3": dict(strloop=0x3F5726, strloop_dlg=0x3F55A5, dispatch=0x3F579F, dispatch_jmp=0x3F57A3, exit=0x3F5A3F, f1loop=0x3F5BEE,
               inc20a=0x5BA9, ret=0x5BAE, c2stub=0x1CB0),
}

REV_SINGLE = {v: k for k, v in SINGLE.items() if v}
REV_F0 = {v: k for k, v in F0_KANA.items()}
REV_KANJI = {v: k for k, v in KANJI.items() if v and not v.startswith("（")}

def load_cfg():
    wb = openpyxl.load_workbook(BUILD / "text.xlsx", read_only=True, data_only=True)
    ws = wb["设定"]; cfg = {}
    for k, v in ws.iter_rows(min_row=2, values_only=True):
        if k: cfg[str(k)] = v
    return cfg

def num(v, default=0):
    if v is None or v == "": return default
    if isinstance(v, (int, float)): return int(v)
    s = str(v).strip()
    try: return int(s, 0)
    except Exception: return default

def chunks(cfg):
    out = []
    for part in str(cfg.get("CHUNKS", "")).split(","):
        if ":" in part:
            b, base = part.split(":"); out.append((int(b, 16), int(base, 16)))
    return out

def pack_glyph(ch, font_path=FONT_PATH, size=12, origin=(1, 3)):
    font = ImageFont.truetype(str(font_path), size)
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

def single_glyph(rom, code):
    idx = code - 1; di = (idx >> 4) * 0x100 + (idx & 0xF) * 8
    return rom[0x300000 + di:0x300000 + di + 8] + rom[0x300000 + di + 0x80:0x300000 + di + 0x88]

def pack_single_glyph(ch, font_path=SINGLE_FONT_PATH, size=12):
    """8x16 half-width cell; Zpix 12px strike, same as the WSC3 build."""
    font = ImageFont.truetype(str(font_path), size, index=0)
    im = Image.new("L", (32, 32), 0)
    ImageDraw.Draw(im).text((0, 0), ch, font=font, fill=255)
    bb = im.getbbox()
    if not bb:
        return bytes(16)
    g = im.crop(bb)
    if g.width > 8:
        g = g.resize((8, g.height), Image.LANCZOS)
    g = g.point(lambda p: 255 if p > 128 else 0)
    out = Image.new("L", (8, 16), 0)
    px = (8 - g.width) // 2 + 1
    if ch == "S": px = 1
    if px + g.width > 8: px = 8 - g.width
    py = 14 - (g.height - 1) - 1
    if py < 0: py = 0
    out.paste(g, (px, py))
    bits = []
    for y in range(16):
        v = 0
        for x in range(8):
            if out.getpixel((x, y)) > 128: v |= 0x80 >> x
        bits.append(v)
    return bytes(bits)

def write_single_ascii(rom):
    for code in range(0x79, 0x9D):
        ch = SINGLE.get(code)
        if not ch or len(ch) != 1:
            continue
        g = pack_single_glyph(ch)
        idx = code - 1
        di = (idx >> 4) * 0x100 + (idx & 0xF) * 8
        rom[0x300000 + di:0x300000 + di + 8] = g[:8]
        rom[0x300000 + di + 0x80:0x300000 + di + 0x88] = g[8:]

def apply_patch(rom, cfg):
    game = str(cfg["GAME"]); a = ADDR[game]
    cave = (ASSETS / "font4096_cave.bin").read_bytes()
    tramp = (ASSETS / "font4096_tramp.bin").read_bytes()
    co = num(cfg["CAVE"]); to = num(cfg["TRAMP"])
    if any(b != 0xFF for b in rom[0x3F0000 + co:0x3F0000 + co + len(cave)]):
        raise RuntimeError("cave not free")
    if any(b != 0xFF for b in rom[0x3F0000 + to:0x3F0000 + to + len(tramp)]):
        raise RuntimeError("tramp not free")
    rom[0x3F0000 + co:0x3F0000 + co + len(cave)] = cave
    rom[0x3F0000 + to:0x3F0000 + to + len(tramp)] = tramp
    rom[a["strloop"] + 1] = 0xE0
    rom[a["strloop_dlg"] + 1] = 0xE0
    rom[a["f1loop"] + 1] = 0xE0
    rom[a["dispatch"] + 1] = 0xE0
    # E0 cave leaves C2 on the chunk bank; restore the font bank before the
    # inc that both glyph-draw branches run, or the next 1-byte glyph reads
    # from the chunk bank (e.g. period after a kanji becomes another glyph).
    stub = (b"\x50\xB0\xF0\xE6\xC2\x58\x36\xFF\x06\x0A\x02\xEA"
            + (a["ret"] & 0xFFFF).to_bytes(2, "little") + b"\x00\xF0")
    so = 0x3F0000 + a["c2stub"]
    if any(b != 0xFF for b in rom[so:so + len(stub)]):
        raise RuntimeError("C2 stub not free")
    rom[so:so + len(stub)] = stub
    io = 0x3F0000 + a["inc20a"]
    rom[io:io + 5] = b"\xEA" + (a["c2stub"] & 0xFFFF).to_bytes(2, "little") + b"\x00\xF0"
    rel = to - (a["dispatch_jmp"] + 3)
    rom[a["dispatch_jmp"]:a["dispatch_jmp"] + 3] = b"\xE9" + (rel & 0xFFFF).to_bytes(2, "little")
    rel2 = (to + 0x0C) - (a["exit"] + 3)
    rom[a["exit"]:a["exit"] + 3] = b"\xE9" + (rel2 & 0xFFFF).to_bytes(2, "little")
    return rom

CMAP_REG = Path(__file__).resolve().parent / "assets" / "cmap_fixed.json"

def alloc_codes(chars):
    """持久码位表：先按 assets/cmap_fixed.json 固定已有字符，再给新字分配空闲码。
    这样重建/增删译文不会让旧存档里的姓名、默认名等码位漂移。"""
    if not CMAP_REG.exists():
        raise RuntimeError("码位固定表缺失，禁止重新分配: %s" % CMAP_REG)
    fixed = {ch: int(v, 16) for ch, v in
             json.loads(CMAP_REG.read_text(encoding="utf-8")).items()}
    chars = set(chars)
    # 固定表里所有码位都保留，不能让新字复用已删除字符的槽位。
    used = set(fixed.values())
    cmap = {}; assigned = set()
    for ch in sorted(chars):
        code = fixed.get(ch)
        if (code is not None and 0xE000 <= code <= 0xEFFF
                and (code & 0xFF) not in (0xFD, 0xFE, 0xFF) and code not in assigned):
            cmap[ch] = code; assigned.add(code)
    code = 0xE000
    for ch in sorted(chars - set(cmap)):
        while code in used or (code & 0xFF) in (0xFD, 0xFE, 0xFF):
            code += 1
        if code > 0xEFFF:
            raise RuntimeError("4096 font overflow")
        cmap[ch] = code; used.add(code); fixed[ch] = code
    rev = {}
    for ch, c in fixed.items():
        if c in rev and rev[c] != ch:
            raise RuntimeError("cmap_fixed 重复码位 %04X: %s/%s" % (c, rev[c], ch))
        rev[c] = ch
    for ch, c in cmap.items(): fixed[ch] = c
    CMAP_REG.write_text(json.dumps({ch: "%04X" % c for ch, c in sorted(fixed.items())},
                                   ensure_ascii=False, indent=0), encoding="utf-8")
    return cmap

def write_font(rom, cfg, cmap):
    chs = chunks(cfg)
    for ch, code in cmap.items():
        n = code - 0xE000
        chunk = n >> 10; local = n & 0x3FF
        if chunk >= len(chs): raise RuntimeError("chunk overflow")
        bank, base = chs[chunk]
        di = base + (local >> 3) * 0x100 + (local & 7) * 0x10
        addr = bank * 0x10000 + di
        g = pack_glyph(ch)
        if any(b != 0xFF for b in rom[addr:addr + 16]) or any(b != 0xFF for b in rom[addr + 0x80:addr + 0x90]):
            raise RuntimeError("font slot not free: %s %04X" % (ch, code))
        rom[addr:addr + 16] = g[:16]
        rom[addr + 0x80:addr + 0x90] = g[16:]

_PLACEHOLDER = re.compile(r"\{([A-Za-z0-9]+):([0-9A-Fa-f]+)\}")

def encode(text, cmap, newline_blank=False):
    text = str(text).replace(" / ", "/").replace("／", "/")
    out = bytearray(); missing = []
    i = 0
    while i < len(text):
        if text[i] == "{":
            m = _PLACEHOLDER.match(text, i)
            if m:
                tag, val = m.group(1).upper(), m.group(2)
                if tag in ("F0","F1","F2","F3","F4","F5","F6","F7","F8","F9","FC","FD") and len(val) <= 2:
                    out += bytes([int(tag, 16), int(val, 16)]); i = m.end(); continue
                if tag == "K" and len(val) <= 4:
                    code = int(val, 16); out += bytes([code >> 8, code & 0xFF]); i = m.end(); continue
                if tag == "B" and len(val) == 2:
                    out.append(int(val, 16)); i = m.end(); continue
        ch = text[i]; i += 1
        if ch in ("/", "\n"):
            out.append(0xFE)
            if newline_blank:
                out.append(0x00)
        elif ch in REV_SINGLE:
            out.append(REV_SINGLE[ch])
        elif ch in REV_F0:
            out += bytes([0xF0, REV_F0[ch]])
        elif ch in cmap:
            c = cmap[ch]; out += bytes([c >> 8, c & 0xFF])
        elif ch in REV_KANJI:
            c = REV_KANJI[ch]; out += bytes([c >> 8, c & 0xFF])
        elif ch.isspace():
            continue
        else:
            missing.append(ch)
    return bytes(out), missing

def _string_end(rom, start, limit):
    i = start
    while i < limit and rom[i] != 0xFF:
        i += 1
    return min(i + 1, limit)

def _bank_cursor(rom, base, first, toff, count):
    last = 0
    for i in range(0xFFFF, -1, -1):
        if rom[base + i] != 0xFF:
            last = i; break
    mx = first
    for idx in range(count):
        v = int.from_bytes(rom[base + toff + 2 * idx:base + toff + 2 * idx + 2], "little")
        if 0x0400 <= v < 0x10000:
            mx = max(mx, _string_end(rom, base + v, base + 0x10000) - base)
    cur = max(last + 1, mx)
    if cur & 1: cur += 1
    if cur >= 0x10000 or any(b != 0xFF for b in rom[base + cur:base + 0x10000]):
        return None
    return cur

def import_story(rom, cfg, stats):
    wb = openpyxl.load_workbook(BUILD / "text.xlsx", read_only=True, data_only=True)
    for name in wb.sheetnames:
        if not (name.startswith("剧情_") or name == "旁白"):
            continue
        ws = wb[name]; rows = list(ws.iter_rows(min_row=2, values_only=True))
        if name == "旁白":
            bank = int(str(cfg["NARR_BANK"]), 16); toff = num(cfg["NARR_TOFF"]); base = bank * 0x10000
            first = int.from_bytes(rom[base + toff:base + toff + 2], "little")
            count = max(0, (first - toff) // 2)
        else:
            bank = int(name.split("_")[1], 16); toff = 0; base = bank * 0x10000
            first = int.from_bytes(rom[base:base + 2], "little")
            count = max(0, first // 2)
        trans = [r for r in rows if len(r) > 7 and r[7]]
        if not trans:
            continue
        cur = _bank_cursor(rom, base, first, toff, count)
        if cur is None:
            stats.setdefault("skipped", []).append((name, "no free tail"))
            continue
        ok = 0
        for r in trans:
            try: idx = int(r[1])
            except Exception: continue
            if idx >= count: continue
            enc, missing = encode(r[7], stats["cmap"], newline_blank=True)
            if len(r) > 4 and r[4] is not None and str(r[4]).strip().lower().startswith("00"):
                enc = bytes([0x00]) + enc
            if missing:
                stats.setdefault("missing", []).extend(missing); continue
            if cur + len(enc) + 1 > 0x10000:
                stats.setdefault("skipped", []).append((name, "bank full")); break
            pos = base + cur
            rom[pos:pos + len(enc)] = enc
            rom[pos + len(enc)] = 0xFF
            rom[base + toff + 2 * idx:base + toff + 2 * idx + 2] = cur.to_bytes(2, "little")
            cur += len(enc) + 1; ok += 1
        stats["imported"][name] = ok

def write_codebook(rom, cfg, stats):
    wb = openpyxl.Workbook(); wb.remove(wb.active)
    H = _Fill("solid", fgColor="DDEBF7")
    def sh(name, hdr, rows, widths):
        ws = wb.create_sheet(name); ws.append(hdr)
        for c in ws[1]: c.fill = H; c.font = _Font(bold=True)
        for r in rows: ws.append(r)
        ws.freeze_panes = "A2"
        for i, w in enumerate(widths, 1): ws.column_dimensions[chr(64 + i)].width = w
    info = [["项目", "说明"], ["GAME", cfg.get("GAME")], ["ROM", cfg.get("ROM")],
            ["FONT_KANA", "0x300000 (8x16)"], ["FONT_KANJI", "0x301000 (16x16)"],
            ["FONT_4096", "E000-EFFF / 4 chunks"],
            ["CHUNKS", cfg.get("CHUNKS")],
            ["字模标准", "双字节 Fusion Pixel 12px 原点(1,3)；单字节日文原版，仅数字/大写 Zpix 12px 重绘；左上8行+右上8行 / 左下+右下"],
            ["名称", "全名用 = 分隔；名称_角色=全名，名称_爱称=短名+对应全名"]]
    sh("说明", ["项目", "说明"], info, [18, 100])
    rows = []
    for code in range(0x01, 0xF0):
        ch = SINGLE.get(code, "")
        rows.append(["%02X" % code, ch, single_glyph(rom, code).hex()])
    sh("单字节字库", ["码", "字符", "字模hex"], rows, [6, 6, 40])
    rows = [["F0%02X" % k, v] for k, v in sorted(F0_KANA.items())]
    sh("F0浊音页", ["码", "字符"], rows, [8, 6])
    rows = []
    for n in range(2048):
        code = 0xF200 + n
        ch = KANJI.get(code, "")
        src = "override" if code in KANJI_OVERRIDES else ("graphic" if ch.startswith("（") else "verified")
        rows.append(["%04X" % code, ch, glyph_bytes(rom, code).hex(), src])
    sh("汉字F2-F9", ["码", "字符", "字模hex", "来源"], rows, [8, 8, 70, 10])
    rows = []
    rev = {v: c for c, v in stats["cmap"].items()}
    for code in range(0xE000, 0xF000):
        ch = rev.get(code, "")
        status = "保留(FD/FE/FF)" if (code & 0xFF) in (0xFD, 0xFE, 0xFF) else ("已分配" if ch else "空")
        rows.append(["%04X" % code, ch, pack_glyph(ch).hex() if ch else "", status])
    sh("4096扩容", ["码", "字符", "字模hex", "状态"], rows, [8, 8, 70, 14])
    rows = [[i + 1, "%02X" % b, "%04X" % base, "1024", "E%03X-E%03X" % (0xE000 + i * 1024, 0xE3FF + i * 1024)] for i, (b, base) in enumerate(chunks(cfg))]
    sh("字库分布", ["chunk", "bank", "base", "槽数", "码位"], rows, [7, 7, 8, 7, 16])
    rows = [["新字模", len(stats["cmap"])], ["已导入剧情", sum(stats["imported"].values())],
            ["跳过", str(stats.get("skipped", []))], ["缺字", "".join(stats.get("missing", []))]]
    sh("校验", ["项目", "值"], rows, [16, 100])
    wb.save(BUILD / "码表.xlsx")

def build(stage=None):
    cfg = load_cfg(); stage = stage or str(cfg.get("BUILD_STAGE", "story"))
    rom = bytearray((BUILD / cfg.get("ROM", "assets/original.ws")).read_bytes())
    apply_patch(rom, cfg)
    write_single_ascii(rom)
    stats = dict(cmap={}, imported={}, missing=[], skipped=[])
    if stage in ("story", "all"):
        chars = set()
        wb = openpyxl.load_workbook(BUILD / "text.xlsx", read_only=True, data_only=True)
        for name in wb.sheetnames:
            if not (name.startswith("剧情_") or name == "旁白"): continue
            ws = wb[name]
            for r in ws.iter_rows(min_row=2, values_only=True):
                if len(r) > 7 and r[7]: chars.update(str(r[7]))
        chars = {c for c in chars if c not in REV_SINGLE and c not in REV_F0 and not c.isspace()}
        stats["cmap"] = alloc_codes(chars)
        write_font(rom, cfg, stats["cmap"])
        import_story(rom, cfg, stats)
    outdir = BUILD / "产物"; outdir.mkdir(exist_ok=True)
    suffix = "CN" if stage in ("story", "all") else "4096"
    out = outdir / ("%s_%s.ws" % (cfg.get("GAME") or "D1", suffix))
    out.write_bytes(rom)
    write_codebook(rom, cfg, stats)
    print("GAME", cfg.get("GAME"), "stage", stage, "glyphs", len(stats["cmap"]),
          "imported", stats["imported"], "skipped", stats["skipped"],
          "missing", "".join(stats.get("missing", [])))
    print("OUT", out)
    return out
