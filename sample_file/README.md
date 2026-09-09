# sample_file — 範例素材

拿來試跑轉檔流程用的檔案。

| 檔案 | 說明 |
|---|---|
| `AllCueList.xlsx` | 範例總表：前 3 張是 `說明` / `(勿動)下拉選單` / `空白模板`，第 4 張起放各組燈流，每組一張工作表、每張兩個自動化表格 |
| `BaseStage.qxw` | 範例底稿：燈具、虛擬控制台都設定好，轉檔時會 merge 進去 |
| `Music/` | 配樂；檔名要與工作表名稱相同才會被自動配對 |
| `Fixtures/` | 兩支燈的 QLC+ 燈具定義（`LSPA-60RC.qxf`、`GuangzhouEnran_ER-554.qxf`） |

## 試跑

```bash
python3 scripts/run_all.py sample_file/AllCueList.xlsx sample_file/Music sample_file/BaseStage.qxw \
    --outdir sample_file
```

**別漏掉 `--outdir`** — 不給的話產物會掉在你當下所在的資料夾（通常是專案根目錄）。
用拖曳介面就不必管這件事，它一定放在 `.xlsx` 旁邊。

會在這個資料夾裡產生 `AllCueList.qxw`（成品）、`AllCueList.qxw.bak`（改音檔路徑前的備份）
與 `temp_AllCueList/`（中繼檔，確認沒問題後可以刪）。中繼資料夾裡每組會有三個檔案：

```
temp_AllCueList/XX組-表演名稱/
├── 1_raw.xlsx        第 1 步拆出來的原始表
├── 2_forqxw.xlsx     第 2 步展開黑燈 cue 後的表（第 3 步讀這份）
└── XX組-表演名稱.mp3                   第 1 步從 Music/ 複製過來的配樂
```

## 配樂

`Music/` 裡的 mp3 要**命名成與工作表完全相同的名稱**才會被自動配對
（工作表 `XX組-表演名稱` → `XX組-表演名稱.mp3`），大小寫與頭尾空白可以不同。

配不到的工作表會看到兩行提醒：

```
[提醒] sample_file/Music/ 裡找不到 XX組-表演名稱.mp3
⚠ XX組-表演名稱 沒有 .mp3 配樂
```

這不影響轉檔——Show 照樣產生，只是少一條配樂軌。

## 前 3 張工作表會被跳過

第 1 步預設從第 4 張工作表開始，所以 `說明`、`(勿動)下拉選單`、`空白模板` 不會被轉換。
第 4 張起每張工作表會變成一個 Show 與兩條 Sequence（60RC 與 ER554 各一），
表格裡每個非零的 `Fades to black(ms)` 會在第 2 步補上一個黑燈 cue。

> 目前 repo 裡的 `AllCueList.xlsx` 只留下前 3 張範本工作表，`Music/` 也是空的
> （實際演出資料沒有一起公開）。要試跑請自己補上燈流工作表與同名的 mp3。

## Fixtures/ 是必要的嗎

`Fixtures/` 裡的 `.qxf` 是 QLC+ 的燈具定義檔，**轉檔程式會讀它**：
底稿 `.qxw` 只記得燈具有幾個通道，通道名稱（`Red`、`Total dimming`…）要靠 `.qxf` 才對得起來。
搜尋順序是底稿旁的 `Fixtures/` → 來源 `.xlsx` 旁的 `Fixtures/` → 上一層 →
QLC+ 使用者燈具庫 → QLC+ 內建燈具庫，任何一處找得到就行。

QLC+ 開檔時若說找不到燈具，把這兩個 `.qxf` 複製到 QLC+ 的使用者燈具庫：
`~/Library/Application Support/QLC+/Fixtures/`（macOS）或
`%USERPROFILE%\QLC+\Fixtures\`（Windows）。
拖曳介面在轉換後會自動檢查這件事，缺了會跳出提示，按一下就幫你複製過去。
