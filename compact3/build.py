#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-only
"""Build a Chinese-patched WonderSwan Color ROM (story + names) with a second font page.
Encoding design:
  * original F2-F9 font bank (0x71) is untouched; 43 Chinese chars reuse
    their original glyph codes.
  * 2048 new glyphs (2035 hanzi + 13 symbols) live in bank 0x72, addressed
    by E000-E7FF.  The glyph dispatcher (0x79046E) is redirected through a
    cave at 0x79E000; the four text loops that decide 1/2-byte codes are
    changed from F0 to E0.
  * story strings are repacked inside their original banks and the u16 LE
    tables updated.  The name pool is repacked the same way -- the pool is
    only reachable through the LE u16 array at 0x7F3471, so the strings are
    laid out compactly with shared suffixes and all 1067 pointers rewritten.
    Menu text and the original font bank are preserved.
"""
from __future__ import annotations
import argparse
import collections
import csv
import hashlib
import json
import re
import struct
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
BASE = Path(__file__).resolve().parent
ASSETS = BASE / "assets"
INPUT = ASSETS
# assets/fonts ships the three fonts the current data uses; optional fallback
# fonts (MZPX/harmony/fashion/wqy10) can be dropped in the same directory
FONT_EXTRA = ASSETS / "fonts"
import types
_w=types.SimpleNamespace()
HIRAGANA = "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
SMALL_HIRA = "ぁぃぅぇぉゃゅょっ"
PA_HIRA = "ぱぴぷぺぽ"
KATAKANA = "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン"
SMALL_KATA = "ァィゥェォャュョッ"
PA_KATA = "パピプペポ"
SINGLE: dict[int, str] = {}
_c = 0x01
for _ch in HIRAGANA:
    SINGLE[_c] = _ch
    _c += 1
for _ch in SMALL_HIRA:
    SINGLE[_c] = _ch
    _c += 1
for _ch in PA_HIRA:
    SINGLE[_c] = _ch
    _c += 1
for _ch in KATAKANA:
    SINGLE[_c] = _ch
    _c += 1
for _ch in SMALL_KATA:
    SINGLE[_c] = _ch
    _c += 1
for _ch in PA_KATA:
    SINGLE[_c] = _ch
    _c += 1
for _i, _ch in enumerate("0123456789"):
    SINGLE[0x79 + _i] = _ch
for _i, _ch in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    SINGLE[0x83 + _i] = _ch
for _i, _ch in enumerate("abcdefghijklmnopqrstuvwxyz"):
    SINGLE[0x9D + _i] = _ch
SINGLE.update({
    0xB7: "。", 0xB8: "、", 0xB9: "’", 0xBA: ",", 0xBB: "・", 0xBC: "‥",
    0xBD: "ー", 0xBE: "+", 0xBF: "±", 0xC0: "=", 0xC1: "％", 0xC2: "/",
    0xC3: ":", 0xC4: "~", 0xC5: "!", 0xC6: "?", 0xC7: "「", 0xC8: "」",
    0xC9: "(", 0xCA: ")",
    0xCB: "Ⓟ", 0xCC: "Ⓑ", 0xCD: "㊂", 0xCE: "⊕", 0xCF: "（圈8）",
    0xD0: "▶", 0xD1: "×", 0xD2: "ν", 0xD3: "Ⅰ", 0xD4: "Ⅱ", 0xD5: "Ⅲ",
    0xD6: "Ⅳ", 0xD7: "Ⅴ", 0xD8: "∧", 0xD9: "◀", 0xDA: "◀", 0xDB: "▶",
    0xDC: "▶", 0xDD: "[", 0xDE: "]",
})
SINGLE[0x00] = ""
for _c in range(0xDF, 0xF0):
    SINGLE[_c] = ""
# The 0x321000 page is a static cache snapshot.  This mapping was aligned from
# menu/weapon text and is useful only as a hint; it is NOT valid globally and
# is known to disagree with name/weapon records.  Never use it for export.
F0_MENU: dict[int, str] = {}
_F0_LAYOUT = [
 "ビ","ー","ム","シ","ャ","ッ","ト","ラ","イ","フ","ル"," ","ジ","ャ","ン","ビ",
 "ー","ニ","ト","ラ","イ","デ","ン","ト"," ","ド","リ","ル","ブ","レ","イ","ジ",
 "ャ","ー","パ","ン"," ","ナ","ダ","ブ","ル","ト","マ","ホ","ー","ク","ブ","ー",
 "メ","ラ","ン"," ","ゲ","ッ","タ","ー","チ","ェ","ン","ジ"," ","ア","タ","ッ",
 "ン","ー","ニ","連","装","ミ","サ","イ","ル","ジ","弾","連","発","パ","イ","ク",
 "シ","サ","イ","施","設","子","名","包","カ","ル","メ","ッ","ト","カ","ラ","シ",
 "ー","ッ","ト","ン","パ","ン","チ","ー","イ","ン","パ","ク","ト","ル","ジ","ェ",
 "ッ","ト","ル","連","続","射","撃","さ","大","車","輪","ロ","ケ","ッ","ト","パ",
]
for _i, _ch in enumerate(_F0_LAYOUT):
    F0_MENU[_i] = _ch
for _i in range(0x80, 0x100):
    F0_MENU[_i] = "（空白）"
# Candidate F0 readings inferred from known name/weapon spellings.  These are
# per-page cache indices, shown only in the optional evidence sheet.
F0_NAME_EVIDENCE: dict[int, str] = {
    0x42: "ガ", 0x44: "グ", 0x46: "ゴ", 0x48: "ジ", 0x49: "ス",
    0x50: "ド", 0x56: "バ", 0x57: "ビ", 0x58: "カ", 0x59: "ル", 0x5A: "メ",
}
# Global F0 kana page (verified from story/battle text).  The same voiced-kana
# slots are used across all text banks; only rare glyph slots vary by scene.
F0_KANA: dict[int, str] = {
    0x06: "が", 0x07: "ぎ", 0x08: "ぐ", 0x09: "げ", 0x0A: "ご",
    0x0B: "ざ", 0x0C: "じ", 0x0D: "ず", 0x0E: "ぜ", 0x0F: "ぞ",
    0x10: "だ", 0x11: "ぢ", 0x12: "づ", 0x13: "で", 0x14: "ど",
    0x1A: "ば", 0x1B: "び", 0x1C: "ぶ", 0x1D: "べ", 0x1E: "ぼ",
    0x42: "ガ", 0x43: "ギ", 0x44: "グ", 0x45: "ゲ", 0x46: "ゴ",
    0x47: "ザ", 0x48: "ジ", 0x49: "ズ", 0x4A: "ゼ", 0x4B: "ゾ",
    0x4C: "ダ", 0x4D: "ヂ", 0x4E: "ヅ", 0x4F: "デ", 0x50: "ド",
    0x51: "パ", 0x52: "ピ", 0x53: "プ", 0x54: "ペ", 0x55: "ポ",
    0x56: "バ", 0x57: "ビ", 0x58: "ブ", 0x59: "ベ", 0x5A: "ボ",
}
w=_w
w.SINGLE=SINGLE
w.F0_KANA=F0_KANA
ROM_PATH: Path | None = None       # set by -i
TEXT_XLSX = ASSETS / "text.xlsx"   # overridden by --text
OUT_ROM: Path | None = None        # set by -o
OUT_BOOK: Path | None = None       # set by --codebook
FONT_PATH = INPUT / "fonts" / "simsun.ttc"
SINGLE_FONT_PATH = INPUT / "fonts" / "zpix.ttf"
FF = bytes([255])
NEW_BANK = 0x72
NEW_C3 = 0x80 | NEW_BANK
NEW_CODE_BASE = 0xE000
NEW_GLYPH_COUNT = 4096
# A glyph code may not end in FD/FE/FF: the engine's byte-wise string copiers
# stop at the first 0xFF (特=E4FF truncated 亚尔达巴奥特 in RAM and the renderer
# then ran on into the neighbouring name buffers), and FD/FE are control bytes.
# Skip those three slots in every 256-code page.
GLYPH_PAGE = 256
GLYPH_SLOTS_PER_PAGE = 253
NEW_GLYPH_SLOTS = (NEW_GLYPH_COUNT // GLYPH_PAGE) * GLYPH_SLOTS_PER_PAGE
def glyph_index(order: int) -> int:
    return (order // GLYPH_SLOTS_PER_PAGE) * GLYPH_PAGE + order % GLYPH_SLOTS_PER_PAGE
STAGE = __import__('os').environ.get('WSC_STAGE', 'all')  # story | names | all
CAVE_AT = 0x79E000
DISPATCH_AT = 0x79047F
LOOP_PATCHES = (0x7505BF, 0x751567, 0x79029C, 0x79040D)
NAME_POOL_START = 0x76C0
NAME_POOL_END = 0x98EA
# ---- bank 0x75 UI strings ----------------------------------------------------
# translation/ui_pending.csv holds every UI string of the 0x98F9-0xC5A0 region:
# offset is bank-relative, avail is the byte budget of that slot (terminator
# included).  Chinese that fits is rewritten in place; what does not fit is
# packed into the unused tail of the bank and its pointer entries are moved.
UI_BANK_BASE = 0x750000
UI_TEXT_LO = 0x98F9
UI_TEXT_HI = 0xC5A0
UI_REL_BASE = 0xFDCC
UI_REL_CAP = 0x10000 - UI_REL_BASE
# u16 pointer tables verified to reference this region (endian per table).
# Repeated-value arrays (0x7F27C4, 0x451C0A, 0x445430) look like one under a
# byte-order guess but are not text pointers, so they are excluded.
UI_PTR_TABLES = [
    (0x7F3F86, 231, ">H"), (0x7F3CC6, 214, ">H"), (0x7F33F2, 63, ">H"),
    (0x7C2EE2, 63, ">H"), (0x7C4044, 26, ">H"),
    (0x7C2FA8, 11, ">H"),
    (0x7F310C, 43, "<H"), (0x7F3166, 22, "<H"), (0x7F31C0, 7, "<H"),
    (0x7F33DC, 7, "<H"), (0x7F4868, 87, "<H"),
]
# 0x7C2EE2 slot 40 only looked like an empty slot (0xA502) because the table was
# read big-endian; read little-endian from 0x7C2EE3 it is 0xA602, the エルフ城 label.
STORY_RANGES = {
    "45": (0x452080, 0x45FBCA, 4160),
    "46": (0x461C70, 0x46AFD1, 3640),
    "53": (0x530C00, 0x53AFDB, 1536),
    "54": (0x540C00, 0x54AFEC, 1536),
    "55": (0x551100, 0x55F7D2, 2176),
    "56": (0x561100, 0x56F5AB, 2176),
    "57": (0x571100, 0x579D1D, 2176),
    "5A": (0x5A1000, 0x5A246C, 2048),
    "70": (0x700450, 0x7038E9, 552),
    "47": (0x471B00, 0x47FFC9, 1408),
}
# 43 Chinese characters whose SimSun-12 bitmap is close to the original
# F2-F9 glyph (selected by IoU; min 0.895).  Reusing these keeps the new
# bank at exactly 2048 glyphs and preserves the original font bank.
# All Chinese text uses freshly rendered SimSun12 glyphs.  The old borrow list
# reused F2-F9 originals to fit the 2,048-glyph bank; those glyphs sit one pixel
# higher (ink rows 3-14 vs 4-14), so mixed text showed inconsistent height
# (e.g. 出 in 出击表).  The font bank now holds 4,096 glyphs, so nothing is
# borrowed anymore.
REUSE = {}
# Composite labels: a name too wide for a 4-single-byte field is drawn into
# several 8x16 single-byte cells (spirit list holds 4 bytes).
COMPOSITES = {}
# Symbols that need a new 16x16 glyph.  '○'/'×' use original F7BC/F7BD.
NEW_SYMBOLS = list("，！？～（）—‘“”《》&→.")
# original single-byte / symbol codes used by the Chinese text
SINGLE_ALIASES = {
    "·": 0xBB,   # ・ middle dot
    "％": 0xC1,
    "’": 0xB9,
    "-": 0xBD,   # half-width long-vowel bar (0xEA is a glyph lead now)
    " ": 0xDF,   # blank cell
}
ORIGINAL_SYMBOL_CODES = {
    "○": 0xF7BC,
    "×": 0xF7BD,
}
# Cave at 9000:E000.  Assembled with NASM (16-bit); see comments in the repo.
CAVE = bytes.fromhex(
    "3ce072343cf073303ce836a3a828e4c350b0f27202b0d0e6c336a1a82888c7"
    "88e025ff0030db80efe001d83d000872032d0008ea65070090"
    "3cf0740d3cf1740e3cf0720fea48070090eaa5040090ea8e040090eaa5040090"
)
def load_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))
def _num(v, base=16):
    if isinstance(v, int):
        return v
    v = str(v).strip()
    return int(v, base) if v else 0
