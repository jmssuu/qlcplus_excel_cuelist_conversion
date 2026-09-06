# Windows 執行檔

這個資料夾放 **Windows 版**的打包腳本與產物。macOS 版在隔壁的 [`../macos/`](../macos/)。

**必須在 Windows 電腦上打包**——PyInstaller 不能跨平台編譯，
在 macOS 上跑再多次也產不出 `.exe`。

## 怎麼產生 .exe

1. 把整個專案資料夾複製到 Windows 電腦（至少要有 `scripts\` 和 `app\`）。
2. 裝 [Python 3.9 以上](https://www.python.org/downloads/windows/)，
   安裝畫面**記得勾「Add Python to PATH」**。
3. 進 `app\windows\`，按兩下 `build_exe.bat`（或在命令提示字元執行它）。

第一次會自動建立 `.venv-win` 並安裝 openpyxl、pyinstaller、tkinterdnd2，約 1～3 分鐘。

## 產出

```
app\windows\
├── build_exe.bat                  打包腳本
├── dist\QLCplus_Converter.exe     ← 成品，單一檔案，可以單獨複製給別人
├── build\                         中繼檔，可以刪
└── QLCplus_Converter.spec         中繼檔，可以刪
```

`--onefile` 打出來的是單一 `.exe`，不必帶著一整個資料夾；
代價是每次啟動會先解壓到暫存資料夾，開啟比 macOS 版慢幾秒。

## 為什麼 .bat 全是英文、.exe 也是英文檔名

**cmd.exe 是用系統的 OEM 編碼（繁體中文 Windows 是 cp950）讀 `.bat`**，
但檔案是以 UTF-8 儲存的。中文註解與訊息會整段變成亂碼，連引號都會被吃掉，
腳本直接跑不動：

```
'甈∪銵??芸?撱箇?' 不是內部或外部命令、可執行的程式或批次檔。
```

`chcp 65001` 也救不了——cmd 是邊讀邊解析，執行到那行時前面已經壞掉了。
所以 `build_exe.bat` **刻意寫成純 ASCII**（連產出的檔名 `QLCplus_Converter.exe` 也是），
中文說明一律留在這份 README 裡。

> 編輯 `build_exe.bat` 時請維持純英文與 CRLF 換行，不要加中文註解。

**程式介面本身還是中文**——那些字在 `..\qlcplus_gui.py` 裡，
由 Python 以 UTF-8 讀取，跟 cmd 的編碼無關。

## 介面與 macOS 版完全相同

同一份 [`app/qlcplus_gui.py`](../qlcplus_gui.py)，只有字體會自動換成
Microsoft JhengHei UI / Consolas。拖曳 `.xlsx` → 確認 Music 資料夾 → 按「執行轉換」，
輸出一樣是 `.xlsx` 旁邊的 `<檔名>.qxw`。

## 常見問題

**Windows Defender SmartScreen 跳出「已保護您的電腦」**
沒有簽章的 `.exe` 都會這樣。按「其他資訊」→「仍要執行」。

**按兩下 .exe 沒反應／閃一下就關掉**
在命令提示字元執行下面兩行，會印出拖曳套件的狀態，有錯誤也會留在畫面上：

```
set QLCPLUS_GUI_SELFTEST=1
dist\QLCplus_Converter.exe
```

**拖曳沒反應**
同上，若印出 `HAS_DND=False` 表示 tkinterdnd2 沒被打包進去，
重跑一次 `build_exe.bat` 即可（介面仍可點擊拖曳區選檔）。

**打包失敗**
腳本結尾有 `pause`，訊息會留在畫面上不會閃退，把它貼出來即可。

**轉檔時出現 `PermissionError`**
最常見的原因是產物（`1_raw.xlsx`、`2_forqxw.xlsx` 或 `.qxw`）正開在 Excel／QLC+ 裡。
程式會先試著刪掉舊檔再重寫，刪不掉時會印出明確訊息告訴你關掉哪個檔案。
把檔案關掉後重跑即可。

## 這份腳本驗證到哪裡

`build_exe.bat` 用的那組 PyInstaller 參數已經在 macOS 上原封不動跑過，
可以正常打包並啟動（`HAS_DND=True tkdnd=2.10.2`），代表路徑與參數本身沒問題；
batch 語法本身則是照 cmd 的規則寫的（純 ASCII、CRLF、`errorlevel` 檢查），
但**尚未在 Windows 上實機跑過**。
