#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次跑完整個流程：拆表 → 展開黑燈 cue → 轉成 QLC+ .qxw → 改回原本的 Music 路徑。

用法::

    python3 run_all.py Project1.xlsx
    python3 run_all.py Project1.xlsx Music
    python3 run_all.py Project1.xlsx Music Basic_stage.qxw
    python3 run_all.py Project1.xlsx /path/to/Music --steps 3
    python3 run_all.py Project1.xlsx Music Basic_stage.qxw --outdir out

流程（``--steps`` 可指定執行到第幾步，預設 4 步全跑）：
1. step1_split_cuelist_xlsx.py：把總表拆成 ``<outdir>/temp_<檔名>/<工作表>/…_cuelist.xlsx``，
   並把音樂資料夾裡同名的 mp3 複製過去。
2. step2_fades_to_black.py：把 ``Fades to black(ms)`` 展開成獨立的黑燈 cue，
   在每個子資料夾裡另存成 ``…_cuelist_forqxw.xlsx``。
3. step3_cuelist_to_qxw.py：直接把上一步產生的專案資料夾當輸入，轉成 ``<outdir>/<檔名>.qxw``
   （同一個資料夾裡有 ``_forqxw`` 版本時只讀轉好的那份）。
4. step4_retarget_qxw_music.py：把 .qxw 裡的音檔路徑改回指向原本的 Music 資料夾。

第一個參數是要轉換的 .xlsx，第二個參數是 Music 的路徑（省略時用執行目錄下的 Music），
第三個參數是底稿 .qxw（可省略），會被複製進產出的專案資料夾，供第 2 步當 merge 底稿。
另可用 ``--outdir`` 指定輸出根目錄、``--steps`` 指定執行到第幾步；
``--`` 後面的參數會傳給 step4_retarget_qxw_music.py。
"""

from __future__ import annotations

import sys
from pathlib import Path

import step1_split_cuelist_xlsx
import step2_fades_to_black
import step3_cuelist_to_qxw
import step4_retarget_qxw_music

TOTAL_STEPS = 4


def take_option(rest, *names):
    """從參數串裡取出 ``--opt value``，回傳值（沒有就 None）。"""
    for name in names:
        if name in rest:
            i = rest.index(name)
            if i + 1 >= len(rest):
                raise SystemExit(f"{name} 後面少了值")
            value = rest[i + 1]
            del rest[i:i + 2]
            return value
    return None


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 2

    source = Path(argv[0])
    rest = argv[1:]

    # ``--`` 之後的參數留給第三步
    retarget_args = []
    if "--" in rest:
        i = rest.index("--")
        retarget_args = rest[i + 1:]
        del rest[i:]

    # 第二個參數若不是選項，就當成 Music 的路徑
    music_dir = Path("Music")
    if rest and not rest[0].startswith("-"):
        music_dir = Path(rest.pop(0))

    # 第三個參數若不是選項，就當成要複製進專案資料夾的底稿 .qxw
    base_qxw = None
    if rest and not rest[0].startswith("-"):
        base_qxw = Path(rest.pop(0))

    steps_value = take_option(rest, "--steps")
    try:
        steps = TOTAL_STEPS if steps_value is None else int(steps_value)
    except ValueError:
        print(f"--steps 必須是 1~{TOTAL_STEPS} 的整數：{steps_value}", file=sys.stderr)
        return 2
    if not 1 <= steps <= TOTAL_STEPS:
        print(f"--steps 必須是 1~{TOTAL_STEPS} 的整數：{steps}", file=sys.stderr)
        return 2

    outdir = Path(take_option(rest, "--outdir") or ".")
    if rest:
        print(f"不認得的參數：{' '.join(rest)}", file=sys.stderr)
        return 2

    if not source.is_file():
        print(f"找不到檔案：{source}", file=sys.stderr)
        return 2

    # --- 第 1 步：拆表 ---
    print(f"=== [1/{steps}] 拆表 {source} ===", flush=True)
    split_args = [str(source), str(music_dir)]
    if base_qxw is not None:
        split_args.append(str(base_qxw))
    split_args += ["--outdir", str(outdir)]
    code = step1_split_cuelist_xlsx.main(split_args)
    if code != 0:
        print("拆表失敗，中止。", file=sys.stderr)
        return code

    # step1_split_cuelist_xlsx 產生的資料夾是 temp_<檔名>（舊版沒有 temp_ 前綴）
    project = outdir / f"temp_{source.stem}"
    if not project.is_dir():
        legacy = outdir / source.stem
        if not legacy.is_dir():
            print(f"拆表沒有產生資料夾 {project}，中止。", file=sys.stderr)
            return 1
        project = legacy
    if steps < 2:
        return 0

    # --- 第 2 步：展開黑燈 cue ---
    print(f"\n=== [2/{steps}] 展開黑燈 cue：{project} ===", flush=True)
    code = step2_fades_to_black.main([str(project)])
    if code != 0:
        print("展開黑燈 cue 失敗，中止。", file=sys.stderr)
        return code
    if steps < 3:
        return 0

    # --- 第 3 步：轉成 .qxw ---
    print(f"\n=== [3/{steps}] 轉成 .qxw：{project} ===", flush=True)
    qxw = (outdir / f"{source.stem}.qxw").resolve()
    code = step3_cuelist_to_qxw.main([str(project), "-o", str(qxw)])
    if code != 0:
        print("轉檔失敗，中止。", file=sys.stderr)
        return code

    if not qxw.is_file():
        print(f"找不到產生的 .qxw：{qxw}，中止。", file=sys.stderr)
        return 1
    if steps < 4:
        return 0

    # --- 第 4 步：把音檔路徑改回原本的 Music ---
    print(f"\n=== [4/{steps}] 改音檔路徑：{qxw} ===", flush=True)
    return step4_retarget_qxw_music.main([str(qxw), str(music_dir), *retarget_args])


if __name__ == "__main__":
    raise SystemExit(main())
