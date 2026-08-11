@echo off
cd /d "%~dp0"
py IKUN_Launcher.py
if errorlevel 1 pause
