# AI 智能助手 STEP 3D 檢視器架構分析

**文檔日期**: 2026-04-15  
**系統**: ISO 286 AI 智能助手  
**框架**: Flask (Python) + Three.js (前端)  
**CAD 引擎**: PythonOCC 7.9.0

---

## 📐 整體系統架構

```
┌─────────────────────────────────────────────────────────────┐
│                    前端層 (Browser)                         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ HTML/CSS (templates/index.html)                        │ │
│  │ ├─ Three.js (3D 渲染引擎)                              │ │
│  │ ├─ OrbitControls (相機控制)                            │ │
│  │ └─ WebGL (GPU 加速)                                   │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
│  JavaScript 模組層                                          │
│  ├─ step_viewer.js      (核心 3D 引擎)                    │
│  ├─ pmi_panel.js        (PMI 列表與交互)                  │
│  ├─ app.js              (主應用邏輯)                      │
│  └─ chat.js             (聊天集成)                        │
│                                                              │
│  JSON HTTP API 調用 (FETCH)                               │
└─────────────────────────────────────────────────────────────┘
                         ↓↑
          /api/step/* REST 端點 (8 個路由)
                         ↓↑
┌─────────────────────────────────────────────────────────────┐
│                Flask 後端層 (ai_app.py)                    │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ 路由層 (step_service.py 中的 8 個路由函數)            │ │
│  │ ├─ route_upload_step()      POST /api/step/upload     │ │
│  │ ├─ route_parse_pmi()        POST /api/step/parse_pmi  │ │
│  │ ├─ route_get_geometry()     GET  /api/step/geometry   │ │
│  │ ├─ route_get_pmi_list()     GET  /api/step/pmi_list   │ │
│  │ ├─ route_highlight_pmi()    POST /api/step/highlight  │ │
│  │ ├─ route_run_asm_worker()   POST /api/step/asm_contact│ │
│  │ ├─ route_get_6dof()         POST /api/step/6dof       │ │
│  │ └─ route_export_step_csv()  POST /api/step/export_csv │ │
│  └────────────────────────────────────────────────────────┘ │
│                           ↓                                  │
│  業務邏輯層 (step_core.py)                                  │
│  ├─ StepXcafEngine              (STEP 加載與拓撲探索)      │
│  ├─ tessellate_face_by_step_ids (三角網格生成)             │
│  ├─ parse_sfa_excel             (Excel PMI 解析)           │
│  ├─ load_sfa_association        (CSV 關聯解析)             │
│  ├─ parse_tessellated_annotations (Tessellated 標註解析)   │
│  └─ build_geometry_feature_tree (幾何特徵樹構建)           │
│                           ↓                                  │
│  OCC 幾何核心 (PythonOCC 7.9.0)                            │
│  ├─ STEPCAFControl_Reader        (STEP 文件加載)           │
│  ├─ TopExp_Explorer              (拓撲遍歷)                │
│  ├─ BRepMesh_IncrementalMesh     (三角化)                  │
│  └─ BRepAdaptor_Surface          (面幾何適配器)           │
│                           ↓                                  │
│  數據存儲                                                    │
│  ├─ MySQL (PmiSession, PmiItem, AssemblyContact 表)       │
│  ├─ 記憶體快取 (_step_sessions 字典)                      │
│  └─ 磁盤文件 (server/data/step_uploads/)                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                         ↓↑
┌─────────────────────────────────────────────────────────────┐
│                 輔助子進程 (asm_worker.py)                 │
│  ├─ 組合件接觸分析 (NIST SFA CSV)                         │
│  ├─ 實體映射與分組                                        │
│  └─ 接觸面檢測 (距離與邊界框)                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 8 大工作流程

### 1. 上傳階段 (Upload)

**流程**:
```
用戶上傳 STEP + XLSX
        ↓ [POST /api/step/upload]
Flask 保存到 server/data/step_uploads/{session_id}/
        ↓
創建 PmiSession 表記錄
        ↓
返回 session_id 到前端
```

**代碼**: `step_service.py:route_upload_step()` (第 67-125 行)

**輸出示例**:
```json
{
  "ok": true,
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "stp_filename": "model.stp"
}
```

---

### 2. PMI 解析階段 (Parse PMI)

**流程**:
```
前端: [POST /api/step/parse_pmi]
        ↓
後端執行:
  1. 加載 STEP 到 OCC
     └─ StepXcafEngine.load()
  
  2. 解析 Excel (SFA)
     └─ parse_sfa_excel() → pmi_rows
  
  3. 加載 CSV ASSOCIATION 鏈
     └─ load_sfa_association() → semantic_id → tao_id 映射
  
  4. 解析 Tessellated 標註
     └─ parse_tessellated_annotations() → leader line 數據
  
  5. 寫入數據庫
     └─ PmiItem 表 (每行 1 個)
  
  6. 快取到記憶體
     └─ _step_sessions[session_id] = {...}
        ↓
