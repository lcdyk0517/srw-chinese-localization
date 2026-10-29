# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-only
"""标题画面文字图块：从 assets/img 的 PNG 生成并写回 ROM。

工作方式：
  * assets/img/<名字>.png      优先使用（汉化后的图）
  * assets/img/<名字>.png.bak  没有 .png 时使用（原始未汉化图）
  * 每张图对应 assets/cells/<名字>.cells.json，记录目标压缩块和 OAM 单元（x,y,图块号,调色板）。
只改文字单元；图块重压后必须不超过 max_compressed，否则构建报错。
"""
from __future__ import annotations
import json
import struct
from collections import Counter
from pathlib import Path
import numpy as np
from PIL import Image

PALETTE_AT = 0x51F130
TEXT_PALETTES = (10, 11, 12)


def _decode(src: bytes, dest_start: int, length: int, mem: bytearray) -> int:
    bx = 0
    di = dest_start
    bp = (dest_start + length) & 0xFFFF
    se = src + b"\0" * 16
    while True:
        ch = se[bx]; bx += 1; cl = 9
        while True:
            cl = (cl - 1) & 0xFF
            if cl == 0:
                ch = se[bx]; bx += 1; cl = 8
            carry = ch & 1; ch >>= 1
            if carry:
                mem[di] = se[bx]; bx += 1; di = (di + 1) & 0xFFFF
                if not (di < bp):
                    return bx
            else:
                tok = se[bx] | (se[bx + 1] << 8); bx += 2
                dh = ((tok & 0xF) + 3) & 0xFF
                si = (di - (tok >> 4)) & 0xFFFF
                if si >= dest_start:
                    while True:
                        mem[di] = mem[si]; si = (si + 1) & 0xFFFF; di = (di + 1) & 0xFFFF
                        dh = (dh - 1) & 0xFF
                        if dh == 0:
                            break
                    if not (di < bp):
                        return bx
                else:
                    dl = (-(si & 0xFF)) & 0x1F
                    while True:
                        mem[di] = 0; di = (di + 1) & 0xFFFF; si = (si + 1) & 0xFFFF
                        if si >= dest_start:
                            while True:
                                dh = (dh - 1) & 0xFF
                                if dh == 0:
                                    break
                                mem[di] = mem[si]; si = (si + 1) & 0xFFFF; di = (di + 1) & 0xFFFF
                            break
                        dh = (dh - 1) & 0xFF
                        if dh == 0:
                            break
                        dl = (dl - 1) & 0xFF
                        if dl != 0:
                            continue
                        si = dest_start
                        while True:
                            mem[di] = mem[si]; si = (si + 1) & 0xFFFF; di = (di + 1) & 0xFFFF
                            dh = (dh - 1) & 0xFF
                            if dh == 0:
                                break
                        break
                    if not (di < bp):
                        return bx


def _encode(data: bytes, max_dist=0xFFF, max_len=18, min_len=3) -> bytes:
    """动态规划最优解析；控制位 LSB 在前：1=原字节，0=令牌。"""
    n = len(data)
    index = {}
    for p in range(n - 2):
        index.setdefault(data[p:p + 3], []).append(p)
    opts = [None] * n
    for p in range(n):
        key = data[p:p + 3]
        cur = []
        if len(key) == 3:
            limit = min(max_len, n - p)
            lens = [0] * (limit + 1)
            for q in reversed(index.get(key, ())):
                if q >= p:
                    continue
                dist = p - q
                if dist > max_dist:
                    break
                ln = 0
                while ln < limit and data[q + ln] == data[p + ln]:
                    ln += 1
                for L in range(min_len, ln + 1):
                    if lens[L] == 0:
                        lens[L] = dist
            cur = [(L, lens[L]) for L in range(min_len, limit + 1) if lens[L]]
        opts[p] = cur
    INF = 1 << 30
    cost = [INF] * (n + 1)
    choice = [None] * n
    cost[n] = 0
    for p in range(n - 1, -1, -1):
        c = 9 + cost[p + 1]
        ch = (1,)
        for L, dist in opts[p]:
            v = 17 + cost[p + L]
            if v < c:
                c = v; ch = (0, L, dist)
        cost[p] = c; choice[p] = ch
    out = bytearray(); pos = 0
    while pos < n:
        ctrl_pos = len(out); out.append(0); ctrl = 0
        for bit in range(8):
            if pos >= n:
                break
            ch = choice[pos]
            if ch[0] == 1:
                ctrl |= 1 << bit
                out.append(data[pos]); pos += 1
            else:
                _, L, dist = ch
                tok = (dist << 4) | (L - 3)
                out += bytes((tok & 0xFF, tok >> 8))
                pos += L
        out[ctrl_pos] = ctrl
    return bytes(out)


def _palettes(rom: bytes):
    pal = {}
    for pi in range(16):
        cols = []
        for j in range(16):
            lo = rom[PALETTE_AT + (pi * 16 + j) * 2]
            hi = rom[PALETTE_AT + (pi * 16 + j) * 2 + 1]
            cols.append(((hi & 0xF) * 17, ((lo >> 4) & 0xF) * 17, (lo & 0xF) * 17))
        pal[pi] = np.array(cols, dtype=int)
    return pal


