@echo off
chcp 65001 > nul
echo ========================================
echo  公差 AI 助手 - Windows 打包腳本
echo ========================================
echo.

:: ── 步驟 1：PyInstaller 打包 Flask ──────────────────────────────
echo [1/3] 打包 Python 後端 (PyInstaller)...
cd server

pyinstaller --onedir ^
  --name ai_app ^
  --noconsole ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --add-data "data;data" ^
  --add-data "config.yaml;." ^
  --hidden-import=rag_engine ^
  --hidden-import=graph_rag ^
  --hidden-import=flask ^
  --hidden-import=flask_cors ^
  --hidden-import=sentence_transformers ^
  --hidden-import=faiss ^
  ai_app.py

if errorlevel 1 (
  echo [錯誤] PyInstaller 失敗，請確認 pyinstaller 已安裝
  pause
  exit /b 1
)

:: 將打包結果移到根目錄 dist/
cd ..
if exist dist\ai_app rmdir /s /q dist\ai_app
move server\dist\ai_app dist\ai_app
echo [1/3] 完成：dist/ai_app/

:: ── 步驟 2：建立佔位圖示（若無真實 icon 時）──────────────────
if not exist electron\assets mkdir electron\assets
if not exist electron\assets\icon.ico (
  echo [2/3] 未找到 icon.ico，跳過圖示設定
  echo        請將 256x256 的 .ico 檔放到 electron/assets/icon.ico
) else (
  echo [2/3] 找到圖示檔案
)

:: ── 步驟 3：Electron 打包 ─────────────────────────────────────
echo [3/3] 打包 Electron 桌面應用...
cd electron

call npm install
if errorlevel 1 (
  echo [錯誤] npm install 失敗，請確認 Node.js 已安裝
  pause
  exit /b 1
)

call npm run build
if errorlevel 1 (
  echo [錯誤] electron-builder 失敗
  pause
  exit /b 1
)

cd ..
echo.
echo ========================================
echo  完成！安裝檔位於 electron/dist/
echo ========================================
pause
