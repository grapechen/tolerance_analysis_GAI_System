import sys
import os
import OCC.Core.XCAFDoc as XCAFDoc
from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
from OCC.Core.TDocStd import TDocStd_Document
from OCC.Core.XCAFApp import XCAFApp_Application
from OCC.Core.TDF import TDF_LabelSequence, TDF_AttributeIterator
from OCC.Core.IFSelect import IFSelect_RetDone

def extract_pmi_robust(filepath):
    print("=====================================================")
    print(f"🛡️  PMI 深度掃描模式: {os.path.basename(filepath)}")
    print("=====================================================")
    
    app = XCAFApp_Application.GetApplication()
    doc = TDocStd_Document("MDTV-PMI-SCAN")
    app.NewDocument("MDTV-PMI-SCAN", doc)
    
    reader = STEPCAFControl_Reader()
    if reader.ReadFile(filepath) != IFSelect_RetDone:
        print("❌ 讀取失敗")
        return
    reader.Transfer(doc)
    
    # 獲取工具 (兼容舊版本語法)
    try:
        dim_tol_tool = XCAFDoc.XCAFDoc_DocumentTool.DimTolTool(doc.Main())
    except AttributeError:
        dim_tol_tool = XCAFDoc.XCAFDoc_DocumentTool_DimTolTool(doc.Main())
        
    dims = TDF_LabelSequence()
    dim_tol_tool.GetDimensionLabels(dims)
    
    print(f"✅ 發現 {dims.Length()} 個 Dimension Labels。開始逐一破解...")

    for i in range(1, dims.Length() + 1):
        label = dims.Value(i)
        print(f"\n[D{i}] 正在掃描標籤屬性...")
        
        # 使用獲取迭代器直接遍歷所有屬性
        it = TDF_AttributeIterator(label)
        found_data = False
        while it.More():
            attr = it.Value()
            attr_type = attr.DynamicType().Name()
            
            if "XCAFDoc_Dimension" in attr_type:
                print(f"   ➤ 發現 Dimension 屬性: {attr_type}")
                # 遍歷所有可能的 getter
                for method_name in ["GetObject", "GetValue", "get", "Get"]:
                    if hasattr(attr, method_name):
                        try:
                            # 嘗試呼叫
                            res = getattr(attr, method_name)()
                            if hasattr(res, "get"): res = res.get()
                            if hasattr(res, "GetValue"):
                                print(f"   ➤ ✨ 數據解鎖! 類別={res.GetType()}, 數值={res.GetValue()}")
                                found_data = True
                        except: pass
                
                if not found_data:
                    print(f"   ➤ 標籤已鎖定，但 Python 層缺少 getter 方法。可用功能：{[m for m in dir(attr) if not m.startswith('_')]}")

            it.Next()

if __name__ == "__main__":
    target = r"C:\Tolerance_Project\test_3d_viz\models\bearing_housing.stp"
    extract_pmi_robust(target)
