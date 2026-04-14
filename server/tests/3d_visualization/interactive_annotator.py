import os
import sys
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Display.SimpleGui import init_display
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.Quantity import Quantity_Color, Quantity_NOC_WHITE, Quantity_NOC_GRAY, Quantity_NOC_YELLOW
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.GeomAbs import GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone, GeomAbs_Sphere, GeomAbs_Torus
from OCC.Core.TopoDS import topods

def get_surface_type(face):
    """識別面特徵的幾何類型 (平面, 圓柱面等)"""
    surf = BRepAdaptor_Surface(face)
    stype = surf.GetType()
    
    type_map = {
        GeomAbs_Plane: "平面 (Plane)",
        GeomAbs_Cylinder: "圓柱面 (Cylinder)",
        GeomAbs_Cone: "圓錐面 (Cone)",
        GeomAbs_Sphere: "球面 (Sphere)",
        GeomAbs_Torus: "圓環面 (Torus)"
    }
    return type_map.get(stype, "複雜曲面 (Other/Complex Surface)")

# 初始化全局顯示數據
last_picked_face = None

def start_annotator(filepath):
    if not os.path.exists(filepath):
        print(f"❌ 找不到檔案: {filepath}")
        return

    # 1. 讀取模型
    step_reader = STEPControl_Reader()
    if step_reader.ReadFile(filepath) != IFSelect_RetDone:
        print("❌ 讀取失敗")
        return
    step_reader.TransferRoot()
    shape = step_reader.Shape()

    # 2. 初始化 3D 視窗
    display, start_display, add_menu, add_function_to_menu = init_display()
    
    # 設定視覺樣式
    my_view = display.get_view() if hasattr(display, 'get_view') else (display.View if hasattr(display, 'View') else None)
    if my_view:
        my_view.SetBackgroundColor(Quantity_Color(Quantity_NOC_WHITE))
    
    display.DisplayShape(shape, color=Quantity_Color(Quantity_NOC_GRAY), update=True)
    
    # 💥 開啟「面選取模式」 (Face Selection Mode)
    display.SetSelectionModeFace()
    
    def on_selection_callback(selected_shapes, *args):
        """當用戶點擊滑鼠時觸發的回呼函式"""
        global last_picked_face
        for shape in selected_shapes:
            if shape.ShapeType() == 4: # TopAbs_FACE = 4
                face = topods.Face(shape)
                last_picked_face = face
                
                # 特徵辨識
                feature_type = get_surface_type(face)
                print("\n" + "="*40)
                print(f"🎯 選中特徵: {feature_type}")
                
                # 獲取細節幾何資訊
                surf = BRepAdaptor_Surface(face)
                if surf.GetType() == GeomAbs_Cylinder:
                    cyl = surf.Cylinder()
                    print(f"   ➤ 半徑 (Radius): {cyl.Radius():.4f} mm")
                elif surf.GetType() == GeomAbs_Plane:
                    # 這裡可以獲取法向量等資訊
                    print(f"   ➤ 定位: 基準平面 (Reference Plane)")
                
                print("📝 請在 Console 中輸入公差設定，或繼續點選其他面。")
                print("="*40)

    # 註冊點擊回呼
    display.register_select_callback(on_selection_callback)
    
    display.FitAll()
    print("\n🚀 [3D 互動標註器已啟動]")
    print("👉 請使用滑鼠「點擊」零件的面來進行特徵感應。")
    print("👉 選取後面會反黃顯示。")
    
    start_display()

if __name__ == "__main__":
    # 使用你的 stp 檔案
    target_stp = r"C:\Tolerance_Project\test_3d_viz\models\bearing_housing.stp"
    start_annotator(target_stp)
