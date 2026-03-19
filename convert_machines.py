import pandas as pd
import json

df = pd.read_csv("c:/Tolerance_Project/data/machines.csv").fillna("")

# Mapping from "機台類型" (屬性) to process_id
process_map = {
    "立式加工中心機": "P_VMC",
    "立式五軸加工機": "P_5AX",
    "臥式加工中心機": "P_HMC",
    "臥式搪銑加工機": "P_HMC",
    "龍門型五面加工中心機": "P_5AX"
}

company_map = {
    "亞崴機電": {"id": "C_AWEA", "brand": "AWEA"},
    "東台精機": {"id": "C_TONGTAI", "brand": "Tongtai"},
    "永進機械": {"id": "C_YCM", "brand": "YCM"},
}

machines = []
capabilities = []

for idx, row in df.iterrows():
    if not str(row["型號"]).strip(): continue
        
    model = str(row["型號"]).strip()
    company_zh = str(row["公司"]).strip()
    ptype_zh = str(row["屬性"]).strip()
    
    comp_info = company_map.get(company_zh, {"id": "C_OTHER", "brand": company_zh})
    comp_id = comp_info["id"]
    brand = comp_info["brand"]
    
    process_id = process_map.get(ptype_zh, "P_VMC")
    machine_id = f"{comp_id.split('_')[-1]}_{model.replace(' ', '_').replace('+', 'P').replace('/', '_')}"
    
    # Machine object
    m_obj = {
        "machine_id": machine_id,
        "company_id": comp_id,
        "brand": brand,
        "model": model,
        "series": model.split('-')[0] if '-' in model else model,
        "process_id": process_id,
        "source": {"name": f"{brand} {model} Specs", "url": "#"}
    }
    machines.append(m_obj)
    
    # Capability object
    cp_kw = str(row["主軸功率(kw)"])
    if not cp_kw.strip(): cp_kw = "0"
        
    rpm = str(row["主軸轉速(rpm)"]).replace(".0", "")
    if not rpm.strip(): rpm = "0"
        
    x = str(row["X行程(mm)"])
    y = str(row["Y行程(mm)"])
    z = str(row["Z行程(mm)"])
    
    travel = {}
    if x.strip(): travel["X"] = float(x)
    if y.strip(): travel["Y"] = float(y)
    if z.strip(): travel["Z"] = float(z)
        
    acc = str(row["定位精度(mm)"])
    rep = str(row["重現精度(mm)"])
    
    cap_obj = {
        "capability_id": f"CAP_{machine_id}",
        "machine_id": machine_id,
        "company_id": comp_id,
        "unit_system": "METRIC",
        "axes": {"count": 3, "travel_mm": travel},
        "spindle": {"speed_max_rpm": rpm, "power_kw": cp_kw},
        "feed": {"rapid_m_per_min": {}},
        "work_envelope": {},
        "accuracy": {
            "positioning_mm": float(acc) if acc.strip() else None,
            "repeatability_mm": float(rep) if rep.strip() else None,
            "notes": "來自備份20260223"
        }
    }
    capabilities.append(cap_obj)

with open("c:/Tolerance_Project/client/machines_data.js", "w", encoding="utf-8") as f:
    f.write("const machines = " + json.dumps(machines, ensure_ascii=False, indent=4) + ";\n\n")
    f.write("const capabilities = " + json.dumps(capabilities, ensure_ascii=False, indent=4) + ";\n")

# Also output JSON for server API
json_data = {
    "ok": True,
    "machines": machines,
    "capabilities": capabilities
}
with open("c:/Tolerance_Project/server/data/machines_data.json", "w", encoding="utf-8") as f:
    json.dump(json_data, f, ensure_ascii=False, indent=4)
