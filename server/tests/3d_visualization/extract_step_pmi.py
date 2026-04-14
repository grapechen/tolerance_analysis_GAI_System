# -*- coding: utf-8 -*-
"""
extract_step_pmi.py — STEP AP242 Semantic PMI 提取工具
=======================================================
修正版 v3：完全不直接建立 TDocStd_Document（避免 segfault），
           改由 STEPCAFControl_Reader 內部管理 Document，
           再透過 reader.XCAFDoc_ShapeTool() / DimTolTool() 取出工具。

執行：
    conda activate tol_3d
    python extract_step_pmi.py "C:\path\to\file.stp"
"""

import sys, os

def p(msg):
    print(msg, flush=True)

# ── 公差類型對照表 ──────────────────────────────────────────────────────────────
GEOM_TOL_NAMES = {
    0: "未知",    1: "平直度",  2: "平整度",  3: "真圓度",
    4: "圓柱度",  5: "線輪廓度", 6: "面輪廓度", 7: "傾斜度",
    8: "垂直度",  9: "平行度",  10: "位置度", 11: "同心度",
    12: "對稱度", 13: "圓偏轉度", 14: "全偏轉度",
}
DIM_NAMES = {
    0: "未知", 1: "直徑", 2: "球徑", 3: "半徑",
    4: "球半徑", 5: "線性距離", 6: "角度", 7: "曲線長度",
}


def label_entry(label):
    try:
        from OCC.Core.TDF import TDF_Tool
        from OCC.Core.TCollection import TCollection_AsciiString
        s = TCollection_AsciiString()
        TDF_Tool.Entry_(label, s)
        return s.ToCString()
    except Exception:
        return "?"


def shape_name(shape_tool, label):
    try:
        from OCC.Core.TDataStd import TDataStd_Name
        attr = TDataStd_Name()
        if label.FindAttribute(TDataStd_Name.GetID_(), attr):
            return attr.Get().ToExtString()
    except Exception:
        pass
    return f"shape@{label_entry(label)}"


