@echo off
echo =========================================
echo 啟動 ISO 286 完整查詢系統 (7010 + 7011)
echo =========================================

echo [1/2] 啟動基礎查詢系統 (Port 7010)...
cd server
start "ISO 286 Basic" /MIN ..\.venv\Scripts\python.exe app.py
cd ..

echo [2/2] 啟動 AI 智能助手 (Port 7011)...
cd server
start "ISO 286 AI" /MIN ..\.venv\Scripts\python.exe ai_app.py
cd ..

echo =========================================
echo 啟動完成！
echo 1. 基礎查詢系統: http://localhost:7010
echo 2. AI 智能助手: http://localhost:7011
echo =========================================
pause