def _set_tile(buf: bytearray, base: int, ts: int, px: np.ndarray, tile_base: int = 0x4000):
    off = (tile_base + ts * 32) - base
    if not 0 <= off <= len(buf) - 32:
        raise ValueError(f"tile {ts} outside block (offset {off:#x})")
    for row in range(8):
        b = [0, 0, 0, 0]
        for x in range(8):
            v = int(px[row, x]); s = 7 - x
            for k in range(4):
                if (v >> k) & 1:
                    b[k] |= 1 << s
        buf[off + row * 4:off + row * 4 + 4] = bytes(b)


def _get_index(buf: bytes, base: int, ts: int, tile_base: int, yy: int, xx: int) -> int:
    off = (tile_base + ts * 32) - base
    b = buf[off + yy * 4:off + yy * 4 + 4]
    s = 7 - xx
    return ((b[0] >> s) & 1) | (((b[1] >> s) & 1) << 1) |            (((b[2] >> s) & 1) << 2) | (((b[3] >> s) & 1) << 3)


def _nearest(rgb, pal):
    d = ((pal - rgb) ** 2).sum(axis=1)
    d[0] = 10 ** 9
    return int(d.argmin())


def _same_colors(a: bytes, b: bytes, base: int, cells, pal, tile_base: int = 0x4000, zero_is_black: bool = False) -> bool:
    """比较两块图块在各自 OAM 调色板下渲染出的颜色（允许同色索引不同）。"""
    for _x, _y, ts, pi, *_rest in cells:
        off = (tile_base + ts * 32) - base
        for row in range(8):
            ba = a[off + row * 4:off + row * 4 + 4]
            bb = b[off + row * 4:off + row * 4 + 4]
            for xx in range(8):
                s = 7 - xx
                va = ((ba[0] >> s) & 1) | (((ba[1] >> s) & 1) << 1) | \
                     (((ba[2] >> s) & 1) << 2) | (((ba[3] >> s) & 1) << 3)
                vb = ((bb[0] >> s) & 1) | (((bb[1] >> s) & 1) << 1) | \
                     (((bb[2] >> s) & 1) << 2) | (((bb[3] >> s) & 1) << 3)
                ca = (0, 0, 0) if (va == 0 and zero_is_black) else (
                    None if va == 0 else tuple(pal[pi][va]))
                cb = (0, 0, 0) if (vb == 0 and zero_is_black) else (
                    None if vb == 0 else tuple(pal[pi][vb]))
                if ca != cb:
                    return False
    return True


