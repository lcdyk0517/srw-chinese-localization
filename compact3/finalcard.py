# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-only
"""最终话标题卡：从 assets/img/final-card-text-*.png 生成两块 LZSS 图块并写回 ROM。

两块结构：+0 word 0xC000、+2 word 0x0800、+4 起 LZSS 流，解压 0x800 字节。
line1 图块基号 0x120，line2 基号 0x160；只改文字单元。
"""
from __future__ import annotations
import json
import struct
from pathlib import Path
import numpy as np
from PIL import Image
from titleimg import _decode, _encode

SPECS = (
    ("final-card-line1", 0x732F87, 0x120),
    ("final-card-line2", 0x732D3C, 0x160),
)


def _nearest(rgb):
    # 卡面文字只有白色填充 + 青色描边（调色板 8 的 1/2 号）
    r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
    d_white = (r - 255) ** 2 + (g - 255) ** 2 + (b - 255) ** 2
    d_cyan = (r - 34) ** 2 + (g - 204) ** 2 + (b - 238) ** 2
    return 1 if d_white <= d_cyan else 2


def _apply_line(rom: bytearray, img_dir: Path, name: str, off: int, first_tile: int) -> dict | None:
    cells_dir = img_dir.parent / "cells"
    meta = json.loads((cells_dir / f"{name}.cells.json").read_text(encoding="utf-8"))
    block = meta["block"]
    length = int(block["header_len"], 16)
    limit = int(block["max_compressed"], 16)
    cells = [(int(r[0]), int(r[1]), int(r[2])) for r in meta["cells"]]

    png = img_dir / "final-card-text-cn.png"
    source = "cn"
    if not png.is_file():
        png = img_dir / "final-card-text-jp.png"
        source = "jp"
    if not png.is_file():
        return None
    if source == "jp":
        return {"source": "jp", "file": png.name, "patched": False}

    if struct.unpack_from("<H", rom, off)[0] != 0xC000 or struct.unpack_from("<H", rom, off + 2)[0] != length:
        raise ValueError(f"{name}: 卡片头不符")

    mem = bytearray(0x10000)
    _decode(bytes(rom[off + 4:off + 4 + 0x400]), 0x8000, length, mem)
    old = bytes(mem[0x8000:0x8000 + length])

    layer = np.array(Image.open(png).convert("RGBA"))
    buf = bytearray(old)
    for x, y, ts in cells:
        rel = (ts - first_tile) * 32
        if not 0 <= rel <= length - 32:
            raise ValueError(f"{name}: 图块 {ts:#x} 不在块内")
        buf[rel:rel + 32] = b"\0" * 32
        for r in range(8):
            b = [0, 0, 0, 0]
            for xx in range(8):
                if layer[y + r, x + xx, 3]:
                    v = _nearest(layer[y + r, x + xx, :3])
                    s = 7 - xx
                    for k in range(4):
                        if (v >> k) & 1:
                            b[k] |= 1 << s
            buf[rel + r * 4:rel + r * 4 + 4] = bytes(b)

    blob = _encode(bytes(buf))
    if len(blob) > limit:
        raise ValueError(f"{name}: 重压后 {len(blob):#x} 超过上限 {limit:#x}")
    rom[off + 4:off + 4 + len(blob)] = blob
    if name.endswith("line1"):
        rom[off + 4 + len(blob):off + 4 + limit] = b"\0" * (limit - len(blob))

    check = bytearray(0x10000)
    _decode(bytes(rom[off + 4:off + 4 + len(blob)]), 0x8000, length, check)
    if bytes(check[0x8000:0x8000 + length]) != bytes(buf):
        raise ValueError(f"{name}: 写回后解压校验失败")
    return {"source": "cn", "file": png.name, "compressed": f"0x{len(blob):X}",
            "limit": f"0x{limit:X}", "cells": len(cells), "patched": True}


def apply_final_card(rom: bytearray, img_dir: Path) -> dict:
    out = {}
    for name, off, first in SPECS:
        r = _apply_line(rom, img_dir, name, off, first)
        if r:
            out[name] = r
    return out
