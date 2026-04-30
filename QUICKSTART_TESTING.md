# STEP PMI 3D Viewer - Quick Start Testing Guide

## TL;DR - Get Started in 3 Steps

### 1️⃣ Start the Server
```bash
cd c:\Tolerance_Project\server
python ai_app.py
```
Expected output:
```
啟動 AI 聊天助手伺服器...
請訪問: http://127.0.0.1:7011
```

### 2️⃣ Open Browser
Navigate to: **http://127.0.0.1:7011**

### 3️⃣ Test Complete Workflow
```
A. Click "📤 上傳 STEP" → Select c:\test0402\cpp_workspace\build\stepcode\Release\bin\part.stp
   Wait for alert: "✅ STEP 檔案已上傳..."
   
B. Click "📊 上傳 XLSX" → Select c:\test0402\0405_test\2_壓縮公差標準代碼表.xlsx
   Wait for alert: "✅ XLSX 檔案已上傳..."
   
C. Click "🔄 比對 & 解析 PMI"
   Watch progress modal:
   • ✅ Step 1: 📊 正在解析 Excel... (1-2 sec)
   • ✅ Step 2: 📂 正在加載 STEP 文件... (1-2 sec)
   • ✅ Step 3: 🔗 正在加載 ASSOCIATION... (0.5 sec)
   • ✅ Step 4: 🌳 正在建構備援數據... (0.5 sec)
   • ✅ Step 5: 🔺 正在解析 Tessellated 標註... (1-2 sec)
   • ✅ Step 6: 💾 正在寫入 N 個 PMI 項目... (1 sec)
   
D. Verify Results:
   ✅ 3D geometry loads (gray semi-transparent model)
   ✅ PMI list displays on right panel
   ✅ Click PMI row → face highlights in 3D (colored)
   ✅ Leader lines appear (black lines from annotations)
```

## Server Console Validation

Look for these messages in server console (indicating Step 4b working):

```
  🔗 [Hook] annotation_XX → TAO#N (dist=X.XXXmm)
ℹ️  智能掛鉤：透過空間距離自動聯繫了 M 條導引線
```

**Interpretation**:
- `[Hook]` entries = auto-linked PMI items via Smart Proximity Hook
- `dist=X.XXXmm` should all be < 2.0 (the threshold)
- `M 條導引線` = total number of auto-linked annotations

## Browser Console Validation

Open Developer Tools (F12) and check Console tab:

```javascript
✅ Session 建立: abc123-def456-...
✅ XLSX 已上傳: 2_壓縮公差標準代碼表.xlsx
🔍 開始比對 & 解析 PMI (Session: abc123-def456-...)
✅ PMI 解析完成: 12 項
```

## Expected Behavior by Feature

### 📤 STEP Upload
- Input: part.stp (valid STEP file)
- Output: Alert "✅ STEP 檔案已上傳。請上傳 XLSX 檔案..."
- Verification: `window._stepSessionId` is set (check console)

### 📊 XLSX Upload
- Input: Tolerance spreadsheet (*.xlsx)
- Output: Alert "✅ XLSX 檔案已上傳。現在點擊「比對 & 解析 PMI」..."
- Verification: File appears in database

### 🔄 Parse & Compare
- Duration: 5-10 seconds (typical)
- Progress: Modal shows real-time 6-step progress
- Result: PMI list + 3D geometry displayed
- Auto-linking: Check console for [Hook] messages

### 3️⃣ 3D Viewer
- Geometry loads: Semi-transparent gray base model
- Controls: 
  - Left drag = rotate
  - Right drag = pan
  - Scroll = zoom
  - Auto-focus on geometry
- Highlighting: Click PMI → face turns colored

### 📋 PMI List
- Shows all parsed items with columns:
  - Label (e.g., "annotation_01")
  - Type (e.g., "dis", "dia")
  - Semantic ID (from XLSX)
  - TAO ID (from linking/hooking)
  - Face IDs (comma-separated)
- Interaction: Click row → highlight in 3D

## Troubleshooting Quick Reference

| Symptom | Cause | Fix |
|---------|-------|-----|
| "❌ Server not running" | Port 7011 already in use | Kill process or use different port |
| "❌ No geometry loads" | STEP file invalid | Verify .stp file is valid CAD model |
| "⏳ Parsing hangs" | Large STEP file / low deflection | Increase deflection parameter (default 0.1) |
| "🔗 No [Hook] messages" | Distances exceed 2.0mm threshold | Check STEP geometry alignment |
| "📋 Empty PMI list" | XLSX parsing failed | Check XLSX file format matches expected schema |
| "🔴 Progress stuck at step 3" | ASSOCIATION loading failed | Check for CSV errors in XLSX |

## Files Used in Testing

```
Input Files:
  c:\test0402\cpp_workspace\build\stepcode\Release\bin\part.stp
  c:\test0402\0405_test\2_壓縮公差標準代碼表.xlsx

Generated Files (on disk):
  server/data/step_uploads/{session_id}/
    ├── part.stp (uploaded STEP file)
    └── 2_壓縮公差標準代碼表.xlsx (uploaded XLSX)

Database Output (MySQL):
  PmiSession: {session_id, stp_path, xlsx_path, status, timestamps}
  PmiItem: {session_id, row_index, label, type_code, semantic_id, tao_id, face_ids, ...}
```

## Performance Benchmarks

```
STP parsing:        2-3 seconds
XLSX parsing:       1 second
Tessellation:       0.5-1 second (per 50 faces)
Distance calc:      0.01-0.05 seconds (per PMI-TAO pair)
Database write:     0.5-1 second
Total parse time:   5-7 seconds (expected)

3D rendering:       60 FPS
Progress updates:   2/sec (500ms SSE interval)
```

## What to Test Next (After Basic Workflow)

1. **Missing XLSX**: Upload only STEP, click parse → fallback layers should activate
2. **Invalid STEP**: Upload bad .stp file → should error gracefully
3. **Large STEP**: Try 500+ face model → measure performance
4. **Auto-linking**: Manually check console [Hook] messages match expected distances
5. **CSV Export**: Export parsed data and verify all columns/rows
6. **Multiple Sessions**: Upload different files in rapid succession → verify session isolation

## Success Criteria

✅ All checks below should pass:

- [ ] Server starts without errors
- [ ] Page loads at http://127.0.0.1:7011
- [ ] STP upload succeeds with session_id
- [ ] XLSX upload stores file
- [ ] Parse starts and shows 6-step progress
- [ ] Progress completes in <10 seconds
- [ ] 3D geometry displays (semi-transparent gray)
- [ ] PMI list shows parsed items
- [ ] Click PMI → geometry highlights
- [ ] Console shows [Hook] auto-linking messages
- [ ] Server console shows completion message with counts
- [ ] No JavaScript errors in browser console
- [ ] No database errors in server logs

**When ALL checks pass**: Implementation is ready for production use ✅

---

## Emergency Debug Mode

If something goes wrong, check these in order:

1. **Browser Console** (F12): `console.log` errors
2. **Server Console**: Printed exceptions and stack traces
3. **Database**: `SELECT * FROM pmi_item WHERE session_id = 'abc123'`
4. **File System**: `ls server/data/step_uploads/{session_id}/`
5. **Network**: Check if SSE connection is open (DevTools → Network → progress endpoint)

For detailed logs, set `debug=True` in ai_app.py:
```python
app.run(host="0.0.0.0", port=7011, debug=True)  # ← adds auto-reload
```
