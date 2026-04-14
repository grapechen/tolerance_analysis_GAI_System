# 部署後測試計畫 (Post-Deployment Testing Plan)

## 快速驗證清單 (Quick Verification)

### 1. Flask 應用啟動 (5 分鐘)

```bash
cd c:\Tolerance_Project\server
python ai_app.py

# 預期輸出：
# * Running on http://localhost:7011
# * WARNING: This is a development server...

# 檢查日誌中沒有 ERROR 或 CRITICAL
```

### 2. 前端載入 (2 分鐘)

```bash
# 開啟瀏覽器
http://localhost:7011

# 檢查項目：
# ✓ 頁面加載成功
# ✓ 左面板顯示所有按鈕 (產品架構、特徵、網路、接觸、STEP 3D、分析、編輯、調配)
# ✓ 右面板顯示聊天界面
# ✓ 浏览器控制台无错误 (F12)
```

### 3. 資料庫連接 (2 分鐘)

```bash
# 檢查 MySQL 中的表
mysql -u root -p tolerance_db -e "SHOW TABLES;"

# 應顯示：
# pmi_session
# pmi_item
# assembly_contact
# (以及其他現有表)
```

---

## 詳細測試流程

### Test 1: STEP 檔案上傳與解析 (10 分鐘)

**前置條件:** 有有效的 .stp 和 .xlsx 檔案

**步驟:**
```
1. 點擊「🔩 STEP 3D 檢視器」按鈕
   ✓ 右邊應出現 STEP 查看器面板
   
2. 拖拽或選擇 .stp 檔案
   ✓ 應顯示「📤 上傳 STEP...」
   ✓ 進度顯示：✅ Session 建立、✅ PMI 解析完成
   
3. 上傳完成後
   ✓ 3D 模型應在 step-viewer-container 中顯示
   ✓ PMI 清單應在下方顯示 (彩色編碼)
   ✓ 窗口可拖拽、縮放、旋轉 (OrbitControls)
```

**驗證資料庫:**
```sql
SELECT * FROM pmi_session WHERE status = 'ready' ORDER BY created_at DESC LIMIT 1;
SELECT COUNT(*) as pmi_count FROM pmi_item WHERE session_id = '<上面的session_id>';
```

**期望結果:** ✅ 上傳成功、PMI 清單填充、3D 模型顯示

---

### Test 2: PMI 清單交互 (5 分鐘)

**前置條件:** 已成功上傳 STEP

**步驟:**
```
1. 在 PMI 清單中點擊任意項目 (例如 dis1)
   ✓ 對應的幾何面應以顏色高亮 (紫色/綠色/橙色)
   ✓ Leader lines 應顯示為黑色線段
   ✓ 相機自動聚焦到該幾何
   
2. 再點擊另一個 PMI 項目
   ✓ 上一個高亮應清除
   ✓ 新的幾何高亮應出現
   
3. 多次點擊
   ✓ 沒有 JavaScript 錯誤
   ✓ 切換流暢無延遲
```

**瀏覽器控制台檢查:**
```javascript
console.log(PmiPanel._pmiRows.length)  // 應有 N 個 PMI
console.log(contactPairs)  // 接觸對陣列
```

**期望結果:** ✅ 高亮流暢、顏色正確、無錯誤

---

### Test 3: AI 驅動的 PMI 高亮 (Phase 4) (10 分鐘)

**前置條件:** 已上傳 STEP、Ollama 運行中

**步驟:**
```
1. 在聊天框輸入：「請高亮 dis3」
   ✓ AI 應回覆相關內容
   ✓ 回覆中應含 <HIGHLIGHT_PMI label="dis3" /> 標籤
   
2. 觀察 3D 模型
   ✓ dis3 對應的幾何應自動高亮
   ✓ 3D 查看器面板應自動打開
   ✓ PMI 清單應自動滾動到對應項目
   
3. 嘗試其他 PMI
   ✓ 「高亮 par1」
   ✓ 「標註 per2」
   ✓ 「dis1 的位置在哪」(應高亮)
```

