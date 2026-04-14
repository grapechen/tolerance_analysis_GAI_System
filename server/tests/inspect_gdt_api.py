import sys
from OCC.Core.TDocStd import TDocStd_Document
from OCC.Core.XCAFApp import XCAFApp_Application
from OCC.Core.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_GDTTool, XCAFDoc_Presentation

def inspect_gdt_api():
    app = XCAFApp_Application.GetApplication()
    doc = TDocStd_Document("MDTV-XCAF")
    app.NewDocument("MDTV-XCAF", doc)
    
    # 1. 檢查 GDTTool 是否能從 DocumentTool 獲取
    try:
        gdt_tool = XCAFDoc_DocumentTool.GDTTool(doc.Main())
        print("=== XCAFDoc_GDTTool Methods ===")
        methods = [m for m in dir(gdt_tool) if not m.startswith('_')]
        for m in sorted(methods):
            print(m)
    except Exception as e:
        print(f"❌ 無法獲取 GDTTool: {e}")

    # 2. 檢查 Presentation 屬性
    try:
        print("\n=== XCAFDoc_Presentation Methods ===")
        methods = [m for m in dir(XCAFDoc_Presentation) if not m.startswith('_')]
        for m in sorted(methods):
            print(m)
    except Exception as e:
        print(f"❌ XCAFDoc_Presentation 不存在: {e}")

if __name__ == "__main__":
    inspect_gdt_api()
