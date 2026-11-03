# -*- coding: utf-8 -*-
"""WS2 trilogy text/code helpers (fonts verified at 0x300000/0x301000)."""
import json, struct, re
from pathlib import Path

TOOLS = Path(__file__).resolve().parent


def _find_data():
    for cand in (TOOLS / "data", TOOLS.parent / "data", Path(r"D:\WSC3\构建\assets")):
        if (cand / "kanji_overrides.json").is_file() and (cand / "verified_kanji.jsonl").is_file():
            return cand
    raise RuntimeError("ws2_common: 找不到 tools/data/kanji_overrides.json")


DATA = _find_data()

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
    json.loads((DATA / "kanji_overrides.json").read_text(encoding="utf-8")).items()
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
