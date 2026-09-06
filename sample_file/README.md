# sample_file — 範例素材

拿來試跑轉檔流程用的檔案。

| 檔案 | 說明 |
|---|---|
| `AllCueList.xlsx` | 範例總表：8 張工作表，第 4 張起共 5 張有燈流資料，每張兩個自動化表格 |
| `BaseStage.qxw` | 範例底稿：燈具、虛擬控制台都設定好，轉檔時會 merge 進去 |
| `Music/` | 放配樂的地方，**目前是空的**；檔名要與工作表名稱相同才會被自動配對 |
| `Fixtures/` | 兩支燈的 QLC+ 燈具定義（`LSPA-60RC.qxf`、`GuangzhouEnran_ER-554.qxf`） |

## 試跑

```bash
python3 scripts/run_all.py sample_file/AllCueList.xlsx sample_file/Music sample_file/BaseStage.qxw \
    --outdir sample_file
```

**別漏掉 `--outdir`** — 不給的話產物會掉在你當下所在的資料夾（通常是專案根目錄）。
用拖曳介面就不必管這件事，它一定放在 `.xlsx` 旁邊。

會在這個資料夾裡產生 `AllCueList.qxw`（成品）、`AllCueList.qxw.bak`（改音檔路徑前的備份）
與 `temp_AllCueList/`（中繼檔，確認沒問題後可以刪）。

## 配樂

`Music/` 目前是空的，所以直接試跑會看到五行

```
[提醒] sample_file/Music/ 裡找不到 XX組-表演名稱.mp3
⚠ XX組-表演名稱 沒有 .mp3 配樂
```

這不影響轉檔——Show 照樣產生，只是沒有配樂軌。想連配樂一起測，
把 mp3 放進 `Music/` 並**命名成與工作表完全相同的名稱**（例如
工作表 `達達組-沙雕男孩` → `達達組-沙雕男孩.mp3`），大小寫與頭尾空白可以不同。

## 前 3 張工作表會被跳過

第 1 步預設從第 4 張工作表開始，所以 `說明`、`(勿動)下拉選單`、`空白模板` 不會被轉換，
實際會產生 5 個 Show、10 條 Sequence。

## 注意

`Fixtures/` 裡的 `.qxf` 是給 QLC+ 用的燈具定義，轉檔程式**不會讀它**
（燈具對應寫死在 `scripts/step2_cuelist_to_qxw.py` 的 `PROFILES` 裡）。
若 QLC+ 開檔時說找不到燈具，把這兩個 `.qxf` 複製到
`~/Library/Application Support/QLC+/fixtures/`（macOS）或
`%LOCALAPPDATA%\QLC+\fixtures\`（Windows）。