**瀏覽器控制台檢查:**
```javascript
// 搜尋日誌
console.log('[AI] Highlighting PMI:')  // 應看到此訊息
```

**驗證 AI 回覆:**
```
在 Network tab (F12) 查看 /api/chat 回應
- 應包含 <HIGHLIGHT_PMI label="..."/>
- 回覆的 intent 應含 "pmi_highlight": true
```

**期望結果:** ✅ AI 理解 PMI 意圖、標籤正確、3D 自動高亮

---

### Test 4: 組合件接觸分析 (Phase 5) (15 分鐘)

**前置條件:** 已上傳 STEP

**步驟:**
```
1. 在 STEP 面板頭部點擊「🔗 分析接觸」按鈕
   ✓ 按鈕應變為「⏳ 分析中...」
   ✓ 後台執行 asm_worker.py
   
2. 等待 10-30 秒 (取決於檔案大小)
   ✓ 按鈕恢復「🔗 分析接觸」
   ✓ 聊天區應出現「🔗 組合件接觸分析完成」訊息
   
3. 自動切換到接觸圖視圖
   ✓ 左面板應顯示接觸關係圖
   ✓ 零件間應有連線表示接觸
```

**檢查瀏覽器控制台:**
```javascript
console.log(contactPairs)  // 應有接觸對
```

**驗證資料庫:**
```sql
SELECT * FROM assembly_contact 
WHERE session_id = '<step_session_id>' 
ORDER BY created_at DESC;

-- 應看到 comp1_name, comp2_name, contact_type 等記錄
```

**期望結果:** ✅ 分析完成、接觸圖顯示、資料入庫

---

### Test 5: 完整工作流 (20 分鐘)

**場景:** 使用者同時進行多項操作

**步驟:**
```
1. 上傳 STEP 檔案
   └─ 等待解析完成

2. 點擊 PMI 清單的第一個項目
   └─ 3D 高亮應出現

3. 在聊天框輸入：「這個機台有幾個零件?」
   └─ AI 回覆應基於 STEP 檔案內容

4. 再輸入：「請高亮 dis1」
   └─ 3D 應自動切換到 dis1 的高亮

5. 點擊「分析接觸」按鈕
   └─ 後台執行分析

6. 同時在聊天框輸入新訊息
   └─ 系統應能正確處理並行請求
```

**檢查項目:**
- [ ] 3D 渲染流暢 (無卡頓)
- [ ] AI 回覆正確
- [ ] 資料庫記錄完整
- [ ] 無 JavaScript 錯誤
- [ ] 無 Python 異常
- [ ] 按鈕狀態正確

**期望結果:** ✅ 完整流程無誤

---

## 壓力測試

### 大型 STEP 檔案 (100+ MB)

```
1. 上傳 100-200 MB STEP 檔案
   ✓ 不應超時 (> 30 秒)
   ✓ 記憶體使用合理 (< 2 GB)
   
2. 解析完成後
   ✓ PMI 清單應完整
   ✓ 3D 模型應正確顯示
```

### 高 PMI 數量 (1000+ 項)

```
1. 包含 1000+ PMI 的 STEP 檔案
   ✓ 清單滾動流暢
   ✓ 點擊響應即時
   ✓ AI 上下文注入無誤 (限制 30 項)
```

### 並發請求

```
1. 打開多個瀏覽器標籤頁
2. 在多個標籤頁上傳不同的 STEP
   ✓ 每個 session_id 獨立
   ✓ 資料不混亂
   ✓ 後端不崩潰
```

---

## 錯誤情景測試

### E1: 無效 STEP 檔案

```
1. 上傳非 STEP 格式的檔案 (例如 .txt)
   ✓ 應顯示「❌ 上傳失敗」
   ✓ 後端日誌顯示具體錯誤
   
2. 上傳損壞的 STEP 檔案
   ✓ 子進程超時後應優雅失敗
   ✓ 不應崩潰主 Flask 進程
```

