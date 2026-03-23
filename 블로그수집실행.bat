@echo off
chcp 65001 >nul 2>&1
title Blog Crawler - Novasonic
cd /d "%~dp0"

echo.
echo ================================================
echo   Blog Crawler - Novasonic Eyecare
echo ================================================
echo.

REM -- Python check --
echo [Step 1] Checking Python...
python --version
if errorlevel 1 (
    echo.
    echo [ERROR] Python not found!
    echo         Download from: https://www.python.org/downloads/
    echo         IMPORTANT: Check "Add Python to PATH" during install!
    echo.
    pause
    exit /b
)
echo OK!
echo.

REM -- Install packages --
echo [Step 2] Installing required packages...
echo          (This may take 1-2 minutes on first run)
echo.
pip install requests beautifulsoup4 lxml python-dotenv openpyxl
echo.
if errorlevel 1 (
    echo [WARNING] Some packages failed to install.
    echo           Trying with --user flag...
    pip install requests beautifulsoup4 lxml python-dotenv openpyxl --user
    echo.
)

REM -- Run crawler --
echo [Step 3] Starting blog crawler...
echo.
python -u blog_crawler.py
if errorlevel 1 (
    echo.
    echo [ERROR] Script failed. Check error message above.
    echo.
)

echo.
echo ================================================
echo   Check the [blog_collect] folder for results.
echo ================================================
echo.
pause
