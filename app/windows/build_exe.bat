@echo off
REM ---------------------------------------------------------------------------
REM  Build the QLC+ cuelist converter GUI into a single Windows .exe.
REM
REM  Usage:  double-click this file, or run  app\windows\build_exe.bat
REM
REM  Output (everything stays inside app\windows):
REM      app\windows\dist\QLCplus_Converter.exe   <- the app, one single file
REM      app\windows\build\, *.spec               <- scratch files, safe to delete
REM
REM  Requires Python 3.9+ ("Add Python to PATH" checked during install).
REM  The first run creates .venv-win and installs openpyxl / pyinstaller /
REM  tkinterdnd2.
REM
REM  NOTE: this file is deliberately pure ASCII. cmd.exe reads .bat files using
REM  the OEM code page (cp950 on zh-TW Windows), so any UTF-8 Chinese text here
REM  turns into garbage and breaks the script. The app's own UI is still in
REM  Chinese - that text lives in ..\qlcplus_gui.py, which Python reads as UTF-8.
REM  See README.md in this folder for the Chinese documentation.
REM ---------------------------------------------------------------------------

setlocal
cd /d "%~dp0"

set "NAME=QLCplus_Converter"
set "ROOT=..\.."
set "SCRIPTS=%ROOT%\scripts"
set "GUI=..\qlcplus_gui.py"
set "VENV=%ROOT%\.venv-win"
set "PY=%VENV%\Scripts\python.exe"

if not exist "%GUI%" (
    echo [ERROR] Cannot find "%GUI%".
    echo         Copy the whole project folder over, not just app\windows.
    goto :fail
)

if not exist "%PY%" (
    echo ==^> Creating virtual env: %VENV%
    py -3 -m venv "%VENV%"
    if not exist "%PY%" python -m venv "%VENV%"
    if not exist "%PY%" (
        echo [ERROR] Could not create a virtual env.
        echo         Install Python 3.9+ from python.org and tick
        echo         "Add Python to PATH", then run this script again.
        goto :fail
    )
)

echo ==^> Installing dependencies
"%PY%" -m pip install --upgrade pip
if errorlevel 1 goto :fail
"%PY%" -m pip install openpyxl pyinstaller tkinterdnd2
if errorlevel 1 goto :fail

echo ==^> Building
if exist "dist\%NAME%.exe" del /q "dist\%NAME%.exe"
"%PY%" -m PyInstaller ^
    --noconfirm --clean --windowed --onefile ^
    --name "%NAME%" ^
    --distpath "dist" --workpath "build" --specpath "." ^
    --paths "%SCRIPTS%" ^
    --collect-all tkinterdnd2 ^
    --hidden-import openpyxl ^
    "%GUI%"
if errorlevel 1 goto :fail
if not exist "dist\%NAME%.exe" goto :fail

echo.
echo Done:  app\windows\dist\%NAME%.exe
echo.
pause
exit /b 0

:fail
echo.
echo Build failed. Copy the messages above and send them over.
echo.
pause
exit /b 1
