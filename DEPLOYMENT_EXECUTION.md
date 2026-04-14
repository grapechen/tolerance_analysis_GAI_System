# 部署執行計畫 (Deployment Execution Plan)

## 📅 執行摘要

- **預計耗時:** 45-85 分鐘
- **難度:** 中等
- **先決條件:** MySQL、Python 3.8+、Ollama

---

## 🎯 部署目標

完成以下任務確保系統完全上線：

1. ✅ 配置環境變數
2. ✅ 初始化資料庫
3. ✅ 啟動 Flask 應用
4. ✅ 驗證所有 API 端點
5. ✅ 測試前端功能
6. ✅ 執行完整工作流測試

---

## 執行步驟

### 💾 第 1 階段：環境準備 (15-30 分鐘)

#### 1.1 驗證系統需求

```bash
# 檢查 Python 版本
python --version
# 預期: Python 3.8+

# 檢查 pip
pip --version

# 檢查 Node.js (可選，用於前端構建)
node --version  # 預期: 14+
```

**記錄檢查結果:**
- [ ] Python 版本: _______
- [ ] pip 版本: _______
- [ ] Node.js (可選): _______

#### 1.2 安裝 Python 依賴

```bash
cd c:\Tolerance_Project\server

# 建議：使用虛擬環境
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

# 安裝依賴
pip install flask flask-cors sqlalchemy pymysql openpyxl python-dotenv ollama

# 關鍵：安裝 OCC
pip install pythonocc-core --only-binary :all:

# 驗證 OCC
python -c "from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh; print('✓ OCC OK')"
```

**檢查結果:**
- [ ] Flask installed
- [ ] SQLAlchemy installed
- [ ] PyMySQL installed
- [ ] pythonocc-core installed

#### 1.3 配置環境變數

```bash
# .env 檔案已自動生成，確認內容
cat .env

# 如需修改，編輯 .env 並更新：
# DATABASE_URL=mysql+pymysql://root:password@localhost:3306/tolerance_db
```

**配置檢查:**
- [ ] DATABASE_URL 設定正確
- [ ] OLLAMA_HOST 設定正確 (預設: http://localhost:11434)
- [ ] FLASK_PORT 設定正確 (預設: 7011)

---

### 🗄️ 第 2 階段：資料庫初始化 (5-10 分鐘)

#### 2.1 驗證 MySQL 連接

```bash
# 確保 MySQL 已啟動
# Windows: Services → MySQL80
# Linux: sudo systemctl status mysql
# macOS: brew services list | grep mysql

# 測試連接 (使用 MySQL Shell 或命令行)
mysql -u root -p -e "SELECT 1;"
# 輸入密碼並驗證
```

**連接檢查:**
- [ ] MySQL 已啟動
- [ ] 可以成功連接
- [ ] 認證資訊正確

#### 2.2 建立資料庫和表

```bash
# 自動建立資料庫和表
python setup_database.py

# 預期輸出:
# [OK] MySQL connection successful
# [OK] Database 'tolerance_db' ready
# [OK] Tables created successfully:
#   ✓ pmi_session
#   ✓ pmi_item
#   ✓ assembly_contact
```

**資料庫檢查:**
- [ ] setup_database.py 執行成功
- [ ] 所有表已建立
- [ ] 無錯誤訊息

#### 2.3 驗證表結構

```bash
# 使用 MySQL 查詢驗證表
mysql -u root -p tolerance_db -e "SHOW TABLES;"

# 應顯示:
# | Tables_in_tolerance_db |
# | assembly_contact       |
# | pmi_item               |
# | pmi_session            |
```

**表結構檢查:**
- [ ] pmi_session 存在
- [ ] pmi_item 存在
- [ ] assembly_contact 存在

---

### 🚀 第 3 階段：應用啟動 (2-5 分鐘)

#### 3.1 啟動 Flask 應用

```bash
# 方法 A: 使用自動檢查啟動指令碼
python run.py

# 方法 B: 直接啟動 (跳過檢查)
python ai_app.py

# 方法 C: 自定義參數
python run.py --host 0.0.0.0 --port 7011 --debug
```

**預期輸出:**
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

 * Running on http://127.0.0.1:7011
 * Press CTRL+C to quit
```

**啟動檢查:**
- [ ] 無語法錯誤
- [ ] 資料庫連接成功
- [ ] 應用監聽 7011 埠
- [ ] 沒有 CRITICAL 錯誤

#### 3.2 確認應用就緒

保持終端開啟，應用現已運行。

**應用檢查:**
- [ ] 應用已啟動
- [ ] 監聽 http://localhost:7011
- [ ] 無運行時錯誤

---

### 🔍 第 4 階段：前端驗證 (5 分鐘)

#### 4.1 開啟前端頁面

```bash
# 在瀏覽器中打開
http://localhost:7011

# 或使用 curl 測試
curl http://localhost:7011
```

**前端檢查:**
- [ ] 頁面加載成功（HTTP 200）
- [ ] 頁面標題正確
- [ ] 無 404 錯誤

#### 4.2 驗證 UI 元素

在瀏覽器中檢查：

```
✓ 左面板:
  - 產品架構 按鈕
  - 特徵面 按鈕
  - 公差網路 按鈕
  - 接觸關係 按鈕
  - 🔩 STEP 3D 檢視器 按鈕  ← Phase 2/5
  - 公差分析 按鈕
  - 編輯公差 按鈕
  - 公差調配 按鈕

✓ 右面板:
  - 聊天輸入框
  - 發送按鈕
  - 聊天歷史區域
  - 模型選擇下拉菜單

✓ 開發者工具 (F12):
  - 控制台無紅色錯誤
  - Network 顯示 200 狀態碼
```

**UI 檢查:**
- [ ] 所有按鈕可見
- [ ] 聊天界面完整
- [ ] 無 JavaScript 錯誤
- [ ] 無 CSS 警告

---

### 🧪 第 5 階段：API 測試 (10-15 分鐘)

在新終端視窗執行 (保持 Flask 運行)：

#### 5.1 測試聊天端點

```bash
# 測試基本聊天
curl -X POST http://localhost:7011/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "你好",
    "model": "llama2",
    "history": [],
    "lang": "zh-TW"
  }'

