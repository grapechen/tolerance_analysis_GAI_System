# STEP PMI 3D Viewer - Complete Workflow Testing Guide

## Overview
This document describes the complete workflow for testing the web-based STEP/PMI 3D viewer with the Smart Proximity Hook (Step 4b) implementation.

## Architecture Summary

### Frontend Flow (app.js)
1. **uploadStepFile()** - Upload STP file, create session
2. **uploadXlsxFile()** - Upload XLSX to existing session
3. **parsePMI()** - Trigger parsing on both files
4. **StepViewer.loadAllGeometry()** - Display 3D model
5. **PmiPanel.render()** - Display PMI list
6. **CSV Export** - Export parsed data

### Backend Flow (step_service.py - route_parse_pmi)
1. **Step 1**: Parse XLSX (parse_sfa_excel)
2. **Step 2**: Load STEP geometry (StepXcafEngine.load)
3. **Step 3**: Load CSV ASSOCIATION (load_sfa_association)
4. **Step 3b**: Three-layer fallback:
   - Layer 1: parse_sfa_visual_sheets (visual forms from XLSX)
   - Layer 2: Create annotation_XX from semantic_to_tao mappings
   - Layer 3: build_geometry_feature_tree (geometry features as last resort)
5. **Step 4**: Parse tessellated annotations (parse_tessellated_annotations)
6. **Step 4a**: STEP direct linking (override XLSX mappings with STEP associations)
7. **Step 4b**: Smart Proximity Hook (NEW - distance-based intelligent matching)
   - Finds unmapped TAO IDs using BRepExtrema_DistShapeShape
   - Calculates distance between face compounds and annotation shapes
   - Auto-links faces to annotations when semantic_to_tao mappings don't exist
   - Uses 2.0mm threshold for match acceptance
   - Creates virtual semantic IDs (auto_pmi_N) for completely unmapped items
8. **Step 4c**: Fallback for unmapped annotations (create unmapped_N entries)
9. **Step 6**: Write to database

## Testing Procedure

### Phase 1: Server Startup
```bash
cd c:\Tolerance_Project\server
python ai_app.py
# Expected: "啟動 AI 聊天助手伺服器... 請訪問: http://127.0.0.1:7011"
```

### Phase 2: Browser Access
1. Navigate to http://127.0.0.1:7011
2. Verify page loads without errors
3. Check for STEP Viewer section with three buttons:
   - "📤 上傳 STEP" (Upload STEP)
   - "📊 上傳 XLSX" (Upload XLSX)
   - "🔄 比對 & 解析 PMI" (Parse & Compare PMI)

### Phase 3: File Upload Test
```
File selections:
  STP: c:/test0402/cpp_workspace/build/stepcode/Release/bin/part.stp
  XLSX: c:/test0402/0405_test/2_壓縮公差標準代碼表.xlsx
```

**Step 3a: Upload STEP**
1. Click "📤 上傳 STEP" button
2. Select part.stp
3. Verify alert: "✅ STEP 檔案已上傳。\n請上傳 XLSX 檔案，然後點擊「比對 & 解析 PMI」。"
4. Check browser console: "✅ Session 建立: [session_id]"

**Step 3b: Upload XLSX**
1. Click "📊 上傳 XLSX" button
2. Select 2_壓縮公差標準代碼表.xlsx
3. Verify alert: "✅ XLSX 檔案已上傳。\n現在點擊「比對 & 解析 PMI」進行比對。"

**Step 3c: Parse & Compare**
1. Click "🔄 比對 & 解析 PMI" button
2. Verify progress modal displays showing 6 steps:
   - Step 1: 🔄 正在解析 XLSX 檔案...
   - Step 2: 📂 正在加載 STEP 文件...
   - Step 3: 🔗 正在加載 ASSOCIATION...
   - Step 4: 🌳 正在建構備援數據...
   - Step 5: 🔺 正在解析 Tessellated 標註...
   - Step 6: 💾 正在寫入 N 個 PMI 項目...
3. Wait for completion

### Phase 4: 3D Visualization Test
After parsing completes:
1. Verify 3D geometry loads in Three.js viewer
2. Check viewport shows:
   - Base geometry (semi-transparent gray)
   - Highlighted faces (colored by type: green, purple, orange, etc.)
   - Annotation leader lines (black lines)
3. Test camera controls:
   - Rotate: Left mouse drag
   - Pan: Right mouse drag
   - Zoom: Scroll wheel
4. Verify focus on geometry works

### Phase 5: PMI List Rendering Test
1. Verify PMI panel displays list of parsed items
2. Check each item shows:
   - Label (e.g., "annotation_01")
   - Type code (e.g., "dis", "dia", "dat")
   - Semantic ID (if exists)
   - TAO ID (from Step 4b mapping)
