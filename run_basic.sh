#!/bin/bash
# 啟動基本公差查詢系統

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "[錯誤] 虛擬環境不存在！"
    echo "請先執行 ./setup.sh 進行環境設置"
    exit 1
fi

echo "=========================================="
echo "  啟動基本公差查詢系統"
echo "=========================================="
echo ""
echo "服務位址: http://127.0.0.1:7010"
echo "按 Ctrl+C 停止服務"
echo ""

source .venv/bin/activate
python server/app.py
