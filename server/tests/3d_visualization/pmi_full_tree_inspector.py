import sys
import os
import OCC.Core.XCAFDoc as XCAFDoc
from OCC.Core.TDF import TDF_LabelSequence, TDF_AttributeIterator, TDF_Tool, TDF_ChildIterator
from OCC.Core.TCollection import TCollection_AsciiString
from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
from OCC.Core.TDocStd import TDocStd_Document
from OCC.Core.XCAFApp import XCAFApp_Application
from OCC.Core.IFSelect import IFSelect_RetDone

def get_label_entry(label):
    entry_as = TCollection_AsciiString()
    TDF_Tool.Entry(label, entry_as)
    return entry_as.ToCString()

def pmi_full_tree_scan(filepath):
    print("=====================================================")
    print(f"📡 TDF 全數據通訊塔掃描: {os.path.basename(filepath)}")
    print("=====================================================")
    
    app = XCAFApp_Application.GetApplication()
    doc = TDocStd_Document("MDTV-FULL")
    app.NewDocument("MDTV-FULL", doc)
    
    reader = STEPCAFControl_Reader()
    if reader.ReadFile(filepath) != IFSelect_RetDone:
        print("❌ 讀取失敗")
        return
    reader.Transfer(doc)
    
    # 遍歷整個文檔的所有標籤
    def scan_recursively(label):
        it = TDF_AttributeIterator(label)
        entry = get_label_entry(label)
        
        while it.More():
            attr = it.Value()
            attr_name = attr.DynamicType().Name()
            
            # 解析 GraphNode 或 Dimension 這種關鍵資料
            if any(k in attr_name for k in ["GraphNode", "Dimension", "GeomTolerance"]):
                try:
                    # 使用萬能的 DumpJson() 繞過類型轉換問題
                    raw_json = attr.DumpJson()
                    # 我們只印出含有 Object 實體資料的 JSON
                    if "Object" in raw_json or "GraphNode" in attr_name:
                        print(f"\n📍 數據源標籤: {entry}")
                        print(f"   ➤ 屬性類別: {attr_name}")
                        print(f"   ➤ 內部資料 (DumpJson): {raw_json}")
                except:
                    pass
            it.Next()
        
        # 遞迴掃描子標籤
        cit = TDF_ChildIterator(label)
        while cit.More():
            scan_recursively(cit.Value())
            cit.Next()

    scan_recursively(doc.Main())
    print("\n🏁 全數據掃描結束。")

if __name__ == "__main__":
    target = r"C:\Tolerance_Project\test_3d_viz\models\bearing_housing.stp"
    pmi_full_tree_scan(target)