def _widths(v):
    s = str(v or "").strip().replace("，", ",").replace(" ", ",")
    return [int(x) for x in s.split(",") if x] or None
BOOK = {"story": [], "names": [], "ui": [], "direct": [], "patches": [], "special": [], "prologue": [], "f1names": []}
def load_book():
    import openpyxl
    wb = openpyxl.load_workbook(TEXT_XLSX, data_only=True)
    story = []
    for name in wb.sheetnames:
        if not name.startswith("剧情_"):
            continue
        ws = wb[name]
        hdr = [c.value for c in ws[1]]
        for row in ws.iter_rows(min_row=2, values_only=True):
            r = dict(zip(hdr, row))
            if r.get("bank") is None:
                continue
            story.append({
                "bank": str(r["bank"]), "index": int(r["index"]),
                "ptr_addr": _num(r["ptr_addr"]), "ptr_value": _num(r["ptr_value"]),
                "raw_hex": r.get("raw_hex") or "", "empty": str(r.get("empty") or ""),
                "keep": str(r.get("保留") or ""),
                "text": r.get("jp") or "", "zh": r.get("zh") or "",
            })
    f1names = []
    f1_sheet = "F1宏" if "F1宏" in wb.sheetnames else ("F1宏武器名" if "F1宏武器名" in wb.sheetnames else None)
    if f1_sheet:
        ws = wb[f1_sheet]
        hdr = [c.value for c in ws[1]]
        for row in ws.iter_rows(min_row=2, values_only=True):
            r = dict(zip(hdr, row))
            if not r.get("宏号"):
                continue
            f1names.append((_num("0x" + str(r["宏号"]).strip().upper()[2:]),
                            r.get("日文") or "", str(r.get("中文") or "").strip(),
                            int(r.get("字宽") or 16),
                            (str(r.get("字体") or "").strip().lower() or None),
                            _widths(r.get("逐字宽")),
                            int(r.get("右移") or 0),
                            int(r.get("自然") or 0),
                            int(r.get("去空白") or 0),
                            str(r.get("留白字") or "").strip(),
                            str(r.get("下移字") or "").strip()))
    names = []
    for sheet_name in wb.sheetnames:
        if not sheet_name.startswith("名称_"):
            continue
        ws = wb[sheet_name]
        hdr = [c.value for c in ws[1]]
        if "index" not in hdr or "jp" not in hdr or "zh" not in hdr:
            continue
        for row in ws.iter_rows(min_row=2, values_only=True):
            r = dict(zip(hdr, row))
            if r.get("index") is None:
                continue
            names.append({
                "index": int(r["index"]), "category": r.get("category") or "",
                "ptr_addr": _num(r["ptr_addr"]), "ptr_value": _num(r["ptr_value"]),
                "text": r.get("jp") or "", "chinese": r.get("zh") or "",
                "alias": r.get("别名") or "",
            })
    names.sort(key=lambda n: n["index"])
    ui = []
    ws = wb["UI文本"]
    hdr = [c.value for c in ws[1]]
    for row in ws.iter_rows(min_row=2, values_only=True):
        r = dict(zip(hdr, row))
        if r.get("原偏移") is None:
            continue
        pts = []
        for part in str(r.get("指针表地址") or "").split(";"):
            if "=" in part:
                aa, vv = part.split("=")
                pts.append((_num(aa), _num(vv)))
        ui.append({
            "offset": _num(r["原偏移"]), "avail": int(r["可用长度"]),
            "jp_text": r.get("原文") or "", "zh_text": (r.get("中文") or "").strip(),
            "target": _num(r.get("目标偏移")) if r.get("目标偏移") not in (None, "") else None,
            "pointers": pts, "source": r.get("来源") or "",
            "immediates": [_num(p) for p in
                           re.split(r"[;,，；\s]+", str(r.get("立即数") or "")) if p],
        })
    direct = []
    ws = wb["池外文本"]
    hdr = [c.value for c in ws[1]]
    for row in ws.iter_rows(min_row=2, values_only=True):
        r = dict(zip(hdr, row))
        if r.get("偏移") is None:
            continue
        ptrs = [_num(p) for p in re.split(r"[;,，；\s]+", str(r.get("指针") or "")) if p]
        direct.append((int(r["bank"]), _num(r["偏移"]), str(r["文本"] or ""), r.get("说明") or "", ptrs))
    # 「指针补丁」：只放非文本的字节级改动（布局坐标、清屏范围、固定指针、补位）。
    # 文字与文本指针分别由编码器和「指针表地址 / 立即数」自动生成，不写入此表。
    # 完整的 11 行清单与分类见 构建/patch_notes.md。
    patches = []
    ws = wb["指针补丁"]
    hdr = [c.value for c in ws[1]]
    for row in ws.iter_rows(min_row=2, values_only=True):
        r = dict(zip(hdr, row))
        if r.get("地址") is None:
            continue
        patches.append((_num(r["地址"]), int(r["原字节"]), int(r["新字节"]), r.get("说明") or ""))
    special = []
    ws = wb["特殊字模"]
    hdr = [c.value for c in ws[1]]
    for row in ws.iter_rows(min_row=2, values_only=True):
        r = dict(zip(hdr, row))
        if r.get("码") is None:
            continue
        special.append((_num(r["码"]), str(r["字符"]), int(r["dx"] or 0),
                        int(r["dy"] or 0), r.get("用途") or ""))
    prologue = []
    ws = wb["序章旁白"]
    hdr = [c.value for c in ws[1]]
    for row in ws.iter_rows(min_row=2, values_only=True):
        r = dict(zip(hdr, row))
        if r.get("页") is None:
            continue
        prologue.append({
            "index": int(r["页"]), "para": r.get("段"),
            "offset": _num(r["原偏移"]), "ptr_addr": _num(r["指针地址"]),
            "jp": r.get("页日文") or "", "zh": (r.get("页中文") or "").strip(),
            "para_jp": r.get("段日文") or "", "para_zh": (r.get("段中文") or "").strip(),
            "empty": str(r.get("空") or ""),
        })
    BOOK.update(story=story, names=names, ui=ui, direct=direct,
                patches=patches, special=special, prologue=prologue, f1names=f1names)
    return BOOK
def make_font():
    return ImageFont.truetype(str(FONT_PATH), 12, index=0)
def glyph_bitmap(ch: str, font, dx: int = 0, dy: int = 0) -> list[list[int]]:
    im = Image.new("L", (16, 16), 0)
    ImageDraw.Draw(im).text((1 + dx, 3 + dy), ch, font=font, fill=255)
    rows = [[1 if im.getpixel((x, y)) > 128 else 0 for x in range(16)] for y in range(16)]
    # No vertical stretching: keep SimSun's own metrics (baseline-aligned),
    # 1px height variance between glyphs is inherent to the outline font.
    return rows
def bitmap_to_glyph(rows: list[list[int]]) -> bytes:
    top = bytearray(16)
    bot = bytearray(16)
    for y in range(8):
        top[y] = sum(rows[y][x] << (7 - x) for x in range(8))
        top[8 + y] = sum(rows[y][x + 8] << (7 - x) for x in range(8))
        bot[y] = sum(rows[y + 8][x] << (7 - x) for x in range(8))
        bot[8 + y] = sum(rows[y + 8][x + 8] << (7 - x) for x in range(8))
    return bytes(top + bot)
def glyph_offset(code: int) -> int:
    n = (code >> 8) - 0xF2
    n = n * 256 + (code & 0xFF)
    return (n >> 3) * 0x100 + (n & 7) * 0x10
def string_end(data: bytes, start: int) -> int:
    """Offset of the standalone 0xFF terminating a code-aware string."""
    i = start
    while i < len(data):
        b = data[i]
        # 0xFF can be the low byte of a two-byte code (e.g. F3 FF = 未),
        # so consume code prefixes before testing for the terminator.
        if 0xE0 <= b <= 0xEF or b in (0xF0, 0xF1, 0xFC, 0xFD) or 0xF2 <= b <= 0xF9:
            i += 2
        elif b == 0xFF:
            return i
        else:
            i += 1
    raise ValueError(f"unterminated string at {start:06X}")
