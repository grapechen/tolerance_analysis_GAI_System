import os
import math
import sys
import pandas as pd
from collections import defaultdict

# PythonOCC Core imports
try:
    from OCC.Core.STEPControl import STEPControl_Reader
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.TopExp import TopExp_Explorer
    from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_SOLID
    from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
    from OCC.Core.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder
    from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib
    from OCC.Core.TopoDS import topods
except ImportError:
    print("❌ 錯誤: 找不到 PythonOCC。請確保已安裝 pythonocc-core 套件。")
    sys.exit(1)

def identify_surface_type(face):
    """
    辨識幾何面類型：GeomAbs_Plane -> Planar, GeomAbs_Cylinder -> Cylindrical
    """
    try:
        adaptor = BRepAdaptor_Surface(face)
        stype = adaptor.GetType()
        if stype == GeomAbs_Plane:
            return "Planar"
        elif stype == GeomAbs_Cylinder:
            return "Cylindrical"
        else:
            return "Other"
    except:
        return "Unknown"

def get_assembly_contact_faces(step_path, tolerance=0.001):
    """
    核心偵測程式：載入組合件 -> ID 映射 -> 接觸掃描 -> 類型推斷
    """
    if not os.path.exists(step_path):
        print(f"⚠️  找不到檔案: {step_path}")
        return []

    print(f"📦 正在載入組合件: {os.path.basename(step_path)} ...")
    reader = STEPControl_Reader()
    status = reader.ReadFile(step_path)
    
    if status != IFSelect_RetDone:
        print("❌ 無法讀取 STEP 檔案")
        return []

    reader.TransferRoots()
    model = reader.StepModel()
    
    # ── 1. 建立 ID 映射 ───────────────────────────
    # 我們遍歷模型中的所有實體 (Solid)，並收集其下的所有面 (Face) 與對應的 STEP ID
    comp_shapes = []
    nb_shapes = reader.NbShapes()
    for i in range(1, nb_shapes + 1):
        comp_shapes.append(reader.Shape(i))

    print(f"🔍 偵測到 {len(comp_shapes)} 個組件根實體...")

    # 封裝 Face 資訊
    class FaceInfo:
        def __init__(self, face, step_id, parent_name):
            self.face = face
            self.id = step_id
            self.parent_name = parent_name
            self.type = identify_surface_type(face)
            self.bbox = Bnd_Box()
            brepbndlib.Add(face, self.bbox)

    all_faces = []
    for i, shape in enumerate(comp_shapes):
        comp_name = f"Component_{i+1}"
        explorer = TopExp_Explorer(shape, TopAbs_FACE)
        while explorer.More():
            face = topods.Face(explorer.Current())
            entity = reader.Entity(face)
            if entity:
                step_id = model.GetId(entity)
                all_faces.append(FaceInfo(face, f"#{step_id}", comp_name))
            explorer.Next()

    print(f"🧩 總計提取 {len(all_faces)} 個幾何面，開始進行接觸分析...")

    # ── 2. 接觸掃描 (雙重迴圈 + 預判) ─────────────────
    contacts = []
    total_faces = len(all_faces)

    for i in range(total_faces):
        f1 = all_faces[i]
        for j in range(i + 1, total_faces):
            f2 = all_faces[j]
            
            # 規則 1：同一個組件內的兩面不計入「組裝接觸」
            if f1.parent_name == f2.parent_name:
                continue

            # 規則 2：Bounding Box 快速過濾 (性能關鍵)
            if f1.bbox.IsOut(f2.bbox):
                continue

            # 規則 3：精密度計算 (BRepExtrema)
            extrema = BRepExtrema_DistShapeShape(f1.face, f2.face)
            if extrema.IsDone():
                dist = extrema.Value()
                if dist < tolerance:
                    # ── 3. 類型推斷 ──
                    c_type = "Unknown"
                    if f1.type == "Planar" and f2.type == "Planar":
                        c_type = "Planar / Mate"
                    elif f1.type == "Cylindrical" and f2.type == "Cylindrical":
                        c_type = "Cylindrical / Coaxial"
                    else:
                        c_type = f"{f1.type} / {f2.type}"

                    contacts.append({
                        'Comp 1': f1.parent_name,
                        'Face A (#ID)': f1.id,
                        'Comp 2': f2.parent_name,
                        'Face B (#ID)': f2.id,
                        'Dist': round(dist, 6),
                        'Type': c_type
                    })

    return contacts

if __name__ == "__main__":
    # 預設路徑：用戶提到的組合件
    target_step = r"c:\test0402\1\1\單一C軸(泓文).STP"
    
    contacts = get_assembly_contact_faces(target_step)
    
    if contacts:
        df = pd.DataFrame(contacts)
        print("\n" + "="*80)
        print("💡 組合件面與面接觸偵測報告 (對應 NIST SFA Entity ID)")
        print("="*80)
        print(df.to_string(index=False))
        
        # 存檔供對應
        output_csv = r"c:\test0402\1\1\assembly_contact_report.csv"
        df.to_csv(output_csv, index=False, encoding='utf-8-sig')
        print(f"\n📊 報告已存檔至: {output_csv}")
    else:
        print("ℹ️  在此公差範圍內 (0.001mm) 未偵測到接觸面。")
