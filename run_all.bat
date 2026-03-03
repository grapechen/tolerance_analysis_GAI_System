@echo off
REM 同時啟動兩個服務

cd /d "%~dp0"

if not exist ".venv" (
    echo [錯誤] 虛擬環境不存在！
    echo 請先執行 setup.bat 進行環境設置
    pause
    exit /b 1
)

echo ==========================================
echo   啟動所有服務
echo ==========================================
echo.
echo 基本查詢系統: http://127.0.0.1:7010
echo AI 智能助手:  http://127.0.0.1:7011
echo.
echo 按 Ctrl+C 停止所有服務
echo.

REM 在新視窗啟動基本查詢系統
start "ISO 286 基本查詢" cmd /k ".venv\Scripts\python.exe server/app.py"

REM 等待 2 秒
timeout /t 2 /nobreak >nul

REM 在新視窗啟動 AI 助手
start "ISO 286 AI 助手" cmd /k ".venv\Scripts\python.exe server/ai_app.py"

echo.
echo ✓ 兩個服務已在新視窗中啟動
echo.
pause
