import sys
from OCC.Core.TDocStd import TDocStd_Document
from OCC.Core.XCAFApp import XCAFApp_Application
from OCC.Core.XCAFDoc import XCAFDoc_DocumentTool

def inspect_api():
    app = XCAFApp_Application.GetApplication()
    doc = TDocStd_Document("MDTV-XCAF")
    app.NewDocument("MDTV-XCAF", doc)
    
    dim_tol_tool = XCAFDoc_DocumentTool.DimTolTool(doc.Main())
    
    print("=== XCAFDoc_DimTolTool Methods ===")
    methods = [m for m in dir(dim_tol_tool) if not m.startswith('_')]
    for m in sorted(methods):
        print(m)

if __name__ == "__main__":
    inspect_api()
