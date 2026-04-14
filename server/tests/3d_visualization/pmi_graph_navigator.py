import sys
import os
import OCC.Core.XCAFDoc as XCAFDoc
from OCC.Core.TDF import TDF_LabelSequence, TDF_AttributeIterator, TDF_Tool
from OCC.Core.TCollection import TCollection_AsciiString
from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
from OCC.Core.TDocStd import TDocStd_Document
from OCC.Core.XCAFApp import XCAFApp_Application
from OCC.Core.IFSelect import IFSelect_RetDone

def get_label_entry(label):
    """輔助函式：使用 AsciiString 容器獲取標籤字串"""
    entry_as = TCollection_AsciiString()
    TDF_Tool.Entry(label, entry_as)
    return entry_as.ToCString()

def pmi_graph_navigation(filepath):
    print("=====================================================")
    print(f"🕸️  PMI 神經網絡遍歷 (2-Args 版): {os.path.basename(filepath)}")
    print("=====================================================")
    
    app = XCAFApp_Application.GetApplication()
    doc = TDocStd_Document("MDTV-GRAPH-NAV")
    app.NewDocument("MDTV-GRAPH-NAV", doc)
    
    reader = STEPCAFControl_Reader()
    if reader.ReadFile(filepath) != IFSelect_RetDone:
        print("❌ 讀取失敗")
        return
    reader.Transfer(doc)
    
    # 獲取工具
    try:
        dim_tol_tool = XCAFDoc.XCAFDoc_DocumentTool.DimTolTool(doc.Main())
    except:
        dim_tol_tool = XCAFDoc.XCAFDoc_DocumentTool_DimTolTool(doc.Main())
        
    dims = TDF_LabelSequence()
    dim_tol_tool.GetDimensionLabels(dims)
    
    print(f"✅ 發現 {dims.Length()} 個 DimensionLabels。開始掃描神經元...")

    for i in range(1, dims.Length() + 1):
        dim_label = dims.Value(i)
        print(f"\n[D{i}] 座標入點: {get_label_entry(dim_label)}")
        
        it = TDF_AttributeIterator(dim_label)
        found_link = False
        while it.More():
            attr_h = it.Value()
            if "XCAFDoc_GraphNode" in attr_h.DynamicType().Name():
                try:
                    # 遍歷連結
                    nb_fathers = attr_h.NbFathers()
                    nb_children = attr_h.NbChildren()
                    
                    if nb_fathers > 0:
                        for f in range(1, nb_fathers + 1):
                            parent = attr_h.GetFather(f)
                            print(f"   🔗 發現【上游】連結: {get_label_entry(parent.Label())}")
                            found_link = True
                            
                    if nb_children > 0:
                        for c in range(1, nb_children + 1):
                            child = attr_h.GetChild(c)
                            print(f"   🔗 發現【下游】連結: {get_label_entry(child.Label())}")
                            found_link = True
                except:
                    pass
            it.Next()
        
        if not found_link:
            print("   ⚠️  本標籤未連網。")

if __name__ == "__main__":
    target = r"C:\Tolerance_Project\test_3d_viz\models\bearing_housing.stp"
    pmi_graph_navigation(target)
