@echo off
echo ============================================
echo IDO SKILLS News - Telegram Bot Launcher
echo ============================================

cd /d "%~dp0"

echo [1/3] Проверка переменных окружения...
if not exist ".env.bot" (
    echo [WARNING] Файл .env.bot не найден, используем значения по умолчанию
) else (
    echo [OK] Файл .env.bot найден
    for /f "delims=" %%a in (.env.bot) do set %%a
)

echo [2/3] Проверка бэкенда...
curl -s http://localhost:5000/api/health >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Бэкенд не отвечает на http://localhost:5000
    echo [INFO] Запустите бэкенд: python app.py
    pause
    exit /b 1
)
echo [OK] Бэкенд доступен

echo [3/3] Запуск бота...
echo Откройте Telegram и найдите вашего бота
echo ============================================

..\venv\Scripts\python.exe telegram_bot_production.py

pause