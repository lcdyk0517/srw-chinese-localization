import struct, re

# 这 9 行原先用单元格内换行强制断行；现改用 / 并在此登记，保留原断点。
FORCE_SLASH = {
    ("剧情_15", 183), ("剧情_16", 1030), ("剧情_16", 1613), ("剧情_16", 1622),
    ("剧情_13", 738), ("剧情_13", 1326), ("剧情_16", 959), ("剧情_16", 1141),
}

# 原版载入器 2 的索引→(bank, table_base) 映射。翻译段只覆盖工作簿里的
# 区间，其余索引仍必须走原版 bank/table；缺口会让 loader 找不到段而反复
# 重入（结束阶段/事件处白屏）。fallback 段直接指回这些原始表。
ORIG_LOADER2 = {
    # bank 值是物理 bank（6 位）；表项打包时会 |0xC0，得到原版 AL=0xD3..0xFB。
    "1": [(0x0000, 0x0600, 0x13, 0x0000), (0x0600, 0x2000, 0x14, 0x0600),
          (0x2000, 0x2700, 0x15, 0x2000), (0x2700, 0x4000, 0x16, 0x2700),
          (0x4000, 0xFFFF, 0x17, 0x4000)],
    "2": [(0x0000, 0x0600, 0x13, 0x0000), (0x0600, 0x2000, 0x14, 0x0600),
          (0x2000, 0x2700, 0x15, 0x2000), (0x2700, 0x2E80, 0x16, 0x2700),
          (0x2E80, 0x4000, 0x17, 0x2E80), (0x4000, 0xFFFF, 0x18, 0x4000)],
    "3": [(0x0000, 0x0600, 0x13, 0x0000), (0x0600, 0x0C00, 0x14, 0x0600),
          (0x0C00, 0x2000, 0x3B, 0x0C00), (0x2000, 0x2880, 0x15, 0x2000),
          (0x2880, 0x3100, 0x16, 0x2880), (0x3100, 0x3980, 0x17, 0x3100),
          (0x3980, 0x4000, 0x18, 0x3980), (0x4000, 0xFFFF, 0x1A, 0x4000)],
}

# 不允许出现在第二行行首的标点（行首标点必须留在上一行）
_BAD_LINE_START = set("、。，．！？」』）】》〉!?,.;:・")
# 这些开引号/括号不能留在第一行行尾
_BAD_LINE_END = set("「『（(《〈")
_DASH_RUN = set("…‥—―─")

def _split_ok(text, i):
    if i <= 0 or i >= len(text):
        return False
    if text[i] in _BAD_LINE_START:
        return False
    if text[i-1] in _BAD_LINE_END:
        return False
    if text[i-1] in _DASH_RUN and text[i] in _DASH_RUN:
        return False
    if text[i] in _DASH_RUN and text[i] in "…‥" and text[i-1] == text[i]:
        return False
    # 第二行不能只有标点
    if all(ch in _BAD_LINE_START for ch in text[i:] if not ch.isspace()):
        return False
    return True

def _reflow_two(raw, cmap, mod, lead, force_break=False):
    """剧情硬规则：最多一次换行（两行）。合并原译文所有 /，再按宽度找切点。
    force_break=True 时优先保留原译文的 /（分支选项/原文单 FE 行），
    即使合成一行也放得下也不合并。返回 None 表示两行放不下，构建必须报错。"""
    explicit_break = "\n" in str(raw)
    plain = re.sub(r"\s+", "", str(raw).replace("\r", "").replace("\n", "/").replace("／", "/"))
    if explicit_break:
        force_break = True
    if force_break and "/" in plain:
        parts = [p.strip() for p in plain.split("/") if p.strip()]
        splits = []
        for k in range(1, len(parts)):
            splits.append((abs(k - len(parts) / 2), "".join(parts[:k]) + "/" + "".join(parts[k:])))
        splits.sort(key=lambda x: x[0])
        for _, text in splits:
            pos = text.find("/")
            if pos > 0 and _split_ok(text, pos + 1) and not too_wide(text, cmap, mod, lead):
                return text
    plain = plain.replace("/", "")
    if not too_wide(plain, cmap, mod, lead):
        return plain
    chars = list(plain)
    depth = 0
    cand = []
    for i in range(1, len(chars)):
        ch = chars[i - 1]
        if ch == "{":
            depth = 1
        elif ch == "}":
            depth = 0
        if depth:
            continue
        score = 2 if ch in "、，。！？…」）!?," else (1 if ch == " " else 0)
        cand.append((i, score))
    cand.sort(key=lambda x: (-x[1], abs(x[0] - len(chars) / 2)))
    fallback = None
    for i, _ in cand:
        text = plain[:i] + "/" + plain[i:]
        if not too_wide(text, cmap, mod, lead):
            if _split_ok(plain, i):
                return text
            if fallback is None:
                fallback = text
    # 两行宽度卡死时退回旧行为，避免构建中断；这类行由审计清单人工核对
    return fallback