返回 PMI 列表到前端
```

**代碼**: `step_service.py:route_parse_pmi()` (第 126-223 行)

**數據流**:
```
Excel (SFA) 
    ├─ "label": "⌀25.00 +0.00"
    ├─ "type_code": "dia"
    └─ "face_ids": [15, 20, 33]
CSV ASSOCIATION
    └─ "semantic_id" → "tao_id" → tessellated curve data
    
合併 → PmiItem 表記錄
```

---

### 3. 幾何加載階段 (Load Geometry)

**流程**:
```
前端: [GET /api/step/geometry?session_id=...&face_ids=*]
        ↓
後端: 
  1. 從快取取得 StepXcafEngine
  2. 三角化 (BRepMesh_IncrementalMesh)
     deflection = 0.3 (概覽) 或 0.1 (標準)
  3. 轉換為 JSON
     ├─ vertices: [[x,y,z], ...]
     ├─ normals:  [[nx,ny,nz], ...]
     └─ faces:    [[i,j,k], ...]
        ↓
前端: Three.js 創建 Mesh 並添加到 Scene
```

**代碼**: `step_core.py:tessellate_face_by_step_ids()`

---

### 4. 3D 渲染階段 (Three.js)

**流程**:
```
JavaScript:
  1. 接收三角網格 JSON
  2. 創建 THREE.BufferGeometry
  3. 創建 THREE.MeshPhongMaterial
  4. 創建 THREE.Mesh
  5. 添加到 Scene
  6. 每幀調用 renderer.render()
        ↓
Canvas 顯示 3D 模型
```

**代碼**: `step_viewer.js:init()`, `loadAllGeometry()`

**顏色編碼**:
- 默認: 淺藍 (0xccddff)
- Datum: 綠色 (0x00DA26)
- Interactive: 紫色 (0xA121F0)
- Individual: 橘色 (0xFFA500)
- Hover: 黃色 (0xFFFF00)

---

### 5. PMI 高亮階段 (Highlight)

**流程**:
```
前端:
  用戶勾選 PMI 條目 (checkbox)
        ↓
  [POST /api/step/highlight]
        ↓
後端:
  1. 查詢 PmiItem
  2. 取得 face_ids
  3. 返回高亮顏色數據
        ↓
前端:
  1. 從 geometryMeshes[face_id] 取出 mesh
  2. 改變顏色材質
     mesh.material.color.setHex(colorCode)
  3. 渲染 Leader Lines (黑色邊界)
     ├─ 從 tao_id 取得 tessellated curve
     ├─ 轉換為 THREE.LineSegments
     └─ 添加到 Scene
        ↓
實時高亮顯示 + 同步多選
```

**代碼**:
- 後端: `step_service.py:route_highlight_pmi()` (第 298-375 行)
- 前端: `step_viewer.js:highlightPmiRow()`
- 列表同步: `pmi_panel.js:onRowCheckChanged()`

---

### 6. 組合件接觸分析 (Assembly Contact)

**流程**:
```
前端: [POST /api/step/asm_contact]
        ↓
後端:
  1. 啟動子進程: asm_worker.py
  2. asm_worker 執行:
     ├─ 加載 STEP
     ├─ 遍歷所有 Solid
     ├─ 計算邊界框 (BBox)
     ├─ 檢測邊界框重疊
     ├─ 計算實際距離 (距離 < 0.1mm)
     ├─ 識別表面類型
     │  ├─ Planar (平面)
     │  ├─ Cylindrical (圓柱面)
     │  └─ Other (其他)
     └─ 輸出 JSON
  3. 後端解析結果 → AssemblyContact 表
        ↓
前端: 使用 ApexCharts 繪製接觸圖表
```

**代碼**: 
- 後端: `step_service.py:route_run_asm_worker()` (第 376-469 行)
- 子進程: `asm_worker.py`, `assembly_contact_detector.py`

---

### 7. 6DOF 提取 (Transform Extraction)

**流程**:
```
前端: [POST /api/step/6dof]
        ↓
後端:
  1. 加載 Step6DofExtractor
  2. 解析 STEP 中的 AXIS2_PLACEMENT_3D
     ├─ 提取位置 (origin point)
     ├─ 提取旋轉軸 (Z axis)
     └─ 提取參考方向 (X axis)
  3. 構建變換矩陣 (gp_Trsf)
     ├─ 3x3 旋轉矩陣
     └─ 3D 平移向量
        ↓
返回四元數與矩陣表示
```

**代碼**: `step_service.py:route_get_6dof()` (第 471-513 行)

---

### 8. 數據導出 (Export)

**流程**:
```
前端: [POST /api/step/export_csv]
        ↓
後端:
  1. 查詢 PmiItem 表
  2. 查詢 AssemblyContact 表
  3. 合併數據
  4. 生成 CSV 文件
     ├─ PMI 條目 (label, type_code, nominal_size, it_grade)
     └─ 接觸信息 (solid_1, solid_2, distance, surface_type)
        ↓
