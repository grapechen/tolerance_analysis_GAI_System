@echo off
REM 啟動 AI 智能助手

cd /d "%~dp0"

if not exist ".venv" (
    echo [錯誤] 虛擬環境不存在！
    echo 請先執行 setup.bat 進行環境設置
    pause
    exit /b 1
)

echo ==========================================
echo   啟動 AI 智能助手
echo ==========================================
echo.
echo 服務位址: http://127.0.0.1:7011
echo 按 Ctrl+C 停止服務
echo.
echo 注意: 需要先安裝並啟動 Ollama
echo       ollama pull gemma3:4b
echo.

.venv\Scripts\python.exe server/ai_app.py
pause
