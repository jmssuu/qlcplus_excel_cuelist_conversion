# scripts — 轉檔程式

四支程式，可以單獨用，也可以用 `run_all.py` 一次跑完。
指令都從**專案根目錄**執行。

| 程式 | 做什麼 | 需要套件 |
|---|---|---|
| `run_all.py` | 一次跑完下面三步 | openpyxl |
| `step1_split_cuelist_xlsx.py` | 第 1 步：把總表拆成每張工作表的 cuelist，並複製同名 mp3 | openpyxl |
| `step2_cuelist_to_qxw.py` | 第 2 步：表格／專案資料夾 → QLC+ `.qxw` | 無（純標準函式庫） |
| `step3_retarget_qxw_music.py` | 第 3 步：把 `.qxw` 裡的音檔路徑改回原本的 `Music/` | 無 |

```bash
python3 -m pip install openpyxl        # 只有拆表那步需要
```

## 整條流程

```bash
python3 scripts/run_all.py sample_file/AllCueList.xlsx sample_file/Music sample_file/BaseStage.qxw \
    --outdir sample_file
```

參數依序是：**總表 `.xlsx`**、**Music 資料夾**（省略時用執行目錄下的 `Music`）、
**底稿 `.qxw`**（可省略）。另有 `--steps 1|2|3` 只跑到第幾步，
`--` 後面的參數會原封不動傳給 `step3_retarget_qxw_music.py`。

⚠️ **前 3 張工作表會被跳過。** 第 1 步預設從第 4 張工作表開始
（`step1_split_cuelist_xlsx.py --start-sheet 4`），因為前面通常是「說明」「下拉選單」
「空白模板」這類非燈流的表。要改就單獨跑第 1 步並指定 `--start-sheet`。

⚠️ **`--outdir` 預設是「目前所在的資料夾」，不是 `.xlsx` 所在的資料夾。**
在專案根目錄跑上面那行卻不給 `--outdir`，產物會掉在專案根目錄。
（拖曳介面會自動帶 `--outdir`，所以產物一定在 `.xlsx` 旁邊。）

會產生：

```
<outdir>/temp_<檔名>/          中繼：每張工作表一個子資料夾（cuelist.xlsx + mp3）
<outdir>/<檔名>.qxw            成品
<outdir>/<檔名>.qxw.bak        第 3 步改路徑前的備份
```

`temp_<檔名>/` 只是中繼產物，確認 `.qxw` 沒問題後可以刪掉。

## 單獨使用

```bash
# 只轉表格，不拆表（每張工作表 / 每個自動化表格一條 Sequence）
python3 scripts/step2_cuelist_to_qxw.py sample_file/AllCueList.xlsx --list
python3 scripts/step2_cuelist_to_qxw.py 燈流.xlsx -o 我的.qxw

# 只拆表
python3 scripts/step1_split_cuelist_xlsx.py sample_file/AllCueList.xlsx sample_file/Music

# 只改音檔路徑（可一次給多個 .qxw，--dry-run 先試跑）
python3 scripts/step3_retarget_qxw_music.py sample_file/AllCueList.qxw sample_file/Music --dry-run
```

每支都有 `--help`，`step2_cuelist_to_qxw.py` 的完整參數與表格格式說明在
[專案根目錄的 README](../README.md)。

## 不想打指令

用 [`app/`](../app/) 裡的拖曳介面：把 `.xlsx` 拖進視窗，按「執行轉換」就是上面那條流程。