# ══════════════════════════════════════════════════════════════════════════════
# 核心：使用 Reader 的 WS（WorkSession）取得 XDE Document
#
# 原理：
#   STEPCAFControl_Reader 內部持有一個 XSControl_WorkSession，
#   WorkSession 持有 Transfer 後的 XDE Document（Handle<TDocStd_Document>）。
#   pythonocc 7.7 提供 reader.GetXCAFDoc_DocumentTool() 或
#   reader.ChangeReader().WS().FindInContext("XDE") 等路徑。
#   最穩定的方式是透過 reader.XCAFDocumentTool() 直接存取。
# ══════════════════════════════════════════════════════════════════════════════
def load_and_get_tools(step_path: str):
    """
    讀取 STEP 並回傳 (shape_tool, dimtol_tool)。
    完全不建立 TDocStd_Document，由 Reader 內部管理。
    """
    from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.XCAFDoc import XCAFDoc_DocumentTool

    # ── plugin 初始化（解決 XCAFApp segfault）─────────────────────────────────
    p("▶ [1/4] 載入 XCAF plugin drivers...")
    for mod in ["OCC.Core.BinXCAFDrivers", "OCC.Core.XmlXCAFDrivers", "OCC.Core.BinDrivers"]:
        try:
            __import__(mod)
            p(f"   ✅ {mod}")
        except Exception as e:
            p(f"   ⚠  {mod}: {e}")

    # ── 建立 Reader ───────────────────────────────────────────────────────────
    p("\n▶ [2/4] 初始化 STEPCAFControl_Reader...")
    reader = STEPCAFControl_Reader()
    reader.SetColorMode(True)
    reader.SetNameMode(True)
    reader.SetLayerMode(True)
    reader.SetDimTolMode(True)   # ★ AP242 語義公差
    p("   ✅ Reader 就緒")

    # ── 讀取檔案 ─────────────────────────────────────────────────────────────
    p(f"\n▶ [3/4] ReadFile: {step_path}")
    if not os.path.isfile(step_path):
        p(f"   ❌ 找不到檔案")
        return None, None, None

    status = reader.ReadFile(step_path)
    if status != IFSelect_RetDone:
        p(f"   ❌ ReadFile 失敗，狀態碼：{status}")
        return None, None, None
    p("   ✅ ReadFile 完成")

    # ── Transfer → XDE Document（Reader 內部管理）────────────────────────────
    p("\n▶ [4/4] Transfer & 取得 Tools...")

    # 方式 A：reader.Transfer(doc) 需要 doc，改用 reader.TransferRoots()
    #         TransferRoots 不需傳入 Document，Reader 自己更新內部 WS
    try:
        ok = reader.TransferRoots()
        p(f"   TransferRoots: {ok}")
    except Exception as e:
        p(f"   ⚠  TransferRoots 失敗：{e}，嘗試 Transfer(doc) 路徑...")

    # 取得 WS → Document → Main Label
    # pythonocc ≥7.6 可用 reader.ChangeReader().WS()
    doc = None
    try:
        ws  = reader.ChangeReader().WS()          # XSControl_WorkSession
        doc = ws.FindInContext("XDE")             # 嘗試取得 XDE doc
        p(f"   WS.FindInContext: {type(doc)}")
    except Exception:
        pass

    # 備用：透過 XCAFApp 取得已打開的 Document（不建立新的）
    if doc is None:
        try:
            from OCC.Core.XCAFApp import XCAFApp_Application
            app = XCAFApp_Application.GetApplication()
            # GetDocument(index=1) 取得第一個已存在的 Document
            app.GetDocument(1, doc)
            p(f"   XCAFApp.GetDocument(1): {type(doc)}")
        except Exception as e:
            p(f"   ⚠  XCAFApp.GetDocument 失敗：{e}")

    # 若仍取不到 Document，嘗試用 XSControl_WorkSession 的 Model
    if doc is None:
        p("   ❌ 無法取得 XDE Document，改走 STEP Model 直讀模式...")
        return reader, None, None

    # 從 Document 取得 ShapeTool / DimTolTool
    try:
        main        = doc.Main()
        shape_tool  = XCAFDoc_DocumentTool.ShapeTool(main)
        dimtol_tool = XCAFDoc_DocumentTool.DimTolTool(main)
        p("   ✅ ShapeTool / DimTolTool 取得成功")
        return reader, shape_tool, dimtol_tool
    except Exception as e:
        p(f"   ❌ Tool 取得失敗：{e}")
        return reader, None, None


# ── 提取幾何公差 ───────────────────────────────────────────────────────────────
def extract_geom_tolerances(shape_tool, dimtol_tool):
    from OCC.Core.TDF import TDF_LabelSequence
    p("\n══ 幾何公差 (Geometric Tolerances) ══")
    labels = TDF_LabelSequence()
    dimtol_tool.GetToleranceLabels(labels)
    p(f"   找到 {labels.Length()} 個")
    count = 0
    for i in range(1, labels.Length() + 1):
        lbl = labels.Value(i)
        try:
            obj   = dimtol_tool.GetDimTolObject(lbl)
            ttype = GEOM_TOL_NAMES.get(int(obj.GetType()), f"#{int(obj.GetType())}")
            try:    val = f"{obj.GetValue():.6f} mm"
            except: val = "?"
            refs = TDF_LabelSequence()
            try: dimtol_tool.GetRefShapeLabel(lbl, refs)
            except: pass
            shapes = [shape_name(shape_tool, refs.Value(j))
                      for j in range(1, refs.Length() + 1)] or ["<無>"]
            p(f"\n   [{i:03d}] {ttype}  {val}  →  {'、'.join(shapes)}")
            count += 1
        except Exception as e:
            p(f"   [{i:03d}] 解析失敗：{e}")
    if count == 0:
        p("   ⚠ 無 Semantic 幾何公差")
    return count


