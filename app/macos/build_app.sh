#!/bin/bash
# 把 ../qlcplus_gui.py 打包成 macOS 可直接雙擊的執行檔。
#
#   app/macos/build_app.sh
#
# 產出（都留在這個 app/macos/ 資料夾裡）：
#   app/macos/dist/QLCplus轉檔工具.app   ← macOS 應用程式（雙擊即可）
#   app/macos/dist/QLCplus轉檔工具/      ← 同一份程式的命令列版本
#   app/macos/build/、app/macos/*.spec   ← PyInstaller 的中繼檔，可以刪
#
# 第一次跑會在專案根目錄建立 .venv 並安裝 openpyxl / pyinstaller / tkinterdnd2。
set -euo pipefail
cd "$(dirname "$0")"

NAME="QLCplus轉檔工具"
ROOT="../.."               # 專案根目錄（.venv 放這裡）
SCRIPTS="$ROOT/scripts"    # 轉檔用的 run_all.py 等模組
GUI="../qlcplus_gui.py"    # 介面原始碼（與 Windows 版共用同一份）
VENV="$ROOT/.venv"

if [ ! -x "$VENV/bin/python" ]; then
    echo "==> 建立 $VENV"
    python3 -m venv "$VENV"
fi
echo "==> 安裝相依套件"
"$VENV/bin/python" -m pip install -q --upgrade pip
"$VENV/bin/python" -m pip install -q openpyxl pyinstaller tkinterdnd2

echo "==> 打包"
rm -rf "build/$NAME" "dist/$NAME" "dist/$NAME.app"
"$VENV/bin/python" -m PyInstaller \
    --noconfirm --clean --windowed \
    --name "$NAME" \
    --osx-bundle-identifier com.qlcplus.excel.conversion \
    --paths "$SCRIPTS" \
    --collect-all tkinterdnd2 \
    --hidden-import openpyxl \
    "$GUI"

# 讓 .xlsx 可以直接拖到 Dock 上的圖示開啟
PLIST="dist/$NAME.app/Contents/Info.plist"
if [ -f "$PLIST" ]; then
    /usr/libexec/PlistBuddy -c "Delete :CFBundleDocumentTypes" "$PLIST" 2>/dev/null || true
    /usr/libexec/PlistBuddy \
        -c "Add :CFBundleDocumentTypes array" \
        -c "Add :CFBundleDocumentTypes:0 dict" \
        -c "Add :CFBundleDocumentTypes:0:CFBundleTypeName string Excel Workbook" \
        -c "Add :CFBundleDocumentTypes:0:CFBundleTypeRole string Viewer" \
        -c "Add :CFBundleDocumentTypes:0:LSItemContentTypes array" \
        -c "Add :CFBundleDocumentTypes:0:LSItemContentTypes:0 string org.openxmlformats.spreadsheetml.sheet" \
        "$PLIST" >/dev/null

    # 沒有這些說明字串，macOS 會直接擋掉 App 讀取「文件 / 桌面 / 下載 / 外接磁碟」
    # 的內容（iterdir 收到 Operation not permitted），連授權視窗都不會跳。
    DESC="需要讀取你選擇的總表、Music 資料夾與底稿 .qxw。"
    for KEY in NSDocumentsFolderUsageDescription NSDesktopFolderUsageDescription \
               NSDownloadsFolderUsageDescription NSRemovableVolumesUsageDescription; do
        /usr/libexec/PlistBuddy -c "Delete :$KEY" "$PLIST" 2>/dev/null || true
        /usr/libexec/PlistBuddy -c "Add :$KEY string $DESC" "$PLIST" >/dev/null
    done
fi

# 改完 Info.plist 一定要重簽：PyInstaller 打包時已經蓋了一個 ad-hoc 簽章，
# 上面那段 PlistBuddy 會破壞封印，變成「已損毀，無法打開」——本機跑不會有事，
# 但只要檔案被下載過（帶 com.apple.quarantine），Gatekeeper 就會直接擋掉。
echo "==> 重新簽章"
codesign --force --deep --sign - "dist/$NAME.app"
codesign --verify --deep --strict "dist/$NAME.app" && echo "    簽章 OK"

echo
echo "完成： app/macos/dist/$NAME.app"
