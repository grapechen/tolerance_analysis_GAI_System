@echo off
title AI 智能助手
cd /d "%~dp0"

echo 正在啟動 AI 助手伺服器...
echo 請保持此視窗開啟，關閉視窗即可關閉伺服器。

:: 延遲 3 秒後自動開啟網頁
start /b cmd /c "timeout /t 3 >nul && start http://127.0.0.1:7011"

:: 啟動伺服器
python server\ai_app.py
