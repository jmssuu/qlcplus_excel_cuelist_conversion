#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把已經產生好的 .qxw 裡面的音檔路徑，改回指向原本輸入的 Music 資料夾。

轉檔流程會把 mp3 複製到 ``<專案>/<工作表>/`` 底下，所以 .qxw 的 ``<Source>``
會寫成 ``Project1/show2/xxx.mp3``。這支程式把那些 ``<Source>`` 換成原始
Music 資料夾裡同一個檔案的路徑，這樣就不必留著那些副本。

用法::

    python3 step3_retarget_qxw_music.py Project1.qxw
    python3 step3_retarget_qxw_music.py Project1.qxw Music
    python3 step3_retarget_qxw_music.py Project1.qxw /path/to/Music --absolute
    python3 step3_retarget_qxw_music.py *.qxw Music --dry-run

第一個參數是要改的 .qxw（可以給多個），最後若是資料夾就當成 Music 的路徑
（省略時用執行目錄下的 Music）。

預設寫相對於 .qxw 所在資料夾的路徑（QLC+ 就是這樣解讀的），算不出相對路徑
時自動退回絕對路徑；加 --absolute 則一律寫絕對路徑。
改檔前會先存一份 ``<檔名>.qxw.bak``，可用 --no-backup 關掉。
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional
from xml.sax.saxutils import escape, unescape

DEFAULT_MUSIC_DIR = "Music"
AUDIO_SUFFIXES = (".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac")

# 只動 Type="Audio" 的 Function，順便抓出 Name 屬性當備援比對的依據
AUDIO_FUNCTION_RE = re.compile(
    r'<Function\b(?=[^>]*\bType="Audio")[^>]*>.*?</Function>',
    re.DOTALL,
)
NAME_ATTR_RE = re.compile(r'\bName="([^"]*)"')
SOURCE_RE = re.compile(r"(<Source>)(.*?)(</Source>)", re.DOTALL)


def collect_music(music_dir: Path, recursive: bool = False) -> List[Path]:
    """列出 Music 資料夾裡的音檔。"""
    it = music_dir.rglob("*") if recursive else music_dir.iterdir()
    return sorted(p for p in it
                  if p.is_file() and p.suffix.lower() in AUDIO_SUFFIXES)


def build_index(files: List[Path]) -> Dict[str, Path]:
    """建立比對用的索引：完整檔名與去掉副檔名的名字，都轉成小寫去頭尾空白。

    先進索引的優先（同名時保留排序在前的那個）。
    """
    index: Dict[str, Path] = {}
    for path in files:
        for key in (path.name, path.stem):
            index.setdefault(key.strip().lower(), path)
    return index


def match_music(index: Dict[str, Path], *candidates: str) -> Optional[Path]:
    """依序拿 candidates（來源路徑、Function 的 Name…）去索引裡找音檔。"""
    for candidate in candidates:
        if not candidate:
            continue
        name = Path(candidate.replace("\\", "/")).name
        for key in (name, Path(name).stem):
            hit = index.get(key.strip().lower())
            if hit is not None:
                return hit
    return None


def make_source(mp3: Path, qxw_path: Path, absolute: bool = False) -> str:
    """決定要寫進 <Source> 的路徑（跟 step2_cuelist_to_qxw 的規則一致）。"""
    mp3 = mp3.resolve()
    if absolute:
        return str(mp3)
    try:
        return str(mp3.relative_to(qxw_path.resolve().parent))
    except ValueError:
        return str(mp3)


