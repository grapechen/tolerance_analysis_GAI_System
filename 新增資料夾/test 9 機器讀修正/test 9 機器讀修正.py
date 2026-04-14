import os
import re
import pandas as pd
from collections import Counter, defaultdict

# ==========================================
# 核心 1：STEP 專用十六進位中文解碼器
# ==========================================
def decode_step_string(s):
    if not isinstance(s, str): return s
    def replacer(match):
        hex_str = match.group(1).replace(' ', '')
        if len(hex_str) % 2 != 0: hex_str = '0' + hex_str
        try: return bytes.fromhex(hex_str).decode('utf-16-be')
        except: return match.group(0)
    return re.sub(r'\\X2\\(.*?)\\X0\\', replacer, s)

# ==========================================
# 核心 2：SFA 機器可讀數據庫萃取 (🔥Bug 修正：dis/dia 變數隔離重置)
# ==========================================
def parse_sfa_single_excel(sfa_excel_file):
    if not os.path.exists(sfa_excel_file):
        print(f"⚠️ 找不到 SFA Excel 檔案：{sfa_excel_file}")
        return [], defaultdict(set)
        
    print(f"📊 正在建立【機器可讀數據庫】(精準分離 dis 與 dia)...")
    
    sheet_code_map = {
        'dimensional': 'dis',         
        'parallelism': 'par',         
        'perpendicularity': 'per',    
        'concentricity': 'co',       
        'coaxiality': 'co',          
        'flatness': 'fla',            
        'circularity': 'cir',         
        'roundness': 'cir',           
        'cylindricity': 'cyl',        
        'position': 'pos',            
        'angularity': 'ang',          
        'symmetry': 'sym',            
        'straightness': 'str',        
        'profile_of_line': 'profl',   
        'line_profile': 'profl',      
        'profile_of_surface': 'profs',
        'surface_profile': 'profs',   
        'total_runout': 'tot',        
        'runout': 'run'               
    }
    
    tol_counters = defaultdict(int)
    tolerance_db = [] 
    
    try:
        sfa_xls = pd.ExcelFile(sfa_excel_file)
        for sheet in sfa_xls.sheet_names:
            sheet_lower = sheet.lower()
            if not ('dimensional' in sheet_lower or 'datum_feature' in sheet_lower or ('_tolerance' in sheet_lower and 'value' not in sheet_lower and 'plus_minus' not in sheet_lower)):
                continue

            df_raw = pd.read_excel(sfa_xls, sheet_name=sheet, header=None)
            
            header_idx = -1
            for i in range(min(15, len(df_raw))):
                row_str = " ".join(str(x).lower() for x in df_raw.iloc[i].values)
                if 'id' in row_str and 'geometry' in row_str:
                    header_idx = i
                    break
                    
            if header_idx == -1: continue
            
            df = df_raw.iloc[header_idx+1:].copy()
            df.columns = df_raw.iloc[header_idx].astype(str)
            
            geom_col = next((c for c in df.columns if 'geometry' in str(c).lower()), None)
            val_col = None
            
            type_code = None
            for key, code in sheet_code_map.items():
                if key in sheet_lower:
                    type_code = code
                    break
            
            if 'dimensional' in sheet_lower:
                val_col = next((c for c in df.columns if 'dimensional' in str(c).lower() and 'tolerance' in str(c).lower()), None)
            elif 'datum_feature' in sheet_lower:
                val_col = next((c for c in df.columns if 'datum' in str(c).lower()), None)
            elif '_tolerance' in sheet_lower:
                val_col = next((c for c in df.columns if 'gd&t' in str(c).lower()), None)

            if val_col and geom_col:
                for _, row in df.iterrows():
                    val = str(row[val_col]).strip()
                    geom = str(row[geom_col])
                    if val and val.lower() != 'nan':
                        clean_val = re.sub(r'\s+', ' ', val).strip()
                        
                        # 🔥 修復 Bug：每次迴圈賦予一個獨立的 current_base_code，避免蓋印章忘記換回來！
                        current_base_code = type_code
                        
                        if current_base_code == 'dis' and not re.search(r'[+\-±]', clean_val):
                            continue
                        
                        # 獨立判斷：如果是圓柱或是帶有 ⌀，這一次的代碼就暫時換成 dia
                        if current_base_code == 'dis' and ('cylindrical_surface' in geom.lower() or '⌀' in clean_val):
                            current_base_code = 'dia'
                        
                        formatted_val = clean_val
                        if '◎' in formatted_val:
                            formatted_val = formatted_val.replace('◎', '').replace('|', '').strip()
                            formatted_val = re.sub(r'\s+', ' ', formatted_val)
                            
                        code_name = ""
                        if current_base_code:
                            tol_counters[current_base_code] += 1
                            code_name = f"{current_base_code}{tol_counters[current_base_code]}"
                        elif 'datum_feature' in sheet_lower:
                            code_name = "dat"
                            formatted_val = f"[{clean_val}]"
                        else:
                            continue
                            
                        # 抓取該公差綁定的所有 Face ID
                        fids = []
                        for line in str(geom).split('\n'):
                            if 'advanced_face' in line.lower():
                                id_parts = line.lower().split('advanced_face')[-1]
                                fids.extend(re.findall(r'\d+', id_parts))
                                
                        if fids:
                            tolerance_db.append({
                                'code_name': code_name,
                                'value': formatted_val,
                                'fids': list(set(fids))
                            })
                            
    except Exception as e:
        print(f"⚠️ 讀取 SFA Excel 時發生錯誤: {e}")
        
    pmi_mapping = defaultdict(set)
    for t in tolerance_db:
        prefix = "🚩 " if t['code_name'] == 'dat' else "🎯 "
        pmi_str = f"{prefix}{t['code_name']}: {t['value']}"
        for fid in t['fids']:
            pmi_mapping[fid].add(pmi_str)
            
    return tolerance_db, pmi_mapping

