# -*- coding: utf-8 -*-
"""WS2（COMPACT 2 三部曲）构建总入口。

流程：调用编译模块完成剧情/名称/UI 导入，再在本脚本里补做跨 bank 重排、
F1 长名/长武器名、事件与通关奖励、奇迹说明、固定串修正等后处理，
最后写回产物并打印 CRC。所有地址/宏号均以注释说明用途，便于以后维护。
"""
import os, sys, struct, zlib, re, importlib.util
from importlib.machinery import SourcelessFileLoader
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ws2_common import read_string, SINGLE
loader = SourcelessFileLoader("bti_full", str(HERE / "build_test_import_full.pyc"))
spec = importlib.util.spec_from_loader("bti_full", loader)
bti = importlib.util.module_from_spec(spec)
loader.exec_module(bti)

import story_xfunc2 as sx

CFG = {
    "1": dict(
        banks={0x05: [(0x0000, 0, 0x1380)], 0x06: [(0x1380, 0, 0x1074)],
               0x07: [(0x2700, 0, 0x08B3)], 0x13: [(0x0000, 0, 0x0600)],
               0x14: [(0x0600, 0, 0x0600)], 0x15: [(0x2000, 0, 0x0700)],
               0x16: [(0x2700, 0, 0x0730)], 0x17: [(0x4000, 0, 0x0180)]},
        loaders={1: dict(patch=0x3F52E0, epi=0x3F5324, tab=0xE900),
                 2: dict(patch=0x3F5330, epi=0x3F5390, tab=0xE980)},
        cave=0xE800, free_banks=[0x04, 0x0F, 0x21, 0x25, 0x27, 0x39, 0x3C]),
    "2": dict(
        banks={0x05: [(0x0000, 0, 0x1040)], 0x06: [(0x1040, 0, 0x1040)],
               0x07: [(0x2080, 0, 0x0680), (0x2700, 0x0800, 0x0C78)],
               0x13: [(0x0000, 0, 0x0600)], 0x14: [(0x0600, 0, 0x0600)],
               0x15: [(0x2000, 0, 0x0700)], 0x16: [(0x2700, 0, 0x0780)],
               0x17: [(0x2E80, 0, 0x04A0)]},
        loaders={1: dict(patch=0x3F53B0, epi=0x3F5402, tab=0xE900),
                 2: dict(patch=0x3F540E, epi=0x3F547C, tab=0xE980)},
        cave=0xE800, free_banks=[0x21, 0x22, 0x3C, 0x04, 0x25, 0x1A]),
    "3": dict(
        banks={0x05: [(0x0000, 0, 0x1040)], 0x06: [(0x1040, 0, 0x1040)],
               0x07: [(0x2080, 0, 0x0680), (0x2700, 0x0800, 0x0C78)],
               0x13: [(0x0000, 0, 0x0600)], 0x14: [(0x0600, 0, 0x0600)],
               0x15: [(0x2000, 0, 0x0880)], 0x16: [(0x2880, 0, 0x0880)],
               0x17: [(0x3100, 0, 0x0880)],
               0x18: [(0x3980, 0, 0x01F0)],
               0x3B: [(0x0C00, 0, 0x0228)]},
        loaders={1: dict(patch=0x3F53D0, epi=0x3F5422, tab=0xE900),
                 2: dict(patch=0x3F542E, epi=0x3F54B8, tab=0xE980)},
        cave=0xE800, free_banks=[0x22, 0x25, 0x3C, 0x1A, 0x04],
        no_inplace=[0x18, 0x3B]),
}

CAVE = bytes.fromhex(
    "5051525657062e8b042e8b540239c3720439d3721183c60a2e833cff75e8"
    "31dbb0c531ffeb1229c32e035c082e8a44042e8b7c06d1e301df36a26103"
    "e6c3b800308ec0268b0536a35d03b8003036a35f0336c6064d0341075f5e"
    "5a5958c3")

WS2_ROOT = Path(os.environ.get("WS2_ROOT", r"D:/WSC3/WS2")).resolve()
PROJECT_ROOT = Path(os.environ.get("WS2_PROJECT_ROOT", str(WS2_ROOT.parent))).resolve()
BUILD_ROOT = Path(os.environ.get("WS2_BUILD_ROOT", str(WS2_ROOT / "构建"))).resolve()
bti.WS2 = WS2_ROOT
bti.ROOT = PROJECT_ROOT
bti.BUILD = BUILD_ROOT
for _k in ("1", "2", "3"):
    bti.GAMES[_k]["text"] = bti.BUILD / ("Dai%s" % _k) / "text.xlsx"


_orig_import_ui = bti.import_ui

def _import_ui_padded(rom, mod, cfg, bdir, ui_rows, cmap, stats):
    _orig_import_ui(rom, mod, cfg, bdir, ui_rows, cmap, stats)
    for r in ui_rows:
        if not r.get("zh"):
            continue
        p = 0x350000 + r["off"]
        avail = int(r.get("avail") or 0)
        if avail <= 1:
            continue
        e = rom.find(b"\xff", p, min(len(rom), p + avail + 4))
        if e < 0:
            continue
        used = e - p
        if 0 < used < avail:
            rom[p + used:p + avail] = b"\x00" * (avail - used)
            rom[p + avail] = 0xFF
    # Name repacking copies referenced suffix strings to new bank-0x35 offsets.
    # Update those relocated copies too, otherwise screens that read the copies
    # (spirit list, status labels) still show Japanese.
    orig_path = Path(bdir) / "assets" / "original.ws"
    if orig_path.exists():
        orig = orig_path.read_bytes()
        moved = 0
        for r in ui_rows:
            if not r.get("zh"):
                continue
            p = 0x350000 + r["off"]
            q = orig.find(b"\xff", p, p + 512)
            if q < 0:
                continue
            raw = orig[p:q + 1]
            enc, missing = mod.encode(r["zh"], cmap)
            if missing or len(enc) + 1 > len(raw):
                continue
            new = enc + b"\xff" + b"\x00" * (len(raw) - len(enc) - 1)
            i = 0x350000
            while True:
                j = rom.find(raw, i, 0x360000)
                if j < 0:
                    break
                if j != p:
                    rom[j:j + len(raw)] = new
                    moved += 1
                i = j + 1
        stats["ui_reloc"] = moved
    def alloc_text(data, limit=0xFFF0):
        data = bytes(data).rstrip(b"\xff") + b"\xff"
        forbid = ((0xFE00, 0xFE70), (0xFF00, 0xFF06)) + tuple(_BANK35_RESERVED)
        n = len(data)
        for off in range(limit - n, 0xEFFF, -1):
            if off % 2:
                continue
            if any(off < b and off + n > a for a, b in forbid):
                continue
            if off > 0 and rom[0x350000 + off - 1] != 0xFF:
                continue
            if all(rom[0x350000 + off + k] == 0xFF for k in range(n)):
                rom[0x350000 + off:0x350000 + off + n] = data
                _BANK35_RESERVED.append((off, off + n))
                return off
        raise RuntimeError("no free space for relocated UI text")
    # Intermission menu labels: 改 00 00 00 造 etc.; 下一关 -> 下个关卡.
    # The original 4/6-byte slots are too small, so relocate the strings and
    # repoint the four 5-byte menu records (same offsets in all three games).
    label_jobs = [
        (0x364132, "改造", True),
        (0x364137, "能力", True),
        (0x36413C, "换乘", True),
        (0x36414B, "下个关卡", False),
    ]
    news = []
    for rec, word, spaced in label_jobs:
        cur_word = "下一关" if word == "下个关卡" else word
        cur_enc, miss1 = mod.encode(cur_word, cmap)
        new_enc, miss2 = mod.encode(word, cmap)
        ptr = int.from_bytes(rom[rec:rec + 2], "little")
        p0 = 0x350000 + ptr
        e0 = rom.find(b"\xff", p0, p0 + 32)
        if miss1 or miss2 or e0 < 0 or rom[p0:e0] != cur_enc:
            raise RuntimeError("intermission label layout unexpected: %s" % word)
        if spaced:
            if len(cur_enc) != 4:
                raise RuntimeError("intermission label is not 2 chars: %s" % word)
            new = cur_enc[:2] + bytes(3) + cur_enc[2:] + b"\xff"
        else:
            new = new_enc + b"\xff"
        news.append((rec, new))
    total = sum(len(n) for _, n in news)
    start = None
    for s in range(0xFDF0 - total, 0xEFFF, -1):
        if s % 2:
            continue
        if all(rom[0x350000 + s + k] == 0xFF for k in range(total)):
            start = s
            break
    if start is None:
        raise RuntimeError("no free space for intermission labels")
    off = start
    for rec, new in news:
        rom[0x350000 + off:0x350000 + off + len(new)] = new
        rom[rec:rec + 2] = off.to_bytes(2, "little")
        off += len(new)
    # Unit-list header: 機->机, あと->剩, レベル->按等, 順->级
    # (together they read 剩 X 机 / 按等级).
    ato = next((r for r in ui_rows
                if r.get("cat") == "幕间菜单" and r.get("jp") == "あと"), None)
    if ato:
        a0 = ato["off"]
        for off, new, avail in ((a0 - 3, "机", 2), (a0, "剩", 2),
                                (a0 + 3, "按等", 4), (a0 + 8, "级", 2)):
            enc, miss = mod.encode(new, cmap)
            if miss or not enc or len(enc) > avail:
                raise RuntimeError("unit-list header slot mismatch: %s" % new)
            p = 0x350000 + off
            rom[p:p + len(enc) + 1] = enc + b"\xff"
            for k in range(p + len(enc) + 1, p + avail + 1):
                rom[k] = 0x00
            rom[p + avail] = 0xFF
    # A few stage names have 4/6-byte slots too small for the Chinese name;
    # relocate them and repoint the stage-name table entries.
    stage_fix = {
        "Dai2": ("little", [(0x3F2E9D, 0xBE88, "「所罗门」")]),
        "Dai3": ("big", [(0x3F2EB2, 0xBF67, "「穆特隆遗迹」"),
                         (0x3F2EC0, 0xBFBF, "「波士顿郊外」"),
                         (0x3F2ED6, 0xC057, "「红色宇宙」"),
                         (0x3F2EDA, 0xC06C, "「阿克西斯」")]),
    }.get(bdir.name, ("little", []))
    order, items = stage_fix
    for slot, old, text in items:
        if rom[slot:slot + 2] != old.to_bytes(2, order):
            raise RuntimeError("stage name pointer mismatch: %04X" % slot)
        enc, miss = mod.encode(text, cmap)
        if miss:
            raise RuntimeError("stage name missing: %s" % text)
        rom[slot:slot + 2] = alloc_text(enc + b"\xff").to_bytes(2, order)
    # Long terrain names: repoint the terrain-name table (bank 0x3C, u16 LE).
    terrain_fix = {
        "Dai2": (0x3C2400, 0x3C2500, {
            0xB36C: "所罗门", 0xB371: "阿纳海姆", 0xB389: "格利普斯2"}),
        "Dai3": (0x3C2500, 0x3C25C0, {
            0xB410: "所罗门", 0xB415: "阿纳海姆", 0xB42D: "格利普斯2",
            0xB477: "无限城", 0xB484: "阿克西斯", 0xB4AB: "无限"}),
    }.get(bdir.name)
    if terrain_fix:
        start, end, mapping = terrain_fix
        new = {}
        for old, text in mapping.items():
            enc, miss = mod.encode(text, cmap)
            if miss:
                raise RuntimeError("terrain name missing: %s" % text)
            new[old] = alloc_text(enc + b"\xff")
        for a in range(start, end, 2):
            v = int.from_bytes(rom[a:a + 2], "little")
            if v in new:
                rom[a:a + 2] = new[v].to_bytes(2, "little")
    # Remaining proper nouns in the name table (entries still using F2-F9
    # Japanese glyphs).  Move the translated string into free space and
    # repoint only that name-table entry.
    name_fix = {
        "Dai1": (0x3F1F89, {
            154: "瓦尔·瓦罗", 1139: "宇宙新星", 1217: "爪", 1475: "剑",
            1538: "舌", 1653: "艾亚瓦尔特"}),
        "Dai2": (0x3F1FB9, {
            154: "瓦尔·瓦罗", 283: "纯白骑士", 1148: "宇宙新星", 1226: "爪",
            1484: "剑", 1547: "舌", 1662: "艾亚瓦尔特"}),
        "Dai3": (0x3F1FB9, {
            154: "瓦尔·瓦罗", 292: "古铁巨人", 1149: "宇宙新星",
            1164: "阿兰奇克莱莫", 1227: "爪", 1246: "剑", 1485: "剑",
            1548: "舌", 1663: "艾亚瓦尔特", 1695: "艾亚瓦尔特"}),
    }.get(bdir.name)
    if name_fix:
        arr, items = name_fix
        for idx, text in items.items():
            enc, miss = mod.encode(text, cmap)
            if miss:
                raise RuntimeError("name fix missing chars %s: %s" % (text, miss))
            off = alloc_text(enc + b"\xff")
            rom[arr + 2 * idx:arr + 2 * idx + 2] = off.to_bytes(2, "little")
    # Relocate strings whose original slots are too small for the WSC3 wording.
    def put(off, text):
        e, m = mod.encode(text, cmap)
        if m or off <= 0 or rom[off - 1] != 0xFF:
            return False
        if any(b != 0xFF for b in rom[off:off + len(e) + 1]):
            return False
        rom[off:off + len(e) + 1] = e + b"\xff"
        return True

    # Intermission "強化"+"パーツ": the パーツ half is only 3 bytes, so point it
    # at "芯片" in free space (-> 强化芯片).
    enc_chip, miss_chip = mod.encode("芯片", cmap)
    if not miss_chip:
        chip_off = alloc_text(enc_chip + bytes([0xFF]))
        # every menu/table copy of the パーツ label -> 芯片
        for p in (0x364146, 0x3641E5, 0x3641EA, 0x3641FF, 0x364219):
            rom[p:p + 2] = chip_off.to_bytes(2, "little")
        slot = 0x3F1EC0 if bdir.name == "Dai1" else 0x3F1EF0
        rom[slot:slot + 2] = chip_off.to_bytes(2, "little")

    # 大根性 32px strip, WSC3 F1FD layout.  F0xx would OR a dakuten mark
    # (the dots) into rows 1-2.  The renderer advances 12px per double-byte
    # glyph and 8px per single-byte glyph, so pack 12+12+8 = 32px into two
    # blank F5 kanji slots plus the blank 0xDF single-byte slot.  Name:
    # F5 39 F5 6D DF FF, which fits the original 6-byte slot.  No F1 macro:
    # its handler rejects single-byte body codes.
    f1 = {
        "Dai1": (0xB1B2, 0x3F1F89, 1686),
        "Dai2": (0xB3F3, 0x3F1FB9, 1701),
        "Dai3": (0xB515, 0x3F1FB9, 1716),
    }.get(bdir.name)
    cells = [
        ("00000404047f0404", "0a0a121160000000"),
        ("000005051fc50507", "0d150505c5000000"),
        ("0000f010f212f24a", "5020205088000000"),
        ("000088a8e8bfa8c8", "be888888bf000000"),
    ]
    def pack_kanji16(seg):
        g = []
        for y in range(8):
            g.append(sum(seg[y][x] << (7 - x) for x in range(8)))
        for y in range(8):
            g.append(sum(seg[y][x + 8] << (7 - x) for x in range(8)))
        for y in range(8, 16):
            g.append(sum(seg[y][x] << (7 - x) for x in range(8)))
        for y in range(8, 16):
            g.append(sum(seg[y][x + 8] << (7 - x) for x in range(8)))
        return bytes(g)
    def pack_single8(seg):
        return bytes([sum(seg[y][x] << (7 - x) for x in range(8))
                      for y in range(16)])
    if f1:
        sname, arrbase, aidx = f1
        strip = [[0] * 32 for _ in range(16)]
        for c, (t, b) in enumerate(cells):
            tb = bytes.fromhex(t) + bytes.fromhex(b)
            for y in range(16):
                for x in range(8):
                    if (tb[y] >> (7 - x)) & 1:
                        strip[y + 2][c * 8 + x] = 1   # rows 2-12 -> 4-14
        def seg16(x0, n):
            return [[strip[y][x0 + x] if x < n else 0 for x in range(16)]
                    for y in range(16)]
        gA = pack_kanji16(seg16(0, 12))
        gB = pack_kanji16(seg16(12, 12))
        gC = pack_single8([[strip[y][24 + x] for x in range(8)]
                           for y in range(16)])
        def kaddr(code):
            n = ((code >> 8) - 0xF2) * 256 + (code & 0xFF)
            return 0x301000 + (n >> 3) * 0x100 + (n & 7) * 0x10
        dfaddr = 0x300000 + ((0xDF - 1) >> 4) * 0x100 + ((0xDF - 1) & 0xF) * 8
        ok = all(not any(rom[a:a + 16]) and not any(rom[a + 0x80:a + 0x90])
                 for a in (kaddr(0xF539), kaddr(0xF56D)))
        ok = ok and not any(rom[dfaddr:dfaddr + 8]) and \
            not any(rom[dfaddr + 0x80:dfaddr + 0x88])
        if not ok:
            raise RuntimeError(
                "大根性 glyph slots not free: kA=%s kB=%s df=%s" % (
                    rom[kaddr(0xF539):kaddr(0xF539) + 16].hex(),
                    rom[kaddr(0xF56D):kaddr(0xF56D) + 16].hex(),
                    rom[dfaddr:dfaddr + 8].hex()))
        for code, g in ((0xF539, gA), (0xF56D, gB)):
            a = kaddr(code)
            rom[a:a + 16] = g[:16]
            rom[a + 0x80:a + 0x90] = g[16:]
        rom[dfaddr:dfaddr + 8] = gC[:8]
        rom[dfaddr + 0x80:dfaddr + 0x88] = gC[8:]
        # Put the compact name in a fresh slot and point only this table entry
        # at it.  The repacked 大根性 string shares its 根性 suffix with the
        # normal 根性 entry, so it must not be overwritten.
        noff = alloc_text(bytes([0xF5, 0x39, 0xF5, 0x6D, 0xDF, 0xFF]))
        rom[arrbase + 2 * aidx:arrbase + 2 * aidx + 2] = noff.to_bytes(2, "little")

    # Terrain-type table: point at relocated Chinese strings so the unit-info
    # "型" line does not reuse an old/duplicated Japanese copy.
    if bdir.name == "Dai1":
        tptrs = [0x3F1FA9, 0x3F1FAD, 0x3F1FAF, 0x3F1FB1, 0x3F1FB3, 0x3F1FB5, 0x3F1FB7]
    else:
        tptrs = [0x3F1FD9, 0x3F1FDD, 0x3F1FDF, 0x3F1FE1, 0x3F1FE3, 0x3F1FE5, 0x3F1FE7]
    for p, text in zip(tptrs, ("陆", "空陆", "水中", "水陆", "水陆空", "陆地中", "宇宙")):
        enc, miss = mod.encode(text, cmap)
        if miss:
            raise RuntimeError("terrain text missing: %s" % text)
        rom[p:p + 2] = alloc_text(enc + b"\xff").to_bytes(2, "little")

    # Intermission title: 00 幕前 00 整备 (blank before and between words).
    a4, m4 = mod.encode("幕前", cmap)
    b4, m5 = mod.encode("整备", cmap)
    if not m4 and not m5:
        buf = b"\x00" + a4 + b"\x00" + b4 + b"\xff"
        rom[0x35FE60:0x35FE60 + len(buf)] = buf
        rom[0x364123:0x364125] = (0xFE60).to_bytes(2, "little")

    # Objective page labels/conditions: 4/7-byte slots cannot hold 胜利条件/
    # 失败条件/敌方全灭, so relocate them and repoint the objective table.
    put(0x35FE00, "胜利条件")
    put(0x35FE20, "失败条件")
    put(0x35FE40, "敌方全灭")
    tbl = {
        "Dai1": (0x3F3462, 0x3F3464, 0x3F3466, 0x3F3560, {0xC9AF, 0xC9E2, 0xCA96}, (0x3F3454, 0x3F3456)),
        "Dai2": (0x3F34A2, 0x3F34A4, 0x3F34A6, 0x3F3580, {0xCAA6, 0xCAD9, 0xCB8D}, (0x3F3494, 0x3F3496)),
        "Dai3": (0x3F34C0, 0x3F34C2, 0x3F34C4, 0x3F35A0, {0xCA2F, 0xCA62, 0xCB16}, (0x3F34B2, 0x3F34B4)),
    }.get(bdir.name)
    if tbl:
        wp, lp, start, end, old, pair2 = tbl
        for a in (wp, pair2[0]):
            rom[a:a + 2] = (0xFE00).to_bytes(2, "little")
        for a in (lp, pair2[1]):
            rom[a:a + 2] = (0xFE20).to_bytes(2, "little")
        for a in range(start, end, 2):
            if int.from_bytes(rom[a:a + 2], "little") in old:
                rom[a:a + 2] = (0xFE40).to_bytes(2, "little")
    # The objective page hardcodes its 胜利/失败 label offsets in bank 0x3C
    # (`mov ax, <offset>`), so repoint those immediates as well.
    obj_code = {
        "Dai1": (0x3C33DD, 0x3C345A),
        "Dai2": (0x3C598D, 0x3C5A0A),
        "Dai3": (0x3C922D, 0x3C92AA),
    }.get(bdir.name)
    if obj_code:
        a1, a2 = obj_code
        if rom[a1] != 0xB8 or rom[a2] != 0xB8:
            raise RuntimeError("objective label code not found")
        rom[a1 + 1:a1 + 3] = (0xFE00).to_bytes(2, "little")
        rom[a2 + 1:a2 + 3] = (0xFE20).to_bytes(2, "little")
    # Text loops still compare against 0xF0 in some banks; E0-EF Chinese would
    # advance one byte per glyph and garble the second character.
    tag = b"\x3c\xf0\x72\x03\x83\xc5\x01\x9a"
    for i in range(len(rom) - 15):
        if rom[i:i + 8] == tag and rom[i + 10:i + 15] == b"\x00\xf0\x83\xc5\x01":
            rom[i + 1] = 0xE0
    # 特殊技能说明是片段拼接：C936「に」只有 1 字节槽，中文放不下，直接置空；
    # 动词片段 C93F 由 UI 表写入「附加。」，疑问句由 C97A「确定吗？」提供。
    particle = {"Dai1": 0xC936, "Dai2": 0xCA2D, "Dai3": 0xC9B6}.get(bdir.name)
    if particle is not None:
        p = 0x350000 + particle
        if rom[p:p + 2] != b"\x16\xff":
            raise RuntimeError("特殊技能助词槽位不符: %s %04X" % (bdir.name, particle))
        rom[p:p + 2] = b"\x00\xff"

