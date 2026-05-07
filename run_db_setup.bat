@echo off
chcp 65001 >nul
echo =========================================
echo  ISO 286 MySQL Database Setup
echo =========================================
echo.

:: ── Step 1: 檢查 MySQL 是否已啟動 ─────────────────────────────────────────
echo [1/3] Checking MySQL service...
sc query MySQL80 >nul 2>&1
if %errorlevel% NEQ 0 (
    sc query MySQL >nul 2>&1
    if %errorlevel% NEQ 0 (
        echo   [WARNING] MySQL service not found.
        echo   Please run setup_mysql_win.ps1 first ^(as Administrator^):
        echo     PowerShell -ExecutionPolicy Bypass -File setup_mysql_win.ps1
        echo.
        pause
        exit /b 1
    )
)
echo   OK - MySQL service found

:: ── Step 2: 啟動 MySQL（若未運行）────────────────────────────────────────
net start MySQL80 >nul 2>&1
net start MySQL   >nul 2>&1
echo   MySQL started

:: ── Step 3: 執行 Python 填資料腳本 ───────────────────────────────────────
echo.
echo [2/3] Setting up Python environment...
cd /d %~dp0

:: 嘗試使用虛擬環境
if exist "server\.venv\Scripts\activate.bat" (
    call server\.venv\Scripts\activate.bat
    echo   Using venv: server\.venv
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo   Using venv: .venv
) else (
    :: 嘗試 Anaconda tol_env
    call conda activate tol_env >nul 2>&1
    echo   Using conda: tol_env
)

:: 確認相依套件
pip install pymysql sqlalchemy python-dotenv --quiet

echo.
echo [3/3] Running populate_iso286.py...
cd server
python populate_iso286.py

if %errorlevel% EQU 0 (
    echo.
    echo =========================================
    echo  SUCCESS! ISO 286 data loaded.
    echo =========================================
) else (
    echo.
    echo =========================================
    echo  ERROR! Check output above.
    echo =========================================
)

pause
