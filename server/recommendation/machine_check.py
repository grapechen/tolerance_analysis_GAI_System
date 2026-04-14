import csv
import os

# =========================
# Machine Capability Validation
# =========================

# Path to the machines CSV
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MACHINES_CSV_PATH = os.path.join(BASE_DIR, 'data', 'machines.csv')

def get_iso_tolerance(diameter):
    """
    Lookup ISO 286 tolerance values (IT7, IT8) for a given diameter.
    Returns tuple (it7_um, it8_um).
    """
    # 單位: μm
    table = [
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
    
    for limit, it7, it8 in table:
        if diameter <= limit:
            return it7, it8
            
    # Default fallback for large diameters > 500mm
    return 63, 97

def find_capable_machines(diameter, safety_factor=1.0, keywords=None):
    """
    Find machines capable of manufacturing the part.
    Logic:
    1. Look up IT7 tolerance for the diameter (as 'g7' substitute).
    2. Convert to mm.
    3. Calculate target repeatability = tolerance / safety_factor.
    4. Filter machines where '重現精度(mm)' <= target repeatability.
    """
    it7_um, it8_um = get_iso_tolerance(diameter)
    
    tol_g7_mm = it7_um / 1000.0
    tol_H8_mm = it8_um / 1000.0
    
    target_repeat = tol_g7_mm / safety_factor
    
    capable_machines = []
    
    if not os.path.exists(MACHINES_CSV_PATH):
        print(f"Error: Machines CSV not found at {MACHINES_CSV_PATH}")
        return {
            "target_repeat_mm": target_repeat,
            "tol_g7_mm": tol_g7_mm,
            "tol_H8_mm": tol_H8_mm,
            "machines": []
        }

    try:
        with open(MACHINES_CSV_PATH, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    # Parse repeatability (handle data errors gracefully)
                    repeat_val = float(row.get('重現精度(mm)', 999))
                    pos_val = float(row.get('定位精度(mm)', 999))
                    
                    # 讀取行程 (若無資料則給一個極大值以防誤刪)
                    x_travel = float(row.get('X行程(mm)') or 9999)
                    y_travel = float(row.get('Y行程(mm)') or 9999)
                    
                    # 1. 精度過濾 & 2. 行程過濾 (直徑不能大於最小的那軸行程)
                    if repeat_val <= target_repeat and diameter <= min(x_travel, y_travel):
                        machine_temp = {
                            "model": row.get('型號', 'Unknown'),
                            "company": row.get('公司', 'Unknown'),
                            "type": row.get('屬性', ''),
                            "repeatability_mm": repeat_val,
                            "positioning_mm": pos_val,
                            "spindle_rpm": row.get('主軸轉速(rpm)', ''),
                            "spindle_kw": row.get('主軸功率(kw)', ''),
                            "travel_x_y_z": f"{row.get('X行程(mm)','-')} x {row.get('Y行程(mm)','-')} x {row.get('Z行程(mm)','-')}",
                            "scenario": row.get('應用場景', '')
                        }

                        # 3. 如果有傳入 keywords，針對應用場景做加分
                        score = 0
                        scenario_text = str(machine_temp['scenario']) + str(machine_temp['type'])
                        if keywords:
                            score = sum(1 for k in keywords if k in scenario_text)

                        # --- [新增] 自動生成推薦理由 ---
                        reasons = []
                        if repeat_val <= target_repeat:
                            diff_pct = ((target_repeat - repeat_val) / target_repeat) * 100
                            if diff_pct > 30:
                                reasons.append(f"加工精度極佳，優於目標要求約 {diff_pct:.0f}% 以上。")
                            else:
                                reasons.append(f"重現精度達 {repeat_val}mm，充分符合 IT7 ({tol_g7_mm}mm) 等級需求。")
                        
                        min_stroke = min(x_travel, y_travel)
                        if min_stroke >= diameter * 1.5:
                            reasons.append(f"加工行程充沛 (Axis Min: {min_stroke}mm)，可處理直徑 {diameter}mm 工件。")
                        
                        if score > 0 and keywords:
                            matched_keywords = [k for k in keywords if k in scenario_text]
                            reasons.append(f"功能匹配度高，具備與您要求的「{', '.join(matched_keywords)}」相關之加工能力。")
                        
                        if not reasons:
                            reasons.append("符合該公差等級之加工規範與行程要求。")
                        
                        machine_temp["recommend_reason"] = " ".join(reasons)
                        machine_temp["match_score"] = score
                        capable_machines.append(machine_temp)

                except ValueError:
                    continue # Skip invalid rows
                    
        # 依照 match_score 降冪排序，再依照精度升冪排序
        capable_machines.sort(key=lambda x: (-x.get('match_score', 0), x['repeatability_mm']))

        # [新增] 只取前 10 名
        capable_machines = capable_machines[:10]

    except Exception as e:
        print(f"Error processing machines CSV: {e}")
        
    return {
        "target_repeat_mm": target_repeat,
        "tol_g7_mm": tol_g7_mm,
        "tol_H8_mm": tol_H8_mm,
        "machines": capable_machines
    }
