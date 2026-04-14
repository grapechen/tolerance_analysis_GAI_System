import sys
import os
import OCC.Core.XCAFDoc as XCAFDoc
from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
from OCC.Core.TDocStd import TDocStd_Document
from OCC.Core.XCAFApp import XCAFApp_Application
from OCC.Core.TDF import TDF_LabelSequence, TDF_AttributeIterator
from OCC.Core.IFSelect import IFSelect_RetDone

def extract_pmi_via_json(filepath):
    print("=====================================================")
    print(f"🕵️  PMI JSON 深度滲透模式: {os.path.basename(filepath)}")
    print("=====================================================")
    
    app = XCAFApp_Application.GetApplication()
    doc = TDocStd_Document("MDTV-JSON")
    app.NewDocument("MDTV-JSON", doc)
    
    reader = STEPCAFControl_Reader()
    if reader.ReadFile(filepath) != IFSelect_RetDone:
        print("❌ 讀取失敗")
        return
    reader.Transfer(doc)
    
    # 獲取工具
    try:
        dim_tol_tool = XCAFDoc.XCAFDoc_DocumentTool.DimTolTool(doc.Main())
    except AttributeError:
        dim_tol_tool = XCAFDoc.XCAFDoc_DocumentTool_DimTolTool(doc.Main())
        
    dims = TDF_LabelSequence()
    dim_tol_tool.GetDimensionLabels(dims)
    
    print(f"✅ 發現 {dims.Length()} 個 Dimension。正在解析 JSON 內部結構...")

    for i in range(1, dims.Length() + 1):
        label = dims.Value(i)
        it = TDF_AttributeIterator(label)
        while it.More():
            attr = it.Value()
            if "XCAFDoc_Dimension" in attr.DynamicType().Name():
                print(f"\n[D{i}] 偵測到 XCAFDoc_Dimension:")
                try:
                    # 使用 DumpJson() 獲取內部數據字串
                    # 這是解決 pythonocc 封裝不完全最通用的「暴力法」
                    raw_json = attr.DumpJson()
                    print(f"   ➤ 原始數據 (DumpJson): {raw_json}")
                except Exception as e:
                    print(f"   ➤ JSON 導出失敗: {e}")
            it.Next()

if __name__ == "__main__":
    target = r"C:\Tolerance_Project\test_3d_viz\models\bearing_housing.stp"
    extract_pmi_via_json(target)
