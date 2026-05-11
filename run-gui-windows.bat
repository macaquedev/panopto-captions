@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py panopto-caption-gui.py
) else (
    python panopto-caption-gui.py
)
if errorlevel 1 pause
