import sys
import os
import json
import re
import OCC.Core.XCAFDoc as XCAFDoc
from OCC.Core.TDF import TDF_LabelSequence, TDF_AttributeIterator, TDF_Tool, TDF_ChildIterator
from OCC.Core.TCollection import TCollection_AsciiString
from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
from OCC.Core.TDocStd import TDocStd_Document
from OCC.Core.XCAFApp import XCAFApp_Application
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Display.SimpleGui import init_display
from OCC.Core.Quantity import Quantity_Color, Quantity_NOC_GRAY80, Quantity_NOC_BLACK, Quantity_NOC_BLUE

def get_label_entry(label):
    entry_as = TCollection_AsciiString()
    TDF_Tool.Entry(label, entry_as)
    return entry_as.ToCString()

class NIST_Style_PMI_Viewer:
    def __init__(self, filepath):
        self.filepath = filepath
        self.pmi_values = {} 
        self.pmi_map = {} 
        
        self._load_data()
        self._run_viewer()
        
    def _load_data(self):
        print(f"📦 解析 STEP AP242 語義與視覺數據...")
        app = XCAFApp_Application.GetApplication()
        self.doc = TDocStd_Document("PMI-PRO-ULTRA")
        app.NewDocument("PMI-PRO-ULTRA", self.doc)
        
        reader = STEPCAFControl_Reader()
        if reader.ReadFile(self.filepath) != IFSelect_RetDone:
            return
        reader.Transfer(self.doc)
        
        # 1. 建立 PMI 資料字典
        def scan_pmi(label):
            it = TDF_AttributeIterator(label)
            while it.More():
                attr = it.Value()
                # 抓取語義公差
                if any(k in attr.DynamicType().Name() for k in ["Dimension", "GeomTolerance"]):
                    try:
                        raw_str = attr.DumpJson()
                        entry = get_label_entry(label)
                        vals = re.findall(r'"Value":\s*([\d.-]+)', raw_str)
                        self.pmi_values[entry] = {
                            "name": re.search(r'"PresentationName":\s*"([^"]+)"', raw_str).group(1) if '"PresentationName"' in raw_str else "N/A",
                            "values": [float(v) for v in vals]
                        }
                    except: pass
                # 抓取空間連結
                if "GraphNode" in attr.DynamicType().Name():
                    pmi_ref = re.search(r'"Label":\s*"(0:1:4:\d+)"', attr.DumpJson())
                    if pmi_ref:
                        self.pmi_map[get_label_entry(label)] = pmi_ref.group(1)
                it.Next()
            for i in range(1, label.NbChildren() + 1):
                # 手動遍歷確保深層搜尋
                pass
            cit = TDF_ChildIterator(label)
            while cit.More():
                scan_pmi(cit.Value())
                cit.Next()

        scan_pmi(self.doc.Main())

    def _run_viewer(self):
        display, start_display, add_menu, add_function_to_menu = init_display()
        display.SetSelectionModeFace()
        
        # 2. 批量渲染零件模型 (update=False 提高效能)
        shape_tool = XCAFDoc.XCAFDoc_DocumentTool.ShapeTool(self.doc.Main())
        dim_tol_tool = XCAFDoc.XCAFDoc_DocumentTool.DimTolTool(self.doc.Main())
        
        roots = TDF_LabelSequence()
        shape_tool.GetFreeShapes(roots)
        for i in range(1, roots.Length() + 1):
            display.DisplayShape(shape_tool.GetShape(roots.Value(i)), color=Quantity_Color(Quantity_NOC_GRAY80), update=False)

        # 3. 🕯️ 集中渲染 3D 公差標註 (Presentation)
        print("🕯️  正在秒速點亮 3D 公差標註線條...")
        pmi_labels = TDF_LabelSequence()
        dim_tol_tool.GetDimensionLabels(pmi_labels)
        dim_tol_tool.GetGeomToleranceLabels(pmi_labels)
        
        for i in range(1, pmi_labels.Length() + 1):
            try:
                pres = dim_tol_tool.GetPresentation(pmi_labels.Value(i))
                if not pres.IsNull():
                    # 💡 update=False 是效能關鍵
                    display.DisplayShape(pres, color=Quantity_Color(Quantity_NOC_BLACK), update=False)
            except: pass

        # 4. 回調與視角優化
        def on_select(selected_shapes, *kwargs):
            for shape in selected_shapes:
                print("\n🎯 選取面語義對位:")
                # 遍歷目前建立的連結庫
                for s_entry, p_entry in self.pmi_map.items():
                    info = self.pmi_values.get(p_entry)
                    if info: print(f"📍 {info['name']}: {info['values']}")
                print("--------------------------------")

        display.register_select_callback(on_select)
        display.FitAll() # 統一繪製畫面
        print("\n🚀 檢視器已啟動！")
        start_display()

if __name__ == "__main__":
    target = r"C:\Tolerance_Project\test_3d_viz\models\bearing_housing.stp"
    NIST_Style_PMI_Viewer(target)
