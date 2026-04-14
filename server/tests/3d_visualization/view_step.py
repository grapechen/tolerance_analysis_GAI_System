import os
import sys
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Display.SimpleGui import init_display
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.Quantity import Quantity_Color, Quantity_NOC_WHITE, Quantity_NOC_GRAY

def view_bearing_housing_pro(filepath):
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
    try:
        display, start_display, add_menu, add_function_to_menu = init_display()
        
        # 3. 背景設定
        my_view = None
        for attr_name in ['View', 'view', 'GetView']:
            if hasattr(display, attr_name):
                val = getattr(display, attr_name)
                my_view = val() if callable(val) else val
                if my_view: break

        if my_view:
            my_view.SetBackgroundColor(Quantity_Color(Quantity_NOC_WHITE))
            print("✅ 純白背景已套用。")
        
        # 4. 模型顏色設定 (直接傳入物件，避開字串 KeyError)
        # 在 pythonocc 中，DisplayShape 可以接受 color=Quantity_Color
        gray_color = Quantity_Color(Quantity_NOC_GRAY)
        display.DisplayShape(shape, color=gray_color, update=True)
        
        display.FitAll()
        print("✨ 3D 展示完成。")
        start_display()
    except Exception as e:
        print(f"❌ 執行視窗出錯: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    stp_path = r"C:\Tolerance_Project\test_3d_viz\models\bearing_housing.stp"
    view_bearing_housing_pro(stp_path)