# ---------------------------------------------------------------------------
# 长武器名 / 长道具名：用 F1 宏压缩到正好 84px，并整宽均匀铺满。
# C2 的 F1 宏体是“若干字模码 + FF”，处理器在 bank 0x3F 的 0x3F5A90。
# 宏表 32 项（F1E0–F1FF）；新名字放到 free tail，宏体指向 7 个 12px 字模块。
# 每个名字按 84/n 的小数步距分配字宽，整条正好 84px，尾部不留空。
# ---------------------------------------------------------------------------
F1_NAMES = {
    "D1": [(0xD0, "扩散米加粒子炮"), (0xE0, "双联装光束加农炮"), (0xE1, "零距离米加光束炮"),
           (0xE2, "四联装导弹发射器"), (0xE5, "大型织女星光束炮"),
           (0xE7, "米诺夫斯基飞行器"), (0xE8, "S-DX机器人冲拳"),
           (0xE9, "机械兽布斯特拉西德"), (0xEA, "美加诺伊德"),
           (0xEB, "美加诺伊德·"),
           (0xFC, "瓦尔基梅德"),
           (0xD6, "精神感应高达MKII"),
           (0xD8, "机械兽布斯丹加鲁恩"), (0xD9, "机械兽哈利维恩V6"),
           (0xDA, "克莉丝蒂娜·玛肯吉"), (0xDB, "帕普提马斯·西罗克"),
           (0xDC, "塞西莉·费尔柴尔德"), (0xDD, "加拉莉亚·尼亚姆希")],
    "D2": [(0xD0, "扩散米加粒子炮"), (0xE0, "双联装光束加农炮"), (0xE1, "零距离米加光束炮"),
           (0xE2, "四联装导弹发射器"), (0xE7, "米诺夫斯基飞行器"),
           (0xE8, "机械兽布斯特拉西德"), (0xE9, "美加诺伊德"),
           (0xEA, "美加诺伊德·"), (0xEB, "S-DX机器人冲拳"),
           (0xEE, "梅加诺伊德"), (0xEF, "瓦尔基梅德"),
           (0xD6, "精神感应高达MKII"),
           (0xD8, "机械兽布斯丹加鲁恩"), (0xD9, "机械兽哈利维恩V6"),
           (0xDC, "克莉丝蒂娜·玛肯吉"), (0xDD, "帕普提马斯·西罗克"),
           (0xDE, "塞西莉·费尔柴尔德"), (0xDF, "加拉莉亚·尼亚姆希"),
           (0xFF, "主人公机")],
    "D3": [(0xD0, "扩散米加粒子炮"), (0xE0, "双联装光束加农炮"), (0xE1, "零距离米加光束炮"),
           (0xE2, "四联装导弹发射器"), (0xE7, "米诺夫斯基飞行器"),
           (0xE8, "机械兽布斯特拉西德"), (0xE9, "美加诺伊德"),
           (0xEA, "美加诺伊德·"), (0xEB, "S-DX机器人冲拳"),
           (0xEE, "梅加诺伊德"), (0xEF, "瓦尔基梅德"),
           (0xD6, "精神感应高达MKII"),
           (0xD8, "机械兽布斯丹加鲁恩"), (0xD9, "机械兽哈利维恩V6"),
           (0xDC, "克莉丝蒂娜·玛肯吉"), (0xDD, "帕普提马斯·西罗克"),
           (0xDE, "塞西莉·费尔柴尔德"), (0xDF, "加拉莉亚·尼亚姆希")],
}
F1_ID_BASE = 0xD0
# 这些宏只改名称指针，不参与临时工作簿替换：名字原字模必须保留，码位才不会漂移。
LONG_NAME_IDS = set(range(0xD4, 0xE0)) | {0xFF}
F1_HANDLER = {
    "D1": dict(sub=0x3F5A9E, legacy=0x3576, f1loop=0x3F5AC6),
    "D2": dict(sub=0x3F5B8A, legacy=0x35AA, f1loop=0x3F5BB2),
    "D3": dict(sub=0x3F5BC6, legacy=0x35CC, f1loop=0x3F5BEE),
}
F1_TABLE_ADDR = 0x3FFF00
F1_BODY_ADDR = 0x3FF800
F1_EMPTY_ADDR = 0x3FFFE6
F1_TABLE_N = 48
F1_MAX_W = 84
F1_WIDTHS = {"扩散米加粒子炮": 72, "机械兽布斯特拉西德": 96, "美加诺伊德": 56, "美加诺伊德·": 60, "S-DX机器人冲拳": 84}
F1_NICK_TEXTS = {"瓦尔基梅德", "梅加诺伊德"}
for _t in F1_NICK_TEXTS:
    F1_WIDTHS[_t] = 56
# 这些短名同时出现在「名称_角色」和「名称_爱称」：角色名保持原尺寸，
# 只有 48px 的爱称槽位改用 F1 宏，避免 5 个字挤不进 4 格。
F1_NICK_ONLY = set()
for _t in F1_NICK_ONLY:
    F1_WIDTHS[_t] = 48
# 9 字以上的角色/机体名统一压到 96px（8 格）；「主人公机」是男女主人公机名的共用前缀。
for _t in ("精神感应高达MKII",
           "机械兽布斯丹加鲁恩", "机械兽哈利维恩V6",
                      "克莉丝蒂娜·玛肯吉", "帕普提马斯·西罗克",
           "塞西莉·费尔柴尔德", "加拉莉亚·尼亚姆希"):
    F1_WIDTHS[_t] = 96
F1_WIDTHS["主人公机"] = 48
F1_PITCH_MAX = 12

# F1 宏配置缓存：由 text.xlsx 的「F1宏」页覆盖上面的默认表。
F1_CFG = {}
F1_MODES = {}
F1_GAPS = {}
F1_SPECIAL = {}


def _load_f1_sheet(src, game):
    """读取 text.xlsx 的 F1宏 页，更新该作的宏名/目标宽/字间距/模式。

    列：宏号 类型 日文 中文 字数 目标宽 字宽 逐字宽 字间距 右移
        自然 字体 字号 模式 说明 校准 去空白 留白字 下移字
    普通/S-DX 行进 F1_NAMES；GP01/武器全名行只进 F1_SPECIAL，由专用函数使用。
    """
    import openpyxl
    wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
    if "F1宏" not in wb.sheetnames:
        wb.close()
        return
    ws = wb["F1宏"]
    hdr = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    cols = {str(h): i for i, h in enumerate(hdr) if h is not None}
    names = []
    cfgs = {}
    special = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        def get(key, default=None):
            i = cols.get(key)
            return row[i] if i is not None and i < len(row) else default
        raw_id = str(get("宏号") or "").strip().upper()
        if not raw_id:
            continue
        raw_id = raw_id[2:] if raw_id.startswith("F1") else raw_id
        try:
            mid = int(raw_id, 16)
        except ValueError:
            continue
        text = str(get("中文") or "").strip()
        if not text:
            continue
        mode = str(get("模式") or "普通").strip()
        try:
            target = int(get("目标宽") or 0)
        except (TypeError, ValueError):
            target = 0
        if target <= 0:
            target = F1_WIDTHS.get(text, F1_MAX_W)
        try:
            gap = int(get("字间距") or 0)
        except (TypeError, ValueError):
            gap = 0
        cfg = dict(mid=mid, text=text, mode=mode, width=target, gap=gap,
                   raw=dict(zip(hdr, row)))
        if mode in ("普通", "S-DX", "前缀"):
            names.append((mid, text))
            F1_WIDTHS[text] = target
            F1_MODES[text] = mode
            F1_GAPS[text] = gap
            cfgs[text] = cfg
        else:
            special.setdefault(mode, []).append(cfg)
    wb.close()
    if names:
        F1_NAMES[game] = names
        F1_CFG[game] = cfgs
        F1_SPECIAL[game] = special
        print("F1CFG", game, "rows", len(names), "special",
              {k: len(v) for k, v in special.items()})

_CMAP_STORE = {}
_orig_load_ws2lib = bti.load_ws2lib

def _load_ws2lib_capture(bdir):
    mod = _orig_load_ws2lib(bdir)
    orig_write_font = mod.write_font

    def write_font(rom, cfg, cmap):
        _CMAP_STORE[str(cfg.get("GAME"))] = dict(cmap)
        return orig_write_font(rom, cfg, cmap)

    mod.write_font = write_font
    # 默认名里的“琳/勃”只出现在 bank0x3D 固定串，不会进入普通文本收集。
    # 给 alloc_codes 补上固定字符，确保字模写入固定码位，后续编码也能取到。
    game = "D" + Path(str(bdir)).name[-1]
    orig_alloc = mod.alloc_codes

    def alloc_codes(chars):
        return orig_alloc(set(chars) | set(PINNED_NAME_CODES.get(game, {})))

    mod.alloc_codes = alloc_codes
    return mod

bti.load_ws2lib = _load_ws2lib_capture


def _f1_cfg(bdir):
    import openpyxl
    wb = openpyxl.load_workbook(Path(bdir) / "text.xlsx", read_only=True, data_only=True)
    ws = wb["设定"]
    cfg = {}
    for k, v in ws.iter_rows(min_row=2, values_only=True):
        if k:
            cfg[str(k)] = v
    return cfg


def _f1_chunks(cfg):
    out = []
    for part in str(cfg["CHUNKS"]).split(","):
        bank, base = part.split(":")
        out.append((int(bank, 16), int(base, 16)))
    return out


def _f1_slot_addr(code, chunks):
    n = code - 0xE000
    ci = n >> 10
    loc = n & 0x3FF
    if ci >= len(chunks):
        raise RuntimeError("F1 glyph chunk overflow: %04X" % code)
    bank, base = chunks[ci]
    return bank * 0x10000 + base + (loc >> 3) * 0x100 + (loc & 7) * 0x10


def _f1_free_codes(rom, chunks, used, need):
    out = []
    for code in range(0xEFFC, 0xDFFF, -1):
        if (code & 0xFF) in (0xFD, 0xFE, 0xFF):
            continue
        if code in used:
            continue
        a = _f1_slot_addr(code, chunks)
        if all(b == 0xFF for b in rom[a:a + 16]) and \
                all(b == 0xFF for b in rom[a + 0x80:a + 0x90]):
            out.append(code)
            if len(out) == need:
                return out
    raise RuntimeError("F1 needs %d free glyph slots, only %d found" % (need, len(out)))


def _f1_targets(n, width=F1_MAX_W):
    """按目标总宽分字宽；只差 1px（例如 9 字 10/11px），+1 宽均匀分布。"""
    base, extra = divmod(width, n)
    wide = set()
    if extra:
        wide = {int(round((k + 0.5) * n / extra - 0.5)) for k in range(extra)}
    return [base + 1 if i in wide else base for i in range(n)]


def _f1_glyph(ch, font):
    """WQY9 12px 单字：底部对齐第 14 行，裁掉左右空白列；返回 (image, natural_width)。"""
    from PIL import Image, ImageDraw
    cell = Image.new("L", (20, 20), 0)
    ImageDraw.Draw(cell).text((1, 5), ch, font=font, fill=255)
    px = cell.load()
    cols = [x for x in range(20) if any(px[x, y] > 128 for y in range(16))]
    if not cols:
        return Image.new("L", (1, 16), 0), 1
    x0, x1 = min(cols), max(cols)
    piece = Image.new("L", (x1 - x0 + 1, 16), 0)
    piece.paste(cell.crop((x0, 0, x1 + 1, 16)), (0, 0))
    return piece, x1 - x0 + 1


def _f1_fit(im, natural, target):
    from PIL import Image
    px = im.load()
    w = natural
    while w > target:
        left = sum(1 for y in range(16) if px[0, y] > 128)
        right = sum(1 for y in range(16) if px[w - 1, y] > 128)
        if left >= 8 and right < 8:
            im = im.crop((0, 0, w - 1, 16))
        else:
            im = im.crop((1, 0, w, 16))
        w -= 1
        px = im.load()
    if w < target:
        out = Image.new("L", (target, 16), 0)
        out.paste(im, (0, 0))
        im = out
    return im


def _f1_ascii_prefix(prefix, font_path):
    """与 WSC3 单字节 ASCII 相同：Zpix 12px，每字 8px 半角格；
    S 等窄字按 (8-w)//2+1 左移 1px，右侧不出格。"""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(str(font_path), 12)
    cells = []
    for ch in prefix:
        if ch == "-":
            bar = Image.new("L", (8, 16), 0)
            ImageDraw.Draw(bar).rectangle((2, 8, 5, 8), fill=255)
            cells.append(bar)
            continue
        cell = Image.new("L", (32, 16), 0)
        ImageDraw.Draw(cell).text((0, 0), ch, font=font, fill=255)
        bb = cell.getbbox()
        if not bb:
            raise RuntimeError("F1 ASCII prefix empty: %s" % prefix)
        im = cell.crop(bb)
        if im.width > 8:
            im = im.resize((8, im.height), Image.LANCZOS)
        im = im.point(lambda p: 255 if p > 128 else 0)
        out = Image.new("L", (8, 16), 0)
        px = (8 - im.width) // 2 + 1
        if ch == "S":
            px = 1
        py = 14 - (im.height - 1) - 1
        if px + im.width > 8:
            px = 8 - im.width
        if py < 0:
            py = 0
        out.paste(im, (px, py))
        cells.append(out)
    res = Image.new("L", (len(cells) * 8, 16), 0)
    for i, c in enumerate(cells):
        res.paste(c, (i * 8, 0))
    return res, len(cells) * 8


def _f1_custom_cjk(text, width, cfg):
    """按 xlsx 的字宽/字号/字间距/逐字宽生成纯中文条带；未配置则返回 None。"""
    if not cfg or not all(ord(ch) >= 128 for ch in text):
        return None
    raw = cfg.get("raw") or {}
    # “压缩=自然”的旧宏走 _f1_render_strip 的墨迹压缩分支，
    # 不能被这里的统一 12px/字 + 字间距布局覆盖。
    if str(raw.get("压缩", "")).strip() in ("自然", "自然压缩"):
        return None
    def _int(key):
        try:
            return int(raw.get(key) or 0)
        except (TypeError, ValueError):
            return 0
    gap = int(cfg.get("gap") or 0)
    widths_raw = str(raw.get("逐字宽") or "").strip()
    base = _int("字宽") or _int("字号")
    # 字号 12 且没有其它配置时沿用默认的 9/10/11 均匀分配
    if not widths_raw and not gap and (not base or base == 12):
        return None
    n = len(text)
    if widths_raw:
        try:
            targets = [int(x) for x in widths_raw.replace("，", ",").replace(" ", ",").split(",") if x]
        except ValueError:
            raise RuntimeError("F1 %s 逐字宽格式错误: %s" % (text, widths_raw))
        if len(targets) != n:
            raise RuntimeError("F1 %s 逐字宽 %d 个 != %d 字" % (text, len(targets), n))
    else:
        base = base or 12
        targets = [base] * n
        if n > 1:
            targets = [base + gap] * (n - 1) + [base]
    diff = width - sum(targets)
    # 余量/超出按字符轮转，保持整条宽度准确
    k = 0
    while diff > 0:
        targets[k % n] += 1
        diff -= 1
        k += 1
    while diff < 0:
        i = k % n
        if targets[i] > 1:
            targets[i] -= 1
            diff += 1
        k += 1
    return targets


