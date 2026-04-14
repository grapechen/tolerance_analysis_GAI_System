import os
import re
import pandas as pd
from collections import Counter, defaultdict

# ==========================================
# STEP 專用十六進位中文解碼器
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
# SFA  Excel 解析器 
# ==========================================
def parse_sfa_single_excel(sfa_excel_file):
    pmi_mapping = defaultdict(set)
    if not os.path.exists(sfa_excel_file):
        print(f"⚠️ 找不到 SFA Excel 檔案：{sfa_excel_file}")
        return pmi_mapping
        
    print(f"📊 正在將 SFA 數據轉換為標準量測代碼 (dis1, par1, ideal...)...")
    
    # 🎯 建立公差代碼對照表
    sheet_code_map = {
        'dimensional': 'dis',         # 尺寸/直徑
        'parallelism': 'par',         # 平行度
        'perpendicularity': 'per',    # 垂直度
        'concentricity': 'co',       # 同心度
        'flatness': 'fla',            # 平面度
        'circularity': 'cir',         # 真圓度
        'cylindricity': 'cy',        # 圓柱度
        'position': 'pos',            # 位置度
        'angularity': 'ang',          # 傾斜度
        'symmetry': 'sym',            # 對稱度
        'profile_of_line': '',   # 線輪廓度
        'line_profile': '',      
        'profile_of_surface': '',# 面輪廓度
        'surface_profile': '',   
        'total_runout': '',        # 全偏角
        'runout': ''               # 偏角
    }
    
    # 記錄每種公差的出現次數
    tol_counters = defaultdict(int)
    
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
                        
                        # 🎯 過濾器：如果它是尺寸 (dis)，但字串裡沒有公差符號 (+, -, ±)，就直接跳過不抓取！
                        if type_code == 'dis' and not re.search(r'[+\-±]', clean_val):
                            continue
                        
                        current_code = ""
                        formatted_val = clean_val
                        
                        if type_code:
                            tol_counters[type_code] += 1
                            current_code = f"🎯 {type_code}{tol_counters[type_code]}: "
                        elif 'datum_feature' in sheet_lower:
                            current_code = "🚩 dat: "
                            formatted_val = f"[{clean_val}]"
                            
                        # 綁定 Face ID
                        for fid in re.findall(r'advanced_face\s+(\d+)', geom, re.IGNORECASE):
                            pmi_mapping[fid].add(f"{current_code}{formatted_val}")
                            
    except Exception as e:
        print(f"⚠️ 讀取 SFA Excel 時發生錯誤: {e}")
            
    print(f"✅ 成功提取並轉換 {len(pmi_mapping)} 個特徵面的公差代碼！\n")
    return pmi_mapping