# ==========================================
# 核心 3：主執行引擎 (產出機器可讀格式)
# ==========================================
def export_sfa_bom_mbd_excel(stp_file, sfa_excel_file, output_excel_path, custom_part_num):
    print(f"🚀 啟動【SFA MBD 機器可讀引擎】...")
    
    tolerance_db, pmi_mapping = parse_sfa_single_excel(sfa_excel_file)

    entities = {}
    with open(stp_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read().replace('\n', '').replace('\r', '')
        for raw in content.split(';'):
            match = re.match(r'\s*#(\d+)\s*=\s*([A-Z_0-9_]+)\s*\((.*)\)', raw)
            if match:
                eid, etype, params = match.groups()
                entities[eid] = {'type': etype.strip(), 'params': params}

    part_features = {} 
    for eid, e in entities.items():
        if e['type'] == 'ADVANCED_BREP_SHAPE_REPRESENTATION':
            name_match = re.search(r"'([^']+)'", e['params'])
            part_name = decode_step_string(name_match.group(1) if name_match else f"未命名_{eid}")
            
            face_ids = set()
            def find_faces(current_id):
                if current_id not in entities: return
                if entities[current_id]['type'] == 'ADVANCED_FACE':
                    face_ids.add(current_id)
                    return
                for ref in re.findall(r'#(\d+)', entities[current_id]['params']):
                    valid = ['MANIFOLD_SOLID_BREP', 'BREP_WITH_VOIDS', 'CLOSED_SHELL', 'ORIENTED_CLOSED_SHELL', 'ADVANCED_FACE']
                    if ref in entities and entities[ref]['type'] in valid: find_faces(ref)
            find_faces(eid)
            
            grouped_faces = defaultdict(lambda: defaultdict(list))
            for fid in face_ids:
                refs = re.findall(r'#(\d+)', entities[fid]['params'])
                found = False
                if refs:
                    for ref in refs:
                        if ref in entities and ('SURFACE' in entities[ref]['type'] or entities[ref]['type'] == 'PLANE'):
                            s_type = entities[ref]['type']
                            param_str = "標準特徵"
                            if s_type == 'CYLINDRICAL_SURFACE':
                                r_match = re.search(r',\s*([-\d\.eE]+)\s*$', entities[ref]['params'])
                                if r_match: param_str = f"半徑 R={float(r_match.group(1)):.3f} (直徑 Ø{float(r_match.group(1))*2:.3f})"
                            grouped_faces[s_type][param_str].append(fid)
                            found = True
                            break
                if not found: grouped_faces['OTHER']["未知參數"].append(fid)
            part_features[part_name] = grouped_faces

    # 建立 Face ID 對應的 特徵代號 (Feature Code)
    fid_to_feat = {} 
    
    for name, features in part_features.items():
        feat_counters = {'P': 1, 'S': 1, 'H': 1, 'F': 1}
        for f_type, param_group in features.items():
            for param_str, f_ids in param_group.items():
                for fid in f_ids:
                    feat_code = ""
                    if f_type == 'PLANE':
                        feat_code = f"{custom_part_num}-P{feat_counters['P']}"
                        feat_counters['P'] += 1
                    elif f_type == 'CYLINDRICAL_SURFACE':
                        face_params = entities[str(fid)]['params']
                        if '.F.' in face_params.split(',')[-1].upper():
                            feat_code = f"{custom_part_num}-H{feat_counters['H']}"
                            feat_counters['H'] += 1
                        else:
                            feat_code = f"{custom_part_num}-S{feat_counters['S']}"
                            feat_counters['S'] += 1
                    else:
                        feat_code = f"{custom_part_num}-F{feat_counters['F']}"
                        feat_counters['F'] += 1
                        
                    fid_to_feat[str(fid)] = feat_code

    # ==========================================
    # 🔥 建立機器可讀列表 (完全依照您的需求排列)
    # ==========================================
    machine_data = []
    for t in tolerance_db:
        # 將 Face ID 排序以確保輸出整齊
        fids_sorted = sorted(t['fids'], key=lambda x: int(x))
        # 尋找這些 Face ID 在拓樸解析中被賦予的特徵代號 (如 1-P1, 1-H2)
        mapped_feats = [fid_to_feat.get(fid, "未知特徵") for fid in fids_sorted]
        
        machine_data.append({
            "公差代碼": t['code_name'],
            "公差數值": t['value'],
            "Face ID": ", ".join([f"#{fid}" for fid in fids_sorted]),
            "特徵代號": ", ".join(mapped_feats)
        })

    # 輸出至 Excel
    try:
        with pd.ExcelWriter(output_excel_path, engine='openpyxl') as writer:
            pd.DataFrame(machine_data).to_excel(writer, index=False, sheet_name='機器可讀_公差列表')
            
            worksheet = writer.sheets['機器可讀_公差列表']
            for col in worksheet.columns:
                column = col[0].column_letter
                worksheet.column_dimensions[column].width = min(max([len(str(c.value)) for c in col] + [0]) + 2, 50)
                
        print(f"\n✅ 大功告成！已產出【精確修復 dis/dia】的機器可讀清單：{output_excel_path}")
    except PermissionError:
        print(f"\n⚠️ 寫入失敗！請檢查 Excel 檔案是否正被開啟著？\n👉 請將 '{output_excel_path}' 關閉後，再執行一次程式！")

# ================= 執行區塊 =================
if __name__ == "__main__":
    # 👉 記得改成您的實際資料夾路徑！
    file_dir = r"C:\Users\tony\Downloads\1" 
    stp_file = os.path.join(file_dir, "2.STP") 
    sfa_excel = os.path.join(file_dir, "2-sfa.xlsx")
    
    print("="*50)
    user_input_num = input("📝 請輸入這個圖檔的專屬零件編號 (例如: 1, A, PartX): ")
    print("="*50)
    
    output_excel = os.path.join(file_dir, f"{user_input_num}_機器可讀公差表.xlsx")
    export_sfa_bom_mbd_excel(stp_file, sfa_excel, output_excel, user_input_num)