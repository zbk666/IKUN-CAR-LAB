@echo off
setlocal EnableExtensions
title CAR LAB Launcher
cd /d "%~dp0"

echo ==========================================
echo CAR LAB v1.3.1
echo ==========================================
echo.

set "VENV=%~dp0.venv\Scripts\python.exe"

if exist "%VENV%" goto RUN

echo [1/3] Creating virtual environment...
where py >nul 2>&1
if not errorlevel 1 (
    py -m venv "%~dp0.venv"
    if errorlevel 1 goto FAIL
    goto PIP
)

where python >nul 2>&1
if not errorlevel 1 (
    python -m venv "%~dp0.venv"
    if errorlevel 1 goto FAIL
    goto PIP
)

echo ERROR: Python was not found.
echo Install Python 3.10+ and run this file again.
goto FAIL

:PIP
set "VENV=%~dp0.venv\Scripts\python.exe"
echo [2/3] Checking pip...
"%VENV%" -m pip --version >nul 2>&1
if errorlevel 1 "%VENV%" -m ensurepip --upgrade

"%VENV%" -m pip --version >nul 2>&1
if errorlevel 1 (
    echo pip is missing. Rebuilding environment...
    rmdir /s /q "%~dp0.venv"
    where py >nul 2>&1
    if not errorlevel 1 (py -m venv "%~dp0.venv") else (python -m venv "%~dp0.venv")
    if errorlevel 1 goto FAIL
)

echo [3/3] Installing dependencies...
"%VENV%" -m pip install -r "%~dp0requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple
if errorlevel 1 (
    echo Mirror failed. Trying official PyPI...
    "%VENV%" -m pip install -r "%~dp0requirements.txt"
    if errorlevel 1 goto FAIL
)

:RUN
echo.
echo Starting CAR LAB...
echo.
"%VENV%" "%~dp0main.py"
set "ERR=%ERRORLEVEL%"
echo.
if "%ERR%"=="0" (
    echo CAR LAB exited normally.
) else (
    echo CAR LAB failed. Error code: %ERR%
    echo Please send this window screenshot.
)
pause
exit /b %ERR%

:FAIL
echo.
echo Launcher failed.
echo Please send this window screenshot.
pause
exit /b 1
