# Server 目錄說明

此目錄包含 ISO 286 公差查詢系統的後端服務。

## 核心文件

### 應用程式
- **`app.py`** - 基本查詢系統（port 7010）
  - 提供 IT 基本公差、軸公差、孔公差、配合分析的 API
  - 包含網頁介面
  
- **`ai_app.py`** - AI 智能助手（port 7011）
  - 支援自然語言查詢
  - 整合 RAG（檢索增強生成）
  - 支援本地模型和雲端模型

### 資料處理
- **`tables.py`** - 資料庫模型定義（SQLAlchemy）
  - ISOTolerance - IT 基本公差表
  - ShaftTolerance - 軸公差表
  - HoleTolerance - 孔公差表

- **`import_all_data.py`** - 資料匯入腳本
  - 從 Excel 檔案匯入 ISO 286-1 和 ISO 286-2 資料
  - 自動處理特殊格式和數據清理
  - 應用 ISO 標準的特殊規則

### RAG 系統
- **`rag_server.py`** - RAG 邏輯實作
  - 查詢解析
  - 資料庫檢索
  - LLM 回應生成

### 資料來源
- **`data/ISO_286_1_test.xlsx`** - ISO 286-1 標準資料
- **`data/ISO_286_2_test.xlsx`** - ISO 286-2 標準資料
- **`data/ISO_286_2_test2.xlsx`** - ISO 286-2 補充資料

## 快速開始

詳細說明請參考專案根目錄的 [README.md](../README.md)

### 建立資料庫
```bash
# 從專案根目錄執行
.venv\Scripts\python.exe server/tables.py
.venv\Scripts\python.exe server/import_all_data.py
```

### 啟動服務
```bash
# 基本查詢系統
.venv\Scripts\python.exe server/app.py

# AI 智能助手
.venv\Scripts\python.exe server/ai_app.py
```

## 服務端口

- **7010** - 基本查詢系統（app.py）
- **7011** - AI 智能助手（ai_app.py）

## 資料庫配置

預設使用 MySQL，連線設定在 `tables.py` 中：
```python
engine = create_engine("mysql+pymysql://root:密碼@127.0.0.1:3307/tol?charset=utf8mb4")
```

請根據你的環境修改連線字串。
