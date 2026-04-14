# 快速啟動指南 (Quick Start Guide)

## ⚠️ 前置條件檢查

在開始前，請確保：

```bash
# 1. MySQL/MariaDB 已啟動
# Windows: Services → MySQL80 or MariaDB (設為自動啟動)
# Linux: sudo systemctl start mysql
# macOS: brew services start mysql

# 2. Python 3.8+ 已安裝
python --version

# 3. 必要的 Python 套件已安裝
pip install flask flask-cors sqlalchemy pymysql pythonocc-core openpyxl ollama python-dotenv

# 4. Ollama 已啟動 (用於本地 LLM)
ollama serve

# 5. OCC 核心可用
python -c "from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh; print('OK')"
```

---

## 🚀 一鍵部署 (One-Command Deployment)

### Windows PowerShell
```powershell
cd C:\Tolerance_Project\server
python setup_database.py
python run.py
```

### Linux / macOS
```bash
cd /path/to/Tolerance_Project/server
python setup_database.py
python run.py
```

---

## 📋 詳細部署步驟

### 步驟 1: 配置環境變數

已自動生成 `.env` 檔案，包含預設值：

```bash
cat .env
```

**如需修改資料庫配置：**
```bash
# 編輯 .env
DATABASE_URL=mysql+pymysql://root:your_password@localhost:3306/tolerance_db
```

### 步驟 2: 初始化資料庫

```bash
python setup_database.py
```

**預期輸出：**
```
[STEP 1] Testing MySQL connection...
[OK] MySQL connection successful

[STEP 2] Creating database (if not exists)...
[OK] Database 'tolerance_db' ready

[STEP 3] Creating tables from ORM models...
[OK] Tables created successfully:
  ✓ pmi_session
  ✓ pmi_item
  ✓ assembly_contact

[STEP 4] Verifying table structure...
[OK] ORM Models verified:
  ✓ PmiSession - 12 columns
  ✓ PmiItem - 12 columns
  ✓ AssemblyContact - 9 columns

[SUCCESS] Database setup completed successfully!
```

### 步驟 3: 啟動應用

```bash
python run.py
```

**或自定義參數：**
```bash
# 綁定所有介面，啟用調試模式
python run.py --host 0.0.0.0 --port 7011 --debug
```

**預期輸出：**
```
================================================================================
Tolerance Project - Flask Application Startup
================================================================================

[CHECK] Verifying dependencies...
  [✓] Flask
  [✓] SQLAlchemy
  [✓] PyMySQL

[CHECK] Testing database connection...
  [✓] Database connection successful

[CHECK] Verifying database tables...
  [✓] pmi_session
  ✓ pmi_item
  ✓ assembly_contact

[STARTUP] Starting Flask application...
  Host: 127.0.0.1
  Port: 7011
  Debug: False

================================================================================

 * Running on http://127.0.0.1:7011
 * Press CTRL+C to quit
```

### 步驟 4: 驗證應用

```bash
# 在新終端視窗打開
# 或在瀏覽器中訪問

http://localhost:7011
```

**檢查項目：**
- [ ] 頁面加載成功
- [ ] 左面板顯示所有按鈕
- [ ] 右面板顯示聊天界面
- [ ] 瀏覽器控制台 (F12) 無紅色錯誤

---

## 🧪 快速測試

### Test 1: STEP 上傳 (2 分鐘)

```
1. 點擊「🔩 STEP 3D 檢視器」按鈕
2. 上傳任何有效的 .stp 檔案
3. 應看到：
   ✓ 3D 模型顯示
   ✓ PMI 清單填充
   ✓ 彩色編碼 (綠/紫/橙)
```

### Test 2: PMI 高亮 (1 分鐘)

```
1. 點擊 PMI 清單中的任意項目
2. 應看到：
   ✓ 3D 模型相應面高亮
   ✓ Leader lines 顯示
   ✓ 相機自動聚焦
```

### Test 3: AI 聊天 (2 分鐘)

```
1. 確保 Ollama 運行中
2. 在聊天框輸入：「請高亮 dis1」
3. 應看到：
   ✓ AI 回覆含相關內容
   ✓ 3D 自動高亮對應 dis1
   ✓ 3D 查看器面板自動打開
```

### Test 4: 組合件分析 (2 分鐘)

