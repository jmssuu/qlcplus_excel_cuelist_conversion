# QLCplus_excel_conversion

把表格（Excel / CSV）形式的燈流轉換成 [QLC+ 5](https://www.qlcplus.org/) 的 Sequence，
省去在 QLC+ 介面裡一步一步手刻 Step 的時間。

主要工具是 **`step3_cuelist_to_qxw.py`**：讀 `.xlsx` 或 `.csv`，把 Sequence 併進
一份既有的底稿 `.qxw`。**每張工作表、每個自動化表格都會變成一條獨立的 Sequence。**

**底稿 `.qxw` 是必要的**——燈具有幾台、fixture ID、DMX 位址、模式與通道長度
全部從底稿讀出來，程式本身不內建任何燈具型號。

也可以直接餵一個**專案資料夾**：底下每個子資料夾會變成一個 Show，
把該資料夾的配樂與轉出的 Sequence 並排放在時間軸 0。

`step3_cuelist_to_qxw.py` 只用 Python 標準函式庫（自己解 xlsx 的 zip 與 mp3 frame header），
不需要 pandas 或任何音訊套件，也不需要網路；
只有拆表那一步 `step1_split_cuelist_xlsx.py` 需要 **openpyxl**。

---

## 資料夾結構

```
QLCplus_excel_conversion/
├── scripts/          轉檔程式（見 scripts/README.md）
│   ├── run_all.py           一次跑完四個步驟
│   ├── step1_split_cuelist_xlsx.py     第 1 步：拆表
│   ├── step2_fades_to_black.py         第 2 步：展開黑燈 cue
│   ├── step3_cuelist_to_qxw.py         第 3 步：轉 .qxw
│   └── step4_retarget_qxw_music.py     第 4 步：改音檔路徑
├── app/              拖曳介面與執行檔（見 app/README.md）
│   ├── qlcplus_gui.py            介面原始碼，兩個平台共用
│   ├── macos/                    macOS 打包腳本與 dist/…app
│   └── windows/                  Windows 打包腳本與 dist/…exe
└── sample_file/      範例素材：AllCueList.xlsx、Music/、Fixtures/、BaseStage.qxw
```

---

## 快速開始

需要 Python 3.8 以上。只用 `step3_cuelist_to_qxw.py` 的話不必裝任何套件；
要跑完整流程（拆表那一步）請先 `python3 -m pip install openpyxl`。

下面的指令都從專案根目錄執行。

```bash
# 先看看檔案裡有哪些工作表與表格
python3 scripts/step3_cuelist_to_qxw.py sample_file/AllCueList.xlsx --list

# 只轉某一張工作表
python3 scripts/step3_cuelist_to_qxw.py sample_file/AllCueList.xlsx \
    --base sample_file/BaseStage.qxw --sheet "XX組-表演名稱" -o XX組.qxw

# 一次吃多個檔，全部併進同一個 .qxw
python3 scripts/step3_cuelist_to_qxw.py 染色燈.csv 台面燈.csv --base 底稿.qxw -o 全部.qxw

# 一次跑完拆表 → 展開黑燈 cue → 轉檔 → 改音檔路徑
# --outdir 指定產物要放哪；不給的話會產生在「目前所在的資料夾」
python3 scripts/run_all.py sample_file/AllCueList.xlsx sample_file/Music sample_file/BaseStage.qxw \
    --outdir sample_file
```

`--list` 會像這樣列出來源裡有什麼：

```
$ python3 scripts/step3_cuelist_to_qxw.py sample_file/AllCueList.xlsx --list
sample_file/AllCueList.xlsx
  - 說明: 沒有自動化表格
  - (勿動)下拉選單: 沒有自動化表格
  - 空白模板: 2 個表格 [染色燈, (無標題)]
  - XX組-表演名稱: 2 個表格 [染色燈, (無標題)]
  ...
```

中括號裡是**表格標題**，取自 `#` 上方那一格；那格空白就顯示 `(無標題)`。

不給來源時程式會找執行目錄下的 `cuelist_transform.xlsx`，找不到才退回 `cuelist_transform.csv`
（這兩個預設檔沒有收在 repo 裡，直接指定來源即可）。

### 不想打指令：用拖曳介面

`app/qlcplus_gui.py` 是 `scripts/run_all.py` 的圖形介面——把燈表 `.xlsx` 拖進視窗，
按「執行轉換」就跑完拆表 → 展開黑燈 cue → 轉 `.qxw` → 改音檔路徑四個步驟，
過程訊息直接顯示在視窗下方
（可以選取、右鍵複製，或按「複製訊息」整份複製、「清除訊息」清空；
錯誤紅字、提醒黃字、成功綠字）。

```bash
open "app/macos/dist/QLCplus轉檔工具.app"   # 打包好的 macOS 執行檔，雙擊也可以
python3 app/qlcplus_gui.py                  # 直接跑原始碼（要 pip install tkinterdnd2 才有拖曳）
app/macos/build_app.sh                      # 改完程式重新打包
```

介面原始碼 [`app/qlcplus_gui.py`](app/qlcplus_gui.py) **兩個平台共用**，
打包腳本與產物則分開放，一眼就看得出哪個是哪個：

| 平台 | 打包腳本 | 產物 |
|---|---|---|
| macOS | `app/macos/build_app.sh` | `app/macos/dist/QLCplus轉檔工具.app` |
| Windows | `app\windows\build_exe.bat` | `app\windows\dist\QLCplus_Converter.exe` |

**Windows 版必須在 Windows 電腦上打包**——PyInstaller 不能跨平台編譯，
在 macOS 上跑再多次也產不出 `.exe`。把專案複製過去後執行 `app\windows\build_exe.bat` 即可，
細節見 [`app/windows/README.md`](app/windows/README.md)。

* Music 資料夾會自動帶入 `.xlsx` 旁邊的 `Music/`，也可以自己拖或按「瀏覽…」改。
* 「Excel 轉換從第 N 張工作表開始轉換」對應第 1 步的 `--start-sheet`，預設 5。
* 底稿 `.qxw` **必填**，會自動帶入 `.xlsx` 旁邊的 `BaseStage.qxw`；
  它會被複製進專案資料夾當 merge 底稿，燈具設定也是從它讀出來的。
* 輸出固定放在 `.xlsx` 所在的資料夾：`<檔名>.qxw`（中繼檔在 `temp_<檔名>/`，
  預設轉換結束後自動刪除，可用核取方塊關掉）。
* 轉換後會檢查 QLC+ 使用者燈具庫有沒有底稿用到的燈具檔，缺了會顯示提示，
  按一下就自動把 `.qxf` 複製過去。
* 打包腳本第一次執行會自動建立虛擬環境（macOS 用 `.venv`、Windows 用 `.venv-win`）
  並安裝 openpyxl、pyinstaller、tkinterdnd2。
* 打包好的 `.app` 沒有簽章，第一次開啟若被 Gatekeeper 擋下，
  請用右鍵 →「打開」，或到「系統設定 → 隱私權與安全性」按「仍要打開」。
* 拖曳沒反應時可用 `QLCPLUS_GUI_SELFTEST=1 "app/macos/dist/QLCplus轉檔工具.app/Contents/MacOS/QLCplus轉檔工具"`
  確認 tkdnd 有沒有被打包進去。

執行後會在 stderr 印出摘要，方便快速核對：

```
  Sequences: 2 （資料夾 Sequence_Cuelist）
      - [工作表 XX組-表演名稱] XX組-表演名稱_染色燈: 20 steps, 3751295 ms, [LSPA60RC [1](ID 2), ...]
      - [工作表 XX組-表演名稱] XX組-表演名稱: 19 steps, 3751295 ms, [ER-554 [2](ID 8), ...]
已輸出: 燈流.qxw
```

專案模式則會多一層 Show 與配樂：

```
  底稿: BaseStage.qxw
  Shows: 5（資料夾 Show）／Sequences: 10 （資料夾 Sequence_Cuelist）
  ▸ Show XX組-表演名稱
      ♪ XX組-表演名稱.mp3: 220865 ms （資料夾 Music）
      - [工作表 XX組-表演名稱60RC] XX組-表演名稱60RC: 19 steps, 3791436 ms, [LSPA60RC [1](ID 2), ...]
      - [工作表 XX組-表演名稱ER554] XX組-表演名稱ER554: 15 steps, 3798436 ms, [ER-554 [2](ID 8), ...]
  ▸ Show YY組-表演名稱
      ...
已輸出: AllCueList.qxw
```

每條 Sequence 前面的 `[工作表 …]` 會標出它是從哪一張工作表來的。

### 常見情境

底稿 `.qxw` 是必填的：來源是專案資料夾時會自動抓資料夾底下那份，
單獨餵 `.xlsx` / `.csv` 則要用 `--base` 指定。

| 想做的事 | 指令 |
|---|---|
| 轉一份 Excel（每張工作表一條 Sequence） | `python3 scripts/step3_cuelist_to_qxw.py 燈流.xlsx --base 底稿.qxw` |
| 轉整個專案（每個子資料夾一個 Show） | `python3 scripts/step3_cuelist_to_qxw.py temp_AllCueList` |
| 先確認檔案裡有什麼 | `python3 scripts/step3_cuelist_to_qxw.py 來源 --list` |
| 只轉某一張工作表 | `python3 scripts/step3_cuelist_to_qxw.py 燈流.xlsx --base 底稿.qxw --sheet "XX組-表演名稱"` |
| 指定要併進哪份 workspace | `python3 scripts/step3_cuelist_to_qxw.py 燈流.xlsx --base 底稿.qxw -o 新版.qxw` |
| 只要 XML 片段，自己貼進去 | `python3 scripts/step3_cuelist_to_qxw.py 燈流.xlsx --base 底稿.qxw --mode snippet --stdout` |
| 指定輸出檔名 | `python3 scripts/step3_cuelist_to_qxw.py 燈流.xlsx --base 底稿.qxw -o 我的.qxw` |
| 改 QLC+ 裡的資料夾名稱 | `python3 scripts/step3_cuelist_to_qxw.py temp_AllCueList --folder 燈流 --music-folder 音樂 --show-folder 節目` |

---

## 專案資料夾模式

把來源指定成一個資料夾，底下每個子資料夾就是一場 Show。
**第 1 步 `step1_split_cuelist_xlsx.py` 產生的 `temp_<檔名>/` 就是長這個樣子**，
所以整條流程才接得起來：

```
我的專案/
├── BaseStage.qxw                   ← 底稿（必要），會自動併進去
├── XX組-表演名稱/
│   ├── 1_raw.xlsx          ← 轉成 Sequence
│   └── XX組-表演名稱.mp3    ← 配樂
├── YY組-表演名稱/
│   ├── 1_raw.xlsx
│   └── YY組-表演名稱.mp3
└── ZZ組-表演名稱/
    ├── 1_raw.xlsx
    └── ZZ組-表演名稱.mp3
```

資料夾本身已經是工作表名稱，所以檔名不再重複一次；開頭的數字對應流程步驟。
跑過第 2 步之後，每個子資料夾還會多一份 `2_forqxw.xlsx`，這一步只會讀轉好的那份。

```bash
python3 scripts/step3_cuelist_to_qxw.py 我的專案          # 產生 我的專案.qxw
python3 scripts/step3_cuelist_to_qxw.py 我的專案 --list   # 先看掃到哪些檔案（不需要底稿）
```

```
$ python3 scripts/step3_cuelist_to_qxw.py sample_file/temp_AllCueList --list
sample_file/temp_AllCueList
  ▸ XX組-表演名稱/
      表格 1_raw.xlsx
      表格 2_forqxw.xlsx
  ▸ YY組-表演名稱/
      表格 1_raw.xlsx
      表格 2_forqxw.xlsx
      配樂 YY組-表演名稱.mp3
  ...
```

產生的 `.qxw` 在 QLC+ 的函式樹裡會長這樣（每組一個 Show、一首配樂、兩條 Sequence）：

```
Music/            每組一個 Audio：XX組-表演名稱.mp3、YY組-表演名稱.mp3…
Sequence_Cuelist/ 每組兩條 Sequence：XX組-表演名稱60RC、XX組-表演名稱ER554…
Show/             每組一個 Show：XX組-表演名稱、YY組-表演名稱…
```

每個 Show 以**子資料夾名稱**命名，裡面每條軌都從 **StartTime=0** 開始，
所以配樂與各條 Sequence 是並排的：

```xml
<Function ID="131" Type="Show" Name="XX組-表演名稱" Path="Show">
 <TimeDivision Type="Time" BPM="120"/>
 <Track ID="0" Name="Track 1" isMute="0">
  <ShowFunction ID="126" StartTime="0" Duration="152616" Color="#608053"/>   <!-- 配樂 -->
 </Track>
 <Track ID="1" Name="Track 2" isMute="0">
  <ShowFunction ID="128" StartTime="0" Duration="3751295" Color="#646464"/>  <!-- 60RC Sequence -->
 </Track>
 <Track ID="2" Name="Track 3" isMute="0">
  <ShowFunction ID="130" StartTime="0" Duration="3751295" Color="#646464"/>  <!-- ER554 Sequence -->
 </Track>
</Function>
```

* **配樂長度**由程式自行解析 mp3 frame header 算出（支援 CBR 與 Xing/Info/VBRI 的 VBR），
  不需要 ffmpeg 或任何套件。
* **Show 軌道上的配樂會往後多留 5 秒**（開始時間仍是 0），免得最後一拍卡在 Show 結尾被切掉；
  Audio 函式本身記錄的長度仍是實際歌長。
* **配樂路徑**只要音檔在輸出 `.qxw` 的資料夾底下就寫相對路徑，
  整個專案搬家後仍然播得出來；否則退回絕對路徑。
* 子資料夾裡有多張表就產生多條 Sequence，名稱前面會冠上子資料夾名以免撞名。
* 子資料夾**沒有 mp3** 只會警告，Show 照樣產生（只是沒有配樂軌）；
  **沒有表格檔**的資料夾則整個略過。
* 資料夾名稱、`Music`、`Show` 都可以用 `--folder` / `--music-folder` / `--show-folder` 改。

### 自動合併底稿

專案資料夾底下放的那份 `.qxw`（例如 `BaseStage.qxw`）就是底稿，
**產生的內容會自動併進去**，燈具設定、既有函式、虛擬控制台都原封不動保留：

```bash
$ python3 scripts/step3_cuelist_to_qxw.py 我的專案
  底稿: BaseStage.qxw
  Shows: 3（資料夾 Show）／Sequences: 6 （資料夾 Sequence_Cuelist）
  ...
已輸出: 我的專案.qxw
```

* **底稿不會被覆寫**，輸出是另一個檔（預設 `<資料夾名>.qxw`）。
* 底下**沒有 `.qxw` 就中止**並提示要指定底稿——燈具設定沒有別的來源。
* 有多個 `.qxw` 時採用檔名排序第一個並提示；自動存檔（`*.autosave.qxw`）與輸出檔本身會被排除。
  （第 1 步每次都會先清空 `temp_<檔名>/`，所以不會撿到上一次留下的舊底稿。）
* 想指定別的底稿就用 `--base`，它的優先度高於資料夾裡那份。
* 表格寫到、但底稿裡沒有的燈具會被忽略，並在最後列出是哪幾盞：

  ```
  ⚠ 這些燈具不在 BaseStage.qxw 裡，相關欄位已忽略: 60RC[4]、60RC[5]、ER-554[1]
  ```

## 表格格式

檔名不限定，表頭符合格式即可。以下用 CSV 舉例，Excel 的欄位規則完全一樣。

```csv
自動化表格 60RC舞台燈
#,Duration(ms),Fade In(ms),Fade Out(ms),LSPA60RC[1-6] Total dimming,LSPA60RC[1-6] Red,LSPA60RC[1-6] Green,LSPA60RC[1-6] Blue,LSPA60RC[1-6] Stroboscopic,Note
1,19030,0,0,255,255,51,183,,
2,4470,0,0,255,255,51,183,204,
```

* **標題列可有可無**，程式會掃過整張表找表頭列：只要某一列出現 `#`，
  或出現 `Duration` / `Duration(ms)` / `Hold` / `時間` 其中之一，就當成表頭。
* **欄位順序不拘**，靠欄位名稱辨識，用不到的欄位會被略過並列在摘要裡。
* 支援 UTF-8 BOM（Excel 另存 CSV 的預設格式）。

### 多張表 = 多條 Sequence

**Excel（推薦）**：每張工作表都會被讀進來，工作表裡有幾個自動化表格就產生幾條 Sequence。
以 `sample_file/AllCueList.xlsx` 為例，每張燈流工作表都有 60RC 與 ER554 兩個表格垂直排列，
所以 N 張有資料的工作表會產生 2N 條 Sequence。

```bash
$ python3 scripts/step3_cuelist_to_qxw.py sample_file/AllCueList.xlsx --list
sample_file/AllCueList.xlsx
  - 說明: 沒有自動化表格
  - XX組-表演名稱: 2 個表格 [染色燈, (無標題)]
  ...
```

> ⚠️ **不要用 Excel「另存新檔 → CSV」來轉多張工作表**：
> CSV 只存得下一張工作表，Excel 只會輸出當前這一張，其他表的資料會整個不見。
> 要一次轉多張表請直接餵 `.xlsx`。

自動化表格不必貼齊左上角。實際版面左邊通常還有一張給人看的中文表
（`編號`／`切換時間`／`配色`…），自動化表格從 N 欄才開始，
程式會自動忽略認不得的欄位，只挑出燈具通道欄。

**CSV**：CSV 沒有 sheet 的概念，所以**把多張表上下疊在同一個檔案裡**即可，
每遇到一列表頭就開一張新表，有幾張表就產生幾條 Sequence（各自帶自己的 BoundScene）。

```csv
自動化表格 60RC舞台燈
#,Duration(ms),Fade In(ms),Fade Out(ms),LSPA60RC[1-6] Total dimming,...
1,19030,0,0,255,...
2,4470,0,0,255,...

自動化表格 ER554舞台燈參數
#,Duration(ms),Fade In(ms),Fade Out(ms),ER-554[1] Total dimming,...
1,19030,0,0,255,...
```

* **Sequence 名稱預設就是工作表名稱**，所以在 QLC+ 裡一眼就知道是哪張表來的。
* 一張工作表裡有**多個表格**時，會自動補上表格標題區分，
  例如 `XX組-表演名稱_60RC舞台燈`、`XX組-表演名稱_ER554舞台燈參數`。
* 標題可以寫「自動化表格 …」「自動化表單 …」或「表格 …」，三種前綴都認得。
* `--name-from title` 可改用表格自己的標題當名稱
  （`60RC舞台燈`、`ER554舞台燈參數`）；此時撞名則改補工作表名稱。
* CSV 沒有工作表的概念，會自動退回表格標題，再退回檔名。
* `--name` 可以直接指定名稱，重複指定依序對應每張表，優先於上述規則。
* 執行摘要一律會用 `[工作表 …]` 標出每條 Sequence 的來源。
* 沒有標題列也可以，直接疊表即可，名稱會依序退回「工作表名 → 表格標題 → 檔名」。
  標題列的判定是「整列只有一兩格有字、且開頭不是數字」，或該列含有「自動化表格 …」，
  所以上一張表的最後一列資料不會被誤認成標題。
* 名稱重複時會自動補 `_2`、`_3`，避免 QLC+ 裡出現兩條同名 Sequence。
* 也可以**一次傳多個檔**（`.xlsx` 與 `.csv` 可混用），全部併進同一份輸出：
  `python3 scripts/step3_cuelist_to_qxw.py a.xlsx b.csv --base 底稿.qxw -o 全部.qxw`
* `--sheet` 可以只挑特定工作表，重複指定就是多選。
* 每張表可以用不同的燈具，`workspace` 模式會自動取燈具聯集，同一盞只宣告一次。
* 沒有任何有效 Step 的表會被跳過並印出警告。

### 時間欄位

表頭在**第 2 列**（第 1 列是「60RC」「ER554」這種區塊標題）。
**欄位順序不拘**，靠名稱辨識。

| 欄位名稱 | 對應 | 說明 |
|---|---|---|
| `#` / `No` / `Step` / `序號` | — | 僅供閱讀，程式不使用 |
| `Fade in(ms)` / `淡入` | `Step FadeIn` | 省略視為 0 |
| `Hold(ms)` / `Duration(ms)` / `時間` | `Step Hold` | 該步停留幾毫秒 |
| `Fade out(ms)` / `淡出` | `Step FadeOut` | 省略視為 0 |
| `Note` / `備註` | `Step Note` | 內容會照抄到 QLC+ 步驟編輯器的 Note 欄；空白就不寫 |

燈流表上實際用的是 **`Fades to black(ms)`**（這個 cue 結束後花多久暗下來），
QLC+ 沒有這個概念，所以由 [第 2 步](scripts/README.md#為什麼要有第-2-步) 先把它
翻成 `Fade out(ms)` 並補上黑燈 cue，再交給這一步轉檔。
直接餵原始表格也能跑，只是 `Fades to black(ms)` 會被當成不認得的欄位略過。

### 燈具通道欄位

格式為 **`<型號>[<索引>] <通道>`**，例如 `LSPA60RC[1-6] Red`、`ER-554[1] White`。

**索引**寫法：

| 寫法 | 意思 |
|---|---|
| `[1]` | 單一盞 |
| `[1-6]`、`[1~6]` | 連續範圍 |
| `[1;3;5]` | 指定數盞 |
| 省略中括號 | 該型號全部燈具 |

> ⚠️ 多盞請用分號 `[1;3;5]`。CSV 會把**沒加引號的逗號**當成欄位分隔，
> 寫成 `[1,3,5]` 會讓整個表頭被拆散。分隔符號也接受 `+` 與 `、`。

**通道**名稱大小寫、空白、連字號都會被忽略，中英文與縮寫皆可：

| 通道 | 可接受的寫法 |
|---|---|
| 亮度 | `Total dimming`、`Dimming`、`Dimmer`、`Dim`、`Intensity`、`Master`、`亮度`、`總亮度`、`調光` |
| 紅 | `Red`、`R`、`紅` |
| 綠 | `Green`、`G`、`綠` |
| 藍 | `Blue`、`B`、`藍` |
| 白（僅 ER-554） | `White`、`W`、`白` |
| 頻閃 | `Stroboscopic`、`Strobe`、`Strobo`、`頻閃`、`閃燈` |
| 模式 | `Function`、`Func`、`Mode`、`模式`、`功能` |
| 速度 | `Speed`、`Spd`、`速度` |

也可以直接寫通道編號：`LSPA60RC[1-6] ch4`、`LSPA60RC[1-6] 4`。

---

## 燈具對應表

**燈具清單不寫在程式裡，一律從輸入的底稿 .qxw 讀出來。** 第 3 步會解析底稿裡的
每個 `<Fixture>`，取得 fixture ID、DMX 位址、模式與通道長度，通道名稱再從對應的
`.qxf` 燈具定義檔補上（搜尋順序：底稿旁的 `Fixtures/`、底稿所在資料夾、來源 .xlsx／
專案資料夾旁的 `Fixtures/`、上一層的 `Fixtures/`、QLC+ 使用者資料夾、QLC+ 內建燈具庫；
內建庫是照廠牌分子資料夾放的，會多找一層）。實際用到哪個 `.qxf` 會印在 log。表頭索引就是底稿裡燈具名稱
結尾的 `[n]`，沒寫的話按 DMX 位址從 1 排。分析結果會印在 log 裡。

表頭寫到、但底稿裡沒有的燈具會被忽略，並在 log 列出是哪幾盞；沒有指定底稿則會直接中止。

以下是 `sample_file/BaseStage.qxw` 的實際配置，換一份底稿就會跟著換。

### LSPA 60RC（染色燈，7 通道）

| 表頭索引 | Fixture ID | DMX Address |
|---|---|---|
| `LSPA60RC[1]` | 2 | 0 |
| `LSPA60RC[2]` | 3 | 7 |
| `LSPA60RC[3]` | 4 | 14 |
| `LSPA60RC[4]` | 5 | 21 |
| `LSPA60RC[5]` | 6 | 28 |
| `LSPA60RC[6]` | 7 | 35 |

通道：`0` Total dimming、`1` Red、`2` Green、`3` Blue、`4` Stroboscopic、`5` Function、`6` Speed

### Guangzhou Enran ER-554（台面燈，8 通道）

| 表頭索引 | 位置 | Fixture ID | DMX Address |
|---|---|---|---|
| `ER-554[1]` | **左**台面燈 | 9 | 48 |
| `ER-554[2]` | **右**台面燈 | 8 | 56 |

通道：`0` Total dimming、`1` Red、`2` Green、`3` Blue、`4` **White**、`5` Stroboscopic、`6` Function、`7` Speed

> 索引依 DMX address 由小到大排。注意 QLC+ 檔案裡這兩盞的**顯示名稱順序是相反的**
> （ID 9 顯示為「ER-554 [1]」、ID 8 顯示為「ER-554 [2]」），
> 而 `FixtureGroup` 的排列順序也與此相反，兩者都不能當作依據。
> 這個對應是拿 `Sequence達達團_面光燈2`（ID 37）的實際數值驗證出來的：
> 該 Sequence 第 3 步 fixture ID 8 的 dimming 是 63，對應表格裡的 `ER-554[2]`。
> 若實際接線相反，在 QLC+ 裡把兩盞燈的名稱 `ER-554 [1]` / `ER-554 [2]` 對調再存檔即可，
> 不必改程式。

---

## 輸出模式

`--mode` 預設是 `merge`。三種模式**都需要底稿 `.qxw`**，因為燈具設定只有它有。

### `--mode merge`（預設）

把 Audio、BoundScene、Sequence、Show 插進底稿 workspace 的 `</Engine>` 之前，
並自動配發沒被占用的新 Function ID（連號）。**原檔其餘內容逐字元保留不動**。

```bash
python3 scripts/step3_cuelist_to_qxw.py sample_file/AllCueList.xlsx \
    --base sample_file/BaseStage.qxw \
    -o 新版.qxw
```

> merge 不會覆寫 `--base`，請用 `-o` 指定輸出檔。

### `--mode snippet`

只輸出 `<Function Type="Sequence">` 區塊，方便手動貼進既有檔案。

```bash
python3 scripts/step3_cuelist_to_qxw.py sample_file/AllCueList.xlsx \
    --base sample_file/BaseStage.qxw --mode snippet --stdout
```

### `--mode workspace`

產生一份獨立、可直接用 QLC+ 開啟的 `.qxw`：依底稿讀到的燈具重新寫一份 Fixture 定義，
加上每張表各自的隱藏 BoundScene 與 Sequence；專案模式下還會包含 Audio 與 Show。
只會宣告表格實際用到的燈具，適合快速預覽或單獨測試一段燈流。

```bash
python3 scripts/step3_cuelist_to_qxw.py sample_file/AllCueList.xlsx \
    --base sample_file/BaseStage.qxw --mode workspace -o 我的.qxw
```

---

## 參數總覽

```
usage: step3_cuelist_to_qxw.py [-h] [--sheet SHEET] [--list] [-o OUT]
                               [--mode {workspace,snippet,merge}]
                               [--base BASE] [--name NAME]
                               [--name-from {sheet,title}] [--folder FOLDER]
                               [--music-folder MUSIC_FOLDER]
                               [--show-folder SHOW_FOLDER]
                               [--run-order {SingleShot,Loop,PingPong}]
                               [--direction {Forward,Backward}] [--keep-zeros]
                               [--no-trim] [--stdout]
                               [來源 ...]
```

| 參數 | 預設 | 說明 |
|---|---|---|
| `來源` | `cuelist_transform.xlsx` | 專案資料夾，或 `.xlsx` / `.csv`（可多個） |
| `--sheet` | 全部 | 只轉換指定的 Excel 工作表；可重複指定 |
| `--list` | 關 | 只列出有哪些工作表與表格，不做轉換 |
| `-o`, `--out` | 沿用第一個來源檔名 | 輸出檔路徑 |
| `--mode` | `merge` | `merge` / `snippet` / `workspace` |
| `--base` | 專案底下的 `.qxw` | **必填**：要合併的既有 `.qxw`，燈具設定就是從這裡讀 |
| `--name` | 工作表名稱 | 直接指定 Sequence 名稱；可重複指定，依序對應每張表 |
| `--name-from` | `sheet` | Sequence 名稱來源：`sheet`=工作表名稱、`title`=表格標題 |
| `--folder` | `Sequence_Cuelist` | 把 Sequence 收進這個資料夾；給空字串則不分資料夾 |
| `--music-folder` | `Music` | 配樂放的資料夾 |
| `--show-folder` | `Show` | Show 放的資料夾 |
| `--run-order` | `SingleShot` | `SingleShot` / `Loop` / `PingPong` |
| `--direction` | `Forward` | `Forward` / `Backward` |
| `--keep-zeros` | 關 | 保留數值為 0 的通道 |
| `--no-trim` | 關 | 保留表格尾端重複的填充列 |
| `--stdout` | 關 | 輸出到畫面而不是檔案 |

---

## 資料夾

產生的 Sequence 會被收進 QLC+ 函式樹的 **`Sequence_Cuelist`** 資料夾，
不會跟既有的函式混在一起。

```xml
<Function ID="1" Type="Sequence" Name="cuelist_transform" Path="Sequence_Cuelist" BoundScene="0">
```

QLC+ 的資料夾就是 `<Function>` 上的 `Path` 屬性（參考檔裡的 `Path="60RC_Color"` 也是同一個機制），
巢狀資料夾用 `/` 分隔，例如 `--folder "燈流/2026迎新"`。

```bash
python3 scripts/step3_cuelist_to_qxw.py 我的專案 --folder "我的燈流"    # 改資料夾名稱
python3 scripts/step3_cuelist_to_qxw.py 我的專案 --folder ""           # 不分資料夾
```

> 每條 Sequence 附帶的 BoundScene 是**隱藏函式**，不會出現在函式樹裡，
> 所以不給它 Path，這點與 QLC+ 自己存檔的行為一致。

## 轉換規則說明

這些規則是比對 `舞台燈同步音樂播放_預先建立顏色與模式版本.qxw` 既有的 Sequence 推導出來的。
轉出的結果與參考檔 **逐字元相同**：60RC 表對上 `Sequence達達團_染色燈`（ID 10，20 步），
ER-554 表對上 `Sequence達達團_面光燈2`（ID 37，19 步）。
直接從 `表演燈流.xlsx` 的「XX組-表演名稱」工作表轉出來的兩條 Sequence 同樣逐字元相同。

### 值為 0 的通道會被省略

QLC+ 只記錄有作用的通道。例如 `dimming=255, R=0, G=0, B=0` 會寫成：

```xml
<Step ... Values="42">2:0,255:3:0,255:4:0,255:5:0,255:6:0,255:7:0,255</Step>
```

而不是把 `1,0,2,0,3,0` 也寫出來。加上 `--keep-zeros` 可保留完整通道。

**例外是整列都填 0 的黑燈 cue**：照上面的規則會變成一個沒有任何通道的空 Step，
QLC+ 會維持上一步的畫面而不是暗場，所以這種列會把表格宣告到的通道全部明確寫成 0。
第 2 步補出來的黑燈 cue 就是靠這個規則生效的。

### `Values` 屬性是總通道數

`Values="42"` 指的是涉及燈具的**通道總數**（6 盞 × 7 通道），
不是這個 Step 實際寫了幾個值。混用時會累加，例如 6 盞 60RC + 2 盞 ER-554 = `42 + 16 = 58`。

### 速度模式

固定輸出 `<SpeedModes FadeIn="PerStep" FadeOut="PerStep" Duration="PerStep"/>`，
讓每個 Step 使用自己的 `Duration(ms)` / `Fade In` / `Fade Out`。

### 尾端填充列會被裁掉

表格常會預留一批空白列（只填了預設的 `dimming=255`）。
程式預設會裁掉「**沒有 Duration，且內容與前一步完全相同**」的尾端列——
60RC 那張表的 30 列因此收斂成 20 個 Step，與參考檔一致。
（ER-554 那張表的填充列完全空白，本來就不會產生 Step，所以是 19 步。）
需要完整保留時加 `--no-trim`。

---

## 其他檔案

| 檔案 | 說明 |
|---|---|
| `scripts/step3_cuelist_to_qxw.py` | 主要工具：Excel / CSV / 專案資料夾 → QLC+ `.qxw` |
| `scripts/run_all.py` | 一次跑完拆表 → 展開黑燈 cue → 轉檔 → 改音檔路徑 |
| `scripts/step1_split_cuelist_xlsx.py` | 第 1 步：把燈表拆成每張工作表的 cuelist，並複製 mp3 與底稿 |
| `scripts/step2_fades_to_black.py` | 第 2 步：把 `Fades to black(ms)` 展開成黑燈 cue |
| `scripts/step4_retarget_qxw_music.py` | 第 4 步：把 `.qxw` 裡的音檔路徑改回 `Music/` |
| `app/qlcplus_gui.py` | 上面那條流程的拖曳介面（macOS / Windows 共用） |
| `app/macos/build_app.sh` | 打包成 `app/macos/dist/QLCplus轉檔工具.app` |
| `app/windows/build_exe.bat` | 在 Windows 上打包成 `app\windows\dist\QLCplus_Converter.exe` |
| `sample_file/AllCueList.xlsx` | 範例燈表：前 4 張是說明／下拉選單／空白模板／測試用，第 5 張起放各組燈流 |
| `sample_file/BaseStage.qxw` | 範例底稿：燈具與虛擬控制台都設定好，供 merge 用 |
| `sample_file/Music/` | 配樂，檔名要與工作表名稱相同才會被自動配對 |
| `sample_file/Fixtures/` | 兩支燈的 QLC+ 燈具定義（`LSPA-60RC.qxf`、`GuangzhouEnran_ER-554.qxf`），第 3 步靠它取得通道名稱 |

> 文件中提到的 `舞台燈同步音樂播放_預先建立顏色與模式版本.qxw`、`表演燈流.xlsx`、
> `cuelist_transform.xlsx/.csv` 是當初推導轉換規則時比對用的檔案，**沒有收在 repo 裡**，
> 出現在下面的說明裡只是為了交代規則的來源。

---

## 疑難排解

**「⚠ 略過 XXX：表頭裡的燈具都不在底稿裡」**
表頭的型號拼法對不上底稿裡的燈具，或索引超出底稿實際有的台數。
型號可以寫底稿裡的型號、廠牌+型號，或燈具名稱去掉 `[n]` 的部分；
索引就是燈具名稱結尾的 `[n]`。執行時 log 會先列出底稿讀到哪些燈具與索引，對照著改即可。

**「⚠ 這些燈具不在 XXX.qxw 裡，相關欄位已忽略」**
同上，只是同一張表裡還有別的燈具能轉，所以只略過那幾欄。

**「沒有指定要合併的 .qxw」**
第 3 步一定要底稿。把 `.qxw` 放進專案資料夾底下（`run_all.py`／拖曳介面的第三個參數），
或用 `--base` 直接指定。

**QLC+ 開檔說找不到燈具**
底稿用到的 `.qxf` 不在 QLC+ 的使用者燈具庫裡。拖曳介面轉換後會自動檢查並提供一鍵複製；
手動的話就把 `.qxf` 複製到 `~/Library/Application Support/QLC+/Fixtures/`（macOS）或
`%USERPROFILE%\QLC+\Fixtures\`（Windows）。

**Excel 轉出來少了一張表的資料**
多半是先用 Excel 另存成 CSV 才轉——CSV 只裝得下一張工作表。請直接餵 `.xlsx`，
或用 `--list` 確認檔案裡實際有哪些表格。

**「⚠ 略過沒有 Step 的表」**
偵測到表頭，但底下沒有任何有效資料列。常見於檔案結尾多了一列表頭，
或用 `cat` 串接沒有換行結尾的檔案，導致上一列資料與下一張表的表頭黏在一起。

**某個欄位被靜靜略過**
執行摘要最後會列出「略過的欄位」。最常見原因是索引裡用了沒加引號的逗號，
把表頭拆成了好幾欄——改用 `[1;3;5]`。

**`PermissionError: Operation not permitted`（只會發生在 macOS 的 .app）**
`~/Documents`、`~/Desktop` 受 macOS 的 TCC 保護，未簽章的 App 不能覆寫
**別的程式建立**的檔案——最常見的是上次用終端機跑過，產物留在那裡。
程式會自己先刪舊檔再重寫，多數情況會自動過關；真的刪不掉時會印出明確訊息
告訴你要刪哪個資料夾。詳見 [`app/macos/README.md`](app/macos/README.md#常見問題)。

---

## Repository

```bash
git clone https://gitlab.com/script6953736/qlcplus_script/qlcplus_excel_conversion.git
```
