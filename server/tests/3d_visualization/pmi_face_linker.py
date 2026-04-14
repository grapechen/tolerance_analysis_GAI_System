import sys
import os
import OCC.Core.XCAFDoc as XCAFDoc
from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
from OCC.Core.TDocStd import TDocStd_Document
from OCC.Core.XCAFApp import XCAFApp_Application
from OCC.Core.TDF import TDF_LabelSequence
from OCC.Core.IFSelect import IFSelect_RetDone

def test_pmi_linkage(filepath):
    print("=====================================================")
    print(f"🔗 PMI-Face 核心對接測試 (修正模型標籤): {os.path.basename(filepath)}")
    print("=====================================================")
    
    app = XCAFApp_Application.GetApplication()
    doc = TDocStd_Document("MDTV-LINK-4")
    app.NewDocument("MDTV-LINK-4", doc)
    
    reader = STEPCAFControl_Reader()
    if reader.ReadFile(filepath) != IFSelect_RetDone:
        print("❌ 讀取失敗")
        return
    reader.Transfer(doc)
    
    # 獲取主標籤與工具
    main_label = doc.Main()
    # 確保工具正確載入
    dim_tol_tool = XCAFDoc.XCAFDoc_DocumentTool.DimTolTool(main_label)
    
    dims = TDF_LabelSequence()
    dim_tol_tool.GetDimensionLabels(dims)
    
    print(f"✅ 發現 {dims.Length()} 個公差標籤。開始 3 參數對位測試...")

    for i in range(1, dims.Length() + 1):
        dim_label = dims.Value(i)
        ref_shapes = TDF_LabelSequence()
        success = False
        
        # 🧪 方案 A: (Context Label, Dim Label, Result Sequence)
        # 這是 OCCT 7.7.x 的標準靜態調用簽名
        try:
            XCAFDoc.XCAFDoc_DimTolTool.GetRefShapeLabel(main_label, dim_label, ref_shapes)
            success = True
            tag = "組合 A (MainL, DimL, Seq)"
        except:
            # 🧪 方案 B: (Dim Label, Result Sequence, Boolean Search)
            try:
                XCAFDoc.XCAFDoc_DimTolTool.GetRefShapeLabel(dim_label, ref_shapes, True)
                success = True
                tag = "組合 B (DimL, Seq, True)"
            except:
                pass

        if success:
            if ref_shapes.Length() > 0:
                # 這裡最關鍵：如果不為 0，代表我們抓到了那個面！
                print(f"   ➤ [D{i}] 成功解碼! 使用【{tag}】鎖定 Face Entry: {ref_shapes.Value(1).Entry()}")
            else:
                print(f"   ➤ [D{i}] 已連通，但標籤未關聯到實體。")
        else:
            print(f"   ❌ [D{i}] 無法解開 Link (所有 3-Args 嘗試失敗)。")

if __name__ == "__main__":
    target = r"C:\Tolerance_Project\test_3d_viz\models\bearing_housing.stp"
    test_pmi_linkage(target)
