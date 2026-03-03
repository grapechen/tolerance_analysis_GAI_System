@echo off
REM API 測試腳本

cd /d "%~dp0"

echo ==========================================
echo   ISO 286 API 測試
echo ==========================================
echo.

if not exist ".venv" (
    echo [錯誤] 虛擬環境不存在！
    echo 請先執行 setup.bat
    pause
    exit /b 1
)

echo 確保服務已啟動在 http://127.0.0.1:7010
echo 如果未啟動，請先執行 run_basic.bat
echo.
pause

echo 執行測試...
.venv\Scripts\python.exe tests/test_api.py

pause
