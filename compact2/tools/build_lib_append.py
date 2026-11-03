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
FONT_PATH = ASSETS / "fonts" / "simsun.ttc"

ADDR = {
    "D1": dict(strloop=0x3F55FE, strloop_dlg=0x3F547D, dispatch=0x3F5677, dispatch_jmp=0x3F567B, exit=0x3F5917),
    "D2": dict(strloop=0x3F56EA, strloop_dlg=0x3F5569, dispatch=0x3F5763, dispatch_jmp=0x3F5767, exit=0x3F5A03),
    "D3": dict(strloop=0x3F5726, strloop_dlg=0x3F55A5, dispatch=0x3F579F, dispatch_jmp=0x3F57A3, exit=0x3F5A3F),
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

def pack_glyph(ch, font_path=FONT_PATH, size=12, origin=(1, 2)):
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
    rom[a["dispatch"] + 1] = 0xE0
    rel = to - (a["dispatch_jmp"] + 3)
    rom[a["dispatch_jmp"]:a["dispatch_jmp"] + 3] = b"\xE9" + (rel & 0xFFFF).to_bytes(2, "little")
    rel2 = (to + 0x0C) - (a["exit"] + 3)
    rom[a["exit"]:a["exit"] + 3] = b"\xE9" + (rel2 & 0xFFFF).to_bytes(2, "little")
    return rom

def alloc_codes(chars):
    cmap = {}; code = 0xE000
    for ch in sorted(set(chars)):
        while (code & 0xFF) in (0xFD, 0xFE, 0xFF):
            code += 1
        if code > 0xEFFF:
            raise RuntimeError("4096 font overflow")
        cmap[ch] = code; code += 1
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

def encode(text, cmap):
    out = bytearray(); missing = []
    for ch in str(text).replace(" / ", "/").replace("／", "/"):
        if ch in ("/", "\n"):
            out.append(0xFE)
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
            enc, missing = encode(r[7], stats["cmap"])
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
            ["字模标准", "SimSun 12px 原点(1,2)，墨迹3-14行；左上8行+右上8行 / 左下+右下"],
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
