# 進度顯示功能使用指南

**文檔日期**: 2026-04-15  
**功能**: 實時進度條顯示  
**技術**: Server-Sent Events (SSE) + Three.js Canvas

---

## 📊 功能概述

在 Web 應用中實現實時進度顯示，類似於原始 tkinter 版本的進度條。用戶在進行長耗時操作（如 STEP 解析、三角化、接觸分析）時，能看到實時的進度條和進度信息。

### 特點

✅ 實時更新（無需輪詢）  
✅ 支持多個並行操作  
✅ 自動隱藏完成時的進度條  
✅ 錯誤狀態提示  
✅ 耗時統計  
✅ 非侵入式設計（自動集成到現有 UI）

---

## 🏗️ 架構設計

### 三部分組成

```
┌─────────────────────────────────────────┐
│      前端 (Browser)                      │
│  ┌───────────────────────────────────┐  │
│  │  progress_bar.js                  │  │
│  │  • 進度條 UI                      │  │
│  │  • SSE 事件監聽器                 │  │
│  │  • 實時更新顯示                   │  │
│  └───────────────────────────────────┘  │
│           ↓↑ SSE 流                      │
├─────────────────────────────────────────┤
│      後端 (Flask)                        │
│  ┌───────────────────────────────────┐  │
│  │  progress_tracker.py              │  │
│  │  • ProgressTracker 類             │  │
│  │  • 全局進度狀態存儲               │  │
│  │  • 線程安全的更新機制             │  │
│  └───────────────────────────────────┘  │
│           ↓↑ API 調用                    │
│  ┌───────────────────────────────────┐  │
│  │  step_service.py                  │  │
│  │  • /api/step/progress (SSE)       │  │
│  │  • /api/step/progress_status      │  │
│  │  • 在操作中集成 ProgressTracker   │  │
│  └───────────────────────────────────┘  │
├─────────────────────────────────────────┤
│      長耗時操作                          │
│  • route_parse_pmi()                     │
│  • route_run_asm_worker()                │
│  • route_get_geometry()                  │
│  • 其他需要顯示進度的操作                │
└─────────────────────────────────────────┘
```

---

## 📁 新增文件

### 1. `server/progress_tracker.py` (104 行)

進度跟踪核心模組，提供：

```python
# 初始化進度追蹤
progress = ProgressTracker(session_id, "operation_name")

# 更新進度
progress.update(current_step, total_steps, "消息")

# 完成或出錯
progress.complete("完成信息")
progress.error("錯誤信息")

# 查詢進度
get_progress(session_id)  # 單個
get_all_progress()         # 所有
```

**主要類**:
- `ProgressTracker`: 單個操作的進度跟踪器
- SSE 流生成函數

---

### 2. `server/static/js/progress_bar.js` (289 行)

前端進度條 UI 和事件監聽器，提供：

```javascript
// 自動初始化
ProgressBar.init()

// 控制
ProgressBar.show()    // 顯示進度條
ProgressBar.hide()    // 隱藏進度條
ProgressBar.dispose() // 清理資源
```

**UI 特性**:
- 浮動進度條 (位於屏幕中央)
- 實時百分比顯示
- 操作名稱和消息
- 進度統計 (當前/總計)
- 耗時計時器
- 完成/錯誤狀態顯示

---

## 🚀 使用方式

### 後端集成（Python）

在需要長時間操作的 Flask 路由函數中添加進度跟踪：

```python
def route_parse_pmi():
    """解析 PMI，填充 pmi_item 資料表"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        
        # 初始化進度追蹤
        progress = ProgressTracker(session_id, "parse_pmi")
        
        # 步驟 1: 加載 STEP
        progress.update(1, 5, "📂 正在加載 STEP 文件...")
        engine_obj = StepXcafEngine()
        engine_obj.load(stp_path)
        
        # 步驟 2: 解析 Excel
        progress.update(2, 5, "📊 正在解析 Excel...")
        face_pmi_map, pmi_rows = parse_sfa_excel(xlsx_path)
        
        # 步驟 3: 加載 CSV ASSOCIATION
        progress.update(3, 5, "🔗 正在加載 ASSOCIATION...")
        semantic_to_tao = load_sfa_association(xlsx_path)
        
        # 步驟 4: 解析 Tessellated
        progress.update(4, 5, "🔺 正在解析 Tessellated...")
        tao_to_data = parse_tessellated_annotations(stp_path)
        
        # 步驟 5: 寫入數據庫
        progress.update(5, 5, "💾 正在寫入數據庫...")
        # ... 寫入邏輯 ...
        
        # 完成
        progress.complete("✅ PMI 解析完成")
        
        return jsonify({"ok": True, ...}), 200
        
    except Exception as e:
        progress.error(f"❌ 解析失敗: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500
```

---

### 前端自動集成

進度條 JavaScript 模組在頁面加載時自動初始化：

```javascript
// 1. HTML 中已引入進度條腳本
<script src="{{ url_for('static', filename='js/progress_bar.js') }}" defer></script>

// 2. 自動連接 SSE
ProgressBar.init()
  ↓
連接 /api/step/progress
  ↓
實時監聽進度更新

// 3. 用戶調用 API（例如在 app.js 或 chat.js）
fetch('/api/step/parse_pmi', {method: 'POST', body: formData})
  ↓
後端發出 ProgressTracker.update()
  ↓
SSE 推送到前端
  ↓
ProgressBar 自動更新顯示
```

---

## 📊 API 文檔

### 1. SSE 端點：`GET /api/step/progress`

**功能**: 實時進度流（Server-Sent Events）

**連接方式**:
```javascript
const eventSource = new EventSource('/api/step/progress');
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data);
};
```