class Encoder:
    def __init__(self, new_chars: list[str], font, specials=()):
        if len(new_chars) > NEW_GLYPH_SLOTS:
            raise ValueError(f"new glyph count {len(new_chars)} > {NEW_GLYPH_SLOTS}")
        self.new_chars = new_chars
        # {S:字} resolves through the 特殊字模 sheet at build time, so a relocated
        # or renumbered glyph slot can never leave stale codes in a direct string.
        self.special: dict[str, int] = {ch: code for code, ch, _dx, _dy, _note in specials}
        self.code_map: dict[str, bytes] = {}
        for order, ch in enumerate(new_chars):
            i = glyph_index(order)
            if i >= NEW_GLYPH_COUNT:
                raise ValueError("new code overflow")
            self.code_map[ch] = bytes([0xE0 + (i >> 8), i & 0xFF])
        for ch, code in REUSE.items():
            if ch in self.code_map:
                raise ValueError(f"duplicate reuse char {ch}")
            self.code_map[ch] = code.to_bytes(2, "big")
        for ch, code in ORIGINAL_SYMBOL_CODES.items():
            if ch in self.code_map:
                raise ValueError(f"duplicate original symbol char {ch}")
            self.code_map[ch] = code.to_bytes(2, "big")
        for ch, (_t, codes) in COMPOSITES.items():
            self.code_map[ch] = b"".join(
                bytes([c >> 8, c & 0xFF]) if c > 0xFF else bytes([c]) for c in codes)
        clash = sorted(ch for ch, code in self.code_map.items()
                       if code[-1] in (0xFD, 0xFE, 0xFF))
        if clash:
            raise ValueError(f"codes ending in a control byte: {clash}")
        self.single: dict[str, int] = {}
        for code, ch in w.SINGLE.items():
            if ch and ch not in self.single:
                self.single[ch] = code
        self.single.update(SINGLE_ALIASES)
        self.f0 = {}
        for code, ch in w.F0_KANA.items():
            if ch and ch not in self.f0:
                self.f0[ch] = code
        self.glyphs = {ch: bitmap_to_glyph(glyph_bitmap(ch, font)) for ch in new_chars}
        self.bbox_bad = []
        for ch in new_chars:
            rows = glyph_bitmap(ch, font)
            xs = [x for y in range(16) for x in range(16) if rows[y][x]]
            ys = [y for y in range(16) for x in range(16) if rows[y][x]]
            if xs and (min(xs) < 1 or max(xs) > 12 or min(ys) < 2 or max(ys) > 14):
                self.bbox_bad.append((ch, min(xs), max(xs), min(ys), max(ys)))
    def encode(self, text: str, *, split_lines: bool, lead_zeros: int = 0,
               line_pad: bool = True) -> tuple[bytes, list[int]]:
        out = bytearray(b"\x00" * lead_zeros)
        bounds = list(range(lead_zeros + 1))
        lines = text.split(" / ") if split_lines else [text]
        for li, line in enumerate(lines):
            if li:
                bounds.append(len(out))
                out.append(0xFE)
                if line_pad:
                    bounds.append(len(out))
                    out.append(0x00)
            i = 0
            while i < len(line):
                mb = re.match(r"\{B:([0-9A-Fa-f]{2})\}", line[i:])
                if mb:
                    bounds.append(len(out))
                    out.append(int(mb.group(1), 16))
                    i += mb.end()
                    continue
                mg = re.match(r"\{G:([0-9A-Fa-f]{4})\}", line[i:])
                if mg:
                    bounds.append(len(out))
                    out.extend(int(mg.group(1), 16).to_bytes(2, "big"))
                    i += mg.end()
                    continue
                ms = re.match(r"\{S:(.)\}", line[i:])
                if ms:
                    code = self.special.get(ms.group(1))
                    if code is None:
                        raise ValueError(f"{{S:{ms.group(1)}}} has no 特殊字模 row in {text!r}")
                    bounds.append(len(out))
                    out.extend(code.to_bytes(2, "big"))
                    i += ms.end()
                    continue
                m = re.match(r"\{([A-Z0-9]+):([0-9A-Fa-f]{2})\}", line[i:])
                if m:
                    typ, val = m.group(1), int(m.group(2), 16)
                    code = {"FD": 0xFD, "FC": 0xFC, "F1": 0xF1}.get(typ)
                    if code is None:
                        raise ValueError(f"unsupported token {m.group(0)!r} in {text!r}")
                    bounds.append(len(out))
                    out.extend((code, val))
                    i += m.end()
                    continue
                ch = line[i]
                if ch in self.code_map:
                    bounds.append(len(out))
                    out.extend(self.code_map[ch])
                elif ch in self.single:
                    bounds.append(len(out))
                    out.append(self.single[ch])
                elif ch in self.f0:
                    bounds.append(len(out))
                    out.extend((0xF0, self.f0[ch]))
                else:
                    raise ValueError(f"no code for {ch!r} U+{ord(ch):04X} in {text!r}")
                i += 1
        bounds.append(len(out))
        return bytes(out), sorted(set(bounds))
    def missing_chars(self, texts) -> collections.Counter:
        miss = collections.Counter()
        for text in texts:
            for ch in text:
                if ch in self.code_map or ch in self.single or ch in self.f0:
                    continue
                if ch in "{}" or ch == "/":
                    continue
                miss[ch] += 1
        return miss
def pack_strings(items: list[tuple[bytes, list[int]]], cap: int):
    """Pack strings, allowing a pointer into a suffix of a longer string."""
    uniq: dict[bytes, list[int]] = {}
    for b, bd in items:
        if b not in uniq:
            uniq[b] = bd
    blob = bytearray(b"\xff")
    offs: dict[bytes, int] = {b"": 0}
    suffix: dict[bytes, int] = {}
    for s in sorted(uniq, key=lambda x: (-len(x), x)):
        if s in offs:
            continue
        if s in suffix:
            offs[s] = suffix[s]
            continue
        base = len(blob)
        offs[s] = base
        blob.extend(s)
        blob.append(0xFF)
        for i in uniq[s]:
            if i <= 0 or i >= len(s):
                continue
            suf = s[i:]
            if suf in uniq and suf not in suffix:
                suffix[suf] = base + i
    if len(blob) > cap:
        raise ValueError(f"packed strings {len(blob)} > cap {cap}")
    return bytes(blob), offs
def build_charset(story_rows, name_rows, menu_texts=(), extra_texts=()):
    freq = collections.Counter()
    for r in story_rows:
        freq.update(r["zh"])
    for r in name_rows:
        freq.update(r["chinese"])
    for text in menu_texts:
        freq.update(text)
    for text in extra_texts:
        freq.update(text)
    hanzi = sorted(ch for ch in freq if 0x4E00 <= ord(ch) <= 0x9FFF)
    new_hanzi = [ch for ch in hanzi if ch not in REUSE]
    # Deterministic: Unicode order, independent of previous builds.
    new_hanzi = sorted(new_hanzi, key=ord)
    new_symbols = sorted([ch for ch in NEW_SYMBOLS if freq[ch]], key=ord)
    new_chars = new_hanzi + new_symbols
    if len(new_chars) > NEW_GLYPH_SLOTS:
        raise ValueError(
            f"hanzi={len(hanzi)} new_hanzi={len(new_hanzi)} symbols={len(new_symbols)} "
            f"new total={len(new_chars)} (max {NEW_GLYPH_SLOTS})"
        )
    return freq, hanzi, new_chars
def check_original_font_bank(rom: bytes):
    if rom[0x720000:0x730000] != b"\xff" * 0x10000:
        raise ValueError("bank 0x72 is not empty")
    if rom[CAVE_AT:CAVE_AT + len(CAVE)] != b"\xff" * len(CAVE):
        raise ValueError("cave area is not empty")
def apply_code_patches(rom: bytearray):
    check_original_font_bank(rom)
    rom[CAVE_AT:CAVE_AT + len(CAVE)] = CAVE
    if rom[DISPATCH_AT:DISPATCH_AT + 6] != bytes.fromhex("3cf074223cf1"):
        raise ValueError("unexpected dispatcher bytes")
    rom[DISPATCH_AT:DISPATCH_AT + 5] = bytes.fromhex("ea00e00090")
    for addr in LOOP_PATCHES:
        if rom[addr:addr + 2] != bytes.fromhex("3cf0"):
            raise ValueError(f"unexpected loop bytes at {addr:06X}: {rom[addr:addr+2].hex()}")
        rom[addr + 1] = 0xE0
def _fmt_for(a):
    for tab, n, fmt in UI_PTR_TABLES:
        if tab <= a < tab + 2 * n:
            return fmt
    raise ValueError(f"pointer address 0x{a:06X} is outside the known tables")
# Every table declared ">H" in UI_PTR_TABLES is really a little-endian u16 table
# whose first entry starts one byte after the recorded address: the recorded base
# is the byte before it, which happens to repeat entry 0's high byte.  The game
# reads entry i at base+1+2i, so writing big-endian at base+2i clobbers the
# previous entry's high byte (the scenario table's 0xB5DE became 0xFEDE after
# patching entry 35, and 第6話 showed a place name).  Write one byte on, with the
# game's endianness.
def ptr_slot(a):
    """(write address, struct format) for one pointer-table entry address."""
    for tab, n, fmt in UI_PTR_TABLES:
        if tab <= a < tab + 2 * n:
            return (a + 1, "<H") if fmt == ">H" else (a, fmt)
    raise ValueError(f"pointer address 0x{a:06X} is outside the known tables")
UI_AUTO_TOP = 0x7598F9          # name-pool end; the auto arena grows downward
UI_AUTO_RELOCATE = False        # OFF: moving a string breaks callers that index it
                                # by base+delta and any cell-count-dependent layout
                                # (2026-10-25: extra newlines, gaps, boxed glyphs)
UI_ARRAY_LO, UI_ARRAY_HI = 0x7F346F, 0x7F3CC6  # name array: values look like offsets too
# Window layout tables in bank 0x76: 5-byte records (ptr LE, flag, pos, id).
# The カタカナ hint line is the last record (flag 0xFF), so it is not in a plain
# u16 table and needs an explicit entry list.
UI_EXTRA_PTRS = (0x76DAE5, 0x76DB37)
def find_ui_pointers(rom: bytes, off16: int):
    """Reference sites for a bank-0x75 UI string offset.  Deliberately narrow:
    only aligned entries of a known pointer table (using the endianness the rest
    of the build already writes them with), an explicit layout-table entry, or a
    `mov ax, imm16`.  A bare byte scan matches code constants too -- 蘑菇平原 has
    23 hits, one of them real."""
    acc, rej = [], []
    for tab, n, fmt in UI_PTR_TABLES:
        for i in range(n):
            if struct.unpack_from(fmt, rom, tab + 2 * i)[0] == off16:
                acc.append((tab + 2 * i, fmt, "table"))
    for a in UI_EXTRA_PTRS:
        if struct.unpack_from("<H", rom, a)[0] == off16:
            acc.append((a, "<H", "layout"))
    for base in range(0x74, 0x80):
        start = base << 16
        chunk = rom[start:start + 0x10000]
        for m in re.finditer(re.escape(struct.pack("<H", off16)), chunk):
            s = start + m.start()
            if s < 2 or UI_ARRAY_LO <= s <= UI_ARRAY_HI:
                continue
            if rom[s - 1] == 0xB8:                          # mov ax, imm16
                acc.append((s, "<H", "mov ax"))
            else:
                rej.append((s, "<H", "unmatched"))
    return acc, rej