def repack_story_crossbank(rom, orig, mod, cfg, key, text_path, sheets, cmap, stats):
    """Repack every story bank into 16-bit tables + free-bank chunks.

    Each segment maps a global line index range to (bank, table offset,
    local-index base).  The story loaders call a table-driven cave instead of
    their hardcoded 64 KB range checks; strings can therefore live anywhere.
    """
    xc = STORY_XCFG[key]
    flash = 0x3F0000

    def align2(x):
        return (x + 1) & ~1

    def scan_runs(banks):
        out = []
        for b in banks:
            b0 = b * 0x10000
            i = 0
            while i < 0x10000:
                if rom[b0 + i] == 0xFF:
                    j = i
                    while j < 0x10000 and rom[b0 + j] == 0xFF:
                        j += 1
                    if j - i >= 0x100:
                        out.append({"bank": b, "start": i, "end": j, "cur": i})
                    i = j
                else:
                    i += 1
        out.sort(key=lambda r: (r["bank"], r["start"]))
        return out

    runs = scan_runs(xc["free_banks"])

    def pack_range(entries, start, count, table_off, data_start, cap_end):
        table, seen, items = {}, {}, []
        pos = data_start
        last = start
        for idx in range(start, count):
            d = entries[idx]
            if d in seen:
                table[idx] = seen[d]
                last = idx + 1
                continue
            if pos + len(d) > cap_end:
                break
            seen[d] = pos
            table[idx] = pos
            items.append((pos, d))
            pos += len(d)
            last = idx + 1
        return table, items, last, pos

    def write_chunk(bank, table_off, start, table, items):
        b0 = bank * 0x10000
        for idx, off in table.items():
            p = b0 + table_off + (idx - start) * 2
            rom[p:p + 2] = off.to_bytes(2, "little")
        for off, d in items:
            rom[b0 + off:b0 + off + len(d)] = d

    segs = {1: [], 2: []}

    def add_segments(loader, bank, cs, ce, table_off, ranges):
        for g0, l0, l1 in ranges:
            a = max(cs, l0)
            b = min(ce, l1)
            if a >= b:
                continue
            gs = g0 + (a - l0)
            ge = g0 + (b - l0)
            segs[loader].append((gs, ge, bank, table_off, a - cs))

    no_inplace = set(xc.get("no_inplace", []))
    for bank, ranges in xc["banks"].items():
        sn = "剧情_%02X" % bank
        s = next((x for x in sheets if x["sheet"] == sn), None)
        if s is None:
            continue
        loader = 1 if bank in (0x05, 0x06, 0x07) else 2
        count = s["count"]
        rows = dict(s["rows"])
        ptrs = [int.from_bytes(orig[s["base"] + 2 * i:s["base"] + 2 * i + 2], "little")
                for i in range(count)]
        entries = []
        for idx in range(count):
            old = ptrs[idx]
            if idx in rows:
                lead = 0
                if 0 < old < 0x10000:
                    p = s["base"] + old
                    while p + lead < s["base"] + 0x10000 and orig[p + lead] == 0:
                        lead += 1
                jp_fe_alone = False
                if 0 < old < 0x10000:
                    je = orig.find(b"\xFF", s["base"] + old,
                                   min(s["base"] + old + 400, s["base"] + 0x10000))
                    if je >= 0:
                        jb = orig[s["base"] + old:je]
                        jp_fe_alone = any(
                            b == 0xFE and (k + 1 >= len(jb) or jb[k + 1] != 0)
                            for k, b in enumerate(jb))
                text = _reflow_two(rows[idx], cmap, mod, lead,
                                   force_break=jp_fe_alone or (sn, idx) in FORCE_SLASH)
                if text is None:
                    stats.setdefault("p0_fail", []).append((sn, idx, str(rows[idx])))
                    text = str(rows[idx]).replace("／", "/")
                if too_wide(text, cmap, mod, lead):
                    stats.setdefault("wide", []).append((sn, idx, text))
                enc, missing = mod.encode(text, cmap, newline_blank=True)
                if missing:
                    stats["missing"].extend(missing)
                    enc = b"\xFF"
                if lead and not enc.startswith(b"\x00" * lead):
                    enc = b"\x00" * lead + enc
                jp_fe = 0
                if 0 < old < 0x10000:
                    oe = orig.find(b"\xFF", s["base"] + old,
                                   min(s["base"] + old + 400, s["base"] + 0x10000))
                    if oe >= 0:
                        jp_fe = orig[s["base"] + old:oe].count(0xFE)
                cn_fe = enc.count(0xFE)
                if cn_fe > jp_fe:
                    with open(str(__import__("pathlib").Path(__file__).resolve().parent.parent /
                                  ("analysis/fe_over_%s.txt" % key)), "a", encoding="utf-8") as ff:
                        ff.write("%s\t%d\t%d\t%d\t%s\n" % (sn, idx, jp_fe, cn_fe,
                                 str(rows[idx]).replace("\t", " ")))
                entries.append(enc + b"\xFF")
            elif 0 < old < 0x10000:
                e = orig.find(b"\xFF", s["base"] + old,
                              min(s["base"] + old + 400, s["base"] + 0x10000))
                entries.append(orig[s["base"] + old:e + 1] if e >= 0 else b"\xFF")
            else:
                entries.append(b"\xFF")

        table_size = count * 2
        if bank in no_inplace:
            # bank3B/18 等还包含非剧情数据（F1 宏体、事件表），不能原地写表，
            # 全部改放到 free_banks。
            start = 0
        else:
            data_start = max(0x2000, align2(table_size))
            table, items, last, pos = pack_range(entries, 0, count, 0, data_start, 0x10000)
            write_chunk(bank, 0, 0, table, items)
            add_segments(loader, bank, 0, last, 0, ranges)
            start = last
        while start < count:
            tsize = align2((count - start) * 2)
            placed = False
            for r in runs:
                if r["cur"] + tsize + 2 > r["end"]:
                    continue
                toff = r["cur"]
                dstart = align2(toff + tsize)
                if dstart >= r["end"]:
                    continue
                table, items, last, pos = pack_range(entries, start, count, toff, dstart, r["end"])
                if last == start:
                    continue
                write_chunk(r["bank"], toff, start, table, items)
                add_segments(loader, r["bank"], start, last, toff, ranges)
                r["cur"] = align2(pos)
                start = last
                placed = True
                break
            if not placed:
                raise RuntimeError("story xbank: no free run for %s at %d" % (sn, start))
        stats["story"][sn] = len(rows)
        stats.setdefault("inplace", {})[sn] = 0
        stats.setdefault("dedup", {})[sn] = 0

    # D3 的 bank3B（0x0C00-0x0E28，552 行结局）和 bank18（0x3880-0x3A70，
    # 496 行最终章）现已作为 剧情_3B / 剧情_18 工作表参与统一重打包，
    # 不再在这里手写直通段。

    # 载入器 2 还负责非剧情文本：D2 的 bank18、D3 的 bank1A 是道具/奖励表。
    # 这些索引从 0x4000 起，剧情段未覆盖时必须回落到原表，否则会落到
    # 剧情段兜底的 bank05 第 0 条（通关奖励会全部显示成第一句台词）。
    # D1 的道具串已并入剧情_17，随剧情段重排；D2/D3 的道具表不在剧情工作簿里。
    item_bank = {"1": None, "2": 0x18, "3": 0x1A}[key]
    if item_bank is not None:
        segs[2].append((0x4000, 0xFFFF, item_bank, 0, 0))

    # 用原版 loader2 映射补齐未翻译的索引区间；这些区间不在工作簿里，
    # 但不能留空，否则载入器会找不到段并反复重入（阶段结束白屏）。
    covered = sorted((a, b) for a, b, _, _, _ in segs[2])
    for oa, ob, obank, obase in ORIG_LOADER2[key]:
        cur = oa
        for ca, cb in covered:
            if cb <= cur or ca >= ob:
                continue
            if ca > cur:
                x, y = cur, min(ca, ob)
                segs[2].append((x, y, obank, 0, x - obase))
            cur = max(cur, cb)
            if cur >= ob:
                break
        if cur < ob:
            segs[2].append((cur, ob, obank, 0, cur - obase))

    def table_bytes(seglist):
        out = bytearray()
        for a, b, bank, toff, tbase in sorted(seglist):
            out += struct.pack("<HHBBHH", a, b, 0xC0 | bank, 0, toff, tbase)
        out += struct.pack("<HHBBHH", 0xFFFF, 0, 0, 0, 0, 0)
        return bytes(out)

    t1 = table_bytes(segs[1])
    t2 = table_bytes(segs[2])
    rom[flash + xc["cave"]:flash + xc["cave"] + len(STORY_XCAVE)] = STORY_XCAVE
    rom[flash + xc["loaders"][1]["tab"]:flash + xc["loaders"][1]["tab"] + len(t1)] = t1
    rom[flash + xc["loaders"][2]["tab"]:flash + xc["loaders"][2]["tab"] + len(t2)] = t2

    for n in (1, 2):
        d = xc["loaders"][n]
        addr, epi, tab = d["patch"], d["epi"], d["tab"]
        mov = b"\xBE" + tab.to_bytes(2, "little")
        rel = (xc["cave"] - (addr + 6)) & 0xFFFF
        call = b"\xE8" + rel.to_bytes(2, "little")
        jmp = b"\xE9" + ((epi - (addr + 9)) & 0xFFFF).to_bytes(2, "little")
        code = mov + call + jmp
        rom[addr:epi] = code + b"\x90" * ((epi - addr) - len(code))
    stats["story_xbank"] = {"segments1": len(segs[1]), "segments2": len(segs[2]),
                            "t1": len(t1), "t2": len(t2)}
    if stats.get("p0_fail"):
        from pathlib import Path as _P
        out = _P(__file__).resolve().parent.parent / "analysis" / ("p0_fail_%s.txt" % key)
        with open(out, "w", encoding="utf-8") as f:
            for sn, idx, txt in stats["p0_fail"]:
                f.write("%s\t%d\t%s\n" % (sn, idx, txt.replace("\t", " ")))
        raise RuntimeError("P0 剧情两行放不下 %d 条，清单: %s" % (len(stats["p0_fail"]), out))
