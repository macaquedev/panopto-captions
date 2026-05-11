@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py build-app.py
) else (
    python build-app.py
)
if errorlevel 1 pause
