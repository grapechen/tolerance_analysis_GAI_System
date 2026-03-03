import pandas as pd

# ==========================================
# 1. 設定：您要加工的產品直徑 (單位: mm)
# ==========================================
nominal_diameter = 29  # <--- 請在此修改您的工件直徑 (例如 10, 50, 100)

# 設定機台能力係數 (Machine Capability Factor)
# 通常機台精度要是產品公差的 1/3 (嚴格) 或 1/2 (寬鬆)
safety_factor = 3 

# ==========================================
# 2. 定義 ISO 286 公差查表函數 (IT7, IT8)
# ==========================================
def get_iso_tolerance(diameter):
    # 單位: micrometer (μm)
    # 格式: (上限直徑, IT7數值, IT8數值)
    lookup_table = [
        (3,   10, 14),
        (6,   12, 18),
        (10,  15, 22),
        (18,  18, 27),
        (30,  21, 33),
        (50,  25, 39),
        (80,  30, 46),
        (120, 35, 54),
        (180, 40, 63),
        (250, 46, 72),
        (315, 52, 81),
        (400, 57, 89),
        (500, 63, 97)
    ]
    
    for limit, it7, it8 in lookup_table:
        if diameter <= limit:
            return it7, it8
    return 63, 97 # 超出範圍預設值 (500mm+)

# 取得公差值 (微米轉毫米)
tol_g7_um, tol_H8_um = get_iso_tolerance(nominal_diameter)
tol_g7_mm = tol_g7_um / 1000.0
tol_H8_mm = tol_H8_um / 1000.0

# 計算目標機台精度 (以較嚴格的 g7 為準)
target_repeatability = tol_g7_mm / safety_factor

print(f"=== 篩選條件分析 (直徑: {nominal_diameter} mm) ===")
print(f"1. 產品規格 H8 (孔): {tol_H8_mm:.3f} mm")
print(f"2. 產品規格 g7 (軸): {tol_g7_mm:.3f} mm (最嚴格標準)")
print(f"3. 建議機台重現精度 <= {target_repeatability:.4f} mm (公差的 1/{safety_factor})")
print("-" * 50)

# ==========================================
# 3. 讀取資料並篩選
# ==========================================
try:
    # 讀取 CSV
    df = pd.read_csv(r'c:\Users\tony\Desktop\碩一\py\PY1\活頁簿1.csv')
    
    # 篩選符合條件的機台 (重現精度 <= 目標值)
    suitable_machines = df[df['重現精度(mm)'] <= target_repeatability]

    # 顯示設定
    pd.set_option('display.unicode.east_asian_width', True)
    pd.set_option('display.max_columns', None)
    
    if not suitable_machines.empty:
        print(f"✅ 找到 {len(suitable_machines)} 台符合需求的機台：")
        # 為了美觀，只顯示重要欄位
        cols = ['型號', '重現精度(mm)', '定位精度(mm)', '公司']
        print(suitable_machines[cols].to_string(index=False))
    else:
        print("❌ 沒有機台符合此精度要求。")
        print("建議：嘗試降低 'safety_factor' 或尋找更高階機型。")

except FileNotFoundError:
    print("找不到檔案，請確認路徑。")