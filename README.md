# ISO 286 公差分析系統

基於 ISO 286-1 標準的軸孔公差查詢與配合分析系統。

## 系統需求

- **Python**: 3.8 或更高版本
- **MySQL**: 5.7+ 或 MariaDB 10.3+
- **Ollama**: (可選) 用於 AI 智能助手功能
- **作業系統**: Windows 10+, Linux, macOS
- **幾何公差符號字體**: 用於正確顯示 GD&T 符號（⊥ ∥ ⌭ ○ ◎ 等）

## 🚀 快速開始

### 🆕 AI 助手 - 支援本地和雲端模型

本專案提供統一的 AI 智能助手，可在同一介面中切換本地模型和雲端模型：

- **🤖 AI 智能助手** - 使用 Ollama 應用程式
  - 啟動：`run_ai.bat`（port 7011）
  - 支援本地模型（如 gemma3:4b、llama3.1:8b）
  - 支援雲端模型（如 gpt-oss:120b-cloud、deepseek3.1:671b-cloud）
  - 在介面右上角即可切換模型
  - 需安裝 Ollama 應用程式

**模型比較**：[CLOUD_COMPARISON.md](CLOUD_COMPARISON.md)  
**雲端模型指南**：[docs/cloud_models_guide.md](docs/cloud_models_guide.md)

### 第一次使用（新環境）

**Windows 使用者：**
```bash
# 1. 環境設置（自動安裝依賴）
setup.bat

# 2. 安裝 Ollama 應用程式
# 下載：https://ollama.com/download
# 安裝後會自動啟動

# 3. 驗證環境（可選但建議）
.venv\Scripts\python.exe validate_setup.py

# 4. 建立資料庫
.venv\Scripts\python.exe server/tables.py
.venv\Scripts\python.exe server/import_all_data.py

# 5. 啟動服務
run_basic.bat    # 基本查詢系統（port 7010）
run_ai.bat       # AI 智能助手（port 7011）⭐ 推薦
run_all.bat      # 同時啟動兩個服務
```

**Linux/Mac 使用者：**
```bash
# 1. 環境設置
chmod +x setup.sh run_basic.sh run_ai.sh run_production.sh
./setup.sh

# 2. 驗證環境（可選但建議）
source .venv/bin/activate
python validate_setup.py

# 3. 建立資料庫
python server/tables.py
python server/import_all_data.py

# 4. 啟動服務
./run_basic.sh   # 基本查詢系統
./run_ai.sh      # AI 智能助手
```

**詳細說明：** 請參考 [快速開始指南 (QUICK_START.md)](QUICK_START.md)

## 功能特色

### 線上版本（需要伺服器）
- **IT 基本公差查詢**：查詢 IT01-IT18 等級的基本公差值
- **軸公差查詢**：查詢軸的上下偏差（a-zc 代號）
- **孔公差查詢**：查詢孔的上下偏差（A-ZC 代號）
- **配合分析**：分析孔軸配合類型（間隙/過盈/過渡配合）
- **AI 智能助手**：使用自然語言查詢，支援本地和雲端模型
- **GD&T 知識庫**：236 個幾何公差項目，支援概念查詢和外部知識整合
- **幾何公差符號**：正確顯示 GD&T 符號（⊥ ∥ ⌭ ○ ◎ 等）

### 離線版本（無需伺服器）
- 📱 **完全離線運作** - 只需瀏覽器，無需安裝任何軟體
- 🚀 **即開即用** - 直接開啟 `client/index.html`
- 💾 **包含完整資料** - 約 5000 筆 ISO 286 資料
- 詳見：[client/README.md](client/README.md)

## 依賴套件說明

所有 Python 依賴已在 `requirements.txt` 中定義：

- **flask** (3.0.0+): Web 框架
- **flask-cors** (4.0.0+): 跨域資源共享支援
- **ollama** (0.1.0+): AI 模型整合
- **sqlalchemy** (2.0.0+): ORM 資料庫操作
- **pymysql** (1.1.0+): MySQL 連接驅動
- **pandas** (2.0.0+): 資料處理
- **openpyxl** (3.1.0+): Excel 檔案讀取
- **requests** (2.31.0+): HTTP 請求
- **python-dotenv** (1.0.0+): 環境變數管理
- **gunicorn** (21.0.0+): 生產環境伺服器 (僅 Linux/Unix)

## 幾何公差符號字體設定

為了正確顯示 GD&T 符號（⊥ ∥ ⌭ ○ ◎ 等），建議安裝專用的幾何公差符號字體：

