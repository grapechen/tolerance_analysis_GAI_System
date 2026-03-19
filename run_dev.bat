@echo off
echo =========================================
echo 啟動 ISO 286 AI 開發環境
echo =========================================

echo 進入 server 目錄啟動 AI 助手核心...
cd server
start "AI API Server" /MIN ..\.venv\Scripts\python.exe ai_app.py
cd ..

echo 啟動完成！
echo 請使用瀏覽器開啟 server/index.html 或是客戶端頁面 (http://127.0.0.1:7011)
echo =========================================
pause
