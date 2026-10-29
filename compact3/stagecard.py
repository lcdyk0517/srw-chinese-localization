# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-only
"""第二话标题卡第二行：56x16 图片 -> 7x2 图块 -> LZSS 写回 0x730A02。

块结构：+0 word 0x1400，+2 起 LZSS，解压 0x1400；图块基号 0x160。
"""
from __future__ import annotations
import json
import struct
from pathlib import Path
import numpy as np
from PIL import Image
from titleimg import _decode, _encode

OFF = 0x730A02
LEN = 0x1400
BASE = 0x160


def _nearest(rgb):
    r, g, b = int(rgb[0]), int(rgb[1]), int(rgb[2])
    d_white = (r - 255) ** 2 + (g - 255) ** 2 + (b - 255) ** 2
    d_cyan = (r - 34) ** 2 + (g - 204) ** 2 + (b - 238) ** 2
    return 1 if d_white <= d_cyan else 2


def apply_stage2_title(rom: bytearray, img_dir: Path) -> dict | None:
    png = img_dir / "stage2-title-cn.png"
    source = "cn"
    if not png.is_file():
        png = img_dir / "stage2-title-jp.png"
        source = "jp"
    if not png.is_file():
        return None
    if source == "jp":
        return {"source": "jp", "file": png.name, "patched": False}
    cells_dir = img_dir.parent / "cells"
    meta = json.loads((cells_dir / "stage2-title.cells.json").read_text(encoding="utf-8"))
    block = meta["block"]
    limit = int(block["max_compressed"], 16)
    top = [int(v) for v in meta["top"]]
    bottom = [int(v) for v in meta["bottom"]]
    img = np.array(Image.open(png).convert("RGBA"))
    if img.shape[0] < 16 or img.shape[1] < 56:
        raise ValueError("stage2-title-cn.png 必须是 56x16")

    if struct.unpack_from("<H", rom, OFF)[0] != LEN:
        raise ValueError("stage2 title block header mismatch")
    mem = bytearray(0x8000 + LEN + 0x100)
    _decode(bytes(rom[OFF + 2:OFF + 2 + 0x4000]), 0x8000, LEN, mem)
    buf = bytearray(mem[0x8000:0x8000 + LEN])
    for row, tiles in ((0, top), (1, bottom)):
        for col, ts in enumerate(tiles):
            off = (ts - BASE) * 32
            for yy in range(8):
                b = [0, 0, 0, 0]
                for xx in range(8):
                    px = img[row * 8 + yy, col * 8 + xx]
                    if px[3]:
                        v = _nearest(px[:3]); s = 7 - xx
                        for k in range(4):
                            if (v >> k) & 1: b[k] |= 1 << s
                buf[off + yy * 4:off + yy * 4 + 4] = bytes(b)
    blob = _encode(bytes(buf))
    if len(blob) > limit:
        raise ValueError(f"stage2 title compressed {len(blob):#x} > {limit:#x}")
    rom[OFF + 2:OFF + 2 + len(blob)] = blob
    check = bytearray(0x8000 + LEN + 0x100)
    _decode(bytes(rom[OFF + 2:OFF + 2 + len(blob)]), 0x8000, LEN, check)
    if bytes(check[0x8000:0x8000 + LEN]) != bytes(buf):
        raise ValueError("stage2 title readback failed")
    return {"file": png.name, "compressed": f"0x{len(blob):X}", "limit": f"0x{limit:X}"}
