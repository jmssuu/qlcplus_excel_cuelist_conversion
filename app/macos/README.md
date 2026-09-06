# macOS 執行檔

這個資料夾放 **macOS 版**的打包腳本與產物。Windows 版在隔壁的 [`../windows/`](../windows/)。

## 打包

```bash
app/macos/build_app.sh
```

第一次執行會在專案根目錄建立 `.venv` 並安裝 openpyxl、pyinstaller、tkinterdnd2，
之後每次約一分半。

## 產出

```
app/macos/
├── build_app.sh                      打包腳本
├── dist/QLCplus轉檔工具.app          ← 成品，雙擊即可執行
├── dist/QLCplus轉檔工具/             同一份程式的命令列版本
├── build/                            中繼檔，可以刪
└── QLCplus轉檔工具.spec              中繼檔，可以刪
```

`.app` 是自帶 Python 的獨立程式（約 36 MB），可以複製到「應用程式」或桌面，
不需要對方電腦裝 Python。

## 常見問題

**第一次開啟被 Gatekeeper 擋下（「無法驗證開發者」）**
沒有簽章的 App 都會這樣。在 Finder 對它**按右鍵 →「打開」→ 再按一次「打開」**，
之後就能直接雙擊。或到「系統設定 → 隱私權與安全性」按「仍要打開」。

**訊息裡出現 `PermissionError: Operation not permitted`**
macOS 的檔案權限（TCC）擋住了 App 覆寫**別的程式建立**的舊檔——最常見的情況是
上次用終端機跑過一次，產物留在 `~/Documents` 底下，App 就改不動它了。

轉檔程式會自己處理：覆寫失敗時先把舊檔刪掉再重寫，多數情況會自動過關。
若連刪都刪不掉，會印出一行明確訊息（不再是 traceback）告訴你要刪哪個資料夾：

```
[失敗] 沒有權限覆寫 …/temp_AllCueList/XX組-表演名稱/1_raw.xlsx（Operation not permitted）。
    舊檔多半是用終端機或別的程式產生的，macOS 不讓未簽章的 App 改它。
    請把 …/temp_AllCueList 整個資料夾刪掉後重跑，
    或到「系統設定 → 隱私權與安全性 → 完全取用磁碟」把這個 App 加進去。
```

照訊息把那個資料夾刪掉即可（`temp_…` 只是中繼產物）。
備份 `.qxw.bak` 失敗則從來不會中斷轉換，只印一行警告。

**拖曳沒反應**

```bash
QLCPLUS_GUI_SELFTEST=1 "app/macos/dist/QLCplus轉檔工具.app/Contents/MacOS/QLCplus轉檔工具"
```

會印出 `HAS_DND=True tkdnd=2.10.2 frozen=True`；若是 `False` 就重跑一次 `build_app.sh`。