### 字體下載與安裝
1. **下載字體**：參考 [這篇文章](https://vocus.cc/article/671e5d95fd89780001c79192) 下載 GD&T 符號字體
2. **安裝字體**：
   - **Windows**：右鍵點擊字體檔案 → 選擇「安裝」
   - **macOS**：雙擊字體檔案 → 點擊「安裝字體」
   - **Linux**：複製到 `~/.fonts/` 目錄並執行 `fc-cache -f -v`

### 支援的符號
系統會自動為以下 GD&T 符號應用專用字體：
- **⊥** 垂直度 (Perpendicularity)
- **∥** 平行度 (Parallelism)  
- **⌭** 圓柱度 (Cylindricity)
- **○** 真圓度 (Circularity)
- **◎** 同心度 (Concentricity)
- **⌖** 位置度 (Position)
- **⌒** 輪廓度 (Profile)

### 備用方案
如果未安裝專用字體，系統會自動回退到系統預設字體，符號仍可正常顯示。

## 快速開始

### 1. 安裝依賴

```bash
pip install -r server/requirements.txt
```

### 2. 設定資料庫

確保 MySQL 服務運行中，並修改 `server/tables.py` 中的連線字串：

```python
engine = create_engine("mysql+pymysql://root:密碼@127.0.0.1:3307/tol?charset=utf8mb4", echo=False)
```

### 3. 建立資料表

```bash
python server/tables.py
```

### 4. 匯入完整 ISO 286 資料

```bash
python server/import_all_data.py
```

這將匯入：
- IT 基本公差（IT01-IT18）：404 筆
- 孔公差（A-ZC）：2000+ 筆
- 軸公差（a-zc）：2000+ 筆
- 總計約 5000 筆資料

### 5. 測試 API（可選）

```bash
python test_complete_api.py
```

### 6. 啟動服務

```bash
python server/app.py
```

服務將在 `http://localhost:7010` 啟動。

## 使用方式

### 基本查詢系統（port 7010）

開啟瀏覽器訪問 `http://localhost:7010`，可使用四個功能頁籤：

1. **IT 基本公差**：輸入 IT 等級（如 IT7）和名目尺寸（如 25mm）
2. **軸公差**：輸入軸代號（如 h）、IT 等級（如 6）和尺寸（如 20mm）
3. **孔公差**：輸入孔代號（如 H）、IT 等級（如 7）和尺寸（如 20mm）
4. **配合分析**：輸入孔軸公差（如 H7/h6）和尺寸（如 20mm）

**注意**：某些尺寸範圍的特定公差代號可能未定義（如 24-30mm 的 h 軸），這是 ISO 286 標準的正常情況。建議使用 18-24mm 範圍測試 H7/h6 配合。

### AI 智能助手（port 7011）⭐

開啟瀏覽器訪問 `http://localhost:7011`，使用自然語言查詢：

**使用本地模型：**
1. 在 Ollama 應用程式中下載模型（如 `gemma3:4b`）
2. 在網頁右上角選擇模型
3. 開始對話

**使用雲端模型：**
1. 在 Ollama 應用程式中登入帳號（Settings → Sign in）
2. 雲端模型會自動出現在模型列表中（標示 ☁️）
3. 選擇雲端模型，例如：
   - `☁️ gpt-oss:120b-cloud` - 超大型推理模型
   - `☁️ deepseek3.1:671b-cloud` - DeepSeek 超大型混合專家模型
   - `☁️ qwen3-coder:480b-cloud` - 程式碼專用超大模型
   - `☁️ qwen3-v1:235b-cloud` - 視覺語言超大模型
   - `☁️ gemma3:27b` - Google 高效能模型
4. 開始對話 - 無需下載，直接使用！

**雲端模型優勢：**
- 🚀 更快的推理速度（資料中心級 GPU）
- 💪 可使用超大模型（最高 671B 參數）
- 💻 不佔用本地資源
- 🔋 省電省記憶體

**查詢範例：**
- "查詢 25mm H7 的公差"
- "分析 30mm H7/h6 的配合"
- "什麼是留隙配合？"

### API 端點

#### 查詢 IT 基本公差
```bash
POST /api/lookup/tolerance
Content-Type: application/json

{
  "size_mm": 25.0,
  "it_grade": "IT7"
}
```

#### 查詢軸公差
```bash
POST /api/lookup/shaft
Content-Type: application/json

{
  "size_mm": 25.0,
  "tolerance_code": "h",
  "it_grade": "IT6"
}
```

#### 查詢孔公差
```bash
POST /api/lookup/hole
Content-Type: application/json

{
  "size_mm": 25.0,
  "tolerance_code": "H",
  "it_grade": "IT7"
}
```

#### 配合分析
```bash
POST /api/analyze/fit
Content-Type: application/json

{
  "size_mm": 25.0,
  "hole_tolerance": "H7",
  "shaft_tolerance": "h6"
}
```

## 資料庫結構

### iso286_tolerance
- IT 基本公差表
- 欄位：尺寸範圍、IT 等級、公差值（μm）

### shaft_tolerance
- 軸公差表
- 欄位：尺寸範圍、公差代號、IT 等級、上下偏差（μm）

### hole_tolerance
- 孔公差表
- 欄位：尺寸範圍、公差代號、IT 等級、上下偏差（μm）

## 專案結構

```
Tolerance_Project/
├── server/
│   ├── app.py                  # Flask 應用主程式（API + 網頁介面）
│   ├── tables.py               # 資料庫模型定義（3 個資料表）
│   ├── import_all_data.py      # 完整資料匯入工具
│   ├── requirements.txt        # Python 依賴
│   └── ISO_286_1_test.xlsm     # ISO 286 資料來源（5 個工作表）
├── test_complete_api.py        # API 測試腳本
├── qa_validation.py            # QA 驗證腳本
├── README.md                   # 專案說明（本文件）
├── QUICK_START.md              # 快速開始指南
├── QA_REPORT.md                # QA 驗證報告
└── DEPLOYMENT.md               # 部署檢查清單
```

## 系統狀態

- **服務地址**：http://localhost:7010
- **資料庫**：MySQL (127.0.0.1:3307/tol)
- **已匯入資料**：
  - IT 基本公差：404 筆
  - 軸公差：2428 筆（a-zc，IT6-IT9）
  - 孔公差：2176 筆（A-ZC，IT6-IT9）
  - 總計：5008 筆
- **測試狀態**：✅ 所有 API 測試通過
- **QA 驗證**：✅ 通過率 82.9%（詳見 QA_REPORT.md）

## 技術架構

- **後端**：Flask 3.0.3 + SQLAlchemy 2.0.31
- **資料庫**：MySQL 5.7+ / MariaDB
- **前端**：原生 JavaScript（無框架依賴）
- **資料處理**：Pandas 2.2.2
- **API**：RESTful，支援 CORS

## 測試

### 執行 API 測試

```bash
# Windows
run_tests.bat

# Linux/Mac
python tests/test_api.py
```

測試項目包括：
- IT 基本公差查詢
- 軸公差查詢
- 孔公差查詢
- 配合分析
- 速率限制
- 錯誤處理

## 生產環境部署

### Linux/Unix 系統

使用 Gunicorn 作為 WSGI 伺服器（效能更好、更穩定）：

```bash
# 啟動生產環境服務（背景執行）
./run_production.sh

# 停止服務
kill $(cat /tmp/iso286_basic.pid) $(cat /tmp/iso286_ai.pid)
```

配置說明：
- 基本查詢系統：4 個 worker processes (port 7010)
- AI 助手：2 個 worker processes (port 7011)
- 綁定到 0.0.0.0 允許外部訪問

### Windows 系統

Windows 不支援 Gunicorn，建議：
1. **開發/測試環境**：使用內建 Flask 伺服器 (`run_basic.bat`, `run_ai.bat`)
2. **生產環境**：部署到 Linux 伺服器或使用容器化方案

### 環境驗證

在啟動服務前，建議執行驗證腳本：

```bash
# Windows
.venv\Scripts\python.exe validate_setup.py

# Linux/Mac
python validate_setup.py
```

驗證項目：
- Python 版本 (>= 3.8)
- 所有依賴套件安裝狀態
- 資料庫連線
- Ollama 可用性（可選）

## 相關文件

### 使用指南
- **[QUICK_START.md](QUICK_START.md)** - 詳細執行指南
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - 故障排除指南 🔧
- **[docs/cloud_models_guide.md](docs/cloud_models_guide.md)** - Ollama 雲端模型使用指南 ⭐
- **[CLOUD_COMPARISON.md](CLOUD_COMPARISON.md)** - 本地模型 vs 雲端模型比較
- **[client/README.md](client/README.md)** - 離線版本使用說明

### 開發與部署
- **[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)** - 完整部署檢查清單 🚀
- **[SETUP_IMPROVEMENTS.md](SETUP_IMPROVEMENTS.md)** - 環境設置改進說明
- **[.env.example](.env.example)** - 環境變數範例

### 技術文件
- **[QA_REPORT.md](QA_REPORT.md)** - QA 驗證報告
- **[USAGE.md](USAGE.md)** - 使用說明（常用配合、API 範例）
- **[server/README.md](server/README.md)** - 後端架構說明

## 授權

本專案僅供學習與研究使用。
