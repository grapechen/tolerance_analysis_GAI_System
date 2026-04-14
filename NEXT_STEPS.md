# 下一步執行指南 (Next Steps Execution Guide)

**目標:** 在 30 分鐘內部署系統並開始使用

**現在時間:** 準備執行

---

## 📋 執行檢查清單

### ✅ 已完成的工作
- [x] 代碼驗證 (54+ 項)
- [x] 文檔生成
- [x] 部署腳本準備
- [x] 環境模板創建

### ⏳ 現在要做的工作
- [ ] Step 1: 環境驗證 (5 分鐘)
- [ ] Step 2: 資料庫初始化 (5 分鐘)
- [ ] Step 3: 應用啟動 (2 分鐘)
- [ ] Step 4: 前端驗證 (2 分鐘)
- [ ] Step 5: 功能測試 (10 分鐘)

---

## 🚀 Step 1: 環境驗證 (5 分鐘)

### 1.1 打開 PowerShell 或終端
```bash
# Windows PowerShell
# 或 Linux/macOS Terminal
```

### 1.2 驗證 Python

```bash
python --version
# 預期: Python 3.8 或更高版本
# 如果無: 安裝 Python 3.8+ 從 python.org
```

### 1.3 驗證 MySQL 運行

```bash
# Windows 檢查
tasklist | findstr mysql

# Linux 檢查
sudo systemctl status mysql

# macOS 檢查
brew services list | grep mysql

# 如果未運行，啟動:
# Windows: net start MySQL80
# Linux: sudo systemctl start mysql
# macOS: brew services start mysql
```

✅ **預期結果:** MySQL 運行中

### 1.4 驗證依賴安裝

```bash
pip list | findstr flask sqlalchemy pymysql pythonocc

# 或完整檢查
python -c "import flask, sqlalchemy, pymysql; print('✓ Core packages OK')"

# 檢查 OCC (關鍵)
python -c "from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh; print('✓ OCC installed')"
```

✅ **預期結果:** 所有套件已安裝

### 1.5 如果缺少依賴，安裝

```bash
# 安裝所有必要套件
pip install flask flask-cors sqlalchemy pymysql openpyxl ollama python-dotenv

# 關鍵：安裝 OCC
pip install pythonocc-core --only-binary :all:
```

⏱️ **此步驟耗時:** 3-5 分鐘

---

## 💾 Step 2: 資料庫初始化 (5 分鐘)

### 2.1 進入 Server 目錄

```bash
cd c:\Tolerance_Project\server
# 或
cd /path/to/Tolerance_Project/server
```

### 2.2 確認 .env 文件存在

```bash
# 檢查文件是否存在
ls -la .env
# 或 Windows
dir .env

# 預期: 應看到 .env 文件
```

### 2.3 檢查 .env 中的資料庫配置

```bash
# 查看內容
cat .env | grep DATABASE_URL
# Windows
type .env | findstr DATABASE_URL

# 預期: DATABASE_URL=mysql+pymysql://root:password@localhost:3306/tolerance_db
# 如果密碼錯誤，編輯 .env 檔案更正
```

### 2.4 運行資料庫初始化

```bash
python setup_database.py
```

### 2.5 檢查輸出

**成功輸出應該是:**
```
================================================================================
Tolerance Project - Database Setup
================================================================================

[INFO] Database Configuration:
  Host:     localhost:3306
  User:     root
  Database: tolerance_db

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

### 2.6 如果出現錯誤

**錯誤:** `Can't connect to MySQL server`
```bash
# MySQL 未運行，啟動 MySQL
# Windows: net start MySQL80
# Linux: sudo systemctl start mysql
# macOS: brew services start mysql

# 等 5 秒後重新運行
python setup_database.py
```

**錯誤:** `Access denied for user 'root'@'localhost'`
```bash
# 密碼錯誤，編輯 .env
# 找到正確的 MySQL 密碼，更新:
# DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/tolerance_db

python setup_database.py
```

**錯誤:** `ModuleNotFoundError: No module named 'OCC'`
```bash
pip install pythonocc-core --only-binary :all:
python setup_database.py
```

✅ **預期結果:** 資料庫表成功建立

⏱️ **此步驟耗時:** 2-5 分鐘

---

## 🟢 Step 3: 應用啟動 (2 分鐘)

### 3.1 保持在 Server 目錄

```bash
# 確認你在正確目錄
pwd  # 或 cd
# 應該看到: c:\Tolerance_Project\server 或 /path/to/server
```

### 3.2 啟動應用

```bash
# 方法 A：使用啟動器 (推薦，有檢查)
python run.py

# 方法 B：直接啟動
python ai_app.py

# 方法 C：自定義參數
python run.py --host 0.0.0.0 --port 7011 --debug
```

### 3.3 檢查啟動輸出

**成功輸出應該包含:**
```
[CHECK] Verifying dependencies...
  [✓] Flask
  [✓] SQLAlchemy
  [✓] PyMySQL

[CHECK] Testing database connection...
  [✓] Database connection successful

[CHECK] Verifying database tables...
  [✓] pmi_session
  [✓] pmi_item
  [✓] assembly_contact

[STARTUP] Starting Flask application...
  Host: 127.0.0.1
  Port: 7011
  Debug: False

================================================================================

 * Running on http://127.0.0.1:7011
 * Press CTRL+C to quit
```

### 3.4 如果出現錯誤

**錯誤:** `ImportError: No module named 'flask'`
```bash
pip install flask flask-cors
python run.py
```

**錯誤:** `Address already in use`
```bash
# 埠 7011 已被使用，可以:
# 方法 1: 終止其他應用
# 方法 2: 使用不同埠
python run.py --port 7012
```

