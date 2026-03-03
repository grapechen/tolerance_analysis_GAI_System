# 快速開始指南

## 🚀 第一次使用（新環境設置）

### Windows 使用者

1. **環境設置**（只需執行一次）
   ```bash
   setup.bat
   ```
   這會自動：
   - 檢查 Python 安裝
   - 建立虛擬環境 (.venv)
   - 安裝所有依賴套件

2. **設置資料庫**（只需執行一次）
   ```bash
   .venv\Scripts\python.exe server/tables.py
   .venv\Scripts\python.exe server/import_all_data.py
   ```

3. **啟動服務**
   - 基本查詢系統：`run_basic.bat`
   - AI 智能助手：`run_ai.bat`
   - 同時啟動兩個：`run_all.bat`

### Linux/Mac 使用者

1. **環境設置**（只需執行一次）
   ```bash
   chmod +x setup.sh run_basic.sh run_ai.sh
   ./setup.sh
   ```

2. **設置資料庫**（只需執行一次）
   ```bash
   source .venv/bin/activate
   python server/tables.py
   python server/import_all_data.py
   ```

3. **啟動服務**
   - 基本查詢系統：`./run_basic.sh`
   - AI 智能助手：`./run_ai.sh`

## 📋 前置需求

### 必要項目
- **Python 3.8+**
  - Windows: 從 [python.org](https://www.python.org/downloads/) 下載
  - Linux: `sudo apt install python3 python3-venv python3-pip`
  - Mac: `brew install python3`

- **MySQL 5.7+ 或 MariaDB**
  - 確保服務運行在 `127.0.0.1:3307`
  - 或修改 `server/tables.py` 中的連線字串

### AI 助手額外需求
- **Ollama**
  - 下載：[ollama.com](https://ollama.com/)
  - 安裝模型：`ollama pull gemma3:4b`

## 🌐 服務位址

- **基本查詢系統**: http://127.0.0.1:7010
- **AI 智能助手**: http://127.0.0.1:7011

## 🔧 常見問題

### Q: setup.bat 執行失敗？
**A:** 確認：
1. Python 已安裝並加入 PATH
2. 有網路連線（需下載套件）
3. 刪除 `.venv` 資料夾後重試

### Q: 資料匯入失敗？
**A:** 確認：
1. MySQL 服務已啟動
2. 資料庫連線資訊正確（`server/tables.py`）
3. Excel 檔案存在於 `server/data/` 目錄

### Q: AI 助手無法啟動？
**A:** 確認：
1. Ollama 已安裝並運行
2. 已下載模型：`ollama pull gemma3:4b`
3. 執行 `ollama list` 確認模型存在

### Q: 如何修改資料庫連線？
**A:** 編輯 `server/tables.py`：
```python
engine = create_engine(
    "mysql+pymysql://使用者:密碼@主機:埠/資料庫?charset=utf8mb4",
    echo=False
)
```

## 📦 從 GitHub 克隆後的步驟

```bash
# 1. 克隆專案
git clone <repository-url>
cd Tolerance_Project

# 2. 執行環境設置
setup.bat          # Windows
./setup.sh         # Linux/Mac

# 3. 設置資料庫
.venv\Scripts\python.exe server/tables.py           # Windows
.venv\Scripts\python.exe server/import_all_data.py  # Windows

source .venv/bin/activate && python server/tables.py           # Linux/Mac
source .venv/bin/activate && python server/import_all_data.py  # Linux/Mac

# 4. 啟動服務
run_basic.bat      # Windows
./run_basic.sh     # Linux/Mac
```

## 🎯 開發模式

如果你要開發或修改程式碼：

```bash
# 啟動虛擬環境
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # Linux/Mac

# 手動啟動服務（可看到詳細輸出）
python server/app.py        # 基本查詢系統
python server/ai_app.py     # AI 助手
```

## 📚 更多資訊

- 完整文件：[README.md](README.md)
- API 文件：查看 `server/app.py` 中的端點說明
- RAG 系統：查看 `docs/rag_system_guide.md`
