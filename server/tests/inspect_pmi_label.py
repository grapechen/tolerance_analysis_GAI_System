import sys
from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
from OCC.Core.TDocStd import TDocStd_Document
from OCC.Core.XCAFApp import XCAFApp_Application
from OCC.Core.XCAFDoc import XCAFDoc_DocumentTool
from OCC.Core.TDF import TDF_LabelSequence, TDF_AttributeIterator
from OCC.Core.IFSelect import IFSelect_RetDone

def inspect_label_attributes(filepath):
    app = XCAFApp_Application.GetApplication()
    doc = TDocStd_Document("MDTV-XCAF")
    app.NewDocument("MDTV-XCAF", doc)
    
    reader = STEPCAFControl_Reader()
    if reader.ReadFile(filepath) != IFSelect_RetDone:
        print("❌ 讀取失敗")
        return
    reader.Transfer(doc)
    
    dim_tol_tool = XCAFDoc_DocumentTool.DimTolTool(doc.Main())
    dims = TDF_LabelSequence()
    dim_tol_tool.GetDimensionLabels(dims)
    
    if dims.Length() == 0:
        print("⚠️ 此檔案沒有 Dimension Label")
        return

    # 取得第一個標籤進行解剖
    first_label = dims.Value(1)
    print(f"=== Inspecting Label: {first_label} ===")
    
    # 遍歷標籤上的所有屬性
    it = TDF_AttributeIterator(first_label)
    while it.More():
        attr = it.Value()
        print(f"Attribute ID: {attr.ID()}")
        print(f"Attribute Dynamic Type: {attr.DynamicType().Name()}")
        # 印出該屬性物件的所有方法
        print(f"Methods: {[m for m in dir(attr) if not m.startswith('_')]}")
        print("-" * 30)
        it.Next()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        inspect_label_attributes(sys.argv[1])