前端: 下載 CSV 文件到本地
```

**代碼**: `step_service.py:route_export_step_csv()` (第 515-603 行)

---

## 📊 HTTP API 端點總覽

| 端點 | 方法 | 功能 | 輸入 | 輸出 |
|------|------|------|------|------|
| `/api/step/upload` | POST | 上傳文件 | FormData (stp, xlsx) | session_id |
| `/api/step/parse_pmi` | POST | 解析 PMI | session_id | pmi_rows, n_faces |
| `/api/step/geometry` | GET | 獲取三角網格 | session_id, face_ids | vertices, normals, faces |
| `/api/step/pmi_list` | GET | 獲取 PMI 列表 | session_id | pmi_items[] |
| `/api/step/highlight` | POST | 高亮 PMI | row_index | color_hex |
| `/api/step/asm_contact` | POST | 接觸分析 | session_id | contacts[] |
| `/api/step/6dof` | POST | 提取轉換 | entity_id | transform_matrix |
| `/api/step/export_csv` | POST | 導出數據 | session_id | CSV 文件 |

---

## 🗂️ 核心文件結構

```
server/
├── ai_app.py                    # Flask 主應用，路由註冊
├── step_service.py              # 8 個 STEP 路由端點
├── step_core.py                 # 核心幾何處理 (1500+ 行)
├── asm_worker.py                # 組合件分析子進程
├── assembly_contact_detector.py # 表面類型識別
├── path_extractor.py            # 6DOF 轉換
├── tables.py                    # SQLAlchemy ORM 模型
│
├── static/js/
│   ├── step_viewer.js           # Three.js 核心引擎
│   ├── pmi_panel.js             # PMI 列表交互
│   ├── app.js                   # 主應用邏輯
│   ├── chat.js                  # 聊天集成
│   └── bom_render.js            # BOM 樹渲染
│
├── templates/
│   └── index.html               # 主 HTML (Canvas 容器)
│
├── static/css/
│   └── style.css                # 樣式表
│
└── data/step_uploads/
    └── {session_id}/
        ├── model.stp            # 上傳的 STEP 文件
        └── sfa.xlsx             # 上傳的 SFA 檔案
```

---

## 💾 數據庫設計

### PmiSession (會話表)
- `session_id`: UUID
- `stp_path`, `xlsx_path`: 文件路徑
- `status`: 'pending' → 'parsing' → 'ready'
- `n_faces`, `n_pmi_rows`: 統計信息

### PmiItem (PMI 條目表)
- `row_index`: PMI 序號
- `label`: "⌀25.00 +0.00"
- `type_code`: "dia", "pos", "dis" 等
- `face_ids`: JSON 數組 [15, 20, 33]
- `nominal_size`, `it_grade`: **新增**
- `is_datum`, `is_interactive`: 分類標記

### AssemblyContact (接觸表)
- `solid_1_name`, `solid_2_name`: 組件名
- `contact_face_ids`: JSON 數組
- `distance`: 實際間距
- `surface_type`: "Planar" / "Cylindrical"

---

## ⚡ 性能指標

| 操作 | 時間 | 備註 |
|------|------|------|
| STEP 加載 | 1-5s | 文件大小相關 |
| 三角化 (deflection=0.3) | 2-10s | 快速概覽 |
| 三角化 (deflection=0.1) | 5-30s | 標準精度 |
| PMI 解析 | 1-3s | Excel + CSV |
| 接觸分析 | 10-60s | 組件數量相關 |
| 3D 渲染 | <100ms | 每幀 (60fps) |

---

## 🔗 集成點

### 聊天系統 (chat.js)
```javascript
// 用戶要求「打開 STEP 檢視器」
openStepViewerPanel();
StepViewer.init('step-viewer-container');
StepViewer.loadAllGeometry(sessionId);
```

### BOM 樹 (app.js)
```javascript
// 點擊零件 → 高亮 3D 幾何
StepViewer.highlightPmiRow(rowIndex);
```

### 公差分析
```javascript
// 選中公差 → 高亮相關面
// 例: 25mm H7 → 高亮圓柱面
```

---

## 🚨 已知限制

1. **Tkinter vs Web**
   - 新模組 `step_pmi_3d_viewer.py` 為桌面應用
   - 與 Web 應用分離
   - 未來統一為純 Web

2. **大文件性能**
   - 100MB+ STEP 加載較慢
   - 需要 LOD (Level of Detail) 優化

3. **PMI 映射精度**
   - CSV ASSOCIATION 鏈可能不完整
   - 需確保 Excel 與 STEP 版本一致

---

## 🔮 未來優化

### 短期
- WebSocket 實時更新
- 進度條反饋
- 快捷鍵支持

### 中期
- BVH 加速結構
- LOD 漸進渲染
- 陰影與紋理

### 長期
- Rust + WASM
- 多格式支持 (IGES, STL)
- AR/VR 集成

---

**版本**: 1.0 | **日期**: 2026-04-15