def retarget(qxw_path: Path, index: Dict[str, Path], *, absolute: bool = False,
             backup: bool = True, dry_run: bool = False) -> int:
    """改寫單一 .qxw，回傳沒對上音檔的數量。"""
    text = qxw_path.read_text(encoding="utf-8")
    misses = 0
    changed = 0

    def fix_function(fn_match: "re.Match[str]") -> str:
        nonlocal misses, changed
        block = fn_match.group(0)
        fn_name = NAME_ATTR_RE.search(block)
        fn_name = unescape(fn_name.group(1)) if fn_name else ""

        def fix_source(src_match: "re.Match[str]") -> str:
            nonlocal misses, changed
            old = unescape(src_match.group(2).strip())
            mp3 = match_music(index, old, fn_name)
            if mp3 is None:
                misses += 1
                print(f"  ⚠ Music 裡找不到 {Path(old).name or fn_name}，保持原樣",
                      file=sys.stderr)
                return src_match.group(0)
            new = make_source(mp3, qxw_path, absolute=absolute)
            if new == old:
                print(f"  · {Path(old).name}：已經指向 Music，不用改")
                return src_match.group(0)
            changed += 1
            print(f"  ✓ {old} -> {new}")
            return f"{src_match.group(1)}{escape(new)}{src_match.group(3)}"

        return SOURCE_RE.sub(fix_source, block)

    new_text = AUDIO_FUNCTION_RE.sub(fix_function, text)

    if changed == 0:
        print(f"  （{qxw_path.name} 沒有需要更新的音檔路徑）")
        return misses
    if dry_run:
        print(f"  [試跑] {qxw_path.name} 會改 {changed} 個路徑，未寫檔")
        return misses

    if backup:
        bak = qxw_path.with_suffix(qxw_path.suffix + ".bak")
        try:
            # 用 copyfile 而非 copy2：不複製 macOS 的擴充屬性，免得踩到權限問題
            shutil.copyfile(qxw_path, bak)
            print(f"  已備份 -> {bak}")
        except OSError as exc:
            print(f"  ⚠ 備份失敗（{exc.strerror}），略過備份繼續更新：{bak}")
    qxw_path.write_text(new_text, encoding="utf-8")
    print(f"  已更新 {qxw_path}（共 {changed} 個路徑）")
    return misses


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="把 .qxw 裡的音檔路徑改回指向原始的 Music 資料夾",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    parser.add_argument("paths", nargs="+", metavar="PATH",
                        help="要修改的 .qxw；最後一個若是資料夾就當成 Music 路徑")
    parser.add_argument("--music-dir", default=None,
                        help=f"原始音樂資料夾（預設為執行目錄下的 {DEFAULT_MUSIC_DIR}）")
    parser.add_argument("--recursive", action="store_true",
                        help="連 Music 的子資料夾一起找")
    parser.add_argument("--absolute", action="store_true",
                        help="一律寫絕對路徑（預設優先用相對路徑）")
    parser.add_argument("--no-backup", dest="backup", action="store_false",
                        help="不要產生 .bak 備份")
    parser.add_argument("--dry-run", action="store_true",
                        help="只印出會怎麼改，不寫檔")
    parser.add_argument("--strict", action="store_true",
                        help="只要有音檔對不上就回傳非 0")
    args = parser.parse_args(argv)

    paths = [Path(p) for p in args.paths]
    music_dir = Path(args.music_dir) if args.music_dir else None

    # 位置參數的最後一個如果是資料夾，就當成 Music 路徑
    if music_dir is None and len(paths) > 1 and paths[-1].is_dir():
        music_dir = paths.pop()
    if music_dir is None:
        music_dir = Path(DEFAULT_MUSIC_DIR)

    if not music_dir.is_dir():
        print(f"找不到音樂資料夾：{music_dir}", file=sys.stderr)
        return 2

    files = collect_music(music_dir, recursive=args.recursive)
    if not files:
        print(f"{music_dir}/ 裡沒有音檔（{', '.join(AUDIO_SUFFIXES)}）", file=sys.stderr)
        return 2
    index = build_index(files)
    print(f"音樂資料夾 {music_dir}：{len(files)} 個音檔")

    qxws = [p for p in paths if p.is_file()]
    missing = [p for p in paths if not p.is_file()]
    for path in missing:
        print(f"找不到檔案：{path}", file=sys.stderr)
    if not qxws:
        return 2

    misses = 0
    for qxw in qxws:
        print(f"\n=== {qxw} ===")
        misses += retarget(qxw, index, absolute=args.absolute,
                           backup=args.backup, dry_run=args.dry_run)

    if missing:
        return 2
    if misses and args.strict:
        print(f"\n有 {misses} 個音檔對不上。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