# ── 提取尺寸公差 ───────────────────────────────────────────────────────────────
def extract_dimensions(shape_tool, dimtol_tool):
    from OCC.Core.TDF import TDF_LabelSequence
    p("\n══ 尺寸公差 (Dimensions) ══")
    labels = TDF_LabelSequence()
    dimtol_tool.GetDimensionLabels(labels)
    p(f"   找到 {labels.Length()} 個")
    count = 0
    for i in range(1, labels.Length() + 1):
        lbl = labels.Value(i)
        try:
            obj   = dimtol_tool.GetDimTolObject(lbl)
            dtype = DIM_NAMES.get(int(obj.GetType()), f"#{int(obj.GetType())}")
            try:    nominal = f"{obj.GetValue():.6f}"
            except: nominal = "?"
            try:    tol_str = f"+{obj.GetUpperTolerance():.4f} / -{abs(obj.GetLowerTolerance()):.4f}"
            except: tol_str = "<未定義>"
            refs = TDF_LabelSequence()
            try: dimtol_tool.GetRefShapeLabel(lbl, refs)
            except: pass
            shapes = [shape_name(shape_tool, refs.Value(j))
                      for j in range(1, refs.Length() + 1)] or ["<無>"]
            p(f"\n   [{i:03d}] {dtype}  標稱={nominal}  偏差={tol_str}  →  {'、'.join(shapes)}")
            count += 1
        except Exception as e:
            p(f"   [{i:03d}] 解析失敗：{e}")
    if count == 0:
        p("   ⚠ 無 Semantic 尺寸公差")
    return count


# ── 備用：STEP Model 直讀（不依賴 XDE）────────────────────────────────────────
def fallback_step_model_scan(reader):
    """
    當 XDE Document 無法取得時，直接從 STEP 底層 Model 掃描實體。
    尋找 GEOMETRIC_TOLERANCE / DIMENSIONAL_CHARACTERISTIC_REPRESENTAION 實體。
    """
    p("\n══ 備用：STEP Model 實體掃描 ══")
    try:
        ws    = reader.ChangeReader().WS()
        model = ws.Model()
        p(f"   STEP Model 實體總數：{model.NbEntities()}")

        tol_keywords = [
            "GEOMETRIC_TOLERANCE",
            "ANGULARITY_TOLERANCE", "FLATNESS_TOLERANCE",
            "CYLINDRICITY_TOLERANCE", "POSITION_TOLERANCE",
            "PERPENDICULARITY_TOLERANCE", "PARALLELISM_TOLERANCE",
            "CIRCULAR_RUNOUT_TOLERANCE", "TOTAL_RUNOUT_TOLERANCE",
            "DIMENSIONAL_CHARACTERISTIC",
        ]

        found = 0
        for i in range(1, model.NbEntities() + 1):
            try:
                ent  = model.Value(i)
                name = type(ent).__name__.upper()
                if any(k in name for k in tol_keywords):
                    p(f"   [#{i}] {type(ent).__name__}")
                    found += 1
            except Exception:
                continue

        if found == 0:
            p("   ⚠ STEP Model 中無公差相關實體")
            p("\n── 結論 ──────────────────────────────────────────────")
            p("   此 STEP 檔不含 AP242 Semantic PMI。")
            p("   建議：確認 CAD 匯出時已啟用「3D PMI / GD&T」選項，")
            p("         且格式選擇 STEP AP242（非 AP203 / AP214）。")
        else:
            p(f"\n   發現 {found} 個公差相關 STEP 實體（XDE 模式才能取出完整數值）")
    except Exception as e:
        p(f"   ❌ Model 掃描失敗：{e}")


# ══════════════════════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    step_file = sys.argv[1] if len(sys.argv) > 1 else "bearing_housing.stp"

    p("╔══════════════════════════════════════════════════════╗")
    p("║  STEP AP242 Semantic PMI 提取工具  (pythonocc-core)  ║")
    p("╚══════════════════════════════════════════════════════╝")
    p(f"目標檔案：{os.path.abspath(step_file)}\n")

    reader, shape_tool, dimtol_tool = load_and_get_tools(step_file)

    if shape_tool is not None and dimtol_tool is not None:
        g = extract_geom_tolerances(shape_tool, dimtol_tool)
        d = extract_dimensions(shape_tool, dimtol_tool)
        if g + d == 0:
            p("\n結論：模型內無 AP242 Semantic PMI 資料。")
        else:
            p(f"\n✅ 提取完成：幾何公差 {g} 個，尺寸公差 {d} 個。")
    elif reader is not None:
        fallback_step_model_scan(reader)
    else:
        p("\n❌ 讀取失敗，請確認檔案路徑正確。")
