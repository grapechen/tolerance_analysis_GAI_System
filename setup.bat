@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo   ISO 286 公差查詢系統 - 環境設置
echo ==========================================
echo.

REM 1. Check if Python is installed
echo [1/4] 檢查 Python 安裝...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [錯誤] 找不到 Python！
    echo 請從 python.org 安裝 Python 3.8+ 並加入 PATH
    pause
    exit /b 1
)
python --version
echo.

REM 2. Check or Create Virtual Environment
echo [2/4] 檢查虛擬環境...
if not exist ".venv" (
    echo 虛擬環境不存在，正在建立...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [錯誤] 無法建立虛擬環境
        pause
        exit /b 1
    )
    echo ✓ 虛擬環境建立成功
) else (
    echo ✓ 虛擬環境已存在
)
echo.

REM 3. Upgrade pip
echo [3/4] 更新 pip...
.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
echo ✓ pip 已更新
echo.

REM 4. Install Dependencies
echo [4/4] 安裝依賴套件...
echo 正在安裝: Flask, SQLAlchemy, pandas, openpyxl, ollama 等套件...
.venv\Scripts\python.exe -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [錯誤] 套件安裝失敗！
    echo.
    echo 可能的解決方法：
    echo 1. 刪除 .venv 資料夾後重新執行此腳本
    echo 2. 檢查網路連線
    echo 3. 確認 Python 版本 ^>= 3.8
    echo 4. 手動執行: .venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)
echo ✓ 所有套件安裝完成
echo.

echo ==========================================
echo   ✓ 環境設置完成！
echo ==========================================
echo.
echo 已安裝的套件：
.venv\Scripts\python.exe -m pip list | findstr /I "flask sqlalchemy pandas ollama"
echo.
echo ==========================================
echo   下一步操作
echo ==========================================
echo.
echo 1. 確保 MySQL 服務已啟動
echo 2. 建立資料庫和資料表：
echo    .venv\Scripts\python.exe server/tables.py
echo    .venv\Scripts\python.exe server/import_all_data.py
echo.
echo 3. 啟動服務：
echo    run_basic.bat    - 基本查詢系統 (port 7010)
echo    run_ai.bat       - AI 助手 (port 7011)
echo    run_all.bat      - 同時啟動兩個服務
echo.
echo 4. (可選) 安裝 Ollama 以使用 AI 功能：
echo    下載: https://ollama.com/download
echo    安裝後執行: ollama pull gemma3:4b
echo.
pause
