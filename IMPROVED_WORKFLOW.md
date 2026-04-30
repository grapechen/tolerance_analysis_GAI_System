# STEP PMI 3D 檢視器 - 改進的工作流程

## 新流程（已優化）

用户现在可以按照以下步骤操作：

### 第 1 步：上傳 STEP 檔案
```
1. 點擊「📤 上傳 STEP」
2. 選擇 STEP 檔案（例：part.stp）
3. 等待上傳完成
4. 系統將：
   ✓ 立即加載 STEP 幾何體到記憶體
   ✓ 快速三角化（使用deflection=0.3，約 3-5 秒）
   ✓ 顯示 3D 模型（灰色半透明底模）
   ✓ 提示「✅ STEP 檔案已上傳，3D 模型已加載。」
```

**效果**：用戶立即看到 3D 模型，可以旋轉/縮放

### 第 2 步：上傳 XLSX 檔案
```
1. 點擊「📊 上傳 XLSX」
2. 選擇 XLSX 檔案（例：sfa.xlsx）
3. 等待上傳完成
4. 系統將：
   ✓ 儲存 XLSX 路徑
   ✓ 提示「✅ XLSX 檔案已上傳。現在點擊「比對 & 解析 PMI」進行比對。」
```

**效果**：準備就緒進行解析

### 第 3 步：點擊「比對 & 解析 PMI」
```
1. 點擊「🔄 比對 & 解析 PMI」按鈕
2. 進度條顯示 6 個步驟：
   - Step 1 (17%): [PARSING] 正在解析 Excel...
   - Step 2 (33%): [LOADING] 正在準備 STEP 數據...
   - Step 3 (50%): [LOADING] 正在加載 ASSOCIATION...
   - Step 4 (67%): [LOADING] 正在建構備援數據...
   - Step 5 (83%): [TESSELLATE] 正在解析 Tessellated 標註...
   - Step 6 (100%): [WRITING] 正在寫入 N 個 PMI 項目...
3. 完成後顯示統計：
   - 「✅ PMI 比對完成！• 51 個面 • 12 個 PMI 項目」
```

**時間估計**：3-5 秒（根據檔案大小）

### 第 4 步：查看 PMI 清單
```
右側面板將顯示 PMI 列表，包含：
- Label: 標註名稱（如 "annotation_01"）
- Type Code: 公差類型（dis, dia, dat 等）
- Semantic ID: 語義 ID（來自 XLSX）
- TAO ID: 標註 ID（來自 STEP 或 Smart Proximity Hook）
- Face IDs: 關聯的面 ID

特別提示：
✓ 帶有 "auto_pmi_" 前綴的項目是 Step 4b Smart Proximity Hook 自動關聯的
✓ 顯示距離（如 dist=0.123mm）表示自動關聯成功
```

### 第 5 步：交互式高亮
```
1. 在右側 PMI 清單中點擊任一行
2. 3D 模型中會：
   ✓ 高亮相關的特徵面（顏色：綠/紫/橙 等）
   ✓ 顯示標註的導引線（黑色直線）
   ✓ 相機自動聚焦到該特徵

點擊不同的 PMI 項目可以逐一檢視各個標註。
```

### 第 6 步：導出 CSV
```
1. 點擊「📥 導出 CSV」按鈕
2. 系統將生成包含以下欄位的 CSV：
   - label: PMI 標籤
   - type_code: 公差類型
   - semantic_id: 語義 ID
   - tao_id: 標註 ID
   - face_ids: 面 ID 列表
   - nominal_size: 公稱尺寸
   - it_grade: IT 等級
3. 檔案自動下載為 step_pmi_export.csv
```

## 效能改進

| 操作 | 舊流程 | 新流程 | 改進 |
|------|--------|--------|------|
| 上傳 STEP | 只存儲 | 加載 + 三角化（0.3） | 立即顯示 3D |
| 三角化精度 | 0.1（精細） | 0.3（快速） | 快 3 倍 |
| 上傳 XLSX | 儲存 | 儲存 | 無變化 |
| 完整解析 | 131 面 × 0.1 | 重用 engine | 快 2 倍 |

## 進度跟踪

進度條會實時更新，顯示：
- **百分比**：0-100%
- **消息**：當前執行的步驟
- **計數**：current/total（例：3/6）
- **耗時**：已耗費的秒數
- **狀態**：running / completed / error

## 流程圖

```
┌─────────────────┐
│  上傳 STEP      │  → 加載幾何 → 立即顯示 3D ✓
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  上傳 XLSX      │  → 儲存路徑 ✓
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 點擊「比對 & 解析」
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  6-步驟解析管道                        │
│  1. 解析 XLSX                        │
│  2. 準備 STEP (重用已加載的 engine)  │
│  3. 加載 ASSOCIATION                │
│  4. 建構備援數據                     │
│  5. 解析 Tessellated 標註           │
│  6. 寫入數據庫                       │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  顯示結果                             │
│  • PMI 清單                          │
│  • 3D 高亮 + 導引線                  │
│  • 允許導出 CSV                      │
└─────────────────────────────────────┘
```

## 故障排除

| 問題 | 原因 | 解決方案 |
|------|------|--------|
| 上傳 STEP 後沒有 3D | 幾何加載失敗 | 檢查 STEP 檔案有效性 |
| 3D 顯示但很卡頓 | 面數太多或 deflection 太小 | 使用 deflection=0.5 |
| 解析很慢 | XLSX 檔案太大 | 檢查 XLSX 是否有格式問題 |
| 看不到標註 | XLSX 解析失敗 | 驗證 XLSX 欄位格式 |
| 沒有 auto_pmi | 距離超過 2.0mm | 檢查幾何對齐 |

## 伺服器端優化

```python
# 上傳 STEP 時：
route_upload_step()
  ├─ 儲存檔案
  ├─ 加載 STEP 到記憶體 (StepXcafEngine)
  └─ 快速三角化 (deflection=0.3)

# 點擊比對時：
route_parse_pmi()
  ├─ 重用記憶體中的 engine（快速）
  ├─ 解析 XLSX
  ├─ 執行 Step 4b Smart Proximity Hook
  └─ 寫入數據庫
```

## 記憶體使用

```
單一 Session：
  ├─ STEP 檔案：1-5 MB（磁碟）
  ├─ Engine 物件：10-50 MB（記憶體）
  ├─ 三角化快取：20-100 MB（記憶體）
  └─ PMI 數據：< 1 MB（數據庫）

總計：30-150 MB per session（取決於檔案複雜度）
```

## 配置參數

在 `step_service.py` 中可調整：

```python
# 1. 上傳 STP 後的三角化精度
StepViewer.loadAllGeometry(session_id, 0.3)  # 改為 0.1-1.0

# 2. 幾何查詢的預設精度
deflection = float(request.args.get('deflection', 0.3))  # 預設 0.3

# 3. Smart Proximity Hook 距離閾值
if best_tid and min_dist < 2.0:  # 改為其他值（單位：mm）
```

## 最佳實踐

1. **首次使用**：使用 deflection=0.3 快速預覽
2. **精確檢查**：需要細節時改為 deflection=0.1
3. **大型組件**：考慮使用 deflection=0.5 以上
4. **批量處理**：按順序上傳，避免並行操作

## 已知限制

- 單一伺服器最多支援 ~10 個並行 session（受記憶體限制）
- 超過 500 個面的部件可能需要 > 10 秒
- Smart Proximity Hook 閾值固定 2.0mm（暫不可用戶配置）