def apply_ui_texts(rom: bytearray, pristine: bytes, encoder: Encoder):
    rows = BOOK["ui"]
    # UI strings break with a bare 0xFE in the original (206/258 of them); the
    # story continuation indent would add a blank cell at the start of line 2.
    for r in rows:
        r["enc"] = (encoder.encode(r["zh_text"], split_lines=True, line_pad=False)[0]
                    if r["zh_text"].strip() else b"")
    # Only rows that actually write something can block a neighbour.
    starts = sorted({0x750000 + r["offset"] for r in rows if r["enc"]})
    by_off = {0x750000 + r["offset"]: r for r in rows if r["enc"]}
    stats = {"rows": len(rows), "filled": 0, "in_place": 0,
             "relocated_rows": 0, "relocated_strings": 0,
             "relocated_bytes": 0, "free": 0, "pointers": 0, "untranslated": 0,
             "auto": [], "auto_unpinned": []}
    def room_from(tgt, r):
        """Bytes usable at tgt before a neighbour's bytes would be destroyed.
        A nested label that still lands on the same bytes (武器改造 holds 改造 at
        +4) does not count as a collision."""
        for s in starts:
            if s <= tgt:
                continue
            k = s - tgt
            other = by_off[s]
            if r is not None and k < len(r["enc"]) and r["enc"][k:].startswith(other["enc"]):
                continue
            return k
        return 0x10000
    seen = set()
    arena = UI_AUTO_TOP
    writes = sorted({0x750000 + (r["target"] if r["target"] is not None else r["offset"])
                     for r in rows if r["zh_text"].strip()})
    for r in rows:                        # pre-pass: who cannot fit where it sits?
        r["auto"] = None
        r["blocked"] = False
        zh = r["zh_text"]
        if not zh.strip():
            continue
        tgt = 0x750000 + (r["target"] if r["target"] is not None else r["offset"])
        need = len(encoder.encode(zh, split_lines=True, line_pad=False)[0]) + 1
        if r["target"] in (None, r["offset"]):
            # in place: bounded by the declared slot and by the next label start --
            # 通关存档 at B0D4 fits its 12-byte slot but runs into 存档 at B0DB
            room = min(r["avail"], room_from(tgt, r))
        else:
            room = next((x - tgt for x in writes if x > tgt), 0x10000)
        if need > room:
            if not UI_AUTO_RELOCATE:
                r["blocked"] = True
                stats["auto_unpinned"].append(
                    (f"{r['offset']:04X}", r["zh_text"], [f"room={room}", f"need={need}"]))
                continue
            arena -= need
            r["auto"] = arena
    if arena < 0x750000 + NAME_POOL_START:
        raise ValueError("auto-relocation arena collides with the name pool")
    for r in rows:
        if r["auto"] is not None:
            new = r["auto"] - 0x750000
            if r["pointers"]:              # the sheet already knows who points at it
                r["pointers"] = [(a, new) for a, _v in r["pointers"]]
                stats["auto"].append((f"{r['offset']:04X}->{new:04X}", r["zh_text"],
                                      len(r["pointers"]), 0))
                r["target"] = new
                continue
            acc, rej = find_ui_pointers(pristine, r["offset"])
            if not acc:
                r["blocked"] = True
                stats["auto_unpinned"].append(
                    (f"{r['offset']:04X}", r["zh_text"],
                     [f"{s:06X}" for s, _f, _w in rej[:6]]))
                r["auto"] = None
                continue
            for s, fmt, _why in acc:
                struct.pack_into(fmt, rom, s, new)
            stats["auto"].append((f"{r['offset']:04X}->{new:04X}",
                                  r["zh_text"], len(acc), len(rej)))
            r["target"] = new
    for r in rows:
        zh = r["zh_text"]
        if not zh or r.get("blocked"):
            continue
        off = 0x750000 + r["offset"]
        avail = r["avail"]
        tgt = 0x750000 + (r["target"] if r["target"] is not None else r["offset"])
        enc, _ = encoder.encode(zh, split_lines=True, line_pad=False)
        if r["auto"] is not None:
            if bytes(rom[tgt:tgt + len(enc) + 1]) != b"\xff" * (len(enc) + 1):
                raise ValueError(f"auto arena at {tgt:06X} is not free")
            rom[tgt:tgt + len(enc) + 1] = enc + FF
            seen.add(tgt)
            stats["filled"] += 1
            for addr, val in r["pointers"]:
                struct.pack_into(ptr_slot(addr)[1], rom, ptr_slot(addr)[0], val)
                stats["pointers"] += 1
            for addr in r["immediates"]:
                struct.pack_into("<H", rom, addr, r["target"])
            continue
        if tgt == off:
            rom[off:off + len(enc) + 1] = enc + FF
            nxt = room_from(off, r)
            if nxt >= avail:
                # preserve the original terminator position (layout depends on it)
                if avail - 1 > len(enc):
                    rom[off + len(enc):off + avail - 1] = bytes(avail - 1 - len(enc))
                rom[off + avail - 1] = 255
            else:
                pad = max(len(enc) + 1, min(avail, nxt))
                rom[off + len(enc) + 1:off + pad] = bytes(pad - len(enc) - 1)
            stats["in_place"] += 1
        else:
            rom[tgt:tgt + len(enc) + 1] = enc + FF
            seen.add(tgt)
            stats["relocated_rows"] += 1
        for addr, val in r["pointers"]:
            struct.pack_into(ptr_slot(addr)[1], rom, ptr_slot(addr)[0], val)
            stats["pointers"] += 1
        for addr in r["immediates"]:
            struct.pack_into("<H", rom, addr, tgt - 0x750000)
        stats["filled"] += 1
    stats["relocated_strings"] = len(seen)
    stats["untranslated"] = len(rows) - stats["filled"]
    return stats, {}
F1_TABLE = 0x7F4977                # legacy 16-entry table (kept; new table below)
F1_TABLE_NEW = 0x7FFE00            # 128-entry table, index = operand - 0x80
F1_CODE_BASE = 0x80
F1_TABLE_LEN = 0x80
F1_HANDLER_SUB = 0x7909D4          # sub ax,0x00F0  ->  sub ax,0x0080
F1_HANDLER_ADD = 0x7909D9          # add ax,0x4977  ->  add ax,0xFE00
F1_STRIP = 0x321000
# pitch -> (bitmap font, the only pixel size its embedded strike accepts)
NARROW_FONTS = {8: (FONT_EXTRA / "MZPXorig_8x12.ttf", 12),
                9: (INPUT / "fonts" / "wenquanyi_9pt.ttf", 12),            # condensed from 12
                10: (INPUT / "fonts" / "wenquanyi_9pt.ttf", 12),          # condensed from 12
                11: (INPUT / "fonts" / "wenquanyi_9pt.ttf", 12),
                12: (INPUT / "fonts" / "wenquanyi_9pt.ttf", 12),
                13: (FONT_EXTRA / "wenquanyi_10pt.ttf", 13)}
F1_FONTS = {                       # optional per-row override (sheet column 字体)
    "harmony": (FONT_EXTRA / "HarmonyOSSansSC-Regular.ttf", None),  # size = pitch
    "fashion": (FONT_EXTRA / "FashionBitmap16_0.092.ttf", None),    # size = pitch
    "mzpx":    (FONT_EXTRA / "MZPXflat_8x12.ttf", None),            # size = pitch
    "wqy9":    (INPUT / "fonts" / "wenquanyi_9pt.ttf", 12),              # single strike
    "wqy10":   (FONT_EXTRA / "wenquanyi_10pt.ttf", 13),
}
F1_RESERVED = range(107, 112)      # MAX (F1FA) / アナライズ keep their original cells
F1_DY = 5                          # baseline: ink rows 4..14, matches the CN font cells
F1_DX = 1                          # shift right 1 px (same as the 1-px right nudge of the CN cells)
F1_SYMBOLS = set("・·()（）[]［］【】〔〕〈〉《》「」『』")  # trimmed with 1 blank px per side
F1_BODY_ARENA = 0x7FFF00           # table lives at 0x7FFE00, bodies after it
F1_BODY_LO, F1_BODY_HI = 0x4991, 0x4A1C   # the only real macro-body span; FD/FE/FF
                                          # table slots point into CODE (0x201 etc.)
