#!/bin/bash
# 生產環境啟動腳本 (使用 Gunicorn)
# 注意: 僅適用於 Linux/Unix 系統

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "[錯誤] 虛擬環境不存在！"
    echo "請先執行 ./setup.sh 進行環境設置"
    exit 1
fi

echo "=========================================="
echo "  ISO 286 生產環境啟動"
echo "=========================================="
echo ""

source .venv/bin/activate

# 檢查 gunicorn 是否安裝
if ! python -c "import gunicorn" 2>/dev/null; then
    echo "[錯誤] Gunicorn 未安裝！"
    echo "請執行: pip install gunicorn"
    exit 1
fi

# 啟動基本查詢系統 (port 7010)
echo "啟動基本查詢系統 (port 7010)..."
gunicorn -w 4 -b 0.0.0.0:7010 --chdir server app:app --daemon --pid /tmp/iso286_basic.pid

# 啟動 AI 助手 (port 7011)
echo "啟動 AI 助手 (port 7011)..."
gunicorn -w 2 -b 0.0.0.0:7011 --chdir server ai_app:app --daemon --pid /tmp/iso286_ai.pid

echo ""
echo "✓ 服務已在背景啟動"
echo ""
echo "基本查詢系統: http://0.0.0.0:7010"
echo "AI 智能助手:  http://0.0.0.0:7011"
echo ""
echo "停止服務: kill \$(cat /tmp/iso286_basic.pid) \$(cat /tmp/iso286_ai.pid)"
echo ""