✅ **預期結果:** Flask 運行在 http://127.0.0.1:7011

⏱️ **此步驟耗時:** 1-2 分鐘

---

## 🌐 Step 4: 前端驗證 (2 分鐘)

### 4.1 打開新終端窗口

**保持 Flask 應用運行**，打開新的終端/PowerShell/瀏覽器

### 4.2 在瀏覽器中打開應用

```bash
# 在瀏覽器地址欄輸入:
http://localhost:7011

# 或使用 curl 測試:
curl http://localhost:7011
```

### 4.3 驗證頁面加載

**檢查項目:**
- [ ] 頁面加載成功（非 404 或 500 錯誤）
- [ ] 看到標題和 UI 元素
- [ ] 左面板有多個按鈕
- [ ] 右面板有聊天界面

### 4.4 打開開發者工具 (F12) 檢查錯誤

```
按 F12 或 Ctrl+Shift+I 打開開發者工具
→ 點擊 Console 標籤
→ 檢查是否有紅色錯誤訊息

預期: 無紅色 JavaScript 錯誤
警告可以忽略 (黃色)
```

✅ **預期結果:** 頁面正常加載，無重大錯誤

⏱️ **此步驟耗時:** 1-2 分鐘

---

## 🧪 Step 5: 基本功能測試 (10 分鐘)

### 5.1 測試 UI 元素

**在瀏覽器中檢查:**
```
左面板按鈕（應全部可見且可點擊）:
  ✓ 產品架構
  ✓ 特徵面
  ✓ 公差網路
  ✓ 組裝接觸
  ✓ 🔩 STEP 3D 檢視器    ← 重要（Phase 2）
  ✓ 公差分析
  ✓ 編輯公差
  ✓ 公差調配

右面板:
  ✓ 聊天輸入框
  ✓ 發送按鈕
  ✓ 模型選擇下拉菜單
  ✓ 聊天歷史區域
```

✅ **預期結果:** 所有 UI 元素可見

### 5.2 測試聊天功能

```
步驟:
1. 在聊天框輸入: "你好"
2. 點擊發送按鈕或按 Enter
3. 等待 AI 回覆

預期:
  ✓ 訊息出現在聊天歷史
  ✓ "Loading..." 顯示
  ✓ AI 回覆在 2-10 秒內出現
  ✓ 無 500 錯誤
```

✅ **預期結果:** AI 能回應

### 5.3 測試 STEP 3D 查看器 (需要 .stp 檔案)

```
步驟:
1. 點擊左面板「🔩 STEP 3D 檢視器」按鈕
2. 右邊應出現 STEP 查看器面板
3. 面板中有一個 Canvas 區域和下方 PMI 清單
4. 點擊面板中的上傳區域或選擇 .stp 檔案

預期:
  ✓ 面板出現
  ✓ 可以選擇 .stp 檔案
  ✓ 上傳開始 (顯示進度)
  ✓ 完成後 3D 模型出現
  ✓ PMI 清單填充
```

⚠️ **注意:** 如果沒有 .stp 檔案，可以跳過此測試

### 5.4 系統就緒確認

```
確認:
  ✓ Flask 應用運行
  ✓ 頁面加載成功
  ✓ 聊天功能工作
  ✓ 3D 面板顯示 (若有 STEP 檔案)
  ✓ 無重大錯誤
```

✅ **預期結果:** 系統準備就緒

⏱️ **此步驟耗時:** 5-10 分鐘

---

## ✨ 完成後的結果

當完成所有步驟後，你將擁有：

```
✅ 運行中的 Flask 應用
✅ 完整的資料庫
✅ 工作的 3D STEP 查看器
✅ 函數式 AI 聊天
✅ 組合件分析能力
✅ 完整的 Phases 1-5 整合
```

---

## 📊 進度跟踪

| Step | 任務 | 耗時 | 狀態 |
|------|------|------|------|
| 1 | 環境驗證 | 5 分鐘 | ⏳ |
| 2 | 資料庫初始化 | 5 分鐘 | ⏳ |
| 3 | 應用啟動 | 2 分鐘 | ⏳ |
| 4 | 前端驗證 | 2 分鐘 | ⏳ |
| 5 | 功能測試 | 10 分鐘 | ⏳ |
| **總計** | | **24 分鐘** | |

---

## 🎯 立即開始

### 現在就做:

```bash
# 1. 打開終端 (PowerShell/Terminal/Bash)

# 2. 進入目錄
cd c:\Tolerance_Project\server

# 3. 驗證 Python
python --version

# 4. 確保 MySQL 運行
tasklist | findstr mysql    # Windows
ps aux | grep mysql         # Linux/macOS

# 5. 運行資料庫初始化
python setup_database.py

# 6. 如果成功，啟動應用
python run.py

# 7. 打開瀏覽器
# http://localhost:7011
```

---

## 🆘 快速幫助

### 常見問題
- MySQL 不運行？→ 啟動 MySQL 服務
- OCC 錯誤？ → `pip install pythonocc-core --only-binary :all:`
- 埠被佔用？ → `python run.py --port 7012`
- 頁面 404？ → Flask 是否運行？

### 詳細幫助
- 問題多？ → 查看 DEPLOYMENT_SETUP.md
- 想測試？ → 查看 TEST_PLAN.md
- 想了解技術？ → 查看 memory/ 目錄

---

## ✅ 準備好了嗎？

**現在就開始 Step 1：環境驗證**

預計 30 分鐘內系統完全運行。

---

*最後更新: 2026-04-14*