3. Test row highlighting:
   - Click on PMI item
   - Verify corresponding face/annotation highlights in 3D viewer
   - Verify leader lines appear for annotations

### Phase 6: Step 4b Smart Proximity Hook Validation
Monitor server console for auto-linking messages:
```
  🔗 [Hook] Label_Name → TAO#ID (dist=X.XXXmm)
ℹ️  智能掛鉤：透過空間距離自動聯繫了 N 條導引線
```

**Verify Hook Behavior:**
1. Count auto-linked annotations in console output
2. Verify linked items appear in PMI list with:
   - semantic_id = "auto_pmi_N" (for unmapped items)
   - tao_id = N (the actual TAO ID matched by distance)
3. Check distances reported (should all be < 2.0mm)

### Phase 7: CSV Export Test
1. Look for "📥 導出 CSV" button in PMI panel
2. Click to export parsed data
3. Verify CSV contains:
   - label
   - type_code
   - semantic_id
   - tao_id
   - face_ids
   - nominal_size
   - it_grade
4. Verify all auto-linked items included (auto_pmi_N entries)

### Phase 8: Error Handling Tests

**Test Case 1: Missing XLSX**
- Upload STEP only
- Click "🔄 比對 & 解析 PMI"
- Verify fallback layers activate (Layer 1 → Layer 2 → Layer 3)
- Check console for fallback messages

**Test Case 2: Missing STEP**
- Upload XLSX only
- Verify appropriate error message
- Check that parse fails gracefully

**Test Case 3: Invalid Files**
- Upload non-STEP file as STP
- Verify error message: "❌ STEP 檔案無效 / STEP 解析失敗"
- Upload non-XLSX file as XLSX
- Verify error message: "❌ XLSX 上傳失敗 / 解析失敗"

## Implementation Checklist

- [x] Step 4b Smart Proximity Hook algorithm implemented
- [x] BRepExtrema_DistShapeShape distance calculation
- [x] 2.0mm threshold for match acceptance
- [x] Virtual semantic ID creation (auto_pmi_N)
- [x] TAO deduplication (prevent double-linking)
- [x] Three-layer fallback system
- [x] Progress tracking with SSE
- [x] Frontend workflow (upload → upload → parse)
- [x] 3D viewer integration
- [x] PMI list rendering
- [ ] CSV export implementation
- [ ] Complete end-to-end testing with actual files

## Known Limitations

1. **Distance Threshold**: Fixed at 2.0mm - may need adjustment based on CAD tolerance
2. **Structure Density Check**: Uses tri_count > 10 and edge_count > 40 - may need tuning
3. **Type-specific Matching**: dis/dia items match any structure; other types need complex structure

## Expected Output

### Server Console Output (Example)
```
⏳ 載入 session [UUID] 的所有幾何...
⏳ 載入 session [UUID] 的 XLSX...
📊 解析 XLSX: 10 行
📂 載入 STEP (part.stp): 45 個面
🔗 載入 ASSOCIATION: 3 個語義映射
🌳 建構備援: 5 個 PMI 項目
🔺 解析 Tessellated 標註: 8 個 TAO
  🔗 [Hook] annotation_01 → TAO#2 (dist=0.123mm)
  🔗 [Hook] annotation_03 → TAO#5 (dist=1.876mm)
ℹ️  智能掛鉤：透過空間距離自動聯繫了 2 條導引線
💾 寫入 5 個 PMI 項目
✅ PMI 解析完成 (45 個面，5 個 PMI 項目)
```

### Browser Console Output (Example)
```
✅ Session 建立: abc123-def456
✅ XLSX 已上傳: 2_壓縮公差標準代碼表.xlsx
🔍 開始比對 & 解析 PMI (Session: abc123-def456)
✅ PMI 解析完成: 5 項
```

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| "❌ Session 不存在或已過期" | Session ID lost | Reload page, upload STEP again |
| "❌ 幾何三角化失敗" | Face data invalid | Check STEP file validity |
| "⚠️ 場景為空，無法聚焦" | No geometry loaded | Verify STEP file has faces |
| No PMI items in list | All three fallback layers failed | Check XLSX structure |
| No auto-linking (Step 4b) | Distances exceed 2.0mm | Reduce threshold or check geometry |
| Export CSV has no data | PMI list is empty | Re-run parse after uploading both files |

## Future Enhancements

1. **Dynamic Threshold**: Allow user to adjust proximity distance
2. **Structure Analysis**: Improve density detection algorithm
3. **Annotation Details**: Show leader line coordinates and annotation shape bounds
4. **Batch Processing**: Support multiple STEP/XLSX pairs in queue
5. **Session Management**: Implement session timeout and cleanup
6. **Caching**: Cache tessellated geometry to speed up re-renders
