# 部署安裝指南 (Deployment Setup Guide)

## 目錄

1. [環境需求](#環境需求)
2. [預部署檢查](#預部署檢查)
3. [安裝步驟](#安裝步驟)
4. [資料庫設定](#資料庫設定)
5. [應用啟動](#應用啟動)
6. [驗證部署](#驗證部署)
7. [常見問題](#常見問題)

---

## 環境需求

### 系統需求
- **OS:** Windows / Linux / macOS
- **Python:** 3.8+
- **Node.js:** 14+ (僅用於前端 JS 檢查，非必需)
- **MySQL:** 5.7+ 或 MariaDB 10.5+

### Python 依賴 (pip install)

```bash
pip install flask flask-cors
pip install sqlalchemy pymysql
pip install pythonocc-core  # [CRITICAL] OCC 核心，用於 STEP 解析
pip install openpyxl       # Excel 讀寫
pip install ollama         # Ollama 本地 LLM
pip install python-dotenv  # 環境變數管理
```

### JavaScript 依賴 (CDN，自動載入)

```html
<!-- Three.js 及 OrbitControls（已在 index.html 中，確認 CDN 可用） -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
```

---

## 預部署檢查

### 1. 驗證 Python 環境

```bash
# 檢查 Python 版本
python --version  # 應為 3.8+

# 檢查 pythonocc-core 安裝
python -c "from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh; print('✓ OCC installed')"

# 檢查 Flask
python -c "from flask import Flask; print('✓ Flask installed')"

# 檢查 SQLAlchemy
python -c "from sqlalchemy import create_engine; print('✓ SQLAlchemy installed')"
```

### 2. 驗證 MySQL 連接

```bash
# 連接測試
mysql -h localhost -u root -p
# 或 MariaDB
mariadb -h localhost -u root -p

# 確認可以建立資料庫
CREATE DATABASE tolerance_db CHARACTER SET utf8mb4;
```

### 3. 驗證檔案完整性

```bash
# 後端檔案
ls -lh server/step_core.py server/step_service.py server/asm_worker.py server/path_extractor.py

# 前端檔案
ls -lh server/static/js/step_viewer.js server/static/js/pmi_panel.js server/static/js/app.js server/static/js/bom_render.js

# 模板
ls -lh server/templates/index.html
```

---

## 安裝步驟

### 步驟 1: 複製檔案

```bash
cd c:\Tolerance_Project\server

# 確認這些檔案存在：
# ✓ step_core.py
# ✓ step_service.py
# ✓ asm_worker.py
# ✓ path_extractor.py
# ✓ rag_engine.py (已修改 Phase 4)
# ✓ ai_app.py (已修改 Phase 4)
# ✓ tables.py (已新增 ORM 類)

# ✓ static/js/step_viewer.js
# ✓ static/js/pmi_panel.js
# ✓ static/js/app.js (已修改)
# ✓ static/js/bom_render.js (已修改)

# ✓ templates/index.html (已修改)
```

### 步驟 2: 設定環境變數

```bash
# 建立或編輯 .env 檔案
cat > .env << EOF
# MySQL 資料庫
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/tolerance_db

# Ollama 設定
OLLAMA_HOST=http://localhost:11434

# Flask
FLASK_ENV=production
FLASK_DEBUG=0

# 應用埠
FLASK_PORT=7011
EOF
```

### 步驟 3: 安裝 Python 依賴

```bash
# 建立 requirements.txt (若還沒有)
pip install -r requirements.txt

# 或直接安裝
pip install flask flask-cors sqlalchemy pymysql pythonocc-core openpyxl ollama python-dotenv
```

---

## 資料庫設定

### 步驟 1: 建立資料庫

```bash
mysql -u root -p << EOF
CREATE DATABASE tolerance_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE tolerance_db;
EOF
```

### 步驟 2: 建立資料表

```bash
# 使用 Python 建立表 (推薦)
cd c:\Tolerance_Project\server

python << 'PYEOF'
from tables import engine, BASE
import sys

try:
    # 建立所有表
    BASE.metadata.create_all(engine)
    print("[OK] All tables created successfully")
    print("    ✓ PmiSession")
    print("    ✓ PmiItem")
    print("    ✓ AssemblyContact")
except Exception as e:
    print(f"[ERROR] Failed to create tables: {e}")
    sys.exit(1)
PYEOF
```

### 步驟 3: 驗證表結構

```bash
mysql -u root -p tolerance_db << EOF
SHOW TABLES;
DESC pmi_session;
DESC pmi_item;
DESC assembly_contact;
EOF
```

---

## 應用啟動

### 方法 1: 直接執行 (開發環境)

```bash
cd c:\Tolerance_Project\server

# 確認環境變數已設定
# 如未設定，Flask 將使用預設值

python ai_app.py
# 應出現：
# * Running on http://localhost:7011
# * Flask development server (use with caution in production)
```

### 方法 2: 使用 Gunicorn (生產環境)

```bash
# 安裝 Gunicorn
pip install gunicorn

# 啟動
cd c:\Tolerance_Project\server
gunicorn -w 1 -b 0.0.0.0:7011 --timeout 120 ai_app:app

# 注意: -w 1 (單一 worker) 因為 _step_sessions 存儲在記憶體中
```

### 方法 3: 使用 Windows 服務 (Windows 環境)

```bash
# 使用 NSSM (Non-Sucking Service Manager)
# 下載: nssm.cc/download

nssm install ToleranceGAI "C:\Python39\python.exe" "c:\Tolerance_Project\server\ai_app.py"
nssm set ToleranceGAI AppDirectory "c:\Tolerance_Project\server"
nssm start ToleranceGAI
```

---

## 驗證部署

### 1. 檢查 Flask 啟動日誌

```
[INFO] 接收到對話請求 - 訊息: '...'
[OK] All modules imported
✓ Database connection successful
✓ All routes registered
```

### 2. 測試 API 端點

```bash
# 測試基礎連接
curl http://localhost:7011/

# 測試 STEP 上傳端點
curl -X POST http://localhost:7011/api/step/upload \
  -F "stp_file=@test.stp" \
  -F "xlsx_file=@test.xlsx"
# 預期回應: {"ok": true, "session_id": "..."}

# 測試 PMI 解析
curl -X POST http://localhost:7011/api/step/parse_pmi \
  -H "Content-Type: application/json" \
  -d '{"session_id": "<uuid>"}'
# 預期: {"ok": true, "n_pmi_rows": N, "pmi_rows": [...]}
```

### 3. 測試前端

```bash
# 開啟瀏覽器
http://localhost:7011

# 應看到：
# ✓ 左面板: 產品架構、特徵、網路、接觸、分析等按鈕
# ✓ 右面板: 聊天介面
# ✓ 上傳按鈕可用

# 測試 STEP 上傳
# 1. 點擊 "🔩 STEP 3D 檢視器" 按鈕
# 2. 拖拽或選擇 .stp 檔案
# 3. 應顯示 3D 模型和 PMI 清單

# 測試 PMI 高亮
# 1. 點擊 PMI 清單中的項目
# 2. 3D 模型應高亮相應的幾何面

# 測試 AI 驅動高亮
# 1. 在聊天框輸入: "請高亮 dis1"
# 2. AI 回覆應包含 <HIGHLIGHT_PMI label="dis1" />
# 3. 3D 模型應自動高亮
```

### 4. 查看 MySQL 資料

```bash
mysql -u root -p tolerance_db << EOF
SELECT * FROM pmi_session LIMIT 5;
SELECT * FROM pmi_item WHERE session_id = '<uuid>' LIMIT 10;
SELECT * FROM assembly_contact LIMIT 5;
EOF
```

---

## 常見問題

### Q1: OCC (pythonocc-core) 無法安裝

**症狀:** `No module named 'OCC'` 或編譯錯誤

**解決方案:**
```bash
# Windows: 使用預構建的輪子
pip install pythonocc-core --only-binary :all:

# Linux (Ubuntu): 安裝編譯依賴
sudo apt-get install libocct-dev

# 若仍無法安裝，考慮 Docker 或預構建環境
```

### Q2: MySQL 連接失敗

**症狀:** `Can't connect to MySQL server` 或 `2003: Can't connect to MySQL server`

**解決方案:**
```bash
# 檢查 MySQL 是否運行
ps aux | grep mysql  # Linux/macOS
tasklist | grep mysql  # Windows

# 檢查 DATABASE_URL 設定
echo $DATABASE_URL  # Linux/macOS
echo %DATABASE_URL%  # Windows

# 測試連接
python -c "from sqlalchemy import create_engine; engine = create_engine('<YOUR_DB_URL>'); print(engine.connect())"
```

### Q3: 大型 STEP 檔案上傳失敗

**症狀:** `413 Payload Too Large` 或超時

**解決方案:**
```python
# 在 ai_app.py 中增加上傳限制
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024  # 200 MB
```

### Q4: JavaScript <HIGHLIGHT_PMI> 標籤未被攔截

**症狀:** AI 輸出含 `<HIGHLIGHT_PMI>`，但 3D 未高亮

**解決方案:**
```javascript
// 檢查瀏覽器開發者工具 (F12)
// 1. 確認 PmiPanel 已載入 (console: typeof PmiPanel)
// 2. 確認 app.js 含有正則表達式 (搜尋 "highlightPmiRegex")
// 3. 檢查 network tab，確認 step_viewer.js 已載入
```

### Q5: 組合件分析 (asm_worker) 超時

**症狀:** `組合件分析超過 30 秒` 或無回應

**解決方案:**
```python
# 在 step_service.py 增加超時時間
ASM_WORKER_TIMEOUT = 60  # 秒

# 確認 asm_worker.py 存在且可執行
ls -la asm_worker.py
python asm_worker.py test.stp /tmp/output.json
```

### Q6: 前端看不到 STEP 3D 查看器面板

**症狀:** 點擊 "🔩 STEP 3D 檢視器" 按鈕無反應

**解決方案:**
```javascript
// 檢查瀏覽器控制台
console.log(typeof openStepViewerPanel)  // 應為 'function'
console.log(typeof StepViewer)  // 應為 'object'

// 檢查 HTML 元素
document.getElementById('step-viewer-panel')  // 應存在

// 檢查 index.html 中的 script 標籤
// 應包含: step_viewer.js, pmi_panel.js
```

---

## 性能調整

### 啟用 GZIP 壓縮 (Flask)

```python
from flask_compress import Compress
Compress(app)
```

### 增加 MySQL 連接池

```python
from sqlalchemy.pool import QueuePool
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20
)
```

### 啟用 Three.js 紋理壓縮

```javascript
// 在 step_viewer.js 中
renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: true,
    powerPreference: 'high-performance'
});
```

---

## 監控和日誌

### Flask 日誌位置

```bash
# 設定日誌檔案
export FLASK_LOG=server.log  # Linux/macOS
set FLASK_LOG=server.log     # Windows

# 查看日誌
tail -f server.log  # Linux/macOS
type server.log     # Windows
```

### MySQL 慢查詢日誌

```sql
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 2;
```

### 瀏覽器控制台日誌

```javascript
// 所有日誌應以 [Phase X] 前綴標識
console.log('[Phase 2] StepViewer initialized');
console.log('[Phase 4] PMI highlight requested');
console.log('[Phase 5] Assembly contact analysis started');
```

---

## 備份和恢復

### 備份 MySQL 資料

```bash
# 完整備份
mysqldump -u root -p tolerance_db > backup.sql

# 恢復
mysql -u root -p tolerance_db < backup.sql
```

### 備份上傳的 STEP 檔案

```bash
# 檔案通常儲存在臨時目錄
# 建立定期備份任務
tar -czf step_files_backup_$(date +%Y%m%d).tar.gz /tmp/step_*
```

---

## 檢查清單

部署前確認：

- [ ] Python 3.8+ 已安裝
- [ ] pythonocc-core 已安裝
- [ ] MySQL/MariaDB 已運行
- [ ] .env 檔案已設定
- [ ] 所有 Python 檔案已複製
- [ ] 所有 JavaScript 檔案已複製
- [ ] index.html 已更新
- [ ] 資料表已建立
- [ ] Flask 可正常啟動
- [ ] API 端點可回應
- [ ] 前端可載入
- [ ] STEP 檔案可上傳
- [ ] PMI 清單可顯示
- [ ] 3D 模型可渲染
- [ ] AI 聊天可互動

---

## 支援聯繫

若遇到問題，請檢查：

1. **部署驗證報告:** c:\Tolerance_Project\DEPLOYMENT_REPORT.md
2. **Flask 啟動日誌:** 檢查控制台輸出
3. **瀏覽器控制台:** F12 檢查 JavaScript 錯誤
4. **MySQL 日誌:** 檢查資料庫連接
5. **memory 檔案:** C:\Users\User\.claude\projects\c--test0402\memory\

---

*最後更新: 2026-04-14*  
*部署版本: Phases 1-5 完整整合*
