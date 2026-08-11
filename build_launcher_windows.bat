@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo IKUN CAR LAB Launcher - Windows Build
echo ==========================================
echo.

where py >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is required to build the launcher.
    pause
    exit /b 1
)

py -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo ERROR: PyInstaller install failed.
    pause
    exit /b 1
)

py -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name IKUN_Launcher ^
  IKUN_Launcher.py

if errorlevel 1 (
    echo ERROR: EXE build failed.
    pause
    exit /b 1
)

if not exist "release" mkdir release
copy /y "dist\IKUN_Launcher.exe" "release\IKUN_Launcher.exe" >nul

echo.
echo Build complete:
echo release\IKUN_Launcher.exe
pause
