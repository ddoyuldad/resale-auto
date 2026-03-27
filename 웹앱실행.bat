@echo off
chcp 65001 >nul 2>&1
title 매입건 자동화 웹앱 v2.1

echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo   매입건 자동화 프로그램 v2.1
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

cd /d "%~dp0"

REM ── 기존 서버 종료 ──
echo [0/3] 기존 서버 정리 중...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8080" ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 2 /nobreak >nul

REM ── 패키지 설치 (화면에 표시) ──
echo [1/3] 패키지 설치 중...
echo.
pip install openpyxl Pillow anthropic requests jinja2 flask google-genai beautifulsoup4
echo.
if errorlevel 1 (
    echo !! pip 설치 실패. Python이 설치되어 있는지 확인해 주세요.
    echo    Python 다운로드: https://www.python.org/downloads/
    pause
    exit /b
)

echo [2/3] 설치 확인 중...
python -c "from google import genai; print('  google-genai OK')"
if errorlevel 1 (
    echo.
    echo !! google-genai 설치 실패. 수동 설치를 시도합니다...
    pip install --upgrade google-genai
    echo.
)

echo [3/3] 서버 시작 중...
echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo   브라우저에서 접속: http://localhost:8080
echo.
echo   페이지가 안 바뀌면 Ctrl+Shift+R
echo   종료하려면 이 창을 닫으세요
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

start /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8080"
python webapp.py

pause
