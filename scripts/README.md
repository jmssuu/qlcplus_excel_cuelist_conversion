# scripts — 轉檔程式

五支程式，可以單獨用，也可以用 `run_all.py` 一次跑完。
指令都從**專案根目錄**執行。

| 程式 | 做什麼 | 需要套件 |
|---|---|---|
| `run_all.py` | 一次跑完下面四步 | openpyxl |
| `step1_split_cuelist_xlsx.py` | 第 1 步：把總表拆成每張工作表的 cuelist，並複製同名 mp3 | openpyxl |
| `step2_fades_to_black.py` | 第 2 步：把 `Fades to black(ms)` 展開成黑燈 cue，另存 `…_forqxw.xlsx` | openpyxl |
| `step3_cuelist_to_qxw.py` | 第 3 步：表格／專案資料夾 → QLC+ `.qxw` | 無（純標準函式庫） |
| `step4_retarget_qxw_music.py` | 第 4 步：把 `.qxw` 裡的音檔路徑改回原本的 `Music/` | 無 |

```bash
python3 -m pip install openpyxl        # 只有拆表那步需要
```

## 整條流程

```bash
python3 scripts/run_all.py sample_file/AllCueList.xlsx sample_file/Music sample_file/BaseStage.qxw \
    --outdir sample_file
```

參數依序是：**總表 `.xlsx`**、**Music 資料夾**（省略時用執行目錄下的 `Music`）、
**底稿 `.qxw`**（可省略）。另有 `--steps 1|2|3|4` 只跑到第幾步，
`--` 後面的參數會原封不動傳給 `step4_retarget_qxw_music.py`。

⚠️ **前 3 張工作表會被跳過。** 第 1 步預設從第 4 張工作表開始
（`step1_split_cuelist_xlsx.py --start-sheet 4`），因為前面通常是「說明」「下拉選單」
「空白模板」這類非燈流的表。要改就單獨跑第 1 步並指定 `--start-sheet`。

⚠️ **`--outdir` 預設是「目前所在的資料夾」，不是 `.xlsx` 所在的資料夾。**
在專案根目錄跑上面那行卻不給 `--outdir`，產物會掉在專案根目錄。
（拖曳介面會自動帶 `--outdir`，所以產物一定在 `.xlsx` 旁邊。）

會產生：

```
<outdir>/temp_<檔名>/          中繼：每張工作表一個子資料夾
    1_raw.xlsx        第 1 步拆出來的原始表
    2_forqxw.xlsx     第 2 步展開黑燈 cue 後的表（第 3 步讀這份）
    <組名>.mp3        配樂
<outdir>/<檔名>.qxw            成品
<outdir>/<檔名>.qxw.bak        第 4 步改路徑前的備份
```

`temp_<檔名>/` 只是中繼產物，確認 `.qxw` 沒問題後可以刪掉。

## 單獨使用

```bash
# 只拆表
python3 scripts/step1_split_cuelist_xlsx.py sample_file/AllCueList.xlsx sample_file/Music

# 只展開黑燈 cue（--dry-run 先看會補幾個）
python3 scripts/step2_fades_to_black.py sample_file/temp_AllCueList --dry-run

# 只轉表格，不拆表（每張工作表 / 每個自動化表格一條 Sequence）
python3 scripts/step3_cuelist_to_qxw.py sample_file/AllCueList.xlsx --list
python3 scripts/step3_cuelist_to_qxw.py 燈流.xlsx -o 我的.qxw

# 只改音檔路徑（可一次給多個 .qxw，--dry-run 先試跑）
python3 scripts/step4_retarget_qxw_music.py sample_file/AllCueList.qxw sample_file/Music --dry-run
```

每支都有 `--help`，`step3_cuelist_to_qxw.py` 的完整參數與表格格式說明在
[專案根目錄的 README](../README.md)。

## 為什麼要有第 2 步

燈流表上的 `Fades to black(ms)` 是「這個 cue 結束後花多久暗下來」，
但 QLC+ 的 Sequence 只有每個 Step 自己的 FadeIn / Hold / FadeOut，沒有這個概念。
所以第 2 步把它翻譯成 QLC+ 懂的形式：

| 轉換前 | 轉換後（`…_forqxw.xlsx`） |
|---|---|
| 欄位 `Fades to black(ms)` | 改名成 `Fade out(ms)` |
| 某列 `Fades to black(ms)` 有值（非空非 0） | 在它下面補一列**全通道歸零**的黑燈 cue，`Fade in(ms)` = 上一列的 `Fade out(ms)`，`Hold(ms)` / `Fade out(ms)` 都是 0 |

例：第 3 個 cue 的 `Fades to black(ms)=7000`

```
#=3  Fade in=0     Hold=4988  Fade out=7000  dimming=255  R=255  G=180  B=160
#=4  Fade in=7000  Hold=0     Fade out=0     所有通道 = 0        ← 補的黑燈 cue
```

暗場就發生在黑燈 cue 的那段淡入裡：畫面在 7000 ms 內從上一個 cue 漸暗到全黑。

`#` 欄會重新編號。原始的 `1_raw.xlsx` 會留著，第 3 步只讀 `2_forqxw.xlsx`。
資料夾本身已經是工作表名稱，所以這兩個檔名不再重複一次組名。

## 覆寫舊產物

三支會寫檔的步驟（`1_raw.xlsx`、`2_forqxw.xlsx`、`.qxw`）都會直接覆寫既有檔案，
重複執行是安全的。若覆寫被作業系統擋下（macOS 的 `.app` 動不了終端機產生的舊檔），
程式會先把舊檔刪掉再重寫；連刪都刪不掉時印出明確訊息而不是 traceback。
詳見 [`app/macos/README.md`](../app/macos/README.md#常見問題)。

## 不想打指令

用 [`app/`](../app/) 裡的拖曳介面：把 `.xlsx` 拖進視窗，按「執行轉換」就是上面那條流程。
