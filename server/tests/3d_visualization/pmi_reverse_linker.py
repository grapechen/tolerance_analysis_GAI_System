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
    """輔助函式：獲取標籤位置字串"""
    entry_as = TCollection_AsciiString()
    TDF_Tool.Entry(label, entry_as)
    return entry_as.ToCString()

def pmi_reverse_navigation(filepath):
    print("=====================================================")
    print(f"🔄 PMI 反向追蹤掃描: {os.path.basename(filepath)}")
    print("=====================================================")
    
    app = XCAFApp_Application.GetApplication()
    doc = TDocStd_Document("MDTV-REVERSE")
    app.NewDocument("MDTV-REVERSE", doc)
    
    reader = STEPCAFControl_Reader()
    if reader.ReadFile(filepath) != IFSelect_RetDone:
        print("❌ 讀取失敗")
        return
    reader.Transfer(doc)
    
    # 獲取工具
    shape_tool = XCAFDoc.XCAFDoc_DocumentTool.ShapeTool(doc.Main())
    
    # 獲取所有頂層形狀
    root_shapes = TDF_LabelSequence()
    shape_tool.GetFreeShapes(root_shapes)
    
    print(f"✅ 發現 {root_shapes.Length()} 個頂層物件。開始全量掃描 TDF 數據樹...")

    # 自適應遍歷：掃描整個標籤樹，尋找所有帶有 GraphNode 且指向 0:1:4 (公差區) 的連結
    def scan_label_recursive(label):
        it = TDF_AttributeIterator(label)
        while it.More():
            attr_h = it.Value()
            if "XCAFDoc_GraphNode" in attr_h.DynamicType().Name():
                # 檢查是否有子節點指向公差標籤
                nb_children = attr_h.NbChildren()
                for i in range(1, nb_children + 1):
                    child = attr_h.GetChild(i)
                    child_label = child.Label()
                    child_entry = get_label_entry(child_label)
                    # 0:1:4 是 XCAF 中典型的 DimTol 存儲區域
                    if "0:1:4" in child_entry:
                        print(f"\n🎯 發現幾何-公差連結!")
                        print(f"   ➤ 幾何特徵: {get_label_entry(label)}")
                        print(f"   ➤ 指向公差: {child_entry}")
            it.Next()
        
        # 遞迴掃描子標籤
        for i in range(1, label.NbChildren() + 1):
            # 這裡需要小心，有些版本使用 FindChild(i)
            # 我們使用 AttributeIterator 之外的標籤遍歷
            pass
            
    # 改用更強大的「大範圍掃描」：從 doc.Main() 開始往下翻
    def deep_scan(start_label):
        # 這裡我們使用一個佇列來做廣度優先搜索 (BFS) 所有標籤
        queue = [start_label]
        while queue:
            curr = queue.pop(0)
            scan_label_recursive(curr)
            
            # 將所有子標籤加入佇列
            # 注意：這裡使用 Tag 遍歷
            from OCC.Core.TDF import TDF_ChildIterator
            child_it = TDF_ChildIterator(curr)
            while child_it.More():
                queue.append(child_it.Value())
                child_it.Next()

    deep_scan(doc.Main())
    print("\n🏁 全量掃描結束。")

if __name__ == "__main__":
    target = r"C:\Tolerance_Project\test_3d_viz\models\bearing_housing.stp"
    pmi_reverse_navigation(target)