# ==========================================
# 核心 3：主執行引擎 (帶零件編號前綴與 ideal 特徵)
# ==========================================
def export_sfa_bom_mbd_excel(stp_file, sfa_excel_file, output_excel_path, custom_part_num):
    print(f"🚀 啟動【SFA MBD ：零件 {custom_part_num} + 代碼 + 純尺寸過濾】...")
    
    pmi_mapping = parse_sfa_single_excel(sfa_excel_file)

    print(f"📁 正在讀取 3D 幾何檔案：{stp_file}...")
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

    def is_noise_part(name, qty=1):
        keywords = ['螺絲', '螺栓', '螺釘', '螺帽', '墊圈', '墊片', 'SCREW', 'BOLT', 'NUT', 'WASHER']
        return any(kw in name.upper() for kw in keywords) or qty >= 8

    global_radius_map = defaultdict(list)
    for p_name, features in part_features.items():
        if is_noise_part(p_name, 1): continue
        if 'CYLINDRICAL_SURFACE' in features:
            for param_str, f_ids in features['CYLINDRICAL_SURFACE'].items():
                match = re.search(r'半徑 R=([-\d\.]+)', param_str)
                if match and float(match.group(1)) > 6.0: 
                    r_val = round(float(match.group(1)), 4)
                    for fid in f_ids: global_radius_map[r_val].append((p_name, fid))

    product_names, pdf_to_product, pd_to_name = {}, {}, {}
    parent_child_links = []
    for eid, e in entities.items():
        if e['type'] == 'PRODUCT':
            strings = re.findall(r"'([^']*)'", e['params'])
            if strings: product_names[eid] = decode_step_string(strings[1] if len(strings)>1 and strings[1].strip() else strings[0])
        elif 'PRODUCT_DEFINITION_FORMATION' in e['type']:
            refs = re.findall(r'#(\d+)', e['params'])
            if refs: pdf_to_product[eid] = refs[0]
        elif e['type'] == 'PRODUCT_DEFINITION':
            refs = re.findall(r'#(\d+)', e['params'])
            if refs and refs[0] in pdf_to_product and pdf_to_product[refs[0]] in product_names:
                pd_to_name[eid] = product_names[pdf_to_product[refs[0]]]
        elif e['type'] == 'NEXT_ASSEMBLY_USAGE_OCCURRENCE':
            refs = re.findall(r'#(\d+)', e['params'])
            if len(refs) >= 2: parent_child_links.append((refs[-2], refs[-1]))

    children_map = defaultdict(list)
    all_children = set()
    for p, c in parent_child_links:
        children_map[p].append(c)
        all_children.add(c)
        
    root_nodes = [pd for pd in pd_to_name if pd not in all_children]

    excel_data = []
    def build_excel_data(pd_id, level=0, qty=1, parent_name="無 (頂層)"):
        name = pd_to_name.get(pd_id, f"未命名_{pd_id}")
        is_assembly = pd_id in children_map
        
        p_num_str = "" if is_assembly else f"零件 {custom_part_num}"
        
        excel_data.append({
            "BOM 階層": level, "所屬父階": parent_name,
            "節點類型": "📂 組合件" if is_assembly else "⚙️ 單一零件",
            "特徵代號": p_num_str,
            "名稱 / 幾何類型": name, "數量 / 面數": qty,
            "幾何參數": "", "接觸配合 (Mating)": "", "公差代碼 (PMI)": "", "Face ID": f"Def #{pd_id}"
        })
        
        if is_assembly:
            for child_id, count in Counter(children_map[pd_id]).items():
                build_excel_data(child_id, level + 1, count, name)
        else:
            if is_noise_part(name, qty):
                excel_data.append({
                    "BOM 階層": level + 1, "所屬父階": name, "節點類型": "🔻 特徵面 (隱藏)",
                    "特徵代號": "-",
                    "名稱 / 幾何類型": "標準件/陣列件", "數量 / 面數": "-",
                    "幾何參數": "已過濾隱藏", "接觸配合 (Mating)": "", "公差代碼 (PMI)": "", "Face ID": ""
                })
            elif name in part_features:
                feat_counters = {'P': 1, 'S': 1, 'H': 1, 'F': 1}
                
                for f_type, param_group in part_features[name].items():
                    for param_str, f_ids in param_group.items():
                        for fid in f_ids:
                            has_pmi = str(fid) in pmi_mapping
                            
                            # 🎯 如果沒被前面的邏輯抓到公差，就給它 ideal
                            pmi_str = " | ".join(sorted(list(pmi_mapping[str(fid)]))) if has_pmi else "ideal"
                            
                            if not has_pmi:
                                if f_type in ['CONICAL_SURFACE', 'TOROIDAL_SURFACE', 'SPHERICAL_SURFACE']: continue
                                if f_type == 'CYLINDRICAL_SURFACE':
                                    r_match = re.search(r'半徑 R=([-\d\.]+)', param_str)
                                    if r_match and float(r_match.group(1)) <= 6.0: continue

                            feat_code = ""
                            if f_type == 'PLANE':
                                feat_code = f"{custom_part_num}-P{feat_counters['P']}"
                                feat_counters['P'] += 1
                            elif f_type == 'CYLINDRICAL_SURFACE':
                                face_params = entities[str(fid)]['params']
                                is_hole = False
                                if '.F.' in face_params.split(',')[-1].upper():
                                    is_hole = True
                                
                                if is_hole:
                                    feat_code = f"{custom_part_num}-H{feat_counters['H']}"
                                    feat_counters['H'] += 1
                                else:
                                    feat_code = f"{custom_part_num}-S{feat_counters['S']}"
                                    feat_counters['S'] += 1
                            else:
                                feat_code = f"{custom_part_num}-F{feat_counters['F']}"
                                feat_counters['F'] += 1

                            mating_str = ""
                            if f_type == 'CYLINDRICAL_SURFACE':
                                r_match = re.search(r'半徑 R=([-\d\.]+)', param_str)
                                if r_match:
                                    r_val = round(float(r_match.group(1)), 4)
                                    if r_val in global_radius_map:
                                        mating_faces = [f"{op} (面 #{ofid})" for op, ofid in global_radius_map[r_val] if op != name]
                                        mating_faces = list(dict.fromkeys(mating_faces))
                                        if mating_faces: mating_str = "🔗 接觸: " + " | ".join(mating_faces)

                            node_icon = "🔻 特徵面"
                            if has_pmi: node_icon = "🎯 帶公差面"
                            elif mating_str: node_icon = "🔗 接觸配合面"

                            excel_data.append({
                                "BOM 階層": level + 1, "所屬父階": name, 
                                "節點類型": node_icon,
                                "特徵代號": feat_code,
                                "名稱 / 幾何類型": f_type, "數量 / 面數": 1,
                                "幾何參數": param_str, 
                                "接觸配合 (Mating)": mating_str,
                                "公差代碼 (PMI)": pmi_str,
                                "Face ID": f"#{fid}"
                            })

    if root_nodes:
        for root in root_nodes: build_excel_data(root, 0, 1)
    else:
        for name, features in part_features.items():
            excel_data.append({
                "BOM 階層": 0, "所屬父階": "無 (頂層)", "節點類型": "⚙️ 單一零件",
                "特徵代號": f"零件 {custom_part_num}",
                "名稱 / 幾何類型": name, "數量 / 面數": 1, "幾何參數": "", "接觸配合 (Mating)": "", "公差代碼 (PMI)": "", "Face ID": "純幾何體"
            })
            
            feat_counters = {'P': 1, 'S': 1, 'H': 1, 'F': 1}
            
            for f_type, param_group in features.items():
                for param_str, f_ids in param_group.items():
                    for fid in f_ids:
                        has_pmi = str(fid) in pmi_mapping
                        
                        pmi_str = " | ".join(sorted(list(pmi_mapping[str(fid)]))) if has_pmi else "ideal"
                        
                        if not has_pmi:
                            if f_type in ['CONICAL_SURFACE', 'TOROIDAL_SURFACE', 'SPHERICAL_SURFACE']: continue
                            if f_type == 'CYLINDRICAL_SURFACE':
                                r_match = re.search(r'半徑 R=([-\d\.]+)', param_str)
                                if r_match and float(r_match.group(1)) <= 6.0: continue
                                
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
                                
                        node_icon = "🎯 帶公差面" if has_pmi else "🔻 特徵面"
                        excel_data.append({
                            "BOM 階層": 1, "所屬父階": name, "節點類型": node_icon,
                            "特徵代號": feat_code,
                            "名稱 / 幾何類型": f_type, "數量 / 面數": 1, "幾何參數": param_str, "接觸配合 (Mating)": "", "公差代碼 (PMI)": pmi_str, "Face ID": f"#{fid}"
                        })

    try:
        with pd.ExcelWriter(output_excel_path, engine='openpyxl') as writer:
            pd.DataFrame(excel_data).to_excel(writer, index=False, sheet_name='代碼公差總表')
            worksheet = writer.sheets['代碼公差總表']
            for col in worksheet.columns:
                column = col[0].column_letter
                if column == 'D': 
                    worksheet.column_dimensions[column].width = 15
                else:
                    worksheet.column_dimensions[column].width = min(max([len(str(c.value)) for c in col] + [0]) + 2, 70)
        print(f"\n✅ 大功告成！已產出包含公差代碼的報表：{output_excel_path}")
    except PermissionError:
        print(f"\n⚠️ 寫入失敗！請檢查 Excel 檔案是否正被開啟著？\n👉 請將 '{output_excel_path}' 關閉後，再執行一次程式！")

# ================= 執行區塊 =================
if __name__ == "__main__":
    file_dir = r"C:\Users\tony\Downloads" 
    stp_file = os.path.join(file_dir, "軸承座-3.STP") 
    sfa_excel = os.path.join(file_dir, "軸承座-3-sfa.xlsx")
    
    print("="*50)
    user_input_num = input("📝 請輸入這個圖檔的專屬零件編號 (例如: 1, A, PartX): ")
    print("="*50)
    
    output_excel = os.path.join(file_dir, f"軸承座_{user_input_num}_公差標準代碼表.xlsx")
    export_sfa_bom_mbd_excel(stp_file, sfa_excel, output_excel, user_input_num)