# app — 拖曳介面與執行檔

`qlcplus_gui.py` 是 [`scripts/run_all.py`](../scripts/run_all.py) 的圖形介面：
把總表 `.xlsx` 拖進視窗 → 確認 Music 資料夾與底稿 `.qxw` → 按「執行轉換」，
過程訊息即時顯示在下方（可選取、右鍵複製，或按「複製訊息」整份複製、「清除訊息」清空）。

```
app/
├── qlcplus_gui.py     介面原始碼，macOS 與 Windows 共用同一份
├── macos/             macOS 打包腳本與產物（見 macos/README.md）
│   ├── build_app.sh
│   └── dist/QLCplus轉檔工具.app
└── windows/           Windows 打包腳本與產物（見 windows/README.md）
    ├── build_exe.bat
    └── dist/QLCplus_Converter.exe
```

**產物是分開的**：macOS 的 `.app` 只會出現在 `macos/dist/`，
Windows 的 `.exe` 只會出現在 `windows/dist/`，兩邊的 `build/` 與 `*.spec` 也各自獨立。

## 直接跑原始碼

```bash
python3 app/qlcplus_gui.py
```

拖曳功能需要 `tkinterdnd2`（`python3 -m pip install tkinterdnd2`）；
沒裝也能用，改成點一下拖曳區選檔。轉檔本身需要 `openpyxl`。

## 打包

| 平台 | 指令 | 產物 |
|---|---|---|
| macOS | `app/macos/build_app.sh` | `app/macos/dist/QLCplus轉檔工具.app` |
| Windows | `app\windows\build_exe.bat`（要在 Windows 上跑） | `app\windows\dist\QLCplus_Converter.exe` |

PyInstaller 不能跨平台編譯：`.exe` 一定要在 Windows 電腦上打包，
在 macOS 上跑再多次也產不出來。

兩邊檔名不一樣是刻意的：cmd.exe 用 cp950 讀 `.bat`，中文會變亂碼，
所以 Windows 那支腳本與產出的 `.exe` 一律用 ASCII 檔名（介面本身仍是中文）。
細節見 [`windows/README.md`](windows/README.md)。

## 介面說明

* **點我展開使用說明** — 收合式說明，列出 `.xlsx` 旁邊要準備哪些東西，以及產物在哪裡。
* **拖曳區** — 拖入 `.xlsx` 後顯示完整路徑；點一下也可以開選檔視窗。
* **Music 資料夾** — 拖入 `.xlsx` 後自動帶入它旁邊的 `Music/`，可再拖或按「瀏覽…」改。
* **底稿 .qxw** — **必填**（燈具設定是從它讀出來的）。拖入 `.xlsx` 後會自動抓旁邊的
  `BaseStage.qxw`；那個檔名不存在但資料夾裡剛好只有一份 `.qxw` 時也會採用。
  自己指定過的路徑不會被自動蓋掉。沒有底稿就按不下去，會跳視窗說明原因。
* **執行轉換結束後自動刪除temp檔** — 預設勾選；不管轉換成功或失敗，
  結束後都會刪掉 `temp_<檔名>/`。取消勾選就會留著中繼檔。
* **執行轉換** — 跑完拆表 → 展開黑燈 cue → 轉 `.qxw` → 改音檔路徑，
  輸出在 `.xlsx` 旁邊的 `<檔名>.qxw`。
* **燈具庫提示列** — 轉換後會檢查 QLC+ 使用者燈具庫有沒有這份底稿用到的燈具檔，
  缺了就顯示警告與「是否要幫你加入燈具檔？」，按一下自動把 `.qxf` 複製過去。
* 訊息區唯讀，但可以選取、`Cmd/Ctrl+C` 複製、右鍵選單，或按「複製訊息」／「清除訊息」。
  訊息會依內容上色：錯誤紅字、提醒黃字、成功綠字。

## 排查

拖曳沒反應時，用終端機執行執行檔並帶上環境變數，會印出拖曳套件的狀態：

```bash
QLCPLUS_GUI_SELFTEST=1 "app/macos/dist/QLCplus轉檔工具.app/Contents/MacOS/QLCplus轉檔工具"
# HAS_DND=True tkdnd=2.10.2 frozen=True
```

`HAS_DND=False` 表示 tkinterdnd2 沒被打包進去，重跑一次打包腳本即可。
