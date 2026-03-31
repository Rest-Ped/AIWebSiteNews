@echo off
setlocal

cd /d "%~dp0"

echo ============================================
echo IDO SKILLS News - Telegram Bot
echo ============================================

if exist ".env.bot" (
    echo [OK] .env.bot found
) else (
    echo [WARN] .env.bot not found, using .env values
)

if exist "..\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=..\.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo [RUN] Starting telegram_bot.py
"%PYTHON_EXE%" telegram_bot.py

endlocal
