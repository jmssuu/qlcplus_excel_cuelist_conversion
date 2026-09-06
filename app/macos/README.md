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
macOS 的檔案權限（TCC）擋住了 App 覆寫某個它沒被授權過的舊檔（例如上次用終端機產生的
`*.qxw.bak`）。把那個舊檔刪掉，或到「系統設定 → 隱私權與安全性 → 完全取用磁碟」
把這個 App 加進去。備份失敗本身不會中斷轉換，只會印一行警告。

**拖曳沒反應**

```bash
QLCPLUS_GUI_SELFTEST=1 "app/macos/dist/QLCplus轉檔工具.app/Contents/MacOS/QLCplus轉檔工具"
```

會印出 `HAS_DND=True tkdnd=2.10.2 frozen=True`；若是 `False` 就重跑一次 `build_app.sh`。
