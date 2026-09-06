# app — 拖曳介面與執行檔

`qlcplus_gui.py` 是 [`scripts/run_all.py`](../scripts/run_all.py) 的圖形介面：
把總表 `.xlsx` 拖進視窗 → 確認 Music 資料夾 → 按「執行轉換」，
過程訊息即時顯示在下方（可選取、右鍵複製，或按「複製訊息」整份複製）。

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

* **拖曳區** — 拖入 `.xlsx` 後顯示完整路徑；點一下也可以開選檔視窗。
* **Music 資料夾** — 拖入 `.xlsx` 後自動帶入它旁邊的 `Music/`，可再拖或按「瀏覽…」改。
* **底稿 .qxw** — 可留空；填了就複製進專案資料夾當 merge 底稿。
* **執行轉換** — 跑完拆表 → 展開黑燈 cue → 轉 `.qxw` → 改音檔路徑，
  輸出在 `.xlsx` 旁邊的 `<檔名>.qxw`。
* 訊息區唯讀，但可以選取、`Cmd/Ctrl+C` 複製、右鍵選單、或按「複製訊息」。

## 排查

拖曳沒反應時，用終端機執行執行檔並帶上環境變數，會印出拖曳套件的狀態：

```bash
QLCPLUS_GUI_SELFTEST=1 "app/macos/dist/QLCplus轉檔工具.app/Contents/MacOS/QLCplus轉檔工具"
# HAS_DND=True tkdnd=2.10.2 frozen=True
```

`HAS_DND=False` 表示 tkinterdnd2 沒被打包進去，重跑一次打包腳本即可。