F1_BODY_END = 0x7FFFF0
def strip_cells(text: str, pitch: int, dx: int = F1_DX, dy: int = F1_DY,
                font_tag: str | None = None, widths: list[int] | None = None,
                shift: int = 0, natural: bool = False, trim: bool = False,
                pad_chars: str | None = None, down_chars: str | None = None) -> list[bytes]:
    """Lay the whole name out as one raster, then cut it into 8-px cells.  The
    strip is a plain bitmap strip, so a glyph may straddle two cells -- that is
    what lets a 10-px glyph work with 8-px cells and an arbitrary pitch."""
    from PIL import Image, ImageDraw, ImageFont
    if font_tag and font_tag in F1_FONTS:
        path, px = F1_FONTS[font_tag]
        px = pitch if px is None else px
    else:
        path, px = NARROW_FONTS.get(pitch, NARROW_FONTS[8])
    f = ImageFont.truetype(str(path), px)
    base_w = pitch * len(text)
    if (base_w + dx + 7) // 8 > (base_w + 7) // 8:
        dx = 0                      # the 1-px nudge must not cost an extra cell
    w = max(1, base_w + dx)
    img = Image.new("1", (w, 16), 1)
    d = ImageDraw.Draw(img)
    d.fontmode = "1"
    for k, ch in enumerate(text):
        d.text((k * pitch + dx, dy), ch, font=f, fill=0)
    adv = max(1, round(f.getlength(text) / max(1, len(text))))
    if trim:
        # natural glyph strike, then cut away the blank side columns of every
        # character and butt the ink boxes together -- no glyph is rescaled.
        # an explicit 逐字宽 entry is the target ink width; any shortfall is
        # taken from the left edge (right-edge verticals are preserved)
        # symbols (middle dot, brackets) keep exactly 1 blank column per side
        if widths and len(widths) != len(text):
            raise ValueError(f"逐字宽 {len(widths)} 个 != 字数 {len(text)}: {text}")
        padset = set(pad_chars or "")
        downset = set(down_chars or "")
        pieces = []
        for k, ch in enumerate(text):
            cw = max(1, round(f.getlength(ch)))
            cell = Image.new("1", (cw + 2, 16), 1)
            dc = ImageDraw.Draw(cell)
            dc.fontmode = "1"
            dc.text((1, dy + (1 if ch in downset else 0)), ch, font=f, fill=0)
            cp = cell.load()
            cols = [x for x in range(cw + 2) if any(cp[x, y] == 0 for y in range(16))]
            if not cols:
                pieces.append(Image.new("1", (max(1, cw // 2), 16), 1))
                continue
            x0, x1 = min(cols), max(cols)
            if widths:
                target = widths[k]
                while x1 - x0 + 1 > target:
                    left_ink = sum(cp[x0, y] == 0 for y in range(16))
                    right_ink = sum(cp[x1, y] == 0 for y in range(16))
                    # keep right-side verticals (射/刂) intact: take the left
                    # edge unless it is itself a solid vertical stroke
                    if left_ink >= 10 and right_ink < 10:
                        x1 -= 1
                    else:
                        x0 += 1
                crop = cell.crop((x0, 0, x1 + 1, 16))
                if crop.width < target:
                    pad = Image.new("1", (target, 16), 1)
                    pad.paste(crop, (0, 0))
                    crop = pad
            else:
                crop = cell.crop((x0, 0, x1 + 1, 16))
            if ch in F1_SYMBOLS or ch in padset:
                pad = Image.new("1", (crop.width + 2, 16), 1)
                pad.paste(crop, (1, 0))
                crop = pad
            pieces.append(crop)
        total = sum(p.width for p in pieces)
        img = Image.new("1", (total, 16), 1)
        xoff = 0
        for p in pieces:
            img.paste(p, (xoff, 0))
            xoff += p.width
        w = total
        px = img.load()
    elif widths:
        # explicit per-character widths: dense glyphs get extra columns, sparse
        # ones give them up, without changing the total
        if len(widths) != len(text):
            raise ValueError(f"逐字宽 {len(widths)} 个 != 字数 {len(text)}: {text}")
        total = sum(widths)
        sq = Image.new("1", (total, 16), 1)
        dst = sq.load()
        xoff = 0
        for k, ch in enumerate(text):
            aw = widths[k]
            if natural:
                # mixed half-width ASCII + full-width CJK: each glyph keeps its own
                # advance, so 'S-DX' stays half-width instead of being scaled by the
                # string average
                cw = max(1, round(f.getlength(ch)))
                ox = 0
            else:
                cw = adv + dx
                ox = dx
            cell = Image.new("1", (cw, 16), 1)
            dc = ImageDraw.Draw(cell)
            dc.fontmode = "1"
            dc.text((ox, dy), ch, font=f, fill=0)
            src = cell.load()
            for x in range(aw):
                x0 = x * cw // aw
                x1 = max(x0 + 1, (x + 1) * cw // aw)
                for y in range(16):
                    if any(src[xx, y] == 0 for xx in range(x0, min(x1, cw))):
                        dst[xoff + x, y] = 0
            xoff += aw
        img = sq
        w = total
        px = sq.load()
    elif pitch < adv:
        # requested pitch is tighter than the glyphs themselves: condense each
        # character inside its own advance box, so every glyph loses exactly the
        # same columns (squeezing the composed raster distributes the loss
        # unevenly and leaves the characters looking different sizes)
        cw = adv + dx
        sq = Image.new("1", (pitch * len(text), 16), 1)
        dst = sq.load()
        for k, ch in enumerate(text):
            cell = Image.new("1", (cw, 16), 1)
            dc = ImageDraw.Draw(cell)
            dc.fontmode = "1"
            dc.text((dx, dy), ch, font=f, fill=0)
            src = cell.load()
            for x in range(pitch):
                x0 = x * cw // pitch
                x1 = max(x0 + 1, (x + 1) * cw // pitch)
                for y in range(16):
                    if any(src[xx, y] == 0 for xx in range(x0, min(x1, cw))):
                        dst[k * pitch + x, y] = 0
        img = sq
        w = pitch * len(text)
        px = sq.load()
    px = img.load()
    if shift:
        from PIL import Image as _Image
        wide = _Image.new("1", (w + shift, 16), 1)
        wide.paste(img, (shift, 0))
        img = wide
        w += shift
        px = img.load()
    cells = []
    for ci in range((w + 7) // 8):
        rows = []
        for r in range(16):
            b = 0
            for x in range(8):
                sx = ci * 8 + x
                if sx < w and px[sx, r] == 0:
                    b |= 1 << (7 - x)
            rows.append(b)
        cells.append(bytes(rows))
    return cells
def apply_f1_names(rom: bytearray, font):
    """Long weapon names are not text: they are pre-rendered 8x16 cells in the
    second kana page (0x321000) and F1 macros slice that strip (each byte = slot+1).
    Re-lay out both: Chinese glyphs as two cells each, then rewrite the macro."""
    rows = BOOK["f1names"]
    if not rows:
        return {"rows": 0}
    # the legacy table only has F0..FF; copy it into the upper half of the new
    # 128-entry table so the untouched Japanese macros keep working
    legacy = list(struct.unpack_from("<16H", rom, F1_TABLE))
    entries = [0] * F1_TABLE_LEN
    for code in range(0xF0, 0x100):
        entries[code - F1_CODE_BASE] = legacy[code - 0xF0]
    slot = 0
    arena = F1_BODY_ARENA
    done = []
    for operand, jp, zh, width, font_tag, widths, shift, natural, trim, pad_chars, down_chars in rows:
        if not (F1_CODE_BASE <= operand < F1_CODE_BASE + F1_TABLE_LEN):
            raise ValueError(f"F1{operand:02X} out of macro range")
        idx = operand - F1_CODE_BASE
        base = F1_STRIP
        body = entries[idx]
        old_n = 0
        while rom[0x7F0000 + body + old_n] != 0xFF:
            old_n += 1
        cells = []
        for cell in strip_cells(zh, width, font_tag=font_tag, widths=widths, shift=shift,
                                natural=bool(natural), trim=bool(trim),
                                pad_chars=pad_chars, down_chars=down_chars):
            s = slot
            while s in F1_RESERVED:
                s += 1
            slot = s + 1
            a = base + (s >> 4) * 0x100 + (s & 0xF) * 8
            rom[a:a + 8] = cell[:8]
            rom[a + 0x80:a + 0x88] = cell[8:]
            cells.append(s)
        if len(cells) > old_n or not (F1_BODY_LO <= body < F1_BODY_HI):
            # the name got longer than its original body slot: give it a new one
            # in the free tail of bank 0x7F and repoint the macro table
            payload = bytes(c + 1 for c in cells) + bytes([255])
            if arena + len(payload) > F1_BODY_END:
                raise ValueError("F1 body arena full")
            if rom[arena:arena + len(payload)] != bytes([255]) * len(payload):
                raise ValueError(f"F1 body arena at {arena:06X} is not free")
            rom[arena:arena + len(payload)] = payload
            entries[idx] = arena - 0x7F0000
            body = arena - 0x7F0000
            arena += len(payload)
        rom[0x7F0000 + body:0x7F0000 + body + len(cells)] = bytes(c + 1 for c in cells)
        rom[0x7F0000 + body + len(cells)] = 0xFF
        for k, c in enumerate(cells):
            a = base + (c >> 4) * 0x100 + (c & 0xF) * 8
            if rom[a:a + 8] == bytes([255]) * 8:
                raise ValueError(f"F1{operand:02X} cell {c} not written")
        done.append((f"F1{operand:02X}", body, len(cells), zh))
    for i, v in enumerate(entries):
        struct.pack_into("<H", rom, F1_TABLE_NEW + 2 * i, v)
    if rom[F1_HANDLER_SUB:F1_HANDLER_SUB + 3] != b"\x2D\xF0\x00":
        raise ValueError("F1 handler sub patch site mismatch")
    rom[F1_HANDLER_SUB:F1_HANDLER_SUB + 3] = bytes([0x2D, F1_CODE_BASE, 0x00])
    if rom[F1_HANDLER_ADD:F1_HANDLER_ADD + 3] != b"\x05\x77\x49":
        raise ValueError("F1 handler add patch site mismatch")
    struct.pack_into("<H", rom, F1_HANDLER_ADD + 1, F1_TABLE_NEW - 0x7F0000)
    return {"rows": len(done), "detail": done, "slots": slot}
def apply_specials(rom: bytearray, encoder: Encoder):
    font = make_font()
    for code, ch, dx, dy, note in BOOK["special"]:
        g = bitmap_to_glyph(glyph_bitmap(ch, font, dx=dx, dy=dy))
        if 0xF2 <= (code >> 8) <= 0xF9:
            base = 0x710000
            di = glyph_offset(code)
        else:
            i = code - 0xE000
            base = 0x720000 if i < 2048 else 0x500000
            j = i if i < 2048 else i - 2048
            di = (j >> 3) * 0x100 + (j & 7) * 0x10
        rom[base + di:base + di + 16] = g[:16]
        rom[base + di + 0x80:base + di + 0x80 + 16] = g[16:]
    for bank, off, text, note, ptrs in BOOK["direct"]:
        enc, _ = encoder.encode(text, split_lines=False)
        a = (bank << 16) + off
        rom[a:a + len(enc) + 1] = enc + FF
        if bytes(rom[a:a + len(enc)]) != enc:
            raise ValueError(f"direct string verify failed at {bank:02X}:{off:04X} ({note})")
        for addr in ptrs:
            struct.pack_into("<H", rom, addr, off)
    for bank, off, text, note, ptrs in BOOK["direct"]:
        for addr in ptrs:
            if struct.unpack_from("<H", rom, addr)[0] != off:
                raise ValueError(f"direct pointer verify failed at {addr:06X} -> {off:04X} ({note})")
    # 指针补丁（工作簿「指针补丁」表，目前共 11 行，全部是非文本字节）：
    #   一、布局坐标：0x76428C、0x76E688 把读档/存档表头的「关卡」起点推到 x=0x80，
    #       避开左侧「已过」；其中 0x76428C 新旧值相同，只作为原字节校验锚点。
    #   二、演示窗口：0x763E0D、0x763E11 把状态文字定位到 0x0E60；
    #       0x7741DB、0x7741DC 把清屏起点改为 0x1CC0；0x7741E0 把清屏宽度改为 0x80。
    #   三、固定指针：0x76DAE5、0x76DB37 指向原版平假名行 0xB00C，与中文码表无关。
    #   四、补位：0x759998 给菜单网格补空格；0x75A046 在反击与 L3 之间补 FF 去空格。
    # 逐字节先核对「原字节」（两处新旧相同，只做校验），再写入「新字节」；
    # 任何一处对不上都会中止构建，避免 ROM 版本不符时静默改错。
    for addr, old, new, note in BOOK["patches"]:
        if rom[addr] != old:
            raise ValueError(f"patch {addr:06X}: expected {old:02X}, found {rom[addr]:02X} ({note})")
        rom[addr] = new
    return {"glyphs": len(BOOK["special"]), "direct": len(BOOK["direct"]),
            "patches": len(BOOK["patches"])}
PROLOGUE_TABLE = 0x775F0C
PROLOGUE_BASE = 0x77AC00

def apply_prologue(rom: bytearray, encoder: Encoder):
    rows = sorted(BOOK["prologue"], key=lambda r: r["index"])
    if [r["index"] for r in rows] != list(range(len(rows))):
        raise ValueError("prologue page indices are not contiguous from 0")
    paras = collections.defaultdict(list)
    for r in rows:
        if r["para"] is not None and str(r["para"]) != "":
            paras[int(r["para"])].append(r)
    for pid, prs in sorted(paras.items()):
        whole = "".join(p["zh"] for p in prs)
        if whole != prs[0]["para_zh"]:
            raise ValueError("prologue 段 %d 拆分与整段译文不一致" % pid)
    cur = PROLOGUE_BASE - 0x770000
    used = 0
    for r in rows:
        slot = PROLOGUE_TABLE + 2 * r["index"]
        if struct.unpack_from("<H", rom, slot)[0] != r["offset"]:
            raise ValueError(f"prologue pointer {r['index']} is not {r['offset']:04X}")
        if r["empty"] == "1" or not r["zh"]:
            enc = b"\x00"
        else:
            enc, _ = encoder.encode(r["zh"], split_lines=False, line_pad=False)
        a = 0x770000 + cur
        if rom[a:a + len(enc) + 1] != bytes([255]) * (len(enc) + 1):
            raise ValueError(f"prologue area at {cur:04X} is not empty")
        if cur + len(enc) + 1 >= 0xF000:
            raise ValueError("prologue data overflows bank 0x77")
        rom[a:a + len(enc) + 1] = enc + FF
        struct.pack_into("<H", rom, slot, cur)
        cur += len(enc) + 1
        used += len(enc) + 1
    for r in rows:
        ptr = struct.unpack_from("<H", rom, PROLOGUE_TABLE + 2 * r["index"])[0]
        start = 0x770000 + ptr
        end = string_end(rom, start)
        if r["empty"] == "1" or not r["zh"]:
            expect = b"\x00"
        else:
            expect = encoder.encode(r["zh"], split_lines=False, line_pad=False)[0]
        if bytes(rom[start:end]) != expect:
            raise ValueError(f"prologue verify failed page {r['index']} ptr {ptr:04X}")
    return {"rows": len(rows), "bytes": used, "base": f"{PROLOGUE_BASE:06X}",
            "table": f"{PROLOGUE_TABLE:06X}"}

NAME_TAG = re.compile(r"\{N:(\d+)\}")
SPEAKER_RE = re.compile(r"^([^「（(]{1,16})([「（(])")
SPEAKER_SKIP = {"強化パーツ", "ユニット", "特殊技能"}
def apply_name_rules():
    """Story names follow the name sheets: {N:index} resolves to that row's zh,
    and a speaker prefix is refreshed from the JP speaker's short-name row."""
    by_index = {n["index"]: n["chinese"] for n in BOOK["names"] if n["chinese"].strip()}
    jp_map = {}
    for n in BOOK["names"]:
        if not n["chinese"].strip():
            continue
        if n["index"] >= 331 or n["text"] not in jp_map:
            jp_map[n["text"]] = n["chinese"]
    alias_pairs = []
    for n in BOOK["names"]:
        if not n["chinese"].strip() or not n.get("alias"):
            continue
        for old in re.split(r"[\s,，、;；]+", str(n["alias"])):
            old = old.strip()
            if len(old) >= 2 and old != n["chinese"]:
                alias_pairs.append((old, n["chinese"]))
    alias_pairs.sort(key=lambda p: -len(p[0]))
    tagged = speakers = alias_hits = 0
    for b in BOOK["story"]:
        zh = b["zh"]
        if not zh:
            continue
        new = zh
        for old, cur in alias_pairs:
            if old in new:
                alias_hits += new.count(old)
                new = new.replace(old, cur)
        new = NAME_TAG.sub(lambda m: by_index.get(int(m.group(1)), m.group(0)), new)
        if new != zh:
            tagged += 1
        mj = SPEAKER_RE.match(b["text"])
        mz = SPEAKER_RE.match(new)
        if mj and mz:
            sp = mj.group(1).strip()
            if sp not in SPEAKER_SKIP and sp in jp_map and mz.group(1) != jp_map[sp]:
                new = jp_map[sp] + mz.group(2) + new[mz.end():]
                speakers += 1
        b["zh"] = new
    return {"name_tags": tagged, "aliases": alias_hits, "speakers": speakers}
def _disp_width(text: str) -> int:
    w = 0
    i = 0
    while i < len(text):
        if text[i] == "{":
            j = text.find("}", i)
            if j >= 0:
                tag = text[i:j + 1]
                w += 8 if tag == "{B:00}" else (24 if tag.startswith(("{FD:", "{FC:", "{F1:")) else 0)
                i = j + 1
                continue
        w += 8 if ord(text[i]) < 0x80 else 12
        i += 1
    return w
def check_widths():
    """Warn when a story segment / prologue page exceeds its text box."""
    out = []
    for b in BOOK["story"]:
        if not b["zh"]:
            continue
        for k, seg in enumerate(b["zh"].split(" / "), 1):
            w = _disp_width(seg)
            lim = 176 if k == 1 else 168
            if w > lim:
                out.append((f"剧情_{b['bank']}", b["index"], k, w, seg))
    for p in BOOK["prologue"]:
        if not p["zh"]:
            continue
        w = _disp_width(p["zh"])
        if w > 144:
            out.append(("序章旁白", p["index"], 1, w, p["zh"]))
    return out
def check_required_fonts():
    """Fail early with a clear message when a bundled font is missing."""
    required = [
        ("宋体 simsun.ttc（因授权不随仓库提供，请自备放到 assets/fonts/）", FONT_PATH),
        ("文泉驿 9pt wenquanyi_9pt.ttf", INPUT / "fonts" / "wenquanyi_9pt.ttf"),
        ("Zpix zpix.ttf", SINGLE_FONT_PATH),
    ]
    missing = [f"{path}  ({label})" for label, path in required if not path.is_file()]
    if missing:
        raise SystemExit("缺少必需字体文件：" + chr(10) + "  " + (chr(10) + "  ").join(missing))


def build_rom(dry_run=False):
    check_required_fonts()
    rom = bytearray(ROM_PATH.read_bytes())
    load_book()
    name_rules = apply_name_rules()
    width_warnings = check_widths()
    if width_warnings:
        print(f"WARN 行宽超框 {len(width_warnings)} 处（剧情第1行≤176px、第2行起≤168px，序章单页≤144px/12字）")
        for sheet, idx, seg, px_w, text in width_warnings[:20]:
            print(f"  {sheet} {idx} 段{seg} {px_w}px: {text[:40]}")
        if len(width_warnings) > 20:
            print(f"  …另有 {len(width_warnings) - 20} 处")
    blocks = BOOK["story"]
    name_table = BOOK["names"]
    story_rows = [{"japanese": b["text"], "zh": b["zh"]} for b in blocks if b["zh"].strip()]
    name_rows = [{"japanese": n["text"], "chinese": n["chinese"]} for n in name_table if n["chinese"].strip()]
    ui_rows = BOOK["ui"]
    ui_texts = [r["zh_text"] for r in ui_rows if r["zh_text"].strip()]
    pro_texts = [r["zh"] for r in BOOK["prologue"] if r["zh"]]
    freq, hanzi, new_chars = build_charset(story_rows, name_rows,
                                           ui_texts, [d[2] for d in BOOK["direct"]] + pro_texts)
    encoder = Encoder(new_chars, make_font(), BOOK["special"])
    if encoder.bbox_bad:
        print("WARN glyph bbox beyond 12x12 cell:", encoder.bbox_bad[:10])
    # Validate coverage before touching anything.
    miss = encoder.missing_chars([b["zh"] for b in blocks if b["zh"].strip()] +
                                 [n["chinese"] for n in name_table if n["chinese"].strip()] +
                                 pro_texts)
    if miss:
        raise ValueError(f"missing encodings: {[(c, hex(ord(c)), n) for c, n in miss.items()]}")
    apply_code_patches(rom)
    # ---- new font bank ----
    for order, ch in enumerate(new_chars):
        i = glyph_index(order)
        j = i if i < 2048 else i - 2048
        base = 0x720000 if i < 2048 else 0x500000
        di = (j >> 3) * 0x100 + (j & 7) * 0x10
        g = encoder.glyphs[ch]
        rom[base + di:base + di + 16] = g[:16]
        rom[base + di + 0x80:base + di + 0x80 + 16] = g[16:]
    for _ch, (text, codes) in COMPOSITES.items():
        n = len(text)
        total = 16 + 12 * (n - 1)
        cw = [16] * n
        src = [12 * i for i in range(n)]
        canvas = Image.new("L", (total, 16), 0)
        for _i, _c in enumerate(text):
            cell = Image.new("L", (16, 16), 0)
            ImageDraw.Draw(cell).text((0, 2), _c, font=make_font(), fill=255)
            cell = cell.resize((cw[_i], 16), Image.LANCZOS)
            canvas.paste(cell, (src[_i], 0))
        px = canvas.load()
        slices = [(i * 12, 16) for i in range(n)]
        def _pix(t, y, x0, w):
            sx = x0 + t
            if 0 <= t < w and 0 <= sx < total:
                return 1 if px[sx, y] > 128 else 0
            return 0
        for _ci, code in enumerate(codes):
            _x0, _w = slices[_ci]
            if code > 0xFF:
                _i2 = code - 0xE000
                _di = (_i2 >> 3) * 0x100 + (_i2 & 7) * 0x10
                for _y in range(8):
                    _l = _r = _bl = _br = 0
                    for _k in range(8):
                        _l = (_l << 1) | _pix(_k, _y, _x0, _w)
                        _r = (_r << 1) | _pix(8 + _k, _y, _x0, _w)
                        _bl = (_bl << 1) | _pix(_k, _y + 8, _x0, _w)
                        _br = (_br << 1) | _pix(8 + _k, _y + 8, _x0, _w)
                    rom[0x720000 + _di + _y] = _l
                    rom[0x720000 + _di + 8 + _y] = _r
                    rom[0x720000 + _di + 0x80 + _y] = _bl
                    rom[0x720000 + _di + 0x88 + _y] = _br
            else:
                _i2 = code - 1
                _di = (_i2 >> 4) * 0x100 + (_i2 & 0xF) * 8
                for _y in range(8):
                    _t2 = _b2 = 0
                    for _k in range(8):
                        _t2 = (_t2 << 1) | _pix(_k, _y, _x0, _w)
                        _b2 = (_b2 << 1) | _pix(_k, _y + 8, _x0, _w)
                    rom[0x320000 + _di + _y] = _t2
                    rom[0x320000 + _di + 0x80 + _y] = _b2
    # ---- single-byte font: half-width digits + latin only ----
    # Kana, lowercase and punctuation keep the original 8x16 pixel glyphs.
    # Digits (0x79-0x82) and uppercase A-Z (0x83-0x9C) are re-rendered from
    # Zpix 12px (its 12px bitmap strike; no vertical stretching).
    _sb_font = ImageFont.truetype(str(SINGLE_FONT_PATH), 12, index=0)
    def _sb_glyph(code: int) -> bytes:
        ch = w.SINGLE.get(code, "")
        if not ch or len(ch) != 1:
            return bytes(16)
        im = Image.new("L", (32, 32), 0)
        ImageDraw.Draw(im).text((0, 0), ch, font=_sb_font, fill=255)
        bb = im.getbbox()
        if not bb:
            return bytes(16)
        g = im.crop(bb)
        if g.width > 8:
            g = g.resize((8, g.height), Image.LANCZOS)
        g = g.point(lambda p: 255 if p > 128 else 0)
        out = Image.new("L", (8, 16), 0)
        px = (8 - g.width) // 2 + 1
        py = 14 - (g.height - 1) - 1
        if px + g.width > 8: px = 8 - g.width
        if py < 0: py = 0
        out.paste(g, (px, py))
        bits = []
        for y in range(16):
            v = 0
            for x in range(8):
                if out.getpixel((x, y)) > 128:
                    v |= 0x80 >> x
            bits.append(v)
        return bytes(bits[0:8] + bits[8:16])
    sb_count = 0
    for code, ch in w.SINGLE.items():
        if not (0x79 <= code <= 0x9C) or not ch or len(ch) != 1:
            continue
        g = _sb_glyph(code)
        idx = code - 1
        di = (idx >> 4) * 0x100 + (idx & 0xF) * 8
        rom[0x320000 + di:0x320000 + di + 8] = g[:8]
        rom[0x320000 + di + 0x80:0x320000 + di + 0x88] = g[8:]
        sb_count += 1
    stats_sb = sb_count
    stats = {"glyphs": len(new_chars), "reuse": len(REUSE), "hanzi": len(hanzi),
             "single_byte": stats_sb, "story_banks": {}, "names": {},
             "name_rules": name_rules, "width_warnings": width_warnings}
    # ---- names: full pool repack ----
    # wsdbg read tracing (2026-10-24) proved the 0x7F3471 array is the only
    # runtime entry point for names: unit/pilot/weapon/alias strings are all
    # fetched through it (odd-address LE; the alias sub-table at 0x7F3703 is
    # the same array from index 329) and rendered from bank 0x75 by the loop at physical
    # 0x90401/0x90405.  So the pool can be laid out from scratch as long as the
    # array is rewritten and every new offset stays inside the name window.
    # 28 original entries point into the middle of another string (suffix /
    # alias sharing); each is decoded to its own text and gets its own copy, so
    # no pointer refers into a string interior afterwards.
    groups: dict[int, list[dict]] = collections.defaultdict(list)
    for r in name_table:
        groups[int(r["ptr_value"])].append(r)
    if STAGE in ("story", "ui"):
        groups.clear()
    POOL_END = 0x98F9  # one past the last pool byte; UI text starts here
    if POOL_END > UI_TEXT_LO:
        raise ValueError("name pool would run into the UI text")
    pool_cap = POOL_END - NAME_POOL_START
    _pristine = ROM_PATH.read_bytes()
    def _raw_pool(off: int) -> bytes:
        a = 0x750000 + off
        i = a
        while _pristine[i] != 0xFF:
            b = _pristine[i]
            i += 2 if (b in (0xF0, 0xF1, 0xFC, 0xFD) or 0xF2 <= b <= 0xF9) else 1
        return _pristine[a:i]
    name_enc: dict[int, bytes] = {}
    name_pos: dict[bytes, int] = {}
    blob = bytearray()
    untranslated = []
    for off, rows in sorted(groups.items()):
        text = rows[0]["text"]
        chinese = rows[0].get("chinese", "") if text.strip() else ""
        if text.strip() and not chinese.strip():
            enc = _raw_pool(off)          # no translation: keep original Japanese
            untranslated.append(off)
        elif not chinese.strip():
            enc = b""                     # empty slot (pointer to a lone FF)
        else:
            enc, _bd = encoder.encode(chinese, split_lines=False)
        if enc not in name_pos:
            name_pos[enc] = len(blob)
            blob += enc + b"\xff"
        name_enc[off] = enc
    if len(blob) > pool_cap:
        raise ValueError(f"name pool overflow: {len(blob)} > {pool_cap}")
    # Relocated UI labels live at 0x8D2F (right after the packed names); fail loudly
    # if a future name edit would grow the pool into them.
    if NAME_POOL_START + len(blob) > 0x8D30:
        raise ValueError("name pool would overwrite the relocated UI labels at 0x8D30")
    rom[0x750000 + NAME_POOL_START:0x750000 + NAME_POOL_START + len(blob)] = blob
    rom[0x750000 + NAME_POOL_START + len(blob):0x750000 + POOL_END] = \
        bytes([0xFF]) * (pool_cap - len(blob))
    new_ptr = {off: NAME_POOL_START + name_pos[enc] for off, enc in name_enc.items()}
    for r in name_table:
        off = int(r["ptr_value"])
        if off in new_ptr:
            struct.pack_into("<H", rom, int(r["ptr_addr"]), new_ptr[off])
    stats["names"] = {
        "entries": len(name_table), "strings": len(groups),
        "written": len(name_enc), "packed": len(blob), "cap": pool_cap,
        "bytes": sum(len(e) + 1 for e in name_enc.values()), "untranslated": len(untranslated),
        "mode": "repack", "pool_start": NAME_POOL_START, "pool_end": POOL_END,
        "array": "0x7F3471+2i rewritten (LE)",
        "longest": max((len(e) for e in name_enc.values()), default=0),
    }
    # ---- story ----
    for bank, (ds, de, entries) in STORY_RANGES.items():
        rows = [b for b in blocks if b["bank"] == bank]
        if len(rows) != entries:
            raise ValueError(f"bank {bank}: {len(rows)} rows != {entries}")
        items = []
        row_enc = []
        for b in rows:
            if b.get("keep") == "1":
                row_enc.append("KEEP")
                continue
            if b["empty"] == "1" or not b["text"].strip():
                row_enc.append(None)
                continue
            zh = b["zh"]
            if not zh.strip():
                raise ValueError(f"missing story translation at bank {bank} index {b['index']}")
            drop_pad = bank == "56"  # bank 0x56 is 978 bytes over with the pads
            enc, bd = encoder.encode(zh, split_lines=True,
                                     lead_zeros=0,
                                     line_pad=not drop_pad)
            items.append((enc, bd))
            row_enc.append(enc)
        cap = 0x10000 - (ds & 0xFFFF)
        blob, offs = pack_strings(items, cap)
        rom[ds:ds + len(blob)] = blob
        empty_off = ds & 0xFFFF
        for b, enc in zip(rows, row_enc):
            if enc == "KEEP":
                continue
            ptr_addr = int(b["ptr_addr"])
            orig = int(b["ptr_value"])
            if enc is None:
                val = 0xFFFF if orig == 0xFFFF else empty_off
            else:
                val = empty_off + offs[enc]
            if not 0 <= val <= 0xFFFF:
                raise ValueError(f"pointer overflow bank {bank}: {val}")
            struct.pack_into("<H", rom, ptr_addr, val)
        stats["story_banks"][bank] = {
            "rows": len(rows), "nonempty": len(items), "packed": len(blob),
            "cap": cap, "free": cap - len(blob), "data_start": ds,
            "drop_pads": bank == "56",
        }
    # ---- UI strings of the 0x98F9-0xC5A0 region ----
    pristine = ROM_PATH.read_bytes()
    stats["ui"], _ = apply_ui_texts(rom, pristine, encoder)
    if stats["ui"]["auto_unpinned"]:
        raise ValueError("UI text left untranslated (does not fit): " +
                         "; ".join(f"{o} {zh} {why}" for o, zh, why in stats["ui"]["auto_unpinned"]))
    stats["specials"] = apply_specials(rom, encoder)
    stats["f1names"] = apply_f1_names(rom, make_font())
    stats["prologue"] = apply_prologue(rom, encoder)
    # ---- verification ----
    for bank, (ds, de, entries) in STORY_RANGES.items():
        rows = [b for b in blocks if b["bank"] == bank]
        for b in rows:
            if b.get("keep") == "1":
                continue
            ptr = struct.unpack_from("<H", rom, int(b["ptr_addr"]))[0]
            if ptr == 0xFFFF:
                continue
            start = (int(bank, 16) << 16) | ptr
            end = string_end(rom, start)
            if b["empty"] == "1" or not b["text"].strip():
                if end != start:
                    raise ValueError(f"empty pointer in bank {bank} is not empty")
            else:
                # reconstruct expected bytes for this row
                drop_pad = bank == "56"
                zh = b["zh"]
                enc, _ = encoder.encode(zh, split_lines=True,
                                        lead_zeros=0,
                                        line_pad=not drop_pad)
                if bytes(rom[start:end]) != enc:
                    raise ValueError(f"story verify failed bank {bank} ptr {ptr:04X}")
    # Written names must read back exactly; untouched names must still be the
    # original Japanese bytes at their unchanged offsets.
    for off, rows in groups.items():
        enc = name_enc.get(off)
        for r in rows:
            ptr = struct.unpack_from("<H", rom, int(r["ptr_addr"]))[0]
            if enc is None:
                continue
            if not NAME_POOL_START <= ptr < POOL_END:
                raise ValueError(f"name pointer out of pool at {r['ptr_addr']}: {ptr:04X}")
            start = 0x750000 + ptr
            if bytes(rom[start:start + len(enc) + 1]) != enc + b"\xff":
                raise ValueError(f"name verify failed: {rows[0]['text']!r} at {ptr:04X}")
    patch_addrs = {p[0] for p in BOOK["patches"]}
    direct_ranges = []
    for bank, off, text, note, _ptrs in BOOK["direct"]:
        e, _ = encoder.encode(text, split_lines=False)
        direct_ranges.append(((bank << 16) + off, (bank << 16) + off + len(e) + 1))
    for r in BOOK["ui"]:
        if not r["zh_text"] or r.get("blocked"):
            continue
        enc, _ = encoder.encode(r["zh_text"], split_lines=True, line_pad=False)
        tgt = 0x750000 + (r["target"] if r["target"] is not None else r["offset"])
        if any(a < tgt + len(enc) + 1 and tgt < b for a, b in direct_ranges):
            continue
        if any(tgt <= a < tgt + len(enc) + 1 for a in patch_addrs):
            continue
        moved = r["target"] is not None and r["target"] != r["offset"]
        if moved:
            if bytes(rom[tgt:tgt + len(enc) + 1]) != enc + FF:
                raise ValueError(f"UI verify failed {r['offset']:04X} -> {tgt-0x750000:04X}")
        else:
            end = string_end(rom, tgt)
            got = bytes(rom[tgt:end])
            if enc == FF:                       # {B:FF} = deliberately empty label
                if rom[tgt] != 0xFF:
                    raise ValueError(f"UI empty-label verify failed {r['offset']:04X}")
            elif got != enc and not (got.startswith(enc) and
                                     all(b == 0 for b in got[len(enc):])):
                raise ValueError(
                    f"UI verify failed {r['offset']:04X} -> {tgt-0x750000:04X} "
                    f"got={got.hex()} want={enc.hex()}")
        for addr, val in r["pointers"]:
            if struct.unpack_from(ptr_slot(addr)[1], rom, ptr_slot(addr)[0])[0] != val:
                raise ValueError(f"UI pointer verify failed {addr:06X}")
        want = r["target"] if r["target"] is not None else r["offset"]
        for addr in r["immediates"]:
            if struct.unpack_from("<H", rom, addr)[0] != want:
                raise ValueError(f"UI immediate verify failed {addr:06X} -> {want:04X}")
    # font readback (glyphs >= 2048 live in the second bank at 0x500000)
    for order, ch in enumerate(new_chars):
        i = glyph_index(order)
        j = i if i < 2048 else i - 2048
        base = 0x720000 if i < 2048 else 0x500000
        di = (j >> 3) * 0x100 + (j & 7) * 0x10
        g = encoder.glyphs[ch]
        if rom[base + di:base + di + 16] != g[:16] or \
           rom[base + di + 0x80:base + di + 0x80 + 16] != g[16:]:
            raise ValueError(f"glyph readback failed {ch} U+{ord(ch):04X} index={i}")
    if rom[DISPATCH_AT:DISPATCH_AT + 5] != bytes.fromhex("ea00e00090"):
        raise ValueError("dispatcher patch missing")
    if rom[CAVE_AT:CAVE_AT + len(CAVE)] != CAVE:
        raise ValueError("cave patch missing")
    stats["sequence_overrides"] = 0
    stats["sha256"] = hashlib.sha256(bytes(rom)).hexdigest()
    stats["crc32"] = f"{__import__('zlib').crc32(bytes(rom)) & 0xffffffff:08X}"
    # changed ranges
    orig = ROM_PATH.read_bytes()
    ranges = []
    s = None
    for i, (a, b) in enumerate(zip(orig, rom)):
        if a != b and s is None:
            s = i
        elif a == b and s is not None:
            ranges.append((s, i - 1))
            s = None
    if s is not None:
        ranges.append((s, len(rom) - 1))
    stats["changed_ranges"] = [[s, e] for s, e in ranges]
    if not dry_run:
        OUT_ROM.parent.mkdir(parents=True, exist_ok=True)
        OUT_ROM.write_bytes(rom)
    # machine-readable map
    rows = []
    for order, ch in enumerate(new_chars):
        i = glyph_index(order)
        di = (i >> 3) * 0x100 + (i & 7) * 0x10
        rows.append({"code": f"{0xE000 + i:04X}",
                     "char": ch, "type": "新字库", "bank": f"{NEW_BANK:02X}",
                     "offset": f"{di:04X}", "unicode": f"U+{ord(ch):04X}"})
    for ch, code in REUSE.items():
        rows.append({"code": f"{code:04X}", "char": ch, "type": "沿用原码",
                     "bank": "71", "offset": f"{glyph_offset(code):04X}",
                     "unicode": f"U+{ord(ch):04X}"})
    for ch, code in ORIGINAL_SYMBOL_CODES.items():
        rows.append({"code": f"{code:04X}", "char": ch, "type": "沿用原符号",
                     "bank": "71", "offset": f"{glyph_offset(code):04X}",
                     "unicode": f"U+{ord(ch):04X}"})
    return rom, encoder, stats, hanzi
def write_codebook(encoder: Encoder, stats: dict, hanzi: list[str]):
    import openpyxl
    from io import BytesIO
    from openpyxl.styles import Font
    from openpyxl.drawing.image import Image as XLImage
    from openpyxl.utils import get_column_letter
    rom = OUT_ROM.read_bytes()
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    def sh(name, header):
        ws = wb.create_sheet(name)
        ws.append(header)
        for c in ws[1]:
            c.font = Font(bold=True)
        ws.freeze_panes = "A2"
        return ws
    def add_tile(ws, row, rows, width, col=3, scale=3):
        """rows: 16 ints, MSB = leftmost pixel; draw white-on-black like the ROM."""
        im = Image.new("RGB", (width * scale, 16 * scale), (0, 0, 0))
        px = im.load()
        for y in range(16):
            bits = rows[y]
            for x in range(width):
                if (bits >> (width - 1 - x)) & 1:
                    for dy in range(scale):
                        for dx in range(scale):
                            px[x * scale + dx, y * scale + dy] = (255, 255, 255)
        buf = BytesIO(); im.save(buf, "PNG"); buf.seek(0)
        img = XLImage(buf); img.width = width * scale; img.height = 16 * scale
        ws.add_image(img, f"{get_column_letter(col)}{row}")
        ws.row_dimensions[row].height = 38
        ws.column_dimensions[get_column_letter(col)].width = 7
    import collections
    story_cnt = collections.Counter()
    for r in BOOK["story"]:
        story_cnt.update(r["zh"])
    name_cnt = collections.Counter()
    for r in BOOK["names"]:
        name_cnt.update(r["chinese"])
    ui_cnt = collections.Counter()
    for r in BOOK["ui"]:
        ui_cnt.update(r["zh_text"])
    ws = sh("中文码表", ["码", "字符", "区", "槽位", "字模", "剧情次数", "名称次数", "UI次数"])
    for order, ch in enumerate(encoder.new_chars):
        i = glyph_index(order)
        code = 0xE000 + i
        bank = NEW_BANK if i < 2048 else 0x50
        j = i if i < 2048 else i - 2048
        di = (j >> 3) * 0x100 + (j & 7) * 0x10
        base = 0x720000 if i < 2048 else 0x500000
        g = rom[base + di:base + di + 16] + rom[base + di + 0x80:base + di + 0x80 + 16]
        ws.append([f"{code:04X}", ch, f"{bank:02X}", f"{di:04X}", g.hex(),
                   story_cnt[ch], name_cnt[ch], ui_cnt[ch]])
    ws = sh("特殊字模", ["码", "字符", "区", "槽位", "dx", "dy", "用途"])
    for code, ch, dx, dy, note in BOOK["special"]:
        ws.append([f"{code:04X}", ch, "71", f"{glyph_offset(code):04X}", dx, dy, note])
    ws = sh("单字节", ["码", "字符", "字模"])
    for code in range(0x79, 0x9D):
        di = ((code - 1) >> 4) * 0x100 + ((code - 1) & 0xF) * 8
        g = rom[0x320000 + di:0x320000 + di + 8] + rom[0x320000 + di + 0x80:0x320000 + di + 0x88]
        ws.append([f"{code:02X}", SINGLE.get(code, ""), g.hex()])
    ws = sh("日文码表", ["Fxxx码", "日文字", "tile", "字模"])
    pristine_font = ROM_PATH.read_bytes()
    kanji_map = {}
    _vp = INPUT / "verified_kanji.jsonl"
    if _vp.exists():
        for _line in _vp.read_text(encoding="utf-8").splitlines():
            if _line.strip():
                _o = json.loads(_line)
                kanji_map[int(_o["code"], 16)] = _o["char"]
    for code in sorted(kanji_map):
        if 0xF200 <= code <= 0xF9FF:
            di = glyph_offset(code)
            g = (pristine_font[0x710000 + di:0x710000 + di + 16] +
                 pristine_font[0x710000 + di + 0x80:0x710000 + di + 0x80 + 16])
            ws.append([f"{code:04X}", kanji_map[code], None, g.hex()])
            bits = [(g[y] << 8) | g[8 + y] for y in range(8)] + \
                   [(g[16 + y] << 8) | g[24 + y] for y in range(8)]
            add_tile(ws, ws.max_row, bits, 16)
    ws = sh("统计", ["项目", "值"])
    for k, v in [("新字模", len(encoder.new_chars)), ("汉字", len(hanzi)),
                 ("剧情槽位", len(BOOK["story"])), ("名称项", len(BOOK["names"])),
                 ("UI行", len(BOOK["ui"])), ("池外文本", len(BOOK["direct"])),
                 ("指针补丁", len(BOOK["patches"])), ("CRC32", stats.get("crc32")),
                 ("SHA256", stats.get("sha256"))]:
        ws.append([k, v])
    ws = sh("校验", ["检查", "结果"])
    ws.append(["字模回读", "通过"])
    ws.append(["UI 指针", "通过"])
    ws.append(["剧情/名称回读", "通过"])
    wb.save(OUT_BOOK)
    print("written:", OUT_BOOK)
def main():
    ap = argparse.ArgumentParser(description="Build a Chinese-patched WSC ROM.")
    ap.add_argument("-i", "--input", required=True, help="原版日文 ROM（.wsc）")
    ap.add_argument("-o", "--output", required=True, help="输出中文 ROM（.wsc）")
    ap.add_argument("--text", help="文本工作簿（默认 assets/text.xlsx）")
    ap.add_argument("--codebook", help="码表输出（默认 <输出>_码表.xlsx）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-xlsx", action="store_true")
    args = ap.parse_args()
    global ROM_PATH, TEXT_XLSX, OUT_ROM, OUT_BOOK
    ROM_PATH = Path(args.input).expanduser().resolve()
    if not ROM_PATH.is_file():
        ap.error(f"input ROM not found: {ROM_PATH}")
    TEXT_XLSX = Path(args.text).expanduser().resolve() if args.text else (ASSETS / "text.xlsx")
    if not TEXT_XLSX.is_file():
        ap.error(f"text workbook not found: {TEXT_XLSX}")
    OUT_ROM = Path(args.output).expanduser().resolve()
    OUT_BOOK = (Path(args.codebook).expanduser().resolve() if args.codebook
                else OUT_ROM.with_name(OUT_ROM.stem + "_码表.xlsx"))
    rom, encoder, stats, hanzi = build_rom(args.dry_run)
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print("hanzi distinct:", len(hanzi), "new glyphs:", len(encoder.new_chars),
          "reused:", len(REUSE))
    if not args.dry_run:
        print("written:", OUT_ROM)
        if not args.no_xlsx:
            write_codebook(encoder, stats, hanzi)
if __name__ == "__main__":
    main()