def _f1_render_cfg_cjk(text, font, width, cfg):
    """纯中文 F1 的可配置排版：逐字宽优先，其次字宽/字号+字间距。"""
    targets = _f1_custom_cjk(text, width, cfg)
    if targets is None:
        return None
    pieces = []
    char_info = []
    x = 0
    for ch, target in zip(text, targets):
        im, natural = _f1_glyph(ch, font)
        im = _f1_fit(im, natural, target)
        pieces.append(im)
        char_info.append((ch, target, natural, target - natural, x))
        x += target
    if x != width:
        raise RuntimeError("F1 %s 配置宽度 %d != %d" % (text, x, width))
    ncell = (width + 11) // 12
    rows = [[0] * (ncell * 12) for _ in range(16)]
    for i, im in enumerate(pieces):
        px = im.load()
        x0 = char_info[i][4]
        for y in range(16):
            for xx in range(im.width):
                if px[xx, y] > 128:
                    rows[y][x0 + xx] = 1
    cells = []
    for c in range(ncell):
        seg = [[0] * 16 for _ in range(16)]
        for y in range(16):
            for xx in range(12):
                seg[y][xx] = rows[y][c * 12 + xx]
        cells.append(seg)
    return cells, width, char_info


def _f1_render_strip(text, font, ascii_font_path=None, width=F1_MAX_W, cfg=None):
    """把 F1 宏名渲染成条带字模（WSC3 同款）。

    配置优先：text.xlsx 的 F1宏 页提供目标宽/字宽/字号/字间距/逐字宽；
    纯中文且显式配置了字号或字间距时走 `_f1_render_cfg_cjk`。
    其余沿用默认：普通名字按目标总宽逐字裁/补 1px，直接相接；
    S-DX机器人冲拳 用 Zpix 半角按黑边裁切，S 左侧 1px、字间 1px。
    """
    from PIL import Image
    got = _f1_render_cfg_cjk(text, font, width, cfg)
    if got is not None:
        return got
    # WSC3 式自然压缩：按字模墨迹宽逐字裁切、直接相接，不再把余量摊到字间；
    # 余量留在条带末尾，超宽时优先压最宽的字。仅“压缩=自然”的旧宏使用。
    natural_pack = bool(cfg and str(cfg.get("raw", {}).get("压缩", "")).strip() in ("自然", "自然压缩"))
    if natural_pack:
        gap = int(cfg.get("gap") or 0) if cfg else 0
        infos = []
        for ch in text:
            im, nat = _f1_glyph(ch, font)
            infos.append([ch, im, nat, nat])
        n = len(infos)
        available = width - gap * (n - 1)
        total = sum(v[3] for v in infos)
        if total > available:
            excess = total - available
            while excess:
                i = max(range(len(infos)), key=lambda k: infos[k][3])
                if infos[i][3] <= 5:
                    raise RuntimeError("F1 %s 超宽 %dpx" % (text, excess))
                infos[i][3] -= 1
                excess -= 1
        pieces = []
        char_info = []
        x = 0
        for idx, (ch, im, nat, target) in enumerate(infos):
            im = _f1_fit(im, nat, target)
            pieces.append(im)
            char_info.append((ch, target, nat, target - nat, x))
            x += target + (gap if idx < n - 1 else 0)
        if x < width:
            from PIL import Image as _Img
            pad = width - x
            pieces.append(_Img.new("L", (pad, 16), 0))
            char_info.append((" ", pad, pad, 0, x))
            x += pad
    elif text == "S-DX机器人冲拳":
        if not ascii_font_path or width != 84:
            raise RuntimeError("S-DX机器人冲拳 F1 需要 84px 和 Zpix 字库")
        gap = int(cfg.get("gap", 1)) if cfg else 1
        pieces = []
        char_info = []
        x = gap  # S 左侧留 1px，避免贴住图标/边框
        for i, ch in enumerate("S-DX"):
            cell, _ = _f1_ascii_prefix(ch, ascii_font_path)
            bb = cell.getbbox()
            if not bb:
                raise RuntimeError("S-DX 空字模: %s" % ch)
            im = cell.crop((bb[0], 0, bb[2], 16))
            pieces.append(im)
            char_info.append((ch, im.width, im.width, 0, x))
            x += im.width + (gap if i < 3 else 0)
        x += gap  # X 与「机器人冲拳」之间 1px
        for ch in "机器人冲拳":
            im, natural = _f1_glyph(ch, font)
            im = _f1_fit(im, natural, 12)
            pieces.append(im)
            char_info.append((ch, 12, natural, 12 - natural, x))
            x += 12
    elif text == "精神感应高达MKII":
        # 中文按墨迹 strip；MKII 保持完整自然字形，把「达」后的空余像素
        # 均匀分到 M 前、M-k、k-、-I、I-I 五个间隔里，绝不裁 M 的竖线。
        pieces = []
        char_info = []
        x = 0
        for ch in "精神感应高达":
            im, natural = _f1_glyph(ch, font)
            pieces.append(im)
            char_info.append((ch, natural, natural, 0, x))
            x += natural
        mk = "MKII"
        mk_parts = []
        for ch in mk:
            im, natural = _f1_glyph(ch, font)
            mk_parts.append((ch, im, natural))
        spare = width - x - sum(n for _, _, n in mk_parts)
        n_gaps = len(mk_parts)  # 前导 + 4 个字间，末尾贴到 96px
        if spare < n_gaps:
            raise RuntimeError("MKII 没有足够空白均匀分配: %dpx" % spare)
        base, extra = divmod(spare, n_gaps)
        gaps = [base] * n_gaps
        for k in range(extra):
            gaps[(k * 2 + 1) % n_gaps] += 1
        for idx, (ch, im, natural) in enumerate(mk_parts):
            x += gaps[idx]
            pieces.append(im)
            char_info.append((ch, natural, natural, 0, x))
            x += natural
    elif text == "美加诺伊德·":
        targets = [11, 11, 11, 11, 11, 5]
        pieces = []
        char_info = []
        x = 0
        for ch, target in zip(text, targets):
            im, natural = _f1_glyph(ch, font)
            if ch == "·":
                out = Image.new("L", (target, 16), 0)
                out.paste(im, ((target - im.width) // 2, 0))
                im = out
            else:
                im = _f1_fit(im, natural, target)
            pieces.append(im)
            char_info.append((ch, target, natural, target - natural, x))
            x += target
    else:
      # 兼容旧数据：S-/S-DX 前缀 + 5 字（当前 S-DX机器人冲拳 已改为整名宏，不再走这里）
      m = re.match(r"^(S-(?:DX)?)(.{5})$", text)
      if m and ascii_font_path:
        prefix, body = m.groups()
        pim, pnat = _f1_ascii_prefix(prefix, ascii_font_path)
        pw = pim.width
        pieces = [pim]
        char_info = [(prefix, pw, pnat, pw - pnat, 0)]
        x = pw
        targets = _f1_targets(len(body), width - pw)
        for ch, target in zip(body, targets):
            im, natural = _f1_glyph(ch, font)
            im = _f1_fit(im, natural, target)
            pieces.append(im)
            char_info.append((ch, target, natural, target - natural, x))
            x += target
      else:
        if any(ch == "·" or ord(ch) < 128 for ch in text):
            infos = []
            for ch in text:
                im, natural = _f1_glyph(ch, font)
                if ch == "·":
                    target = 4
                elif ord(ch) < 128:
                    target = natural
                else:
                    target = 12
                infos.append([ch, im, natural, target])
            total = sum(v[3] for v in infos)
            if total <= width:
                # 均匀铺满：余量按字符轮转 +1，避免全塞给最后一个字或只撑大少数汉字
                extra = width - total
                for k in range(extra):
                    infos[k % len(infos)][3] += 1
            else:
                excess = total - width
                cjk = [i for i, v in enumerate(infos)
                       if v[0] != "·" and ord(v[0]) >= 128]
                if not cjk:
                    raise RuntimeError("F1 %s 无法压缩到 %dpx" % (text, width))
                while excess:
                    i = max(cjk, key=lambda k: infos[k][3])
                    if infos[i][3] <= 6:
                        raise RuntimeError("F1 %s 超宽 %dpx" % (text, excess))
                    infos[i][3] -= 1
                    excess -= 1
            pieces = []
            char_info = []
            x = 0
            for ch, im, natural, target in infos:
                if ch == "·":
                    out = Image.new("L", (target, 16), 0)
                    out.paste(im, ((target - im.width) // 2, 0))
                    im = out
                else:
                    im = _f1_fit(im, natural, target)
                pieces.append(im)
                char_info.append((ch, target, natural, target - natural, x))
                x += target
        else:
            targets = _f1_targets(len(text), width)
            pieces = []
            char_info = []
            x = 0
            for ch, target in zip(text, targets):
                im, natural = _f1_glyph(ch, font)
                im = _f1_fit(im, natural, target)
                pieces.append(im)
                char_info.append((ch, target, natural, target - natural, x))
                x += target
    if x != width:
        raise RuntimeError("F1 %s 排完宽度 %d != %d" % (text, x, width))
    ncell = (width + 11) // 12
    rows = [[0] * (ncell * 12) for _ in range(16)]
    for i, im in enumerate(pieces):
        px = im.load()
        x0 = char_info[i][4]
        for y in range(16):
            for xx in range(im.width):
                if px[xx, y] > 128:
                    rows[y][x0 + xx] = 1
    cells = []
    for c in range(ncell):
        seg = [[0] * 16 for _ in range(16)]
        for y in range(16):
            for xx in range(12):
                seg[y][xx] = rows[y][c * 12 + xx]
        cells.append(seg)
    return cells, width, char_info


def _f1_render_gp01(font, ascii_font_path, width=96, gap=1, left=2):
    """GP01 前缀按黑边裁切；G 左侧留 left，GP01 在中文前的 24px 区均匀分配。

    gap 是字母间基础间距；剩余像素补给「1」与「全」之间。
    """
    from PIL import Image
    prefix = "GP01"
    body = "全方位推进型"
    pieces = []
    char_info = []
    tight = []
    for ch in prefix:
        cell, _ = _f1_ascii_prefix(ch, ascii_font_path)
        bb = cell.getbbox()
        if not bb:
            raise RuntimeError("GP01 前缀空字模: %s" % ch)
        tight.append(cell.crop((bb[0], 0, bb[2], 16)))
    prefix_area = width - 12 * len(body)
    ink = sum(im.width for im in tight)
    gaps_total = prefix_area - left - ink
    if gaps_total < 0 or prefix_area < 0:
        raise RuntimeError("GP01 + 全方位推进型 超出 %dpx" % width)
    # 三个字母间基础 gap；其余全部给「1」与「全」之间
    inner = max(0, gap) * (len(tight) - 1)
    if inner > gaps_total:
        inner = gaps_total
        gap = max(1, inner // (len(tight) - 1))
        inner = gap * (len(tight) - 1)
    x = left
    for i, im in enumerate(tight):
        pieces.append(im)
        char_info.append((prefix[i], im.width, im.width, 0, x))
        x += im.width
        if i + 1 < len(tight):
            x += gap
    if x > prefix_area:
        raise RuntimeError("GP01 前缀分配超宽 %d > %d" % (x, prefix_area))
    x = prefix_area  # 「1」与「全」之间用掉全部剩余空白
    for ch in body:
        im, natural = _f1_glyph(ch, font)
        im = _f1_fit(im, natural, 12)
        pieces.append(im)
        char_info.append((ch, 12, natural, 12 - natural, x))
        x += 12
    if x > width:
        raise RuntimeError("GP01 F1 排完宽度 %d > %d" % (x, width))
    ncell = (width + 11) // 12
    rows = [[0] * (ncell * 12) for _ in range(16)]
    for i, im in enumerate(pieces):
        px = im.load()
        x0 = char_info[i][4]
        for y in range(16):
            for xx in range(im.width):
                if px[xx, y] > 128:
                    rows[y][x0 + xx] = 1
    cells = []
    for c in range(ncell):
        seg = [[0] * 16 for _ in range(16)]
        for y in range(16):
            for xx in range(12):
                seg[y][xx] = rows[y][c * 12 + xx]
        cells.append(seg)
    return cells, width, char_info


def _f1_pack_seg(seg):
    top = bytearray()
    for y in range(8):
        v = 0
        for x in range(8):
            v = (v << 1) | seg[y][x]
        top.append(v)
    for y in range(8):
        v = 0
        for x in range(8, 16):
            v = (v << 1) | seg[y][x]
        top.append(v)
    bot = bytearray()
    for y in range(8, 16):
        v = 0
        for x in range(8):
            v = (v << 1) | seg[y][x]
        bot.append(v)
    for y in range(8, 16):
        v = 0
        for x in range(8, 16):
            v = (v << 1) | seg[y][x]
        bot.append(v)
    return bytes(top), bytes(bot)


def _f1_temp_book(src, game, dst):
    """生成临时工作簿，供编译模块导入文本/名称。

    只把旧的短 F1 名字（武器、爱称等）替换成 {F1:xx}，让名称重排直接写宏；
    9 字以上角色/机体名故意保留原文，既要保留原字模，也避免全局码位漂移，
    构建结束后再由 apply_long_name_macros 改名称指针。
    """
    import openpyxl
    _load_f1_sheet(src, game)
    ids = {text: mid for mid, text in F1_NAMES[game]}
    plain = {text for mid, text in F1_NAMES[game] if mid in LONG_NAME_IDS}
    wb = openpyxl.load_workbook(src)
    seen = set()
    for sn in wb.sheetnames:
        ws = wb[sn]
        hdr = [c.value for c in ws[1]]
        if "jp" not in hdr or "zh" not in hdr:
            continue
        zi = hdr.index("zh")
        for row in ws.iter_rows(min_row=2):
            zh = row[zi].value
            if not isinstance(zh, str):
                continue
            t = zh.strip()
            # 长角色/机体名：保留原字模，构建结束后只改名称指针。
            if t in plain:
                seen.add(t)
                continue
            if t in ("男主人公机2(饭)", "女主人公机2(饭)") and "主人公机" in plain:
                seen.add("主人公机")
                continue
            # 名称池没有空格字模；用 0xDF 空白单字节分隔 GP02A 与中文名。
            if t == "GP02A 酸浆果":
                row[zi].value = "GP02A{B:DF}酸浆果"
                seen.add(t)
                continue
            if t in ids:
                # 爱称专用的窄宏不能套到同名角色行，否则角色名会被缩成 48px。
                if t in F1_NICK_ONLY and sn != "名称_爱称":
                    continue
                row[zi].value = "{F1:%02X}" % ids[t]
                seen.add(t)
                continue
            # 机体名「美加诺伊德·XX」：前缀条带 + 3 字后缀，总宽 96px
            if t.startswith("美加诺伊德·"):
                row[zi].value = "{F1:%02X}" % ids["美加诺伊德·"] + t[len("美加诺伊德·"):]
                seen.add("美加诺伊德·")
                continue
            # 机体全名「美加诺伊德V」：前缀用爱称条带，保留 V
            if t.startswith("美加诺伊德") and t[len("美加诺伊德"):] in ("V", "Ⅴ"):
                row[zi].value = "{F1:%02X}" % ids["美加诺伊德"] + t[len("美加诺伊德"):]
                seen.add("美加诺伊德")
                continue
    # 旧宏（F0–FA）已经以 {F1:xx} 令牌写在名称表里，不需要在本工作簿中查找中文原名；
    # 对应字模/表项由 apply_f1_weapon_names 按 F1宏 页重建。
    legacy_ids = set(range(0xF0, 0xFB))
    missing = {t for t in (set(ids) - seen) if ids[t] not in legacy_ids}
    if missing:
        raise RuntimeError("F1 长名未在表格中找到：%s" % "、".join(sorted(missing)))
    wb.save(dst)
    return len(seen)


def apply_f1_weapon_names(rom, game, bdir, used):
    from PIL import ImageFont
    cfg = _f1_cfg(bdir)
    chunks = _f1_chunks(cfg)
    names = F1_NAMES[game]
    font_path = Path(bdir) / "assets" / "fonts" / "wenquanyi_9pt.ttf"
    font = ImageFont.truetype(str(font_path), 12)
    mzpx_path = Path(bdir) / "assets" / "fonts" / "MZPXorig_8x12.ttf"
    mzpx_font = ImageFont.truetype(str(mzpx_path), 12) if mzpx_path.exists() else None

    rendered = []
    for mid, text in names:
        cfg = F1_CFG.get(game, {}).get(text)
        width = cfg["width"] if cfg else F1_WIDTHS.get(text, F1_MAX_W)
        fnt = font
        raw = (cfg or {}).get("raw", {}) or {}
        if str(raw.get("字体", "")).strip().lower() in ("mzpxorig12", "mzpxorig", "mzpx"):
            if mzpx_font is None:
                raise RuntimeError("F1 %s 需要 MZPXorig_8x12.ttf" % text)
            fnt = mzpx_font
        cells, width, char_info = _f1_render_strip(
            text, fnt, Path(bdir) / "assets" / "fonts" / "zpix.ttf",
            width=width, cfg=cfg)
        rendered.append((mid, text, cells, width, char_info))
    # 新规则：F1 汉字最小 9px。中点和 ASCII 标点允许自然窄宽；
    # 任何汉字低于 9px 都说明该名字在当前槽宽里塞不下，构建直接失败并列出。
    too_small = {}
    # 旧宏 F4「精神感应型光束军刀」要压到与日版相同的 84px（10 字，约 8px/字），
    # 这是用户要求的等长例外；其余仍执行最小 9px。
    f1_min9_exempt = {"双重光束三叉戟","超绝米加粒子炮","精神感应型光束军刀","米加火箭筒发射器","暗黑大将军"}
    for _, text, _, width, char_info in rendered:
        for ch, target, _natural, _delta, _x in char_info:
            if ord(ch) >= 128 and ch != "·" and target < 9 and text not in f1_min9_exempt:
                too_small.setdefault((text, width), []).append((ch, target))
    if too_small:
        lines = []
        for (text, width), items in too_small.items():
            worst = min(t for _, t in items)
            lines.append("%s（%dpx 槽，最低 %dpx：%s）" %
                         (text, width, worst, "、".join(ch for ch, _ in items)))
        raise RuntimeError("F1 最小 9px 无法满足：\n" + "\n".join(lines))
    need = sum(len(cells) for _, _, cells, _, _ in rendered)
    codes = _f1_free_codes(rom, chunks, used, need)

    if any(b != 0xFF for b in rom[F1_TABLE_ADDR:F1_EMPTY_ADDR + 1]):
        raise RuntimeError("F1 table/body region 0x%06X is not free" % F1_TABLE_ADDR)
    if any(b != 0xFF for b in rom[F1_BODY_ADDR:F1_BODY_ADDR + 0x300]):
        raise RuntimeError("F1 body arena 0x%06X is not free" % F1_BODY_ADDR)

    body_addr = F1_BODY_ADDR
    body_offs = {}
    detail = []
    for mid, text, cells, width, char_info in rendered:
        if len(cells) > 8:
            raise RuntimeError("F1 %s needs %d cells (>8)" % (text, len(cells)))
        name_codes = [codes.pop(0) for _ in cells]
        for code, seg in zip(name_codes, cells):
            a = _f1_slot_addr(code, chunks)
            top, bot = _f1_pack_seg(seg)
            rom[a:a + 16] = top
            rom[a + 0x80:a + 0x90] = bot
        body = b"".join(c.to_bytes(2, "big") for c in name_codes) + b"\xff"
        if body_addr + len(body) >= 0x3FFF00:
            raise RuntimeError("F1 body arena overflow")
        rom[body_addr:body_addr + len(body)] = body
        body_offs[mid] = body_addr - 0x3F0000
        sizes = " ".join("%s12px/宽%d(自然%d,%+d)" % (ch, t, n, d)
                         for ch, t, n, d, x in char_info)
        detail.append((f"F1{mid:02X}", text, width, len(cells), sizes, char_info))
        body_addr += len(body)

    # 表项 0x00–0x1F 给新宏 D0–EF，0x20–0x2F 保留原 F1F0–F1FF。
    legacy_base = F1_HANDLER[game]["legacy"]
    legacy = [struct.unpack_from("<H", rom, 0x3F0000 + legacy_base + 2 * k)[0]
              for k in range(16)]
    table = [F1_EMPTY_ADDR - 0x3F0000] * F1_TABLE_N
    table[32:48] = legacy
    for mid, off in body_offs.items():
        table[mid - F1_ID_BASE] = off
    for i, v in enumerate(table):
        struct.pack_into("<H", rom, F1_TABLE_ADDR + 2 * i, v)

    h = F1_HANDLER[game]
    sub = h["sub"]
    if bytes(rom[sub:sub + 3]) != b"\x2d\xf0\x00":
        raise RuntimeError("F1 handler sub site mismatch at 0x%06X" % sub)
    rom[sub:sub + 3] = b"\x2d\xd0\x00"
    add = sub + 5
    if rom[add] != 0x05 or bytes(rom[add + 1:add + 3]) != h["legacy"].to_bytes(2, "little"):
        raise RuntimeError("F1 handler add site mismatch at 0x%06X" % add)
    rom[add + 1:add + 3] = b"\x00\xff"
    if rom[h["f1loop"] + 1] != 0xE0:
        rom[h["f1loop"] + 1] = 0xE0

    return {"names": detail, "slots": need, "table": "0x%06X" % F1_TABLE_ADDR}


# 「奥克斯坦发射器B/E」：完整武器名 7 汉字 + 1 个半角字母，原名 92px，
# 武器列表槽 84px，超出 8px。改成 7 个 F1 字模（76px）+ 8px 半角字母。
WEAPON_FULL_F1 = {
    "D2": [
        (bytes.fromhex("e2 29 e0 b8 e3 f7 e1 ed e1 44 e2 75 e1 ce 84"),
         "奥克斯坦发射器", "B"),
        (bytes.fromhex("e2 29 e0 b8 e3 f7 e1 ed e1 44 e2 75 e1 ce 87"),
         "奥克斯坦发射器", "E"),
    ],
    "D3": [
        (bytes.fromhex("e2 44 e0 c4 e4 1e e2 09 e1 5c e2 9a e1 e2 84"),
         "奥克斯坦发射器", "B"),
        (bytes.fromhex("e2 44 e0 c4 e4 1e e2 09 e1 5c e2 9a e1 e2 87"),
         "奥克斯坦发射器", "E"),
    ],
}
WEAPON_FULL_F1_IDS = [0xD1, 0xD2]
WEAPON_FULL_F1_WIDTH = 84


def _f1_all_used_codes(rom, cmap_codes):
    used = set(cmap_codes)
    for i in range(F1_TABLE_N):
        off = struct.unpack_from("<H", rom, F1_TABLE_ADDR + 2 * i)[0]
        if not (F1_BODY_ADDR - 0x3F0000 <= off < F1_EMPTY_ADDR - 0x3F0000):
            continue
        p = 0x3F0000 + off
        while p + 1 < len(rom) and rom[p] != 0xFF:
            used.add((rom[p] << 8) | rom[p + 1])
            p += 2
    return used


def apply_weapon_fullname_f1(rom, game, bdir, cmap_codes):
    if game not in WEAPON_FULL_F1:
        return None
    import struct as _struct
    from PIL import Image, ImageFont

    cfg = _f1_cfg(bdir)
    chunks = _f1_chunks(cfg)
    font = ImageFont.truetype(str(Path(bdir) / "assets" / "fonts" / "wenquanyi_9pt.ttf"), 12)
    zpix = Path(bdir) / "assets" / "fonts" / "zpix.ttf"

    table = [_struct.unpack_from("<H", rom, F1_TABLE_ADDR + 2 * i)[0]
             for i in range(F1_TABLE_N)]
    empty_off = F1_EMPTY_ADDR - 0x3F0000
    for mid in WEAPON_FULL_F1_IDS:
        if table[mid - F1_ID_BASE] < empty_off - 0x100:
            raise RuntimeError("F1 macro %02X already used" % mid)

    used = _f1_all_used_codes(rom, cmap_codes)
    items = WEAPON_FULL_F1[game]
    codes = _f1_free_codes(bytes(rom), chunks, used, 7 * len(items))

    body = 0x3FFF60
    if rom[body:body + 3 * (7 * 2 + 1)] != b"\xff" * (3 * (7 * 2 + 1)):
        raise RuntimeError("weapon fullname F1 body area not free")

    result = []
    for (old, text, suffix), mid in zip(items, WEAPON_FULL_F1_IDS):
        targets = _f1_targets(len(text), WEAPON_FULL_F1_WIDTH - 8)
        rows = [[0] * WEAPON_FULL_F1_WIDTH for _ in range(16)]
        x = 0
        for ch, target in zip(text, targets):
            im, natural = _f1_glyph(ch, font)
            im = _f1_fit(im, natural, target)
            px = im.load()
            for y in range(16):
                for xx in range(im.width):
                    if px[xx, y] > 128:
                        rows[y][x + xx] = 1
            x += target
        sim, sn = _f1_ascii_prefix(suffix, zpix)
        px = sim.load()
        for y in range(16):
            for xx in range(sim.width):
                if px[xx, y] > 128:
                    rows[y][x + xx] = 1
        x += sn
        if x != WEAPON_FULL_F1_WIDTH:
            raise RuntimeError("weapon fullname width %d != %d" % (x, WEAPON_FULL_F1_WIDTH))

        cells = []
        for c in range(7):
            seg = [[0] * 16 for _ in range(16)]
            for y in range(16):
                for xx in range(12):
                    seg[y][xx] = rows[y][c * 12 + xx]
            cells.append(seg)
        ncs = [codes.pop(0) for _ in cells]
        for code, seg in zip(ncs, cells):
            a = _f1_slot_addr(code, chunks)
            top, bot = _f1_pack_seg(seg)
            rom[a:a + 16] = top
            rom[a + 0x80:a + 0x90] = bot
        bb = b"".join(c.to_bytes(2, "big") for c in ncs) + b"\xff"
        if body + len(bb) >= F1_EMPTY_ADDR:
            raise RuntimeError("weapon fullname F1 body area overflow")
        rom[body:body + len(bb)] = bb
        _struct.pack_into("<H", rom, F1_TABLE_ADDR + 2 * (mid - F1_ID_BASE),
                          body - 0x3F0000)
        i = 0x350000
        hit = 0
        while True:
            j = rom.find(old, i, 0x360000)
            if j < 0:
                break
            rom[j:j + 3] = bytes([0xF1, mid, 0xFF])
            hit += 1
            i = j + 3
        if not hit:
            raise RuntimeError("weapon fullname not found: %s" % game)
        result.append((hex(mid), hit, text + suffix))
        body += len(bb)
    return result


# 清除数据/继承界面的「クリア」统一译「通关」。旧版曾担心关卡选择的
# 已通关行放两字会叠行，单独改用「通」；D1/D2 实机复测（带通关记录的存档）
# 显示「通关」完全正常，没有叠字/乱码，因此菜单表和关卡选择代码统一用
# 「通关」；旧「通」短串仅保留分配位置、不再引用。
CLEAR_LABEL = {
    "D1": dict(old=0xBA72, table=(0x36E478, 0x36E487, 0x36E496, 0x36E4A5, 0x36E8E3),
               code=(0x3D3F21, 0x3DB449), alloc=0xFEE0),
    "D2": dict(old=0xBCB3, table=(0x36E478, 0x36E487, 0x36E496, 0x36E4A5, 0x36E8E3),
               code=(0x3DB583,), alloc=0xFEE0),
    "D3": dict(old=0xBDD5, table=(0x36E478, 0x36E487, 0x36E496, 0x36E4A5, 0x36E8E3),
               code=(0x3DB450,), alloc=0xFEE0),
}


GP_MECHA_F1 = [
    ("GP01全方位推进型", 0xD3),
]
GP_MECHA_PLAIN = [
    ("GP-03S雄蕊", "GP03雄蕊"),
    ("GPー03典罗比乌姆", "GP03石斛兰"),
    ("GPー02A赛撒里斯", "GP02A 酸浆果"),
]
GP_MECHA_F1_WIDTH = 96


def apply_gp_mecha_f1(rom, game, bdir, cmap):
    import struct as _struct
    from PIL import ImageFont

    cfg = _f1_cfg(bdir)
    chunks = _f1_chunks(cfg)
    font = ImageFont.truetype(str(Path(bdir) / "assets" / "fonts" / "wenquanyi_9pt.ttf"), 12)
    zpix = Path(bdir) / "assets" / "fonts" / "zpix.ttf"
    table = [_struct.unpack_from("<H", rom, F1_TABLE_ADDR + 2 * i)[0]
             for i in range(F1_TABLE_N)]
    empty_off = F1_EMPTY_ADDR - 0x3F0000
    for _, mid in GP_MECHA_F1:
        if table[mid - F1_ID_BASE] < empty_off - 0x100:
            raise RuntimeError("F1 macro %02X already used" % mid)
    used = _f1_all_used_codes(rom, set(cmap.values()) if isinstance(cmap, dict) else cmap)
    codes = _f1_free_codes(bytes(rom), chunks, used, (GP_MECHA_F1_WIDTH // 12) * len(GP_MECHA_F1))
    body = 0x3FFF7E
    out = []
    gp_cfg = next((c for c in F1_SPECIAL.get(game, {}).get("GP01", [])), None)
    gp_width = gp_cfg["width"] if gp_cfg else GP_MECHA_F1_WIDTH
    gp_gap = gp_cfg["gap"] if gp_cfg else 1
    try:
        gp_left = int((gp_cfg["raw"] if gp_cfg else {}).get("右移") or 2)
    except (TypeError, ValueError):
        gp_left = 2
    for text, mid in GP_MECHA_F1:
        if text == "GP01全方位推进型":
            cells, width, gpinfo = _f1_render_gp01(font, zpix, width=gp_width, gap=gp_gap, left=gp_left)
        else:
            cells, width, gpinfo = _f1_render_strip(text, font, zpix, width=gp_width)
        if len(cells) != gp_width // 12:
            raise RuntimeError("GP mecha F1 cells %d != %d: %s" %
                               (len(cells), gp_width // 12, text))
        ncs = [codes.pop(0) for _ in cells]
        for code, seg in zip(ncs, cells):
            a = _f1_slot_addr(code, chunks)
            top, bot = _f1_pack_seg(seg)
            rom[a:a + 16] = top
            rom[a + 0x80:a + 0x90] = bot
        bb = b"".join(c.to_bytes(2, "big") for c in ncs) + bytes([0xFF])
        if body + len(bb) >= F1_EMPTY_ADDR:
            raise RuntimeError("GP mecha F1 body overflow")
        rom[body:body + len(bb)] = bb
        _struct.pack_into("<H", rom, F1_TABLE_ADDR + 2 * (mid - F1_ID_BASE),
                          body - 0x3F0000)
        out.append((hex(mid), text, width, gpinfo))
        body += len(bb)

    return out


def apply_stage_location_fix(rom, game, bdir, cmap):
    """关卡地点里放不进原槽的中文名，重定位到 bank35 并改关卡选择表。

    关卡选择表在 bank3F 0x2E81 起，小端 u16 指向 bank35；
    UI 导入遇到超长串会留下错误指针，这里按原始表项精确修正。
    """
    if game == "D1":
        return None
    fixes = {
        "D2": {0xBE88: "「所罗门」"},
        "D3": {0xBF67: "「穆特隆遗迹」", 0xC057: "「红色宇宙」",
               0xC06C: "「阿克西斯」"},
    }.get(game, {})
    if not fixes:
        return None
    mod = bti.load_ws2lib(bdir)
    orig = (Path(bdir) / "assets" / "original.ws").read_bytes()
    if game == "D2":
        # D2 表 0x3F2E81 起为小端，槽位落在奇地址。
        tab_lo, tab_hi, endian = 0x3F2E81, 0x3F2F00, "little"
    else:
        # D3 表 0x3F2EA0 起为大端，槽位落在偶地址；不能套用 D2 的
        # 小端/奇地址搜索，否则会跨条目写入，把相邻两个地点指针写坏。
        tab_lo, tab_hi, endian = 0x3F2EA0, 0x3F2F00, "big"
    out = []
    for old_off, zh in fixes.items():
        enc, miss = mod.encode(zh, cmap)
        if miss:
            raise RuntimeError("关卡地点编码缺字: %s %s" % (zh, "".join(sorted(miss))))
        new_off = _alloc_bank35(rom, enc + bytes([0xFF]))
        p = old_off.to_bytes(2, endian)
        sites = [q for q in range(tab_lo, tab_hi, 2)
                 if orig[q:q + 2] == p]
        if not sites:
            # 「赤い宇宙」等只用于说明、不在关卡选择表里的条目，跳过。
            continue
        for q in sites:
            rom[q:q + 2] = new_off.to_bytes(2, endian)
        out.append((hex(old_off), hex(new_off), len(sites), zh))
    return out


def apply_clear_label(rom, game, bdir, cmap):
    cfg = CLEAR_LABEL[game]
    mod = bti.load_ws2lib(bdir)
    enc, missing = mod.encode("通关", cmap)
    if missing or len(enc) != 4:
        raise RuntimeError("clear label encode failed: %s" % missing)
    # 不再用固定槽，改为前后都留 FF 的独立分配
    off = _alloc_bank35(rom, enc + bytes([0xFF]))
    # 旧版曾为关卡选择单独分配「通」；D1/D2 复测两字「通关」在该行
    # 不会叠字/乱码，故代码指针也统一用「通关」。短串仍分配以保持
    # bank35 其余分配位置不变，但不再被引用。
    enc1, miss1 = mod.encode("通", cmap)
    if miss1 or len(enc1) != 2:
        raise RuntimeError("clear label short encode failed: %s" % miss1)
    short = _alloc_bank35(rom, enc1 + bytes([0xFF]))
    old = cfg["old"].to_bytes(2, "little")
    new = off.to_bytes(2, "little")
    hit = 0
    for a in cfg["table"]:
        if rom[a:a + 2] == old:
            rom[a:a + 2] = new
            hit += 1
        elif rom[a:a + 2] != new:
            raise RuntimeError("clear label pointer mismatch at 0x%06X" % a)
    short_b = short.to_bytes(2, "little")
    for a in cfg["code"]:
        if rom[a:a + 2] in (old, short_b):
            rom[a:a + 2] = new
            hit += 1
        elif rom[a:a + 2] != new:
            raise RuntimeError("clear label code pointer mismatch at 0x%06X" % a)
    return {"off": hex(off), "short": hex(short), "hits": hit}


# 关卡选择左列最后一行的 ラスト 原槽只有 3 字节，中文「最后」需要 4 字节+FF，
# 必须重定位。bank0x3D 里用 `mov ax,<偏移>` 立即数选标签，按旧偏移反查唯一指令。
STAGE_LAST_LABEL = {
    "D1": 0xBA6E,
    "D2": 0xBCAF,
    "D3": 0xBDD1,
}


def apply_stage_last_label(rom, game, bdir, cmap):
    """把关卡选择最后一行显示为「最后」（对齐 WSC3）。"""
    mod = bti.load_ws2lib(bdir)
    old_off = STAGE_LAST_LABEL[game]
    pat = b"\xB8" + old_off.to_bytes(2, "little")
    hits = []
    pos = 0x3D0000
    while True:
        i = rom.find(pat, pos, 0x3E0000)
        if i < 0:
            break
        hits.append(i)
        pos = i + 1
    if len(hits) != 1:
        raise RuntimeError(
            "关卡选择最后一行立即数定位失败: %s %s"
            % (game, [hex(x) for x in hits]))
    enc, miss = mod.encode("最后", cmap)
    if miss or len(enc) != 4:
        raise RuntimeError("关卡选择最后一行编码失败: %s" % "".join(sorted(miss)))
    new_off = _alloc_bank35(rom, enc + bytes([0xFF]))
    site = hits[0] + 1
    rom[site:site + 2] = new_off.to_bytes(2, "little")
    return {"old": hex(old_off), "new": hex(new_off), "site": hex(site)}


BQ_TABLE = 0x395881
BQ_BANK_BASE = 0x390000
BQ_FREE = 0x397000
BQ_END = 0x3A0000
BQ_COUNT = 266


def apply_battle_quotes_other(rom, game, bdir, cmap):
    """D2/D3 攻击台词：D1 的同文译文优先，武器宏改成中文全名。

    D3 有 266 项台词表（0x398528）；D2 的台词由事件脚本直接按旧偏移引用。
    译文统一放 bank39 空闲尾部，表项和脚本里的 E6 <ptr> 一起改指新串。
    """
    if game == "D1":
        return None
    import struct as _struct
    tsv = {}
    d1dir = bti.BUILD / "Dai1"
    p = d1dir / "assets" / "battle_quotes_zh.tsv"
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            jp, zh = line.split("\t")
            tsv[jp] = zh
    mod = bti.load_ws2lib(bdir)

    manual = {
        "ドー「いっけーっ!!」": "多「上啊!!」",
        "ジュドー「一気にいくぜっ!/{F1:F5}!」": "捷多「一口气上吧!/超绝米加火箭炮!」",
        "シーブック「うおおおっ!!!/{F1:F5}!!」": "西布克「哦哦哦!!!/{F1:F5}!!」",
        "ブライト「{F1:F3}、/発射!!」": "布莱特「{F1:F3}、/发射!!」",
        "シーマ「フフフ‥おしまいだねぇ‥!」": "西玛「呵呵……结束了呢……！」",
        "???「‥‥‥‥」": "？？？「…………」",
        "ルー「まとめていくわよ!/{F1:F5}!!」": "露「一起收拾掉!/{F1:F5}!!」",
    }

    def translate(jp):
        if jp in tsv:
            return tsv[jp]
        # 原版 D2/D3 个别台词与 D1 有错字（良しき/悪しき），按同义句复用译文。
        norm = jp.replace("良しき", "悪しき")
        if norm in tsv:
            return tsv[norm]
        # F1:F5 / F1:F3 现在直接走 F1 宏显示（中文由 F1宏 页重建），
        # 不能再回退到「ハイパーメガバズーカ」等字面武器名，否则会绕过宏。
        if "{F1:F5}" not in jp and "{F1:F3}" not in jp:
            for macro, weapon in (("{F1:F5}", "ハイパーメガバズーカ"),
                                  ("{F1:F3}", "ハイパーメガ粒子砲")):
                if macro in jp:
                    cand = jp.replace(macro, weapon)
                    if cand in tsv:
                        return tsv[cand]
                    zh = tsv.get(cand)
                    if zh:
                        return zh
        if jp in manual:
            return manual[jp]
        return None

    if game == "D2":
        scan = (0x395780, 0x396000)
        tab = 0x394A1B
        arena = 0x397000
        count = 266
    else:
        scan = (0, 0)
        # D3 主表从 0x398528 起 264 条；0x398520-0x398527 是 4 条特殊
        # 台词的前置表，不能当主表项改，否则战斗事件脚本会跑飞。
        tab = 0x398528
        arena = 0x39A000
        count = 264
    base = 0x390000
    old_offs = []
    if tab is not None:
        for i in range(count):
            v = _struct.unpack_from("<H", rom, tab + 2 * i)[0]
            if 0x4000 <= v < 0xF000 and v not in old_offs:
                if mod.read_string(rom, base + v, 4)[0]:
                    old_offs.append(v)
    i = scan[0]
    while i < scan[1]:
        if rom[i] == 0xFF:
            i += 1
            continue
        j = rom.find(b"\xff", i, scan[1])
        if j < 0:
            break
        s, _, bad, kc, ctrl = mod.read_string(rom, i, j - i + 1)
        if kc >= 1 and bad == 0 and ctrl <= 2 and len(s) >= 2:
            off = (i - base) & 0xFFFF
            if off not in old_offs:
                old_offs.append(off)
        i = j + 1

    missing = []
    trans = {}
    for off in old_offs:
        jp = mod.read_string(rom, base + off, 400)[0]
        zh = translate(jp)
        if zh is None:
            missing.append((off, jp))
        else:
            trans[off] = zh
    if missing:
        raise RuntimeError("D2/D3 攻击台词未译: %s" %
                           "；".join("%04X=%s" % (o, s) for o, s in missing[:20]))

    cmap2 = dict(cmap)
    used = set(cmap2.values())
    need = set()
    for zh in trans.values():
        _, miss = mod.encode(zh, cmap2)
        need.update(miss)
    # D3 主表前的 4 条特殊战斗台词不在主表里，但被战斗脚本按原偏移直接
    # 引用；只做原位翻译，绝不改 0x398520-0x398527 的前置表结构。
    special = []
    if game == "D3":
        special = [
            (0x8738, "叶月「冈道尔炮、对准!」"),
            (0x8750, "忍「以爱之心斩断邪恶空间!/其名，断空光牙剑!!」"),
            (0x877E, "罗米娜「光子炮、射!」"),
            (0x8792, "爱娜「开火!」"),
        ]
        for off, zh in special:
            if off in old_offs:
                raise RuntimeError("特殊台词与主表重叠: %04X" % off)
            _, miss = mod.encode(zh, cmap2)
            need.update(miss)
    cfg = mod.load_cfg()
    chunks = mod.chunks(cfg)

    def slot_addr(code):
        n = code - 0xE000
        ci, loc = n >> 10, n & 0x3FF
        if ci >= len(chunks):
            raise RuntimeError("攻击台词字库溢出")
        bank, bbase = chunks[ci]
        di = bbase + (loc >> 3) * 0x100 + (loc & 7) * 0x10
        return bank * 0x10000 + di

    code = 0xE000
    for ch in sorted(need):
        while code <= 0xEFFF:
            if code in used or (code & 0xFF) in (0xFD, 0xFE, 0xFF):
                code += 1
                continue
            addr = slot_addr(code)
            if (all(b == 0xFF for b in rom[addr:addr + 16]) and
                    all(b == 0xFF for b in rom[addr + 0x80:addr + 0x90])):
                break
            code += 1
        else:
            raise RuntimeError("攻击台词字库溢出")
        g = mod.pack_glyph(ch)
        rom[addr:addr + 16] = g[:16]
        rom[addr + 0x80:addr + 0x90] = g[16:]
        cmap2[ch] = code
        used.add(code)
        code += 1

    special_hits = 0
    for off, zh in special:
        enc, miss = mod.encode(zh, cmap2)
        if miss:
            raise RuntimeError("特殊台词编码缺字: %s" % "".join(sorted(miss)))
        p = base + off
        end = rom.find(b"\xFF", p)
        if end < 0:
            raise RuntimeError("特殊台词无终止符: %04X" % off)
        if len(enc) + 1 > end - p + 1:
            raise RuntimeError("特殊台词放不下: %04X %d/%d" % (off, len(enc) + 1, end - p + 1))
        rom[p:p + len(enc)] = enc
        rom[p + len(enc)] = 0xFF
        special_hits += 1

    cur = arena
    old_to_new = {}
    for off in old_offs:
        enc, miss = mod.encode(trans[off], cmap2, newline_blank=True)
        if miss:
            raise RuntimeError("攻击台词编码缺字: %s" % "".join(sorted(miss)))
        if cur + len(enc) + 1 > base + 0x10000:
            raise RuntimeError("攻击台词 bank39 溢出")
        rom[cur:cur + len(enc)] = enc
        rom[cur + len(enc)] = 0xFF
        old_to_new[off] = cur - base
        cur += len(enc) + 1
    # 表项改指新译文
    table_hits = 0
    if tab is not None:
        for i in range(count):
            q = tab + 2 * i
            v = _struct.unpack_from("<H", rom, q)[0]
            if v in old_to_new:
                _struct.pack_into("<H", rom, q, old_to_new[v])
                table_hits += 1
    # 原串能原位放下的也覆盖，兼顾未识别的旧引用
    inplace = 0
    for off in old_offs:
        start = base + off
        end = start
        while end < 0x3A0000 and rom[end] != 0xFF:
            end += 1
        enc, _ = mod.encode(trans[off], cmap2, newline_blank=True)
        if len(enc) + 1 <= end - start + 1:
            rom[start:start + len(enc)] = enc
            rom[start + len(enc)] = 0xFF
            inplace += 1
    # 事件脚本里的 E6 <ptr>
    _ranges = _story_string_ranges(rom)
    refs = 0
    for off, rel in ({} if os.environ.get("SKIP_BQ_REFS") == "1" else old_to_new).items():
        pat = off.to_bytes(2, "little")
        s = 0
        while True:
            k = rom.find(pat, s)
            if k < 0:
                break
            if game in ("D2", "D3"):
                # D3 的 3A 命中全是裸数据；D2 的 4 处旧目标也是空串/数据指针。
                # 旧引用重写对 D2/D3 全部跳过，只保留表/串翻译。
                ok = False
            else:
                ok = (k > 0 and rom[k - 1] == 0xE6 and
                      not (0x390000 <= k < 0x3A0000) and
                      not _in_story_string(k, _ranges) and
                      (k >> 16) not in STORY_TEXT_BANKS[game])
            if ok:
                rom[k:k + 2] = rel.to_bytes(2, "little")
                refs += 1
            s = k + 1
    return {"strings": len(old_offs), "table": table_hits,
            "refs": refs, "inplace": inplace, "special": special_hits,
            "bytes": cur - arena}


# 攻击台词 E6 引用扫描必须避开剧情文本/空闲块：剧情里 E6 xx 只是普通
# 汉字/控制字节，扫描器会把汉字码误当旧偏移改写（静 E899 被写成 4B B4）。
STORY_TEXT_BANKS = {
    "D1": {0x04, 0x05, 0x06, 0x07, 0x0F, 0x13, 0x14, 0x15, 0x16, 0x17, 0x1A, 0x21, 0x25, 0x27, 0x35, 0x39, 0x3B, 0x3C},
    "D2": {0x04, 0x05, 0x06, 0x07, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x1A, 0x21, 0x22, 0x25, 0x27, 0x35, 0x39, 0x3B, 0x3C},
    "D3": {0x04, 0x05, 0x06, 0x07, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x1A, 0x21, 0x22, 0x25, 0x27, 0x35, 0x39, 0x3B, 0x3C},
}

import bisect

def _story_string_ranges(rom):
    """返回最终 ROM 中所有剧情串的 [start,end) 区间，供 E6 误报过滤。"""
    ranges = []
    for tab in (0x3FE900, 0x3FE980):
        i = tab
        while i + 10 <= len(rom):
            a, b, mb, _z, toff, tbase = struct.unpack_from("<HHBBHH", rom, i)
            if a == 0xFFFF:
                break
            bank = mb & 0x3F
            b = min(b, 0x10000)
            for gi in range(a, b):
                p = bank * 0x10000 + toff + (gi - a + tbase) * 2
                if p + 2 > len(rom):
                    continue
                off = struct.unpack_from("<H", rom, p)[0]
                if off == 0 or off == 0xFFFF:
                    continue
                start = bank * 0x10000 + off
                end = rom.find(b"\xFF", start, min(start + 2000, bank * 0x10000 + 0x10000))
                if end >= start:
                    ranges.append((start, end + 1))
            i += 10
    ranges.sort()
    merged = []
    for s, e in ranges:
        if merged and s <= merged[-1][1]:
            if e > merged[-1][1]:
                merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    return merged

def _in_story_string(pos, ranges):
    i = bisect.bisect_right(ranges, (pos, 1 << 30)) - 1
    return i >= 0 and ranges[i][0] <= pos < ranges[i][1]

QUOTE_REF_FIX = {
    "D1": (0x395881, 0x69cf),
    "D2": (0x394A1B, 0x5b3c),
    "D3": (0x398528, 0x9643),
}
QUOTE_TABLE_COUNTS = {"D1": 266, "D2": 266, "D3": 264}


def apply_quote_ref_fix(rom, game, bdir):
    """旧实现把台词旧偏移做全局 16 位替换，已停用。

    该值会误命中 bank25/26 的事件脚本/文本字节（D1 0x254208 被改成
    新台词偏移后，战斗结束脚本跳飞、栈溢出白屏）。需要恢复台词引用时，
    必须先解析出真正的指针表，不能按字节全局替换。
    """
    return None


def _apply_quote_ref_fix_legacy(rom, game, bdir):
    """布莱特「高能米加粒子炮」这类台词被脚本/表用旧 bank39 偏移引用。

    攻击台词表之外还有多套旧引用（如 D2 bank07 的指针表、D3 bank3A 脚本），
    这里把该句旧偏移的所有 16 位引用统一改到新译文，避免仍显示日文。
    """
    if game not in QUOTE_REF_FIX:
        return None
    tab, old = QUOTE_REF_FIX[game]
    orig = (Path(bdir) / "assets" / "original.ws").read_bytes()
    idx = None
    for i in range(QUOTE_TABLE_COUNTS[game]):
        if int.from_bytes(orig[tab + 2 * i:tab + 2 * i + 2], "little") == old:
            idx = i
            break
    if idx is None:
        return None
    new = int.from_bytes(rom[tab + 2 * idx:tab + 2 * idx + 2], "little")
    if new == old:
        return None
    pat = old.to_bytes(2, "little")
    hit = 0
    s = 0
    while True:
        i = rom.find(pat, s)
        if i < 0:
            break
        # bank35 是名称池/F1 串，bank3F 含名称指针表；16 位值相同纯属巧合，
        # 全局替换会把别的名字指针改成台词偏移（GP02A 曾因此丢失名称）。
        if not (0x390000 <= i < 0x3A0000) and not (0x350000 <= i < 0x360000)                 and not (0x3F0000 <= i < 0x400000):
            rom[i:i + 2] = new.to_bytes(2, "little")
            hit += 1
        s = i + 1
    return {"old": hex(old), "new": hex(new), "refs": hit}


def apply_battle_quotes(rom, game, bdir, cmap):
    if game != "D1":
        return None
    tsv = Path(bdir) / "assets" / "battle_quotes_zh.tsv"
    if not tsv.exists():
        raise RuntimeError("battle quote translation missing: %s" % tsv)
    table = {}
    for ln, line in enumerate(tsv.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 2:
            raise RuntimeError("bad battle quote line %d" % ln)
        jp, zh = parts
        table[jp] = zh

    entries = []
    prev = -1
    for i in range(BQ_COUNT):
        p = BQ_TABLE + 2 * i
        off = int.from_bytes(rom[p:p + 2], "little")
        if off == 0xFFFF or off <= prev or not (0x4000 <= off < 0x10000):
            raise RuntimeError("battle quote table entry %d invalid: %04X" % (i, off))
        jp = read_string(rom, BQ_BANK_BASE + off, 400)[0]
        if jp not in table:
            raise RuntimeError("battle quote missing translation: %r" % jp)
        entries.append((p, off, jp))
        prev = off

    mod = bti.load_ws2lib(bdir)
    cfg = mod.load_cfg()
    chunks = mod.chunks(cfg)
    cmap2 = dict(cmap)
    used = set(cmap2.values())

    missing = set()
    for _, _, jp in entries:
        _, miss = mod.encode(table[jp], cmap2)
        missing.update(miss)

    def slot_addr(code):
        n = code - 0xE000
        ci, loc = n >> 10, n & 0x3FF
        if ci >= len(chunks):
            raise RuntimeError("battle quote font overflow")
        bank, base = chunks[ci]
        di = base + (loc >> 3) * 0x100 + (loc & 7) * 0x10
        return bank * 0x10000 + di

    code = 0xE000
    for ch in sorted(missing):
        while code <= 0xEFFF:
            if code in used or (code & 0xFF) in (0xFD, 0xFE, 0xFF):
                code += 1
                continue
            addr = slot_addr(code)
            if (all(b == 0xFF for b in rom[addr:addr + 16]) and
                    all(b == 0xFF for b in rom[addr + 0x80:addr + 0x90])):
                break
            code += 1
        else:
            raise RuntimeError("battle quote font overflow")
        g = mod.pack_glyph(ch)
        rom[addr:addr + 16] = g[:16]
        rom[addr + 0x80:addr + 0x90] = g[16:]
        cmap2[ch] = code
        used.add(code)
        code += 1

    cur = BQ_FREE
    old_to_new = {}
    encoded = []
    for p, off, jp in entries:
        enc, miss = mod.encode(table[jp], cmap2)
        if miss:
            raise RuntimeError("battle quote encode missing: %s" % "".join(miss))
        if cur + len(enc) + 1 > BQ_END:
            raise RuntimeError("battle quote arena overflow")
        rom[cur:cur + len(enc)] = enc
        rom[cur + len(enc)] = 0xFF
        rel = cur - BQ_BANK_BASE
        if rel > 0xFFFF:
            raise RuntimeError("battle quote pointer overflow")
        rom[p:p + 2] = rel.to_bytes(2, "little")
        old_to_new[off] = rel
        encoded.append((off, enc))
        cur += len(enc) + 1

    # 原串仍被事件脚本按旧偏移引用；能原位放下的直接覆盖原文，
    # 放不下的把脚本里的 E6 <ptr> 引用改到新译文。
    if os.environ.get("BQ_NO_EXTRA") == "1":
        return {"quotes": len(entries), "chars": len(missing),
                "bytes": cur - BQ_FREE, "table": "0x%06X" % BQ_TABLE,
                "refs": 0}
    for off, enc in encoded:
        start = BQ_BANK_BASE + off
        end = start
        while end < BQ_END and rom[end] != 0xFF:
            end += 1
        if len(enc) + 1 <= end - start + 1:
            rom[start:start + len(enc)] = enc
            rom[start + len(enc)] = 0xFF
    refs = 0
    if os.environ.get("BQ_ALLOW_REFS") != "1":
        return {"quotes": len(entries), "chars": len(missing),
                "bytes": cur - BQ_FREE, "table": "0x%06X" % BQ_TABLE,
                "refs": 0}
    _ranges = _story_string_ranges(rom)
    for off, rel in old_to_new.items():
        pat = off.to_bytes(2, "little")
        s = 0
        while True:
            i = rom.find(pat, s)
            if i < 0:
                break
            if (i > 0 and rom[i - 1] == 0xE6 and
                    not (0x390000 <= i < 0x3A0000) and
                    not _in_story_string(i, _ranges) and
                    (i >> 16) not in STORY_TEXT_BANKS[game]) or \
                    (game == "D3" and 0x3A0000 <= i < 0x3B0000):
                rom[i:i + 2] = rel.to_bytes(2, "little")
                refs += 1
            s = i + 1
    return {"quotes": len(entries), "chars": len(missing),
            "bytes": cur - BQ_FREE, "table": "0x%06X" % BQ_TABLE,
            "refs": refs}


NAME_COPY_E0 = {
    "D1": ((0x3DC403, 0x3DC678, 0x3DC6A2), 0x3DC3F0),
    "D2": ((0x3DC549, 0x3DC7BE, 0x3DC7E8), 0x3DC536),
    "D3": ((0x3DC401, 0x3DC676, 0x3DC6A0), 0x3DC3EE),
}


def apply_name_copy_e0(rom, game):
    sites, long_site = NAME_COPY_E0[game]
    changed = False
    for a in sites:
        cur = rom[a:a + 2]
        if cur == bytes([0x3C, 0xE0]):
            continue
        if cur != bytes([0x3C, 0xF0]):
            raise RuntimeError("name copy site mismatch at 0x%06X" % a)
        rom[a + 1] = 0xE0
        changed = True
    cur = rom[long_site:long_site + 3]
    if cur == bytes([0x80, 0x3D, 0xE0]):
        pass
    elif cur == bytes([0x80, 0x3D, 0xF0]):
        rom[long_site + 2] = 0xE0
        changed = True
    else:
        raise RuntimeError("name copy site mismatch at 0x%06X" % long_site)
    return changed


SKILL_TABLE_FIX = {
    "D1": (0x3F3454, 0xC8FE, 0xC903),
    "D2": (0x3F3494, 0xC9F5, 0xC9FA),
    "D3": (0x3F34B2, 0xC97E, 0xC983),
}
IRON_WALL_ITEM = {
    "D1": (0x3F1F88, 1679),
    "D2": (0x3F1FB8, 1694),
    "D3": (0x3F1FB8, 1709),
}


def apply_table_fixes(rom, game, bdir, cmap):
    """修复两张共享表：技能名前两项被目标标签重定位覆盖；铁壁名称表指向旧混合副本。"""
    addr, a0, a1 = SKILL_TABLE_FIX[game]
    rom[addr:addr + 2] = a0.to_bytes(2, "little")
    rom[addr + 2:addr + 4] = a1.to_bytes(2, "little")
    arr, idx = IRON_WALL_ITEM[game]
    off = int.from_bytes(rom[arr + 1 + 2 * idx:arr + 3 + 2 * idx], "little")
    p = 0x350000 + off
    if bytes(rom[p:p + 2]) != bytes([0xF2, 0x87]):
        raise RuntimeError("铁壁名称副本不是旧混合文本: %s 0x%06X" % (game, p))
    mod = bti.load_ws2lib(bdir)
    enc, missing = mod.encode("铁壁", cmap)
    if missing:
        raise RuntimeError("铁壁编码缺字: %s" % missing)
    rom[p:p + len(enc) + 1] = enc + bytes([0xFF])
    return {"skill": (a0, a1), "iron": off}


def apply_skill_name_fix(rom, game, cmap):
    """特技名「ニュー型L9」前半仍是日文：名称池里是 ニュー+型，改成「新人类」，
    等级后缀 L9 由游戏代码追加。"""
    mod = bti.load_ws2lib(bti.BUILD / ("Dai%s" % game[1]))
    enc, missing = mod.encode("新人类", cmap)
    if missing:
        raise RuntimeError("技能名编码缺字: %s" % missing)
    tcode = cmap.get("型")
    if tcode is None:
        raise RuntimeError("技能名定位缺「型」码")
    pat = bytes([0x52, 0x71, 0xBD]) + tcode.to_bytes(2, "big") + bytes([0xFF])
    i = rom.find(pat, 0x350000, 0x360000)
    if i < 0:
        raise RuntimeError("技能名「ニュー型」未找到: %s" % game)
    end = i + len(pat)
    if end < len(rom) and rom[end] == 0:
        end += 1
    new = enc + bytes([0xFF])
    if end - i != len(new):
        raise RuntimeError("技能名槽长度不符: %s %d/%d" % (game, end - i, len(new)))
    rom[i:end] = new
    return {"addr": i, "to": "新人类"}


STAGE_CLEAR_START = 0x40C2
STAGE_CLEAR_END = 0x40E0
STAGE_CLEAR_TABLE = 0xEBD2
STAGE_CLEAR_DATA = 0xEC20
STAGE_CLEAR_TAB2 = 0xE980

# 事件表 0x40E0-0xFFFF 仍指向 bank18/1A 偏移 0 的原始表，之前没有翻译。
# 新表放在同 bank 的空闲 FF 区，段表改指新表；字符串必须在同一 bank，
# 因为表项是 16 位 bank 内偏移。
# D3 旁白保留 F7BC/F7BD 后多 2 字节；事件表 C 后移 2 字节让位。
EVENT_ALL_TAB = {"D2": (0x18, 0xB800), "D3": (0x18, 0xD0C2)}
EVENT_ALL_COUNT = 384
# 事件表里译文缺失、但确实会显示的条目：招式解锁、机体入手等。
EVENT_EXTRA_ZH = {
    "D2": {
        224: "螺旋飞拳已可使用",
    },
    "D3": {
        224: "强力{F1:F0}已可使用",
        225: "断空光牙剑已可使用",
        226: "神之声已可使用",
        227: "神鸟头部切割已可使用",
        228: "获得「萨拜因」！",
        229: "获得「兹瓦斯」！",
        230: "获得「GP02A{B:DF}酸浆果」！",
        231: "发现本梅尔收藏的/加贝拉·泰特拉",
    },
}
EVENT_LINE_PX = 224
EVENT_CLOSE = "，。！？‥…、；：」』）】》〉!?,.;:"


def _event_char_px(ch):
    """事件框按 12px 汉字步进估算；宏/控制码按 24px 预留。"""
    if ch == "{":
        return 24
    return 12 if ord(ch) >= 128 else 6


def _wrap_event(text, limit_px=EVENT_LINE_PX):
    """按事件框宽度折行，保留原有 `/`；最多两行，放不下直接报错。"""
    text = str(text).replace(" / ", "/").replace("／", "/")
    lines = []
    for part in text.split("/"):
        cur = ""
        cur_px = 0
        i = 0
        while i < len(part):
            ch = part[i]
            w = _event_char_px(ch)
            if cur and cur_px + w > limit_px:
                cut = -1
                for k in range(len(cur) - 1, max(0, len(cur) - 8) - 1, -1):
                    if cur[k] in EVENT_CLOSE:
                        cut = k + 1
                        break
                if cut > 0:
                    lines.append(cur[:cut])
                    cur = cur[cut:]
                    cur_px = sum(_event_char_px(c) for c in cur)
                else:
                    while cur and cur[0] in EVENT_CLOSE and lines:
                        lines[-1] += cur[0]
                        cur = cur[1:]
                    if cur:
                        lines.append(cur)
                        cur = ""
                        cur_px = 0
            cur += ch
            cur_px += w
            i += 1
        if cur:
            lines.append(cur)
    if len(lines) > 2:
        raise RuntimeError("事件文本超过两行: %r" % text)
    return "/".join(lines)


def _load_d1_event_map():
    """D1 剧情_17 与 D2/D3 事件表大量同文，按日文原文复用已有译文。"""
    import openpyxl
    p = bti.BUILD / "Dai1" / "text.xlsx"
    if not p.exists():
        return {}
    wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
    if "剧情_17" not in wb.sheetnames:
        wb.close()
        return {}
    ws = wb["剧情_17"]
    hdr = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
    ji, zi = hdr.index("jp"), hdr.index("zh")
    out = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        jp, zh = row[ji], row[zi]
        if jp and zh:
            out.setdefault(str(jp).strip(), str(zh).strip())
    wb.close()
    return out


def apply_stage_clear_messages(rom, game, bdir, cmap):
    """D2/D3 的 bank18/1A 与 D1 剧情_17 是同一张事件/道具表，但两边索引并不
    完全对齐，D1 有很多「ダミー」。这里按 D1 日文原文精确匹配译文，匹配不到
    的真实事件台词使用 assets/event_bank_zh.json 的人工译文；其余保留原日文。"""
    if game == "D1":
        return None
    import json
    trans = json.loads((Path(bdir) / "assets" / "event_bank_zh.json").read_text(encoding="utf-8"))
    mod = bti.load_ws2lib(bdir)
    flash = 0x3F0000
    item_bank = 0x18 if game == "D2" else 0x1A
    d1_map = _load_d1_event_map()
    extra_zh = EVENT_EXTRA_ZH.get(game, {})
    # 主构建会把剧情串写进空闲 bank，可能覆盖当前 ROM 里的事件原文；
    # 事件表和原文必须从原始 ROM 读取，不能读已构建的 ROM。
    orig_rom = (Path(bdir) / "assets" / "original.ws").read_bytes()

    def orig_string(idx):
        off = int.from_bytes(orig_rom[item_bank * 0x10000 + 2 * idx:
                                       item_bank * 0x10000 + 2 * idx + 2], "little")
        if off >= 0x10000:
            return bytes([0xFF])
        p = item_bank * 0x10000 + off
        e = p
        while e < item_bank * 0x10000 + 0x10000 and orig_rom[e] != 0xFF:
            e += 2 if (orig_rom[e] in (0xFC, 0xFD) or orig_rom[e] >= 0xE0) else 1
        return bytes(orig_rom[p:e + 1])

    # 先整理 0x40E0-0xFFFF 事件表 384 条：JSON 译文 → D1 同文译文 → 手工补译。
    event_rows = []
    untranslated = []
    for idx in range(EVENT_ALL_COUNT):
        off = int.from_bytes(orig_rom[item_bank * 0x10000 + 2 * idx:
                                      item_bank * 0x10000 + 2 * idx + 2], "little")
        jp = mod.read_string(orig_rom, item_bank * 0x10000 + off, 400)[0]
        zh = trans.get("%04X" % (0x4000 + idx)) or d1_map.get(jp) or extra_zh.get(idx)
        # 259 起是结局制作人员名单（英文/片假名），保留原文即可；
        # 0-258 才是会出现在事件框里的台词/道具/招式提示。
        if (not zh and idx < 259 and
                re.search(r"[\u3040-\u30ff]", jp.replace("ー", ""))):
            untranslated.append((idx, jp))
        event_rows.append((idx, orig_string(idx), jp, zh))
    if untranslated:
        raise RuntimeError("事件表仍有日文未译: %s" %
                           "；".join("%04X=%s" % (0x40E0 + i, s)
                                    for i, s in untranslated[:20]))

    cmap2 = dict(cmap)
    used = set(cmap2.values())
    wrapped = {}
    missing = set()
    for idx, _, _, zh in event_rows:
        if not zh:
            continue
        w = _wrap_event(zh)
        wrapped[idx] = w
        _, miss = mod.encode(w, cmap2)
        missing.update(miss)

    cfg = mod.load_cfg()
    chunks = mod.chunks(cfg)

    def slot_addr(code):
        n = code - 0xE000
        ci, loc = n >> 10, n & 0x3FF
        if ci >= len(chunks):
            raise RuntimeError("事件文本字库溢出")
        bank, base = chunks[ci]
        di = base + (loc >> 3) * 0x100 + (loc & 7) * 0x10
        return bank * 0x10000 + di

    code = 0xE000
    for ch in sorted(missing):
        while code <= 0xEFFF:
            if code in used or (code & 0xFF) in (0xFD, 0xFE, 0xFF):
                code += 1
                continue
            addr = slot_addr(code)
            if (all(b == 0xFF for b in rom[addr:addr + 16]) and
                    all(b == 0xFF for b in rom[addr + 0x80:addr + 0x90])):
                break
            code += 1
        else:
            raise RuntimeError("事件文本字库溢出")
        g = mod.pack_glyph(ch)
        rom[addr:addr + 16] = g[:16]
        rom[addr + 0x80:addr + 0x90] = g[16:]
        cmap2[ch] = code
        used.add(code)
        code += 1

    def encode_group(indices, bank, table_off):
        table = bytearray()
        data = bytearray()
        data_off = (table_off + len(indices) * 2 + 1) & ~1
        cur = data_off
        for idx in indices:
            zh = trans.get("%04X" % (0x4000 + idx))
            if zh:
                enc, miss = mod.encode(zh, cmap2, newline_blank=True)
                if miss:
                    raise RuntimeError("事件行 %04X 编码缺字: %s" %
                                       (0x4000 + idx, "".join(sorted(miss))))
                enc += bytes([0xFF])
            else:
                enc = orig_string(idx)
            if cur + len(enc) > 0x10000:
                raise RuntimeError("事件覆盖区溢出 bank %02X" % bank)
            table += cur.to_bytes(2, "little")
            data += enc
            cur += len(enc)
        if any(b != 0xFF for b in rom[bank * 0x10000 + table_off:
                                      bank * 0x10000 + data_off + len(data)]):
            raise RuntimeError("事件覆盖区不是空闲 FF: bank%02X +%04X-%04X" %
                               (bank, table_off, data_off + len(data)))
        rom[bank * 0x10000 + table_off:bank * 0x10000 + data_off] = table + bytes(data_off - table_off - len(table))
        rom[bank * 0x10000 + data_off:bank * 0x10000 + data_off + len(data)] = data
        return table_off, data_off, len(table), len(data)

    # A: 0x4000-0x4070
    a_bank = 0x18 if game == "D2" else 0x19
    a_tab = 0xAAC7 if game == "D2" else 0x0000
    a_tab, a_data, a_tsz, a_dsz = encode_group(range(0x00, 0x70), a_bank, a_tab)
    # B: 0x4070-0x40E0 (含 0x40C2-0x40DF 的通关奖励/道具)
    b_tab = 0xEBD2
    b_tab, b_data, b_tsz, b_dsz = encode_group(range(0x70, 0xE0), 0x3F, b_tab)

    # C: 0x40E0-0xFFFF 事件表（原表在 bank18/1A 偏移 0，未翻译）。
    ev_bank, ev_tab = EVENT_ALL_TAB[game]
    ev_data_off = (ev_tab + EVENT_ALL_COUNT * 2 + 1) & ~1
    ev_table = bytearray()
    ev_data = bytearray()
    cur = ev_data_off
    for idx, ob, jp, zh in event_rows:
        if zh:
            enc, miss = mod.encode(wrapped[idx], cmap2, newline_blank=True)
            if miss:
                raise RuntimeError("事件行 40%02X 编码缺字: %s" %
                                   (0xE0 + idx, "".join(sorted(miss))))
            enc += bytes([0xFF])
        else:
            enc = ob
        if cur + len(enc) > 0x10000:
            raise RuntimeError("事件表 C 溢出 bank %02X: slot=%d len=%d cur=%04X" %
                               (ev_bank, idx, len(enc), cur))
        ev_table += cur.to_bytes(2, "little")
        ev_data += enc
        cur += len(enc)
    ev_start = ev_bank * 0x10000 + ev_tab
    ev_end = ev_bank * 0x10000 + ev_data_off + len(ev_data)
    if any(b != 0xFF for b in rom[ev_start:ev_end]):
        raise RuntimeError("事件表 C 覆盖区不是空闲 FF: bank%02X +%04X-%04X" %
                           (ev_bank, ev_tab, ev_data_off + len(ev_data)))
    rom[ev_start:ev_bank * 0x10000 + ev_data_off] = ev_table + bytes(ev_data_off - ev_tab - len(ev_table))
    rom[ev_bank * 0x10000 + ev_data_off:ev_end] = ev_data

    base = flash + STAGE_CLEAR_TAB2
    entries = []
    i = 0
    while i < 0x200:
        a, b, bank, _pad, toff, tbase = struct.unpack_from("<HHBBHH", rom, base + i)
        if a == 0xFFFF and b == 0:
            break
        entries.append((a, b, bank & 0x3F, toff, tbase))
        i += 10
    else:
        raise RuntimeError("剧情载入段表异常: %s" % game)
    out = [e for e in entries if e[0] < 0x4000]
    out += [
        (0x4000, 0x4070, a_bank, a_tab, 0),
        (0x4070, 0x40E0, 0x3F, b_tab, 0),
        (0x40E0, 0xFFFF, ev_bank, ev_tab, 0),
    ]
    out.sort(key=lambda x: x[0])
    packed = bytearray()
    for a, b, bank, toff, tbase in out:
        packed += struct.pack("<HHBBHH", a, b, 0xC0 | bank, 0, toff, tbase)
    packed += struct.pack("<HHBBHH", 0xFFFF, 0, 0, 0, 0, 0)
    if len(packed) > 0x180:
        raise RuntimeError("事件载入段表超长: %s %d" % (game, len(packed)))
    rom[base:base + len(packed)] = packed
    return {"A": (hex(a_bank), hex(a_tab), a_tsz, a_dsz),
            "B": (hex(b_tab), b_tsz, b_dsz),
            "C": (hex(ev_bank), hex(ev_tab), len(ev_table), len(ev_data)),
            "glyphs": len(missing)}


UI_PTR_RESTORE = {
    "D1": (0x3F2C62, 0x3F2D5E),
    "D2": (0x3F2CDE, 0x3F2DAC),
    "D3": (0x3F2CFE, 0x3F2DCA),
}
MIRACLE_PTR = {"D1": 0x3F2D59, "D2": 0x3F2DA7, "D3": 0x3F2DC5}
# 跳过动画补丁会在 bank35 的固定槽写「动画 开 / 动画 关」，构建时预留，避免其他串压上去。
SKIP_BANK35_RESERVED = {"D1": [(0xFA1C, 0xFA30)], "D2": [(0xFB59, 0xFB6D)], "D3": [(0xFC68, 0xFC7C)]}
MIRACLE_SLOT = {"D1": 0xF9E1, "D2": 0xFB1E, "D3": 0xFBA0}
MIRACLE_TEXT = "同时使用魂、闪避、必中、幸运、/努力、大根性、加速各一次，气合3次。"
ORIG_ROM = {
    "D1": "Super Robot Taisen Compact 2 - Dai-1-bu - Chijou Gekidou Hen (Japan).ws",
    "D2": "Super Robot Taisen Compact 2 - Dai-2-bu - Uchuu Gekishin Hen (Japan) (Rev 4).ws",
    "D3": "Super Robot Taisen Compact 2 - Dai-3-bu - Ginga Kessen Hen (Japan) (Rev 2).ws",
}


def restore_ui_pointer_table(rom, game):
    """D1 的 UI 指针表与 JP 一致；D2/D3 的表已被名称重排重定位，
    恢复 JP 表会让精神名变成 ????，因此只对 D1 恢复。"""
    if game != "D1":
        return None
    a, b = UI_PTR_RESTORE[game]
    orig = (bti.BUILD / ("Dai%s" % game[-1]) / "assets" / "original.ws").read_bytes()
    if orig[a:b] == rom[a:b]:
        return None
    rom[a:b] = orig[a:b]
    return {"range": (hex(a), hex(b))}


def apply_miracle_text(rom, game, bdir, cmap):
    """奇迹说明原槽只有 3 字节的 ???；重定位到 bank35 空闲区。"""
    mod = bti.load_ws2lib(bdir)
    text = "同时使用魂、闪避、必中、幸运、/努力、大根性、加速各一次，气合3次。"
    enc, miss = mod.encode(text, cmap, newline_blank=False)
    if miss:
        raise RuntimeError("奇迹说明编码缺字: %s" % "".join(sorted(miss)))
    # 跳过补丁会在固定槽写「动画 开/关」，旧固定槽可能正好接在奇迹串尾；
    # 一律重新分配，并在串前后各留一个 FF，避免读过头或终止符被覆盖。
    blob = bytes([0xFF]) + enc + bytes([0xFF])
    base = _alloc_bank35(rom, blob)
    off = base + 1
    ta = MIRACLE_PTR[game]
    rom[ta:ta + 2] = off.to_bytes(2, "little")
    return {"slot": hex(off), "ptr": hex(ta), "bytes": len(enc)}


EXCELEN_FULL = {
    "D1": (0x3DB786, "艾克瑟莲·白朗宁", "艾克塞琳·勃朗宁"),
    "D2": (0x3DB8B8, "艾克瑟莲·白朗宁", "艾克塞琳·勃朗宁"),
    "D3": (0x3DB778, "艾克瑟莲·白朗宁", "艾克塞琳·勃朗宁"),
}


def apply_name_string_fixes(rom, game, bdir, cmap):
    """bank 0x3D 的默认主角/恋人固定串不在名称表重排范围内，单独替换。"""
    mod = bti.load_ws2lib(bdir)
    addr, old, new = EXCELEN_FULL[game]
    # 补「琳/勃」等缺字：从空闲 E0 槽分配字模码
    cfg = _f1_cfg(bdir)
    chunks = _f1_chunks(cfg)
    used = set(cmap.values())
    for ch in new:
        if ch in cmap:
            continue
        for code in range(0xE000, 0xF000):
            if code in used or (code & 0xFF) in (0xFD, 0xFE, 0xFF):
                continue
            n = code - 0xE000
            ci, loc = n >> 10, n & 0x3FF
            if ci >= len(chunks):
                break
            bank, base = chunks[ci]
            slot = bank * 0x10000 + base + (loc >> 3) * 0x100 + (loc & 7) * 0x10
            if all(b == 0xFF for b in rom[slot:slot + 16]) and                     all(b == 0xFF for b in rom[slot + 0x80:slot + 0x90]):
                g = mod.pack_glyph(ch)
                rom[slot:slot + 16] = g[:16]
                rom[slot + 0x80:slot + 0x90] = g[16:]
                cmap[ch] = code
                used.add(code)
                break
        else:
            raise RuntimeError("名称缺字无法分配: %s" % ch)
    o, mo = mod.encode(old, cmap)
    n, mn = mod.encode(new, cmap)
    if mo or mn:
        raise RuntimeError("艾克塞琳名称编码缺字: %s%s" % (mo, mn))
    if len(n) > len(o):
        raise RuntimeError("艾克塞琳名称槽不够: %d>%d" % (len(n), len(o)))
    if rom[addr:addr + len(o)] != o:
        raise RuntimeError("艾克塞琳名称串不匹配: %s 0x%06X" % (game, addr))
    rom[addr:addr + len(o)] = n + b"\x00" * (len(o) - len(n))
    # 单独的爱称（不带姓氏）也统一
    oa, _ = mod.encode("艾克瑟莲", cmap)
    na, _ = mod.encode("艾克塞琳", cmap)
    if game == "D1":
        # D1 名称表在 UI 导入后又被重排，重新把 大根性 指回 F1/32px 条带
        strip = rom.find(bytes([0xF5, 0x39, 0xF5, 0x6D, 0xDF, 0xFF]), 0x350000, 0x360000)
        if strip < 0:
            raise RuntimeError("D1 大根性条带串未找到")
        rom[0x3F2CB5:0x3F2CB7] = (strip - 0x350000).to_bytes(2, "little")
    cnt = 0
    start = 0
    while True:
        i = rom.find(oa, start)
        if i < 0:
            break
        if len(na) <= len(oa):
            rom[i:i + len(oa)] = na + b"\x00" * (len(oa) - len(na))
            cnt += 1
        start = i + 1
    return {"addr": hex(addr), "alias": cnt}


_BANK35_RESERVED = []


def _alloc_bank35(rom, data):
    """在 bank 0x35 的高位空闲区分配一段短文本。

    名称指针只存 16 位偏移，因此宏串必须放在 bank 0x35。
    从 0xFFF0 向下找 2 字节对齐、整段都是 FF 的位置；
    必须避开 UI 固定槽 0xFE00-0xFE70 和 0xFF00-0xFF06。
    已分配的串（含 FF 终止符）和固定「通关」槽也登记在 forbid 中，
    否则后来的 3 字节宏可能从上一串的 FF 终止符开始写，把两串粘在一起。
    尾部只保留一个 FF 终止符；前一个字节必须是 FF，串与串之间只隔一个 FF。
    """
    data = bytes(data).rstrip(b"\xff") + b"\xff"
    base = 0x350000
    forbid = [(0xFE00, 0xFE70), (0xFF00, 0xFF06)] + list(_BANK35_RESERVED)
    n = len(data)
    for off in range(0xFFF0 - n, 0xEFFF, -1):
        if off % 2:
            continue
        if any(off < b and off + n > a for a, b in forbid):
            continue
        # 候选起点前一个字节是正文，说明它正踩在已有串的 FF 终止符上。
        if off > 0 and rom[base + off - 1] != 0xFF:
            continue
        if all(rom[base + off + k] == 0xFF for k in range(n)):
            rom[base + off:base + off + n] = data
            _BANK35_RESERVED.append((off, off + n))
            return off
    raise RuntimeError("名称宏串无空闲区")


def apply_menu_label_spacing(rom, game, bdir, cmap):
    """机体/机师/妖精三个菜单标签：字间插 3 个 00，重定位并改所有指针。

    原始串在 bank 0x35 连续排列（机体FF机师00FF妖精FF）。菜单表/代码里
    用小端 16 位指针引用；这里为三条串各分配新串，保留机师原有尾随 00。
    """
    mod = bti.load_ws2lib(bdir)
    labels = ["机体", "机师", "妖精"]
    encs = []
    for t in labels:
        e, miss = mod.encode(t, cmap)
        if miss or len(e) != 4:
            raise RuntimeError("菜单标签编码异常: %s %s" % (t, miss))
        encs.append(e)
    Z = bytes([0])
    FF = bytes([255])
    pat = encs[0] + FF + encs[1] + Z + FF + encs[2] + FF
    p0 = rom.find(pat, 0x350000, 0x360000)
    if p0 < 0:
        raise RuntimeError("菜单标签连续串未找到: %s" % game)
    offs = [p0 - 0x350000,
            p0 - 0x350000 + len(encs[0]) + 1,
            p0 - 0x350000 + len(encs[0]) + 1 + len(encs[1]) + 2]
    new_offs = []
    for idx, (e, off) in enumerate(zip(encs, offs)):
        data = e[:2] + Z * 3 + e[2:] + FF
        if idx == 1:
            data = e[:2] + Z * 3 + e[2:] + Z + FF
        new_offs.append(_alloc_bank35(rom, data))
    # 只改菜单标签的真实记录指针。
    # 0x36448E/0x364493 是幕前整备的「机体/机师」；
    # 0x36449E/0x3644A3 是换乘界面的「机师/妖精」。
    # 0x3641C6/0x3641D0 等是列表标题/底部，代码段里也有数值相同的字节（不是指针），
    # 绝不能一起改，否则其它界面乱码。
    menu_slots = {0x36448E: 0, 0x364493: 1, 0x36449E: 1, 0x3644A3: 2}
    patched = 0
    for q, idx in menu_slots.items():
        old = int.from_bytes(rom[q:q + 2], "little")
        if old not in offs:
            raise RuntimeError("菜单标签指针槽不符: %s 0x%06X=%04X" % (game, q, old))
        rom[q:q + 2] = new_offs[offs.index(old)].to_bytes(2, "little")
        patched += 1
    return {"new": [hex(x) for x in new_offs], "patched": patched}


# ---------------------------------------------------------------------------
# 默认姓名码位固定表
#
# 主角名、恋人名、机体名都能在游戏里改写；玩家一旦存档，这些字符的字体码位
# 就会写进 SRM。之后再改码表，老存档的姓名会显示成符号或黑块。因此把默认名
# 用到的每个字符的码位永久钉死：构建时 alloc_codes 优先使用 cmap_fixed.json
# 里的固定值，构建后再逐字校验；任何漂移都直接报错，不允许静默生成。
# 这些值来自用户实际存档反查（琳/勃）和既有稳定码表（其余字符）。
# 注意：若要修改默认名文本，必须同步修改本表、cmap_fixed.json 和文案表。
# ---------------------------------------------------------------------------
PINNED_NAMES = {
    # D1 的第二台默认机体是亡灵（ゲシュペンスト），D2/D3 是白骑士。
    "D1": ["古铁", "亡灵", "响介·南部", "响介", "艾克塞琳·勃朗宁", "艾克塞琳"],
    "D2": ["古铁", "白骑士", "响介·南部", "响介", "艾克塞琳·勃朗宁", "艾克塞琳"],
    "D3": ["古铁", "白骑士", "响介·南部", "响介", "艾克塞琳·勃朗宁", "艾克塞琳"],
}

PINNED_NAME_CODES = {
    "D1": {
        "古": 0xE156, "铁": 0xE7DD,
        "亡": 0xE04F, "灵": 0xE4F4,
        "响": 0xE1A4, "介": 0xE05D, "·": 0xE008, "南": 0xE12F, "部": 0xE7C5,
        "艾": 0xE68D, "克": 0xE0B9, "塞": 0xE206, "琳": 0xE000,
        "勃": 0xE00B, "朗": 0xE41B, "宁": 0xE251,
    },
    "D2": {
        "古": 0xE14D, "铁": 0xE7EF,
        "白": 0xE57C, "骑": 0xE86D, "士": 0xE208,
        "响": 0xE195, "介": 0xE05F, "·": 0xE008, "南": 0xE127, "部": 0xE7D7,
        "艾": 0xE6A2, "克": 0xE0B8, "塞": 0xE201, "琳": 0xE00D,
        "勃": 0xE00F, "朗": 0xE42C, "宁": 0xE24E,
    },
    "D3": {
        "古": 0xE164, "铁": 0xE841,
        "白": 0xE5B6, "骑": 0xE8C3, "士": 0xE225,
        "响": 0xE1B1, "介": 0xE061, "·": 0xE00B, "南": 0xE13F, "部": 0xE825,
        "艾": 0xE6D8, "克": 0xE0C4, "塞": 0xE21C, "琳": 0xE007,
        "勃": 0xE008, "朗": 0xE450, "宁": 0xE271,
    },
}

# 旧版导入先把“琳/勃”动态分配到下列闲置码位并写入字模，随后固定码位又
# 写到正式槽位，旧字模没有清除。这两个码位现在登记为未使用的符号，保留
# 冗余字模只是为了让固定码位改动不改动 ROM 字节（CRC 不变）；没有文本
# 引用它们，将来若启用同码位符号，write_font 会覆盖。
LEGACY_NAME_GLYPHS = {
    "D1": [],
    "D2": [("琳", 0xE005), ("勃", 0xE00B)],
    "D3": [("琳", 0xE005), ("勃", 0xE006)],
}

# bank0x3D 默认名块头部固定 12 字节，之后紧接 6 条 FF 结尾串。
# 不写死字符串地址：导入会按译名长度压紧，地址可能移动。
_DEFAULT_NAME_HEAD = bytes.fromhex("3203030000000000b2030300")


def verify_pinned_codes(cmap, game):
    """构建后校验：默认名字符必须落在固定码位，且码位不能被别的字符占用。"""
    codes = PINNED_NAME_CODES[game]
    bad = []
    for ch, want in codes.items():
        got = cmap.get(ch)
        if got != want:
            bad.append("%s=%s(期望%04X)" % (ch, "无" if got is None else "%04X" % got, want))
    if bad:
        raise RuntimeError(
            "%s 默认名码位漂移：%s。请恢复 构建/Dai%s/assets/cmap_fixed.json 中的固定值"
            % (game, "、".join(bad), game[-1]))
    rev = {c: ch for ch, c in cmap.items()}
    for ch, code in codes.items():
        other = rev.get(code)
        if other is not None and other != ch:
            raise RuntimeError("%s 码位 %04X 被 %s 占用（应为 %s）" % (game, code, other, ch))


def _default_name_block(rom, game):
    """在 bank0x3D 中定位默认名块，返回第一条字符串的起始地址。"""
    a = rom.find(_DEFAULT_NAME_HEAD, 0x3D0000, 0x3E0000)
    if a < 0:
        raise RuntimeError("默认名块定位失败: %s" % game)
    return a + len(_DEFAULT_NAME_HEAD)


def apply_pinned_names(rom, game, bdir):
    """按固定码位重写默认主角/恋人/机体名，并校验字模槽与串长度。"""
    mod = bti.load_ws2lib(bdir)
    cfg = mod.load_cfg()
    chunks = mod.chunks(cfg)
    codes = PINNED_NAME_CODES[game]
    seen = {}
    for ch, code in codes.items():
        if code in seen:
            raise RuntimeError("默认名码位重复: %s %04X %s/%s" % (game, code, seen[code], ch))
        seen[code] = ch
    # 字模：直接写固定槽。若槽里已有别的字形则报错，避免覆盖其他字符。
    for ch, code in codes.items():
        g = mod.pack_glyph(ch)
        n = code - 0xE000
        ci, loc = n >> 10, n & 0x3FF
        if ci >= len(chunks):
            raise RuntimeError("默认名字模越界: %s %s %04X" % (game, ch, code))
        bank, base = chunks[ci]
        p = bank * 0x10000 + base + (loc >> 3) * 0x100 + (loc & 7) * 0x10
        cur = rom[p:p + 16] + rom[p + 0x80:p + 0x90]
        if any(b != 0xFF for b in cur) and cur != g:
            raise RuntimeError("默认名字模槽冲突: %s %s %04X" % (game, ch, code))
        rom[p:p + 16] = g[:16]
        rom[p + 0x80:p + 0x90] = g[16:]
    # 兼容旧版输出：保留动态分配遗留的冗余字模，详见 LEGACY_NAME_GLYPHS 注释。
    for ch, code in LEGACY_NAME_GLYPHS[game]:
        g = mod.pack_glyph(ch)
        n = code - 0xE000
        ci, loc = n >> 10, n & 0x3FF
        bank, base = chunks[ci]
        p = bank * 0x10000 + base + (loc >> 3) * 0x100 + (loc & 7) * 0x10
        rom[p:p + 16] = g[:16]
        rom[p + 0x80:p + 0x90] = g[16:]
    # 字符串：按块内顺序逐条覆盖。长度必须与导入结果一致，否则拒绝静默重排。
    pos = _default_name_block(rom, game)
    for text in PINNED_NAMES[game]:
        miss = [ch for ch in text if ch not in codes]
        if miss:
            raise RuntimeError("默认名缺少固定码位: %s %r %s" % (game, text, "".join(miss)))
        enc = b"".join(codes[ch].to_bytes(2, "big") for ch in text)
        end = rom.find(b"\xff", pos, pos + 64)
        if end < 0:
            raise RuntimeError("默认名串缺少终止符: %s 0x%06X" % (game, pos))
        cap = end - pos + 1
        if len(enc) + 1 != cap:
            raise RuntimeError(
                "默认名串长度变化，拒绝静默重排: %s %r 槽=%d 新=%d"
                % (game, text, cap, len(enc) + 1))
        if rom[pos:end] != enc:
            raise RuntimeError(
                "默认名块内容与固定表不符: %s %r 槽内=%s"
                % (game, text, rom[pos:end].hex()))
        rom[pos:pos + len(enc)] = enc
        rom[pos + len(enc)] = 0xFF
        pos = end + 1
    return {"block": hex(pos - 1), "chars": len(codes)}


def apply_long_name_macros(rom, game, bdir, cmap):
    """处理 9 字以上角色/机体名：保留原字模，只把名称指针改指向 F1 宏短串。

    为什么不能直接在临时工作簿里把长名换成 {F1}：
    - 这些名字里的部分汉字只在这个名字中出现，替换后字库不再收录，
      会导致全局码位/字模重新分配，旧存档里的自定姓名可能错字；
    - 名称池长度变化还会让整张指针表重排，增加不必要差异。
    因此这里先按原字模导入，构建后再：
    1) 用当前 cmap 在原 ROM 的 bank 0x35 里找到该名字的原串；
    2) 只在名称表区间（D1 0x3F1F89 起 1771 项，D2/D3 0x3F1FB9 起
       1786/1801 项）内找指向该串的小端 2 字节指针；表外与名称池
       偏移相同的巧合值不能改，否则会破坏开机/战斗流程；
    3) 在 bank 0x35 高位分配 `F1 xx FF` 短串，改写这些指针。
    男女主人公机没有独立的「主人公机」行，使用“单字 + F1 FF + 后缀”的拼法。
    """
    mod = bti.load_ws2lib(bdir)
    ids = {text: mid for mid, text in F1_NAMES[game]}
    jobs = []  # (原文, 原文编码, 新宏串)
    for mid, text in F1_NAMES[game]:
        if mid not in LONG_NAME_IDS or text == "主人公机":
            continue
        enc, miss = mod.encode(text, cmap)
        if miss:
            raise RuntimeError("长名编码缺字: %s %s" % (text, "".join(sorted(miss))))
        jobs.append((text, enc, bytes([0xF1, mid, 0xFF])))
    if "主人公机" in ids:
        for text in ("男主人公机2(饭)", "女主人公机2(饭)"):
            enc, miss = mod.encode(text, cmap)
            h, mh = mod.encode(text[0], cmap)
            t, mt = mod.encode(text[5:], cmap)
            if miss or mh or mt:
                raise RuntimeError("主人公机名编码缺字: %s" % text)
            # 例：男 + F1FF(主人公机) + 2(饭) + FF
            jobs.append((text, enc, h + bytes([0xF1, 0xFF]) + t + bytes([0xFF])))

    # 名称表：D1 0x3F1F89、D2/D3 0x3F1FB9，各 1771/1786/1801 项。
    # 只能在这张表内改指针；0x3F13xx 等处也有与名称池偏移相同的数值，
    # 它们不是名称指针，误改会破坏开机/标题流程（D1 会卡在 logo 循环）。
    name_base, name_count = {
        "D1": (0x3F1F89, 1771),
        "D2": (0x3F1FB9, 1786),
        "D3": (0x3F1FB9, 1801),
    }[game]
    name_end = name_base + 2 * name_count

    def refs_for(off):
        """在名称表内找 bank 0x35 偏移 off 的小端指针。"""
        pat = off.to_bytes(2, "little")
        out = []
        for i in range(name_base, name_end, 2):
            if rom[i:i + 2] == pat:
                out.append(i)
        return out

    patched = []
    seen_refs = set()
    for text, enc, macro in jobs:
        found = []
        start = 0x350000
        # 同一名字可能在名称池中有多份副本（后缀派生/重排），全部找出
        while True:
            p = rom.find(enc, start, 0x360000)
            if p < 0:
                break
            off = p - 0x350000
            for q in refs_for(off):
                found.append((p, q))
            start = p + 1
        if not found:
            raise RuntimeError("长名指针未找到: %s %s" % (game, text))
        new_off = _alloc_bank35(rom, macro)
        for p, q in found:
            if q in seen_refs:
                continue
            seen_refs.add(q)
            old = int.from_bytes(rom[q:q + 2], "little")
            if old != p - 0x350000:
                raise RuntimeError("长名指针值不符: %s 0x%06X" % (text, q))
            # 名称指针是小端 16 位，指向 bank 0x35；改成新分配的宏串偏移
            rom[q:q + 2] = new_off.to_bytes(2, "little")
        patched.append((text, len(found)))
    return patched


# ---------------------------------------------------------------------------
# FA/FB（8px 单字节页 + 宏）构建
#
# 配置全部来自 text.xlsx：
#   FA页     —— 每作的页/跳板/cave/FB 处理器地址、名称表范围
#   FB武器名 —— 每行一个武器名：布局、左右空、ASCII 宽、逐字宽、FB 号、FA 起始格
# 文本里只写 `FB id FF`；FB 体每字节一个 FA 格号，FF 结束；FB 处理器把
# 每个格号交给共享字模入口（AL=FA, AH=格号）绘制 8px 一格。
# ---------------------------------------------------------------------------
_FA_REV = None


def _fa_num(v, default=0):
    if v is None or v == "":
        return default
    if isinstance(v, (int, float)):
        return int(v)
    try:
        return int(str(v).strip(), 0)
    except Exception:
        return default


def _fa_csv(v):
    if v is None or str(v).strip() == "":
        return []
    return [int(x) for x in str(v).replace("，", ",").split(",") if str(x).strip()]


def _fa_kv(wb, name):
    ws = wb[name]
    out = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row and row[0] is not None:
            out[str(row[0]).strip()] = row[1]
    return out


def _fa_native(rom, ch):
    """取游戏原生 8x16 单字节 ASCII 字模；'-' 用 4px 横线。"""
    global _FA_REV
    from PIL import Image, ImageDraw
    if ch == "-":
        im = Image.new("L", (8, 16), 0)
        ImageDraw.Draw(im).rectangle((2, 8, 5, 8), fill=255)
        return im
    if _FA_REV is None:
        _FA_REV = {v: k for k, v in SINGLE.items() if v}
    code = _FA_REV.get(ch)
    if code is None:
        raise RuntimeError("单字节字库没有 %r" % ch)
    idx = code - 1
    di = (idx >> 4) * 0x100 + (idx & 0xF) * 8
    raw = rom[0x300000 + di:0x300000 + di + 8] + rom[0x300000 + di + 0x80:0x300000 + di + 0x88]
    im = Image.new("L", (8, 16), 0)
    px = im.load()
    for y in range(16):
        b = raw[y]
        for x in range(8):
            if (b >> (7 - x)) & 1:
                px[x, y] = 255
    return im


def _fa_trim(im):
    px = im.load()
    cols = [x for x in range(im.width) if any(px[x, y] > 128 for y in range(16))]
    if not cols:
        return im
    return im.crop((min(cols), 0, max(cols) + 1, 16))


def _fa_fit(im, target):
    from PIL import Image
    if im.width == target:
        return im
    if im.width > target:
        return im.crop((0, 0, target, 16))
    out = Image.new("L", (target, 16), 0)
    out.paste(im, (0, 0))
    return out


def _fa_strip(rom, text, layout, left, ascii_w, ascii_gap, ascii_after,
              widths, right, width, font):
    from PIL import Image
    im = Image.new("L", (width, 16), 0)
    if layout == "S-DX":
        chars = list(text)
        n = len(ascii_w)
        x = left
        for i in range(n):
            g = _fa_fit(_fa_trim(_fa_native(rom, chars[i])), ascii_w[i])
            im.paste(g, (x, 0))
            x += ascii_w[i]
            if i < n - 1:
                x += ascii_gap
        x += ascii_after
        for ch, w in zip(chars[n:], widths):
            g, _nat = _f1_glyph(ch, font)
            im.paste(g, (x, 0))
            x += w
    else:
        x = left
        for ch, w in zip(text, widths):
            g = _fa_native(rom, ch) if ord(ch) < 128 else _f1_glyph(ch, font)[0]
            im.paste(g, (x, 0))
            x += w
    if x + right != width:
        raise RuntimeError("FA 条带宽度不符: %s x=%d right=%d width=%d" % (text, x, right, width))
    return im


def _fa_slice(im, cells):
    from PIL import Image
    if im.width < cells * 8:
        pad = Image.new("L", (cells * 8, 16), 0)
        pad.paste(im, (0, 0))
        im = pad
    px = im.load()
    out = []
    for c in range(cells):
        top = bytearray()
        bot = bytearray()
        for y in range(8):
            v = 0
            for x in range(8):
                v = (v << 1) | (1 if px[c * 8 + x, y] > 128 else 0)
            top.append(v)
        for y in range(8, 16):
            v = 0
            for x in range(8):
                v = (v << 1) | (1 if px[c * 8 + x, y] > 128 else 0)
            bot.append(v)
        out.append(bytes(top) + bytes(bot))
    return out


def _fa_build_cave(tramp, blit_write, page_base, fb_handler, base):
    resume = tramp + 4
    kanji = tramp + 0x65
    fb_at, kanji_at, ext_at = 18, 15, 21
    c = bytearray()
    c += bytes.fromhex("3cfb")
    c += bytes((0x74, (fb_at - 4) & 0xFF))
    c += bytes.fromhex("3cfa")
    c += bytes((0x74, (ext_at - 8) & 0xFF))
    c += bytes.fromhex("3cf2")
    c += bytes((0x73, (kanji_at - 12) & 0xFF))
    c += bytes((0xE9,)) + ((resume - (base + 15)) & 0xFFFF).to_bytes(2, "little")
    c += bytes((0xE9,)) + ((kanji - (base + 18)) & 0xFFFF).to_bytes(2, "little")
    c += bytes((0xE9,)) + ((fb_handler - (base + 21)) & 0xFFFF).to_bytes(2, "little")
    c += bytes.fromhex("55" "33ed" "88e0" "30e4" "88c3" "240f" "c0e003"
                       "80e3f0" "30ff" "c1e304" "03c3")
    c += bytes((0x05,)) + page_base.to_bytes(2, "little")
    c += bytes.fromhex("89c7" "368b360602" "ba0020" "8ec2" "33d2" "b0fb" "e6c2")
    c += bytes((0xEA,)) + blit_write.to_bytes(2, "little") + bytes((0x00, 0xF0))
    return c


def _fa_build_handler(table_off, blitter, blit_exit, base):
    c = bytearray()
    c += bytes.fromhex("88e0" "30e4" "d1e0")
    c += bytes((0x05,)) + table_off.to_bytes(2, "little")
    c += bytes.fromhex("89c3" "2e8b2f")
    loop = len(c)
    c += bytes.fromhex("2e8a4600")
    c += bytes.fromhex("3cff")
    je = len(c)
    c += bytes((0x74, 0))
    c += bytes.fromhex("88c4" "b0fa")
    c += bytes((0x9A,)) + blitter.to_bytes(2, "little") + bytes((0x00, 0xF0))
    c += bytes.fromhex("45")
    jmp = len(c)
    c += bytes((0xEB, 0))
    done = len(c)
    c += bytes((0xE9,)) + ((blit_exit - (base + done + 3)) & 0xFFFF).to_bytes(2, "little")
    c[je + 1] = (done - (je + 2)) & 0xFF
    c[jmp + 1] = (loop - (jmp + 2)) & 0xFF
    return c


def _fa_audit(rom, nb, nc):
    """审计正文：FA/FB 不得作为前导码出现（低字节不受影响）。"""
    bad = []
    for i in range(nc):
        ptr = int.from_bytes(rom[nb + 2 * i:nb + 2 * i + 2], "little")
        if not (0x0400 <= ptr < 0x10000):
            continue
        p = 0x350000 + ptr
        limit = min(0x360000, p + 256)
        data = bytearray()
        while p < limit and rom[p] != 0xFF:
            data.append(rom[p])
            p += 1
        j = 0
        while j < len(data):
            b = data[j]
            if b in (0xFF, 0xFE):
                break
            if b >= 0xE0:
                if b in (0xFA, 0xFB):
                    bad.append(("名称表", hex(nb + 2 * i), hex(b)))
                j += 2
            else:
                j += 1
    for k in range(48):
        off = int.from_bytes(rom[0x3FFF00 + 2 * k:0x3FFF02 + 2 * k], "little")
        if not (0xF800 <= off < 0xFF00):
            continue
        p = 0x3F0000 + off
        while p + 1 < 0x400000 and rom[p] != 0xFF:
            if rom[p] in (0xFA, 0xFB):
                bad.append(("F1体", hex(p), hex(rom[p])))
            p += 2
    if bad:
        raise RuntimeError("FA/FB 前导码冲突: %s" % bad[:8])


def apply_fa_fb(rom, game, bdir, book_path=None):
    """按 FA页 / FB武器名 生成 8px 页与 FB 宏；没有配置页时跳过。"""
    import openpyxl
    from PIL import ImageFont
    book = Path(book_path) if book_path else Path(bdir) / "text.xlsx"
    wb = openpyxl.load_workbook(book, read_only=True, data_only=True)
    try:
        if "FA页" not in wb.sheetnames or "FB武器名" not in wb.sheetnames:
            raise RuntimeError("%s 缺少 FA页/FB武器名 sheet，请先合并 text_fafb.xlsx" % game)
        kv = _fa_kv(wb, "FA页")
        rows = list(wb["FB武器名"].iter_rows(min_row=2, values_only=True))
    finally:
        wb.close()
    page = _fa_num(kv.get("页基址"))
    page_base = _fa_num(kv.get("页内基址"))
    tramp = _fa_num(kv.get("跳板"))
    cave = _fa_num(kv.get("cave"))
    blit_write = _fa_num(kv.get("单字节写入入口"))
    blitter = _fa_num(kv.get("字模入口"))
    blit_exit = _fa_num(kv.get("共享出口"))
    fb_handler = _fa_num(kv.get("FB处理器"))
    fb_table = _fa_num(kv.get("FB表"))
    fb_body = _fa_num(kv.get("FB体"))
    nb = _fa_num(kv.get("名称表基址"))
    nc = _fa_num(kv.get("名称表项数"))
    _fa_audit(rom, nb, nc)
    font = ImageFont.truetype(str(Path(bdir) / "assets" / "fonts" / "wenquanyi_9pt.ttf"), 12)

    items = []
    for row in rows:
        if not row or row[0] is None:
            continue
        items.append(dict(
            fid=_fa_num(row[0]), mid=str(row[1]).strip(), text=str(row[3]).strip(),
            layout=str(row[4]).strip(), left=_fa_num(row[5]),
            ascii_w=_fa_csv(row[6]), ascii_gap=_fa_num(row[7]), ascii_after=_fa_num(row[8]),
            widths=_fa_csv(row[9]), right=_fa_num(row[10]),
            width=_fa_num(row[11]), cells=_fa_num(row[12]), fa=_fa_num(row[13])))

    # 1) FA 页字模
    for it in items:
        cells = _fa_slice(_fa_strip(rom, it["text"], it["layout"], it["left"],
                                    it["ascii_w"], it["ascii_gap"], it["ascii_after"],
                                    it["widths"], it["right"], it["width"], font),
                          it["cells"])
        it["glyphs"] = cells
        for c, gl in enumerate(cells):
            idx = it["fa"] + c
            a = page + (idx >> 4) * 0x100 + (idx & 0xF) * 8
            if any(b != 0xFF for b in rom[a:a + 8] + rom[a + 0x80:a + 0x88]):
                raise RuntimeError("%s FA 页槽非空 FA%02X" % (game, idx))
            rom[a:a + 8] = gl[:8]
            rom[a + 0x80:a + 0x88] = gl[8:]

    # 2) FB 体 + 表
    table = [0] * 16
    body_off = fb_body & 0xFFFF
    for it in items:
        body = bytes(range(it["fa"], it["fa"] + it["cells"])) + b"\xFF"
        a = 0x3F0000 + body_off
        if any(b != 0xFF for b in rom[a:a + len(body)]):
            raise RuntimeError("%s FB 体区非空 @%04X" % (game, body_off))
        rom[a:a + len(body)] = body
        table[it["fid"]] = body_off
        body_off += len(body)
    tb = fb_table & 0xFFFF
    if any(b != 0xFF for b in rom[0x3F0000 + tb:0x3F0000 + tb + 32]):
        raise RuntimeError("%s FB 表区非空" % game)
    for i, v in enumerate(table):
        rom[0x3F0000 + tb + 2 * i:0x3F0000 + tb + 2 * i + 2] = v.to_bytes(2, "little")

    # 3) FB 名称串 + 名称表改指
    end = nb + 2 * nc
    patched = []
    for it in items:
        off = _alloc_bank35(rom, bytes((0xFB, it["fid"], 0xFF)))
        mid = int(it["mid"][2:], 16)
        pat = bytes((0xF1, mid, 0xFF))
        occ = []
        i = 0x350000
        while True:
            j = rom.find(pat, i, 0x360000)
            if j < 0:
                break
            occ.append(j - 0x350000)
            i = j + 1
        hits = 0
        for q in range(nb, end, 2):
            if int.from_bytes(rom[q:q + 2], "little") in occ:
                rom[q:q + 2] = off.to_bytes(2, "little")
                hits += 1
        if not hits:
            raise RuntimeError("%s FB 名称表指针未找到: %s %s" % (game, it["mid"], it["text"]))
        patched.append((it["mid"], it["text"], it["width"], it["cells"], hits))

    # 4) 跳板/cave/FB 处理器
    if rom[tramp:tramp + 4] != bytes.fromhex("3cf27361"):
        raise RuntimeError("%s FA 跳板不符" % game)
    rom[tramp:tramp + 3] = bytes((0xE9,)) + ((cave - (tramp + 3)) & 0xFFFF).to_bytes(2, "little")
    rom[tramp + 3] = 0x90
    c = _fa_build_cave(tramp, blit_write, page_base, fb_handler, cave)
    if any(b != 0xFF for b in rom[cave:cave + len(c)]):
        raise RuntimeError("%s FA cave 非空" % game)
    rom[cave:cave + len(c)] = c
    h = _fa_build_handler(fb_table & 0xFFFF, blitter, blit_exit, fb_handler & 0xFFFF)
    if any(b != 0xFF for b in rom[fb_handler:fb_handler + len(h)]):
        raise RuntimeError("%s FB 处理器区非空" % game)
    rom[fb_handler:fb_handler + len(h)] = h
    return dict(items=patched, fb_body_end=hex(body_off), handler=len(h))


bti.import_ui = _import_ui_padded

sx.STORY_XCFG = CFG
sx.STORY_XCAVE = CAVE
sx.struct = struct
sx.reflow_story = bti.reflow_story
sx.too_wide = bti.too_wide
bti.STORY_XCFG = CFG
bti.STORY_XCAVE = CAVE
bti.repack_story_crossbank = sx.repack_story_crossbank

os.environ["STORY_XBANK"] = "1"

if __name__ == "__main__":
    for k in (sys.argv[1:] or ["1", "2", "3"]):
        game = "D%s" % k
        _BANK35_RESERVED.clear()
        _BANK35_RESERVED.extend(SKIP_BANK35_RESERVED.get(game, []))
        bdir = bti.BUILD / ("Dai%s" % k)
        outdir = bdir / "产物"
        outdir.mkdir(parents=True, exist_ok=True)
        src_book = Path(os.environ.get("SRC_BOOK_%s" % k, str(bdir / "text.xlsx")))
        tmp_book = outdir / ("_f1_%s.xlsx" % game)
        _f1_temp_book(src_book, game, tmp_book)
        bti.GAMES[k]["text"] = tmp_book
        # 主导入模块是编译字节码，内部仍写死旧文件名「文本.xlsx」。
        # 每次构建都必须用当前 text.xlsx 覆盖，不能沿用上一次的临时副本；
        # 构建结束立即删除，源码/发布包只保留 text.xlsx。
        legacy_book = bdir / "文本.xlsx"
        legacy_book.write_bytes(src_book.read_bytes())
        try:
            r = bti.build(k)
        finally:
            bti.GAMES[k]["text"] = src_book
            try:
                legacy_book.unlink(missing_ok=True)
            except PermissionError:
                pass
        import gc
        gc.collect()
        try:
            tmp_book.unlink(missing_ok=True)
        except PermissionError:
            pass
        out = Path(r["out"])
        rom = bytearray(out.read_bytes())
        used = set(_CMAP_STORE.get(game, {}).values())
        if not used:
            raise RuntimeError("%s cmap was not captured" % game)
        # 默认姓名码位是存档兼容的硬约束：导入阶段一旦漂移就立即报错。
        verify_pinned_codes(_CMAP_STORE.get(game, {}), game)
        # 二分启动问题时可用 SKIP_PATCHES=名字,... 逐组跳过后期补丁
        skip = set(filter(None, os.environ.get("SKIP_PATCHES", "").split(",")))
        on = lambda n: n not in skip
        if os.environ.get("STOP_AFTER_BASE") == "1":
            out.write_bytes(rom)
            print("BASE", game, "CRC %08X" % (zlib.crc32(rom) & 0xFFFFFFFF))
            continue
        if on("F1NAMES"):
            info = apply_f1_weapon_names(rom, game, bdir, used)
        else:
            info = {"slots": 0, "table": None, "names": []}
        wf1 = apply_weapon_fullname_f1(rom, game, bdir, used) if on("WF1") else None
        gp = apply_gp_mecha_f1(rom, game, bdir, _CMAP_STORE.get(game, {})) if on("GPF1") else None
        cl = apply_clear_label(rom, game, bdir, _CMAP_STORE.get(game, {})) if on("CLEAR") else None
        sl = apply_stage_location_fix(rom, game, bdir, _CMAP_STORE.get(game, {})) if on("STAGELOC") else None
        if os.environ.get("SKIP_BQ") == "1":
            bq = bq2 = qr = None
        else:
            bq = apply_battle_quotes(rom, game, bdir, _CMAP_STORE.get(game, {}))
            bq2 = None if os.environ.get("SKIP_BQ2") == "1" else apply_battle_quotes_other(rom, game, bdir, _CMAP_STORE.get(game, {}))
            qr = None if os.environ.get("SKIP_QR") == "1" else apply_quote_ref_fix(rom, game, bdir)
        nc = apply_name_copy_e0(rom, game) if on("NAMECOPY") else None
        tf = apply_table_fixes(rom, game, bdir, _CMAP_STORE.get(game, {})) if on("TABLEFIX") else None
        sk = apply_skill_name_fix(rom, game, _CMAP_STORE.get(game, {})) if on("SKILLNAME") else None
        sc = apply_stage_clear_messages(rom, game, bdir, _CMAP_STORE.get(game, {})) if on("STAGECLEAR") else None
        rt = restore_ui_pointer_table(rom, game) if on("RESTOREUI") else None
        mi = apply_miracle_text(rom, game, bdir, _CMAP_STORE.get(game, {})) if on("MIRACLE") else None
        nf = apply_name_string_fixes(rom, game, bdir, _CMAP_STORE.get(game, {})) if on("NAMEFIX") else None
        ex = apply_pinned_names(rom, game, bdir) if on("NAMEFIX") else None
        ml = apply_menu_label_spacing(rom, game, bdir, _CMAP_STORE.get(game, {})) if on("MENULABEL") else None
        ln = apply_long_name_macros(rom, game, bdir, _CMAP_STORE.get(game, {})) if on("LONGNAME") else None
        fafb = apply_fa_fb(rom, game, bdir, src_book) if on("FAFB") else None
        ll = apply_stage_last_label(rom, game, bdir, _CMAP_STORE.get(game, {})) if on("STAGELAST") else None
        out.write_bytes(rom)
        crc = zlib.crc32(rom) & 0xFFFFFFFF
        print("F1", game, "CRC %08X" % crc, info["slots"], info["table"])
        if wf1:
            print("WF1", game, wf1)
        print("GPF1", game, gp)
        print("CLEAR", game, cl)
        if sl:
            print("STAGELOC", game, sl)
        if bq:
            print("BQ", game, bq)
        if bq2:
            print("BQ2", game, bq2)
        if qr:
            print("QUOTEREF", game, qr)
        if nc:
            print("NAMECOPY", game, "F0->E0 x4")
        print("TABLEFIX", game, tf)
        print("SKILLNAME", game, sk)
        if sc:
            print("STAGECLEAR", game, sc)
        print("MIRACLE", game, mi)
        print("NAMEFIX", game, nf)
        print("MENULABEL", game, ml)
        print("LONGNAME", game, ln)
        print("FAFB", game, fafb)
        if fafb:
            sep = chr(9)
            eol = chr(10)
            with open(outdir / "FAFB表.txt", "w", encoding="utf-8") as f:
                f.write(sep.join(["FB号", "宏号", "名称", "宽", "格数", "名称表改指"]) + eol)
                for i, (mid, text, w, cells, hits) in enumerate(fafb["items"]):
                    f.write(sep.join(["%02X" % i, mid, text, str(w), str(cells), str(hits)]) + eol)
                f.write("# FB体结束 %s, handler %dB" % (fafb["fb_body_end"], fafb["handler"]) + eol)
        print("STAGELAST", game, ll)
        print("PINNED", game, ex)
        for row in info["names"]:
            print("   ", row[:5])
        with open(outdir / "F1字号表.txt", "w", encoding="utf-8") as f:
            f.write("宏\t名称\t字\t字体\t字号\t目标宽\t自然宽\t调整\t起始X\n")
            for label, text, width, ncells, sizes, char_info in info["names"]:
                f.write(f"# {label}\t{text}\t总宽={width}px\t块数={ncells}\n")
                for ch, target, natural, delta, x in char_info:
                    f.write(f"{label}\t{text}\t{ch}\tWenQuanYi 9pt\t12px\t{target}\t{natural}\t{delta:+d}\t{x}\n")
