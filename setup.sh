#!/bin/bash
# ISO 286 公差查詢系統 - 環境設置腳本 (Linux/Mac)

set -e  # Exit on error

echo "=========================================="
echo "  ISO 286 公差查詢系統 - 環境設置"
echo "=========================================="
echo ""

# 1. Check Python
echo "[1/4] 檢查 Python 安裝..."
if ! command -v python3 &> /dev/null; then
    echo "[錯誤] 找不到 Python3！"
    echo "請安裝 Python 3.8+ 後再執行此腳本"
    exit 1
fi
python3 --version
echo ""

# 2. Create Virtual Environment
echo "[2/4] 檢查虛擬環境..."
if [ ! -d ".venv" ]; then
    echo "虛擬環境不存在，正在建立..."
    python3 -m venv .venv
    echo "✓ 虛擬環境建立成功"
else
    echo "✓ 虛擬環境已存在"
fi
echo ""

# 3. Activate and Upgrade pip
echo "[3/4] 更新 pip..."
source .venv/bin/activate
python -m pip install --upgrade pip --quiet
echo "✓ pip 已更新"
echo ""

# 4. Install Dependencies
echo "[4/4] 安裝依賴套件..."
if pip install -r requirements.txt; then
    echo "✓ 所有套件安裝完成"
else
    echo ""
    echo "[錯誤] 套件安裝失敗！"
    echo "可能的解決方法："
    echo "1. 檢查網路連線"
    echo "2. 刪除 .venv 資料夾後重新執行"
    echo "3. 手動執行: source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi
echo ""

echo "=========================================="
echo "  ✓ 環境設置完成！"
echo "=========================================="
echo ""
echo "已安裝的套件："
python -m pip list | grep -E "flask|sqlalchemy|pandas|ollama|gunicorn"
echo ""
echo "=========================================="
echo "  下一步操作"
echo "=========================================="
echo ""
echo "1. 確保 MySQL 服務已啟動"
echo "2. 建立資料庫和資料表："
echo "   python server/tables.py"
echo "   python server/import_all_data.py"
echo ""
echo "3. 啟動服務："
echo "   ./run_basic.sh       - 基本查詢系統 (port 7010)"
echo "   ./run_ai.sh          - AI 助手 (port 7011)"
echo "   ./run_production.sh  - 生產環境 (使用 Gunicorn)"
echo ""
echo "4. (可選) 安裝 Ollama 以使用 AI 功能："
echo "   下載: https://ollama.com/download"
echo "   安裝後執行: ollama pull gemma3:4b"
echo ""