```
1. STEP 上傳完成後
2. 點擊「🔗 分析接觸」按鈕
3. 等待 10-30 秒
4. 應看到：
   ✓ 按鈕恢復正常
   ✓ 聊天顯示完成訊息
   ✓ 接觸圖更新
```

---

## 🔧 故障排除

### 問題 1: MySQL 連接失敗

```
[ERROR] Failed to connect to MySQL server
```

**解決方案：**
```bash
# 檢查 MySQL 是否運行
# Windows
tasklist | findstr mysql

# Linux/macOS
ps aux | grep mysql

# 啟動 MySQL
# Windows: net start MySQL80
# Linux: sudo systemctl start mysql
# macOS: brew services start mysql

# 驗證 .env 中的憑證
cat .env | grep DATABASE_URL
```

### 問題 2: OCC 未安裝

```
ModuleNotFoundError: No module named 'OCC'
```

**解決方案：**
```bash
pip install pythonocc-core --only-binary :all:
```

### 問題 3: JavaScript 錯誤

```
Uncaught ReferenceError: StepViewer is not defined
```

**解決方案：**
1. F12 打開開發者工具
2. 檢查 Network 標籤，確認：
   - step_viewer.js 已加載
   - pmi_panel.js 已加載
   - app.js 已加載
3. 刷新頁面 (Ctrl+Shift+R)

### 問題 4: AI 未回應

```
Chat 框輸入無反應或顯示 [ERROR]
```

**解決方案：**
```bash
# 檢查 Ollama 是否運行
curl http://localhost:11434

# 確保 Ollama 模型已下載
ollama list

# 如無模型，下載一個
ollama pull llama2
```

### 問題 5: 3D 模型不顯示

```
Canvas 為空白或黑色
```

**解決方案：**
1. 檢查瀏覽器控制台 (F12)，查看 WebGL 錯誤
2. 驗證 Three.js CDN：
   ```javascript
   console.log(typeof THREE)  // 應為 'object'
   ```
3. 確認 STEP 檔案已成功上傳：
   ```javascript
   console.log(window._stepSessionId)  // 應有值
   ```

---

## 📊 性能調整

### 啟用生產模式

```bash
# 不使用 --debug 標誌
python run.py
```

### 增加 Flask Worker 數量

```bash
# 安裝 Gunicorn
pip install gunicorn

# 啟動多 worker (注意：使用 -w 1 因為 session 存在記憶體)
gunicorn -w 1 -b 0.0.0.0:7011 ai_app:app
```

### 配置 MySQL 連接池

已在 `tables.py` 中預設配置：
- pool_size: 10
- max_overflow: 20

可在 .env 中調整：
```env
SQLALCHEMY_POOL_SIZE=20
SQLALCHEMY_MAX_OVERFLOW=40
```

---

## 📝 日誌和監控

### 啟用 Flask 日誌

```python
# 修改 ai_app.py
import logging

logging.basicConfig(level=logging.DEBUG)
logging.getLogger('flask').setLevel(logging.DEBUG)
```

### 查看 MySQL 慢查詢

```sql
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 2;
SHOW VARIABLES LIKE 'slow%';
```

### 監控應用狀態

```bash
# 在新終端視窗
# Monitor Flask access logs
tail -f access.log

# Monitor error logs
tail -f error.log
```

---

## ✅ 部署檢查清單

在生產環境中部署前，確認：

- [ ] Python 3.8+ 已安裝
- [ ] MySQL 已運行且可連接
- [ ] 所有 Python 依賴已安裝
- [ ] .env 已正確配置
- [ ] 資料庫表已建立
- [ ] 前端檔案完整 (JS, CSS, HTML)
- [ ] Ollama 已啟動
- [ ] 防火牆允許 7011 埠訪問
- [ ] 備份現有資料
- [ ] 執行完整的功能測試

---

## 🎉 完成！

應用現已上線。訪問：

```
http://localhost:7011
```

開始使用：
1. 上傳 STEP 檔案
2. 與 AI 聊天
3. 分析組合件接觸

---

## 📞 需要幫助？

請查看：
- [DEPLOYMENT_SETUP.md](DEPLOYMENT_SETUP.md) — 詳細安裝指南
- [DEPLOYMENT_REPORT.md](DEPLOYMENT_REPORT.md) — 驗證報告
- [TEST_PLAN.md](TEST_PLAN.md) — 測試計畫
- memory/ 目錄 — Phase 1-5 技術文檔

---

*最後更新: 2026-04-14*  
*版本: Phases 1-5 整合*