def _apply_one(rom: bytearray, img_dir: Path, name: str) -> dict:
    cells_dir = img_dir.parent / "cells"
    meta = json.loads((cells_dir / f"{name}.cells.json").read_text(encoding="utf-8"))
    block = meta["block"]
    off = int(block["rom_offset"], 16)
    dest = int(block["dest"], 16)
    length = int(block["header_len"], 16)
    limit = int(block["max_compressed"], 16)
    tile_base = int(block.get("tile_base", "0x4000"), 16)
    transparent_black = bool(block.get("transparent_black", False))
    mode = block.get("mode", "normal")
    cells = []
    for row in meta["cells"]:
        cells.append((int(row[0]), int(row[1]), int(row[2]), int(row[3]),
                      int(row[4]) if len(row) > 4 else 0,
                      int(row[5]) if len(row) > 5 else 0))
    alt_cells = []
    for row in meta.get("alt_cells", []):
        alt_cells.append((int(row[0]), int(row[1]), int(row[2]), int(row[3]),
                          int(row[4]) if len(row) > 4 else 0,
                          int(row[5]) if len(row) > 5 else 0))
    fixed = [(int(r[0]), int(r[1])) for r in meta.get("fixed", [])]

    png = img_dir / f"{name}-cn.png"
    source = "cn"
    if not png.is_file():
        png = img_dir / f"{name}-jp.png"
        source = "jp"
    if not png.is_file():
        raise ValueError(f"图片素材缺失：{name}-cn.png / {name}-jp.png")

    hdr = struct.unpack_from("<H", rom, off - 2)[0]
    if hdr != length:
        raise ValueError(f"{name}: 头部长度不符 {hdr:#x} != {length:#x}")

    mem = bytearray(0x10000)
    _decode(bytes(rom[off:off + limit + 0x100]), dest, length, mem)
    old = bytes(mem[dest:dest + length])

    layer = np.array(Image.open(png).convert("RGBA"))
    use_cells = cells if mode == "delta" else (cells + alt_cells)
    allxy = [(x, y) for x, y, *_ in use_cells] + fixed
    maxy = max(y for _, y in allxy) + 8
    maxx = max(x for x, _ in allxy) + 8
    if layer.shape[0] < maxy or layer.shape[1] < maxx:
        pad = np.zeros((max(maxy, layer.shape[0]), max(maxx, layer.shape[1]), 4), np.uint8)
        pad[:layer.shape[0], :layer.shape[1]] = layer
        layer = pad

    if mode == "normal":
        covered = np.zeros(layer.shape[:2], bool)
        for x, y in allxy:
            covered[y:y + 8, x:x + 8] = True
        miss = (layer[:, :, 3] > 0) & ~covered
        if miss.any():
            ys, xs = np.where(miss)
            raise ValueError(f"{name}: {len(xs)} 个像素落在 OAM 单元外，例 ({xs[0]},{ys[0]})")

    if source == "cn" and fixed:
        jp = img_dir / f"{name}-jp.png"
        if not jp.is_file():
            raise ValueError(f"{name}: 有 fixed 单元时必须保留 {name}-jp.png 作为对照")
        jl = np.array(Image.open(jp).convert("RGBA"))
        for x, y in fixed:
            if not np.array_equal(layer[y:y + 8, x:x + 8], jl[y:y + 8, x:x + 8]):
                raise ValueError(f"{name}: fixed 单元 ({x},{y}) 不允许修改（该处图块不在本块内）")

    pal = _palettes(rom)
    counts = Counter(ts for _x, _y, ts, _pi, _fh, _fv in cells)
    tiles = {}
    if mode == "delta":
        jp_path = img_dir / block.get("jp_ref", f"{name}-jp.png")
        fire_path = img_dir / block.get("fire_ref", "")
        if not jp_path.is_file():
            raise ValueError(f"{name}: delta 模式需要 {jp_path.name}")
        jp = np.array(Image.open(jp_path).convert("RGB"))
        fire = np.array(Image.open(fire_path).convert("RGB")) if fire_path.is_file() else None
        cn = layer[:, :, :3]
        for x, y, ts, pi, fh, fv in cells:
            if counts[ts] > 1:
                continue
            tile = np.zeros((8, 8), int)
            for yy in range(8):
                for xx in range(8):
                    yt = 7 - yy if fv else yy
                    xt = 7 - xx if fh else xx
                    cp = cn[y + yy, x + xx]
                    if np.array_equal(cp, jp[y + yy, x + xx]):
                        tile[yt, xt] = _get_index(old, dest, ts, tile_base, yt, xt)
                    elif fire is not None and np.array_equal(cp, fire[y + yy, x + xx]):
                        tile[yt, xt] = 0
                    else:
                        tile[yt, xt] = _nearest(cp, pal[pi])
            tiles[ts] = tile
    else:
        for x, y, ts, pi, fh, fv in use_cells:
            sub = layer[y:y + 8, x:x + 8, :]
            if fh:
                sub = sub[:, ::-1]
            if fv:
                sub = sub[::-1, :]
            tile = np.zeros((8, 8), int)
            for yy in range(8):
                for xx in range(8):
                    if sub[yy, xx, 3]:
                        rgb = sub[yy, xx, :3]
                        if transparent_black and rgb[0] == 0 and rgb[1] == 0 and rgb[2] == 0:
                            tile[yy, xx] = 0
                        else:
                            tile[yy, xx] = _nearest(rgb, pal[pi])
            if ts in tiles and not np.array_equal(tiles[ts], tile):
                raise ValueError(f"{name}: 图块 {ts} 在两个布局里内容不同")
            tiles[ts] = tile

    buf = bytearray(old)
    for ts in tiles:
        _set_tile(buf, dest, ts, np.zeros((8, 8), int), tile_base)
    for ts, tile in tiles.items():
        _set_tile(buf, dest, ts, tile, tile_base)

    if source == "jp":
        if not _same_colors(old, bytes(buf), dest, cells, pal, tile_base, transparent_black):
            raise ValueError(f"{name}: 原始 -jp 图与 ROM 图块不一致（素材与 ROM 不同版本）")
        return {"source": "jp", "file": png.name, "compressed": "-",
                "limit": f"0x{limit:X}", "cells": len(cells), "patched": False}

    blob = _encode(bytes(buf))
    if len(blob) > limit:
        raise ValueError(f"{name}: 重压后 {len(blob):#x} 超过上限 {limit:#x}")
    rom[off:off + len(blob)] = blob

    check = bytearray(0x10000)
    _decode(bytes(rom[off:off + len(blob)]), dest, length, check)
    if bytes(check[dest:dest + length]) != bytes(buf):
        raise ValueError(f"{name}: 写回后解压校验失败")

    return {"source": "cn", "file": png.name, "compressed": f"0x{len(blob):X}",
            "limit": f"0x{limit:X}", "cells": len(cells),
            "shared_kept": sum(1 for t in counts if counts[t] > 1), "patched": True}


def apply_title_graphics(rom: bytearray, img_dir: Path) -> dict:
    if not img_dir.is_dir():
        return {}
    out = {}
    for name in ("title-bg",):
        if (img_dir.parent / "cells" / f"{name}.cells.json").is_file():
            out[name] = _apply_one(rom, img_dir, name)
    return out
