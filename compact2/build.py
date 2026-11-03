# -*- coding: utf-8 -*-
"""超级机器人大战 COMPACT 2 三部曲汉化构建入口。

仓库不附带游戏 ROM；请用 --d1/--d2/--d3 传入三作日文原版，
构建会先校验 CRC，再在临时目录里复制素材和 ROM 完成构建。

用法：
  python build.py --d1 Dai1.ws --d2 Dai2.ws --d3 Dai3.ws -o out
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOOLS = ROOT / "tools"
ASSETS = ROOT / "assets"
sys.path.insert(0, str(TOOLS))
import text_sync  # TSV 镜像 → 构建工作簿

ORIG_CRC = {
    1: "782877BC",
    2: "ECBB46DE",
    3: "0B0F8981",
}
OUT_NAME = "超级机器人大战compact2-{n}[cn][lcdyk][v1].ws"


def crc32(path: Path) -> str:
    return "%08X" % (zlib.crc32(path.read_bytes()) & 0xFFFFFFFF)


def check_rom(n: int, path: Path) -> None:
    if not path.is_file():
        raise SystemExit("Dai-%d ROM not found: %s" % (n, path))
    got = crc32(path)
    if got != ORIG_CRC[n]:
        raise SystemExit(
            "Dai-%d ROM CRC mismatch: got %s, expected %s\n"
            "Use the Japanese original (D1 782877BC / D2 ECBB46DE / D3 0B0F8981)."
            % (n, got, ORIG_CRC[n])
        )


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the Compact 2 trilogy Chinese ROMs.")
    ap.add_argument("--d1", required=True, help="original Dai-1 .ws")
    ap.add_argument("--d2", required=True, help="original Dai-2 .ws")
    ap.add_argument("--d3", required=True, help="original Dai-3 .ws")
    ap.add_argument("-o", "--outdir", default="out", help="output directory (default: out)")
    ap.add_argument("--keep-work", action="store_true", help="keep the temporary build tree")
    ap.add_argument("--fonts", choices=("simsun", "fusion", "both"), default="simsun",
                    help="字体版本：simsun（默认）/ fusion / both")
    args = ap.parse_args()

    roms = {1: Path(args.d1).expanduser().resolve(),
            2: Path(args.d2).expanduser().resolve(),
            3: Path(args.d3).expanduser().resolve()}
    # 先校验三作原版 CRC，避免用错版本（Rev 不同会导致地址/文本全错）
    for n, p in roms.items():
        check_rom(n, p)

    outdir = Path(args.outdir).expanduser().resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    # 在仓库内建临时构建树：每作复制一份 assets，并把原版 ROM 放到 assets/original.ws。
    # build_xbank 通过 WS2_ROOT/WS2_PROJECT_ROOT/WS2_BUILD_ROOT 指向这里，
    # 因此不会污染源码目录；结束默认自动删除，--keep-work 可保留排查。
    work = Path(tempfile.mkdtemp(prefix="compact2-build-", dir=str(ROOT)))
    try:
        for n in (1, 2, 3):
            src = ASSETS / ("Dai%d" % n)
            dst = work / ("Dai%d" % n)
            # 每作以 assets/DaiN/text/*.tsv 为入库源；构建时重建工作簿。
            tsv_dir = src / "text"
            built_book = None
            if (tsv_dir / "_manifest.json").is_file():
                built_book = text_sync.write_xlsx(tsv_dir, src / "text.build.xlsx")
            shutil.copytree(src, dst)
            if built_book is not None:
                shutil.copy2(built_book, dst / "text.xlsx")
            shutil.copy2(roms[n], dst / "assets" / "original.ws")

        env = os.environ.copy()
        env["WS2_ROOT"] = str(work)
        env["WS2_PROJECT_ROOT"] = str(work)
        env["WS2_BUILD_ROOT"] = str(work)

        fonts = ("simsun", "fusion") if args.fonts == "both" else (args.fonts,)
        for font in fonts:
            env2 = env.copy()
            if font == "fusion":
                env2["WS2_FONT"] = "fusion"
                env2["OUT_SUFFIX"] = "_fusion"
            else:
                env2.pop("WS2_FONT", None)
                env2.pop("OUT_SUFFIX", None)
            sfx = "_fusion" if font == "fusion" else ""
            for n in (1, 2, 3):
                print("== build Dai-%d (%s) ==" % (n, font), flush=True)
                subprocess.run([sys.executable, str(TOOLS / "build_xbank.py"), str(n)],
                               cwd=str(ROOT), env=env2, check=True)
                src = work / ("Dai%d" % n) / "产物" / ("D%d_CN_test%s.ws" % (n, sfx))
                if not src.is_file():
                    raise SystemExit("build output missing: %s" % src)
                name = OUT_NAME.format(n=n)
                if font == "fusion":
                    name = name.replace(".ws", "[fusion].ws")
                dst = outdir / name
                shutil.copy2(src, dst)
                print("written:", dst, "CRC", crc32(dst), flush=True)
    finally:
        if args.keep_work:
            print("work tree kept:", work)
        else:
            shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
