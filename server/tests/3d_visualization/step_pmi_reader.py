# -*- coding: utf-8 -*-
"""
STEP PMI Explorer prototype (基於 OpenCascade XCAF)
功能: 遍歷 STEP AP242 檔案中的語意 PMI (公差、基準、尺寸數據)
"""

from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
from OCC.Core.TDocStd import TDocStd_Document
from OCC.Core.XCAFDoc import XCAFDoc_DocumentTool
from OCC.Core.TDataStd import TDataStd_Name
from OCC.Core.TCollection import TCollection_AsciiString

def explore_pmi(step_file):
    # 建立 XCAF 文件
    doc = TDocStd_Document(TCollection_AsciiString("PMI_Doc"))
    
    # 建立 Reader
    reader = STEPCAFControl_Reader()
    reader.SetColorMode(True)
    reader.SetNameMode(True)
    reader.SetLayerMode(True)
    reader.SetPropsMode(True)
    reader.SetGDTPMode(True) # 開啟 GD&T (PMI) 模式
    
    print(f"正在讀取檔案: {step_file}...")
    status = reader.ReadFile(step_file)
    
    if status != 1:
        print("❌ 讀取失敗! 請檢查檔案路徑是否正確且為 STEP 格式。")
        return

    # 將數據導入文件
    if not reader.Transfer(doc):
        print("❌ 導入資料失敗!")
        return

    # 取得 XCAF 工具
    shape_tool = XCAFDoc_DocumentTool.ShapeTool(doc.Main())
    dim_tol_tool = XCAFDoc_DocumentTool.DimTolTool(doc.Main())
    
    # 遍歷所有的標註 (GD&T / PMI)
    tol_labels = TDocStd_Document().GetLabels() # 這是一個簡化寫法，實際需透過 DimTolTool 獲取
    
    print("\n--- 提取到的語意 PMI 數據 ---")
    # 實際開發時，需針對 DimTol 與 Datum 進行深層遍歷
    # 以下為示範邏輯
    
    # TODO: 實現具體的 PMI 標籤遍歷獲取邏輯
    # 1. 抓取所有幾何公差 (Geometric Tolerances)
    # 2. 抓取所有基準 (Datums)
    # 3. 建立幾何面與公差的 Mapping

    print("✅ 初始框架建立完成。請確認環境與 python-occ 是否安裝成功。")

if __name__ == "__main__":
    # 測試檔案路徑
    test_file = r"c:\Tolerance_Project\新增資料夾\軸承座\軸承座-3.STP"
    explore_pmi(test_file)