# 預期: {"reply": "...", "intent": {...}}
```

**聊天 API 檢查:**
- [ ] 回應 HTTP 200
- [ ] reply 欄位有內容
- [ ] intent 欄位存在

#### 5.2 測試 STEP 上傳端點 (需要 STEP 檔案)

```bash
# 需要先準備 .stp 檔案
# 例: test.stp

curl -X POST http://localhost:7011/api/step/upload \
  -F "stp_file=@test.stp"

# 預期: {"ok": true, "session_id": "..."}
```

**STEP 上傳檢查:**
- [ ] 回應 HTTP 200
- [ ] ok 為 true
- [ ] session_id 已生成

#### 5.3 測試 PMI 解析端點

```bash
# 使用上一步得到的 session_id
SESSION_ID="<上面的session_id>"

curl -X POST http://localhost:7011/api/step/parse_pmi \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SESSION_ID\"}"

# 預期: {"ok": true, "n_pmi_rows": N, "pmi_rows": [...]}
```

**PMI 解析檢查:**
- [ ] 回應 HTTP 200
- [ ] ok 為 true
- [ ] pmi_rows 陣列有數據

#### 5.4 測試組合件分析端點

```bash
# 使用同一個 session_id
curl -X POST http://localhost:7011/api/step/asm_contact \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SESSION_ID\"}"

# 預期: {"ok": true, "contacts": [...]}
```

**組合件分析檢查:**
- [ ] 回應 HTTP 200
- [ ] ok 為 true
- [ ] contacts 陣列有數據或為空

---

### 🎮 第 6 階段：功能集成測試 (15-20 分鐘)

#### 6.1 STEP 上傳測試

```
步驟:
1. 在瀏覽器中打開 http://localhost:7011
2. 點擊左面板「🔩 STEP 3D 檢視器」按鈕
3. 等待右邊出現 STEP 查看器面板
4. 拖拽或選擇 .stp 檔案上傳
5. 等待處理完成

預期結果:
  [✓] 面板出現
  [✓] 上傳顯示進度
  [✓] 3D 模型顯示
  [✓] PMI 清單填充
  [✓] 清單項有顏色編碼
```

**檢查項目:**
- [ ] 面板顯示
- [ ] 模型渲染
- [ ] 清單填充
- [ ] 顏色正確

#### 6.2 PMI 高亮測試

```
步驟:
1. STEP 上傳完成後
2. 在 PMI 清單中點擊第一個項目
3. 觀察 3D 模型

預期結果:
  [✓] 面高亮顯示
  [✓] 顏色對應清單項
  [✓] Leader lines 顯示
  [✓] 相機自動調整
```

**檢查項目:**
- [ ] 面高亮
- [ ] Leader lines 顯示
- [ ] 相機聚焦
- [ ] 無 JavaScript 錯誤

#### 6.3 AI 驅動高亮測試 (Phase 4)

```
步驟:
1. STEP 上傳完成後
2. 在聊天框輸入: 「請高亮 dis1」
3. 觀察 AI 回覆和 3D 模型

