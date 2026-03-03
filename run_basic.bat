@echo off
REM 啟動基本公差查詢系統

cd /d "%~dp0"

if not exist ".venv" (
    echo [錯誤] 虛擬環境不存在！
    echo 請先執行 setup.bat 進行環境設置
    pause
    exit /b 1
)

echo ==========================================
echo   啟動基本公差查詢系統
echo ==========================================
echo.
echo 服務位址: http://127.0.0.1:7010
echo 按 Ctrl+C 停止服務
echo.

.venv\Scripts\python.exe server/app.py
pause