### E2: 資料庫離線

```
1. 停止 MySQL 服務
2. 嘗試上傳 STEP
   ✓ 應顯示連接錯誤訊息
   ✓ 不應無限掛起
   
3. 恢復 MySQL
   ✓ 後續請求應恢復正常
```

### E3: OCC 未安裝

```
1. 移除或禁用 pythonocc-core
2. 啟動 Flask
   ✓ 應顯示清晰的依賴錯誤訊息
   ✓ 不應導致 500 Internal Server Error
   ✓ API 應回傳 503 Service Unavailable + 説明
```

### E4: 無效 session_id

```
1. 在 /api/step/highlight 中使用不存在的 session_id
   ✓ 應回傳 404 或 400
   ✓ 含有明確的錯誤訊息
```

---

## 性能基準 (Benchmarks)

| 操作 | 目標 | 實際 |
|------|------|------|
| STEP 上傳 (10 MB) | < 5 秒 | _____ |
| PMI 解析 | < 10 秒 | _____ |
| 3D 渲染初始化 | < 2 秒 | _____ |
| PMI 高亮切換 | < 500ms | _____ |
| AI 回覆 | < 10 秒 | _____ |
| 組合件分析 | < 30 秒 | _____ |
| 資料庫查詢 | < 100ms | _____ |

---

## 安全測試

### S1: SQL 注入防護

```javascript
// 嘗試在 label 中輸入 SQL
"'; DROP TABLE pmi_item; --"

// 預期：應被當作普通字符串，不應執行 SQL
```

### S2: XSS 防護

```javascript
// 嘗試在 PMI label 或聊天中注入 JavaScript
"<img src=x onerror=alert('xss')>"

// 預期：應被轉義或過濾，不應執行
```

### S3: 路徑遍歷防護

```bash
# 嘗試上傳時指定惡意路徑
# POST /api/step/upload with path="../../etc/passwd"

# 預期：應被拒絕或安全處理
```

---

## 檢查清單 (Checklist)

### 基礎功能
- [ ] Flask 應用啟動正常
- [ ] 前端頁面加載無誤
- [ ] MySQL 表結構正確

### Phase 1 (後端)
- [ ] STEP 上傳端點回應正確
- [ ] PMI 解析完成
- [ ] 資料存入資料庫
- [ ] 組合件分析子進程運行

### Phase 2 (前端 3D)
- [ ] Three.js 初始化成功
- [ ] 3D 模型渲染正確
- [ ] OrbitControls 互動流暢
- [ ] PMI 清單顯示完整

### Phase 3 (PMI 交互)
- [ ] PMI 列表點擊高亮
- [ ] Leader lines 顯示
- [ ] 相機聚焦正常

### Phase 4 (AI 整合)
- [ ] PMI 意圖檢測工作
- [ ] AI 上下文注入有效
- [ ] <HIGHLIGHT_PMI> 標籤攔截
- [ ] 前端自動高亮

### Phase 5 (組合件分析)
- [ ] 分析按鈕可點擊
- [ ] subprocess 執行成功
- [ ] 結果入庫
- [ ] 接觸圖顯示

### 跨功能
- [ ] 無 JavaScript 錯誤
- [ ] 無 Python 異常
- [ ] 資料一致性
- [ ] 性能滿足目標

---

## 簽核

| 項目 | 負責人 | 日期 | 簽核 |
|------|--------|------|------|
| 環境準備 | | | |
| 代碼部署 | | | |
| 資料庫設定 | | | |
| 功能測試 | | | |
| 性能測試 | | | |
| 安全測試 | | | |
| **最終驗收** | | | |

---

## 問題追蹤

| ID | 問題 | 嚴重性 | 狀態 | 備註 |
|----|------|--------|------|------|
| | | | | |

---

*測試計畫版本: 1.0*  
*最後更新: 2026-04-14*  
*適用範圍: Phases 1-5*