預期結果:
  [✓] AI 回覆相關內容
  [✓] 回覆含 <HIGHLIGHT_PMI label="dis1" /> 標籤
  [✓] 3D 自動高亮 dis1
  [✓] 3D 面板自動打開
```

**檢查項目:**
- [ ] AI 回覆正確
- [ ] 標籤被攔截
- [ ] 3D 自動高亮
- [ ] 面板自動打開

#### 6.4 組合件分析測試 (Phase 5)

```
步驟:
1. STEP 上傳完成後
2. 在 STEP 面板頂部點擊「🔗 分析接觸」按鈕
3. 等待 10-30 秒分析完成
4. 觀察結果

預期結果:
  [✓] 按鈕變為「⏳ 分析中...」
  [✓] 分析完成後恢復正常
  [✓] 聊天區顯示完成訊息
  [✓] 自動切換到接觸圖
  [✓] MySQL 有新記錄
```

**檢查項目:**
- [ ] 分析執行
- [ ] 完成訊息顯示
- [ ] 接觸圖更新
- [ ] 資料庫有記錄

#### 6.5 完整工作流測試

```
整合測試: 上傳 → 高亮 → AI 聊天 → 分析 → 檢視結果

步驟:
1. 上傳 STEP 檔案
2. 點擊 PMI 清單項目 → 高亮
3. 聊天: 「這個零件有多少個 PMI?」
4. 聊天: 「高亮最大的特徵」
5. 點擊「分析接觸」
6. 聊天: 「接觸分析結果如何?」

預期: 所有操作流暢、無錯誤、結果正確
```

**整合檢查:**
- [ ] 上傳成功
- [ ] 高亮流暢
- [ ] AI 理解 PMI
- [ ] 分析完成
- [ ] 接觸圖正確

---

## 📊 驗證檢查清單

### 必須通過

- [x] Python 3.8+
- [x] Flask 應用啟動
- [x] MySQL 連接成功
- [x] 資料表建立
- [x] 前端頁面加載
- [x] 聊天 API 回應
- [x] STEP 上傳成功 (需要檔案)
- [x] PMI 清單顯示
- [x] 3D 高亮工作

### 建議驗證

- [ ] AI 聊天正確
- [ ] <HIGHLIGHT_PMI> 攔截
- [ ] 組合件分析完成
- [ ] 接觸圖更新
- [ ] MySQL 資料持久
- [ ] 瀏覽器控制台無錯誤

---

## ⚠️ 常見問題快速解決

| 問題 | 原因 | 解決方案 |
|------|------|---------|
| 無法連接 MySQL | MySQL 未啟動 | `net start MySQL80` 或 `brew services start mysql` |
| OCC 匯入失敗 | 未安裝 | `pip install pythonocc-core --only-binary :all:` |
| 頁面 404 | Flask 未運行 | 確認 `python run.py` 執行 |
| 3D 不顯示 | Three.js 加載失敗 | F12 檢查 Network，確認 CDN 可用 |
| AI 無回應 | Ollama 未啟動 | `ollama serve` |

---

## 🎉 部署完成確認

所有以下項都完成✓時，部署成功：

- [ ] Flask 應用運行中
- [ ] 資料庫表已建立
- [ ] 前端頁面加載
- [ ] STEP 上傳功能工作
- [ ] 3D 模型可渲染
- [ ] PMI 清單可交互
- [ ] AI 聊天可通訊
- [ ] 組合件分析可執行
- [ ] 無 Critical 錯誤

**狀態:** ________________

**部署時間:** ________________

**簽核人:** ________________

---

## 📁 關鍵檔案位置

| 檔案 | 位置 | 用途 |
|------|------|------|
| .env | `c:\Tolerance_Project\server\.env` | 環境配置 |
| setup_database.py | `c:\Tolerance_Project\server\setup_database.py` | 資料庫初始化 |
| run.py | `c:\Tolerance_Project\server\run.py` | 應用啟動 |
| ai_app.py | `c:\Tolerance_Project\server\ai_app.py` | Flask 主程式 |
| index.html | `c:\Tolerance_Project\server\templates\index.html` | 前端頁面 |

---

## 📞 支援

若遇到問題，參考：
- QUICK_START.md — 快速啟動
- DEPLOYMENT_SETUP.md — 詳細安裝
- TEST_PLAN.md — 完整測試計畫
- memory/ — 技術細節

---

*版本: 1.0*  
*日期: 2026-04-14*  
*適用: Phases 1-5*
