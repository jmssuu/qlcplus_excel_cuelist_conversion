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
沒有經過 Apple 公證（notarize）的 App 都會這樣。到
**「系統設定 → 隱私權與安全性」**往下捲，會看到剛才被擋的 App，按**「仍要打開」**。
（macOS 15 之後 Apple 拿掉了右鍵 →「打開」的捷徑，只剩系統設定這條路。）

**「已損毀，無法打開。你應該將其丟到垃圾桶」**
這不是檔案真的壞掉，是**簽章封印被破壞**——Gatekeeper 對簽章無效的 App 只會給這個
訊息，連「仍要打開」都不給。只會發生在**下載過**的檔案（帶 `com.apple.quarantine`
標記），本機剛打包出來的那份不會有事，所以很容易到發佈給別人時才發現。

`build_app.sh` 已經處理掉最常見的原因：PyInstaller 打包時會蓋一個 ad-hoc 簽章，
而腳本後面用 PlistBuddy 改 `Info.plist`（加上拖曳 `.xlsx` 的設定）會破壞封印，
所以改完之後一定要重簽：

```bash
codesign --force --deep --sign - "dist/QLCplus轉檔工具.app"
codesign --verify --deep --strict "dist/QLCplus轉檔工具.app"   # 沒有輸出就是通過
```

拿到別人給的 `.app` 若還是出現這個訊息，可以直接清掉 quarantine 標記：

```bash
xattr -dr com.apple.quarantine "/Applications/QLCplus轉檔工具.app"
```

要診斷到底是哪裡不合格，用 Apple 自己的工具（macOS 14 以上）：

```bash
syspolicy_check distribution "dist/QLCplus轉檔工具.app"
```

只列出 `Adhoc Signed App` 與 `Notary Ticket Missing` 是正常的（未公證的必然結果）；
若出現 `Invalid Info.plist (plist or signature have been modified)` 就是封印壞了，重簽即可。

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