**數據格式**:
```json
{
  "type": "update",
  "data": {
    "session_id_1": {
      "operation": "parse_pmi",
      "current": 3,
      "total": 5,
      "percentage": 60,
      "message": "正在加載 ASSOCIATION...",
      "status": "running",
      "elapsed": 12.5
    },
    "session_id_2": {
      "operation": "asm_contact",
      "current": 15,
      "total": 100,
      "percentage": 15,
      "message": "掃描接觸面...",
      "status": "running",
      "elapsed": 8.3
    }
  }
}
```

---

### 2. REST 端點：`GET /api/step/progress_status`

**功能**: 查詢單個 session 的進度狀態（不使用 SSE）

**請求**:
```
GET /api/step/progress_status?session_id=550e8400-e29b-41d4-a716-446655440000
```

**響應**:
```json
{
  "ok": true,
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "progress": {
    "operation": "parse_pmi",
    "current": 3,
    "total": 5,
    "percentage": 60,
    "message": "正在加載 ASSOCIATION...",
    "status": "running",
    "elapsed": 12.5
  }
}
```

---

## 🎨 UI 樣式

### 進度條外觀

```
╔═══════════════════════════════════════════╗
║  📊 解析 PMI...                          [×] ║
╠═══════════════════════════════════════════╣
║  📂 正在加載 STEP 文件...                 ║
║  ┌───────────────────────────────────────┐ ║
║  │████████████░░░░░░░░░░░░░░░░░░░  60%   │ ║
║  └───────────────────────────────────────┘ ║
║  3 / 5                          耗時: 12s  ║
╚═══════════════════════════════════════════╝
```

### 顏色方案

- **背景**: 淺灰色 (#f0f0f0)
- **進度條**: 綠色漸變 (完成) / 紅色漸變 (錯誤)
- **文本**: 深灰色

---

## 🔧 配置參數

### ProgressTracker 初始化

```python
progress = ProgressTracker(
    session_id="550e8400-e29b-41d4-a716-446655440000",
    operation="parse_pmi"  # 操作名稱，用於 UI 標題
)
```

**操作名稱對應 UI 標題**:
- `"parse_pmi"` → 📊 解析 PMI...
- `"asm_contact"` → 🔍 接觸分析...
- `"tessellate"` → 🔺 三角化...
- 其他 → 處理中...

---

## 📈 性能考慮

### SSE 更新頻率

- **前端監聽**: 每 500ms 接收一次更新
- **後端發送**: 根據實際進度變化

```python
# 在 progress_bar.js 中
yield f"data: {json.dumps(data)}\n\n"
time.sleep(0.5)  # 500ms 間隔
```

### 線程安全

使用 `threading.Lock` 保護全局進度狀態：

```python
_state_lock = Lock()

with _state_lock:
    _progress_states[session_id] = {...}
```

---

## 🐛 故障排查

### 進度條不顯示

**檢查清單**:
1. ✓ progress_bar.js 是否已加載 (檢查瀏覽器控制台)
2. ✓ `/api/step/progress` 是否可訪問
3. ✓ 後端是否創建了 ProgressTracker
4. ✓ 瀏覽器是否支持 EventSource (檢查 polyfill)

**控制台日誌**:
```javascript
// 正常情況
✅ ProgressBar 初始化完成
SSE 更新: {type: 'update', data: {...}}

// 錯誤情況
❌ SSE 連接錯誤: ...
❌ SSE 數據解析錯誤: ...
```

---

### SSE 連接中斷

**原因**:
- 代理不支持 SSE (Nginx 等)
- 瀏覽器關閉標籤頁
- 網絡超時

**解決**:
```python
# 在 Flask 應用中配置 SSE
response.headers['Cache-Control'] = 'no-cache'
response.headers['X-Accel-Buffering'] = 'no'
response.headers['Connection'] = 'keep-alive'
```

---

## 🔮 未來增強

### 短期
- [ ] 進度條取消按鈕
- [ ] 多進度條並行顯示
- [ ] 預估完成時間

### 中期
- [ ] 進度持久化（刷新頁面仍保留）
- [ ] 歷史記錄查看
- [ ] 通知系統集成

### 長期
- [ ] WebSocket 雙向通信
- [ ] 進度數據導出
- [ ] 分析儀表板

---

## 📚 集成示例

### 在現有操作中添加進度跟踪

**修改前**:
```python
def route_run_asm_worker():
    # 直接執行子進程
    result = subprocess.run([...], capture_output=True)
```

**修改後**:
```python
def route_run_asm_worker():
    session_id = request.json.get('session_id')
    progress = ProgressTracker(session_id, "asm_contact")
    
    try:
        # 步驟 1: 準備
        progress.update(1, 3, "準備接觸分析...")
        # ...
        
        # 步驟 2: 執行子進程
        progress.update(2, 3, "執行子進程...")
        result = subprocess.run([...], capture_output=True)
        
        # 步驟 3: 解析結果
        progress.update(3, 3, "解析結果...")
        # ...
        
        progress.complete("接觸分析完成")
        return jsonify({"ok": True, ...}), 200
        
    except Exception as e:
        progress.error(str(e))
        return jsonify({"ok": False, "error": str(e)}), 500
```

---

## ✅ 檢查清單

部署前確認：

- [ ] `server/progress_tracker.py` 已創建
- [ ] `server/static/js/progress_bar.js` 已創建
- [ ] `ai_app.py` 已註冊進度路由
- [ ] `index.html` 已引入 progress_bar.js
- [ ] `step_service.py` 已導入 ProgressTracker
- [ ] 主要操作函數已集成進度跟踪
- [ ] 測試 SSE 連接 (F12 Network 查看)
- [ ] 測試進度條 UI (長時間操作時)

---

**版本**: 1.0 | **日期**: 2026-04-15
