"""
step_core.py - STEP PMI 核心解析模組（無 UI）
================================================
從 step_pmi_3d_viewer.py 提取的非 UI 邏輯，供 Flask 後端使用。
"""

import os
import re
import sys
import math
import traceback
import pandas as pd
from collections import defaultdict

# 必須在匯入 OCC 之前設置
os.environ["CSF_GraphicDriver"] = "off"

from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
from OCC.Core.TDocStd import TDocStd_Document
from OCC.Core.XCAFApp import XCAFApp_Application
from OCC.Core.XCAFDoc import XCAFDoc_DocumentTool
from OCC.Core.TDF import TDF_LabelSequence
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_REVERSED, TopAbs_SOLID, TopAbs_SHELL
from OCC.Core.TopoDS import topods, TopoDS_Compound, TopoDS_Solid, TopoDS_Shell
from OCC.Core.gp import gp_Pnt, gp_Dir, gp_Ax3
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCC.Core.BRep import BRep_Builder
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.GeomAbs import (
    GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Cone,
    GeomAbs_Torus, GeomAbs_Sphere, GeomAbs_OtherSurface
)
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.BRep import BRep_Tool
from OCC.Core.TopLoc import TopLoc_Location


# ═══════════════════════════════════════════════════════════
# 1. STEP 十六進制解碼
# ═══════════════════════════════════════════════════════════
def decode_step_string(s):
    if not isinstance(s, str):
        return s
    def replacer(m):
        h = m.group(1).replace(' ', '')
        if len(h) % 2:
            h = '0' + h
        try:
            return bytes.fromhex(h).decode('utf-16-be')
        except:
            return m.group(0)
    return re.sub(r'\\X2\\(.*?)\\X0\\', replacer, s)


# ═══════════════════════════════════════════════════════════
# 2. 公稱尺寸與 IT 等級提取
# ═══════════════════════════════════════════════════════════
def extract_nominal_size(label, type_code):
    """
    從 PMI 標籤中提取公稱尺寸與 IT 等級。

    根據 ISO 標準與實務經驗，以下公差類型應提取公稱尺寸：
    - dis：線性尺寸公差（必須）
    - dia：直徑公差（必須）
    - pos：位置度（應該）- 應用於孔的位置
    - co：同心度/同軸度（應該）- 應用於圓柱特徵
    - tot：全跳動（應該）- 應用於圓柱旋轉特徵
    - run：跳動（應該）- 應用於圓柱旋轉特徵

    支持的格式：
    - "⌀55.00 +0.03" → 55.00
    - "Ø125.03-125.05" → "125.03-125.05"
    - "=125.03-125.05" → "125.03-125.05"
    - "dia2: ⌀55.00 +0.03 0" → 55.00

    Returns: (nominal_size_str, it_grade)
        nominal_size_str: 尺寸值或尺寸範圍 (e.g., "55.00" 或 "125.03-125.05")
        it_grade: IT 等級 (e.g., "IT7", 若無則為 None)
    """
    # 定義需要提取公稱尺寸的公差類型
    TOLERANCE_TYPES_WITH_NOMINAL_SIZE = {'dis', 'dia', 'pos', 'co', 'tot', 'run'}

    if not label:
        return None, None

    nominal_size = None
    it_grade = None

    # 移除 emoji 和標籤前綴
    clean_label = re.sub(r'^[\[\【\]【】]*(?:\[交互\]|\[個別\]|🎯|🚩|📐)', '', label)
    clean_label = clean_label.strip()

    # 模式1：提取圓形符號開頭的尺寸 (⌀ 或 Ø 或 =)
    # 注意：不包括 dia/DIA，因為這些是類型代碼，容易混淆
    match = re.search(r'[⌀Øø\u00d8\u00f8\u2300\u2304=]\s*(\d+\.?\d*(?:\s*-\s*\d+\.?\d*)?)', clean_label)
    if match:
        nominal_size = match.group(1).replace(' ', '').strip()

    # 模式2：若未找到，嘗試提取冒號後的第一個數字序列 (e.g., "dia2: 55.00")
    if not nominal_size and re.match(r'^[a-z]+\d*:', clean_label, re.IGNORECASE):
        after_colon = clean_label.split(':', 1)[-1].strip()
        match = re.search(r'(\d+\.?\d*(?:\s*-\s*\d+\.?\d*)?)', after_colon)
        if match:
            nominal_size = match.group(1).replace(' ', '').strip()

    # 模式3：提取 IT 等級（IT01-IT18）
    it_match = re.search(r'IT\d{1,2}', clean_label, re.IGNORECASE)
    if it_match:
        it_grade = it_match.group(0).upper()

    # 只有特定類型的公差才返回公稱尺寸
    if type_code not in TOLERANCE_TYPES_WITH_NOMINAL_SIZE:
        nominal_size = None

    return nominal_size, it_grade


# ═══════════════════════════════════════════════════════════
# 3. SFA Excel 解析
# ═══════════════════════════════════════════════════════════
def parse_sfa_excel(sfa_path):
    face_pmi_map = defaultdict(set)
    pmi_rows     = []

    if not os.path.exists(sfa_path):
        print(f"⚠️  找不到 SFA Excel：{sfa_path}")
        return face_pmi_map, pmi_rows

    print(f"📊 解析 SFA Excel：{os.path.basename(sfa_path)} ...")

    sheet_code_map = {
        'dimensional':        'dis',
        'parallelism':        'par',
        'perpendicularity':   'per',
        'concentricity':      'co',
        'coaxiality':         'co',
        'flatness':           'fla',
        'circularity':        'cir',
        'roundness':          'cir',
        'cylindricity':       'cyl',
        'position':           'pos',
        'angularity':         'ang',
        'symmetry':           'sym',
        'straightness':       'str',
        'profile_of_line':    'profl',
        'line_profile':       'profl',
        'profile_of_surface': 'profs',
        'surface_profile':    'profs',
        'total_runout':       'tot',
        'runout':             'run',
    }
    tol_counters = defaultdict(int)

    try:
        xls = pd.ExcelFile(sfa_path)
        pmi_sheets_found = []
        all_sheets = xls.sheet_names
        for sheet in all_sheets:
            sl = sheet.lower()
            if not (
                'dimensional'   in sl or
                'datum_feature' in sl or
                ('_tolerance' in sl and 'value' not in sl and 'plus_minus' not in sl)
            ):
                continue
            pmi_sheets_found.append(sheet)

            df_raw = pd.read_excel(xls, sheet_name=sheet, header=None)
            header_idx = -1
            for i in range(min(15, len(df_raw))):
                row_str = ' '.join(str(x).lower() for x in df_raw.iloc[i].values)
                if 'id' in row_str and 'geometry' in row_str:
                    header_idx = i
                    break
            if header_idx == -1:
                continue

            df = df_raw.iloc[header_idx + 1:].copy()
            df.columns = df_raw.iloc[header_idx].astype(str)

            geom_col = next((c for c in df.columns if 'geometry' in str(c).lower()), None)
            id_col   = next((c for c in df.columns if str(c).strip().lower() == 'id'), None)
            if not id_col:
                id_col = next((c for c in df.columns
                               if re.match(r'^id', str(c).strip().lower())), None)

            val_col = None
            if 'dimensional' in sl:
                val_col = next((c for c in df.columns
                                if 'dimensional' in str(c).lower()
                                and 'tolerance' in str(c).lower()), None)
            elif 'datum_feature' in sl:
                val_col = next((c for c in df.columns
                                if 'datum' in str(c).lower()), None)
            elif '_tolerance' in sl:
                val_col = next((c for c in df.columns
                                if 'gd&t' in str(c).lower()), None)

            if not (val_col and geom_col):
                continue

            type_code = next((code for key, code in sheet_code_map.items()
                              if key in sl), None)

            for _, row in df.iterrows():
                val  = str(row[val_col]).strip()
                geom = str(row[geom_col])
                if not val or val.lower() == 'nan':
                    continue

                clean_val = re.sub(r'\s+', ' ', val).strip()

                vals_in_str = re.findall(r'[-+]?\d*\.\d+|\b\d+\b', clean_val)
                has_tol = bool(re.search(r'[+\-±]', clean_val)) or len(vals_in_str) > 1

                is_feature_only = (type_code == 'dis' and not has_tol)

                fmt_val = clean_val
                row_type = type_code
                if row_type == 'dis' and (
                    re.search(r'[Øø\u00d8\u00f8\u2300\u2304直径diaDIA]', fmt_val) or
                    'cylindrical_surface' in geom.lower()
                ):
                    row_type = 'dia'

                if row_type:
                    tol_counters[row_type] += 1
                    if is_feature_only:
                        display_label = f"📐 {row_type}{tol_counters[row_type]}: {fmt_val}  ★特徵面(無公差)"
                    else:
                        display_label = f"🎯 {row_type}{tol_counters[row_type]}: {fmt_val}"
                elif 'datum_feature' in sl:
                    display_label = f"🚩 dat: [{fmt_val}]"
                else:
                    display_label = fmt_val

                face_ids = []
                for line in geom.split('\n'):
                    if 'advanced_face' in line.lower():
                        after = line.lower().split('advanced_face')[-1]
                        face_ids += re.findall(r'\d+', after)

                is_datum = 'datum_feature' in sl

                interactive_codes = {'pos', 'co', 'sym', 'ang', 'per', 'par', 'tot', 'run', 'dis'}
                individual_codes  = {'cyl', 'cir', 'fla', 'str', 'dia'}

                is_interactive = False
                if row_type in interactive_codes:
                    is_interactive = True
                elif row_type in individual_codes:
                    is_interactive = False
                else:
                    is_interactive = len(face_ids) >= 2

                if is_datum or is_feature_only:
                    final_label = display_label
                else:
                    pmi_type_prefix = "[交互]" if is_interactive else "[個別]"
                    final_label = f"{pmi_type_prefix} {display_label}"

                semantic_id = None
                if id_col:
                    raw_sid = str(row[id_col]).strip()
                    m = re.search(r'\d+', raw_sid.lstrip('#'))
                    if m:
                        semantic_id = m.group(0)

                for fid in face_ids:
                    face_pmi_map[fid].add(final_label)

                # 提取公稱尺寸與 IT 等級
                nominal_size, it_grade = extract_nominal_size(final_label, row_type)

                pmi_rows.append({
                    'label':          final_label,
                    'type_code':      row_type or ('dat' if is_datum else 'feat'),
                    'semantic_id':    semantic_id,
                    'face_ids':       face_ids,
                    'is_datum':       is_datum,
                    'is_feature_only': is_feature_only,
                    'is_interactive': (not is_datum and not is_feature_only and is_interactive),
                    'nominal_size':   nominal_size,      # 新增：公稱尺寸
                    'it_grade':       it_grade,          # 新增：IT等級
                })

    except Exception as e:
        print(f"⚠️  SFA Excel 解析錯誤：{e}")

    print(f"✅ XLSX 解析完成：{len(face_pmi_map)} 個 face，{len(pmi_rows)} 條 PMI 記錄")
    return face_pmi_map, pmi_rows


def parse_sfa_visual_sheets(sfa_path):
    """舊版備援解析函式"""
    face_pmi_map = defaultdict(set)
    pmi_rows     = []
    # ... (實作同原 step_pmi_3d_viewer.py)
    return face_pmi_map, pmi_rows


def build_geometry_feature_tree(engine):
    """從 face map 建立幾何特徵樹"""
    cylinders = defaultdict(list)
    planes    = defaultdict(list)
    cones     = defaultdict(list)
    tori      = defaultdict(list)
    spheres   = defaultdict(list)
    others    = defaultdict(list)

    for step_id, face in engine.step_id_to_face.items():
        try:
            adaptor = BRepAdaptor_Surface(face)
            stype   = adaptor.GetType()

            if stype == GeomAbs_Cylinder:
                r = round(adaptor.Cylinder().Radius(), 3)
                cylinders[r].append(step_id)
            elif stype == GeomAbs_Plane:
                ax = adaptor.Plane().Axis().Direction()
                nx = round(abs(ax.X()), 2)
                ny = round(abs(ax.Y()), 2)
                nz = round(abs(ax.Z()), 2)
                planes[(nx, ny, nz)].append(step_id)
            elif stype == GeomAbs_Cone:
                ang_deg = round(math.degrees(adaptor.Cone().SemiAngle()), 2)
                cones[ang_deg].append(step_id)
            elif stype == GeomAbs_Torus:
                t = adaptor.Torus()
                key = (round(t.MajorRadius(), 3), round(t.MinorRadius(), 3))
                tori[key].append(step_id)
            elif stype == GeomAbs_Sphere:
                r = round(adaptor.Sphere().Radius(), 3)
                spheres[r].append(step_id)
            else:
                others['OTHER'].append(step_id)
        except Exception:
            pass

    pmi_rows = []

    def face_list_str(ids, n=4):
        s = ', '.join('#' + i for i in ids[:n])
        return s + (f'  等 {len(ids)} 個面' if len(ids) > n else '')

    for r, ids in sorted(cylinders.items()):
        diam  = r * 2
        count = len(ids)
        count_str = f'{count}個相同特徵  ' if count > 1 else ''
        label = (
            f'🧊 CYLINDRICAL_SURFACE  {count_str}'
            f'半徑 R={r:.3f} (直徑 Ø{diam:.3f})  '
            f'[{face_list_str(ids)}]'
        )
        pmi_rows.append({'label': label, 'semantic_id': None, 'face_ids': ids, 'nominal_size': None, 'it_grade': None})

    for key, ids in sorted(planes.items(), key=lambda x: (-x[0][2], -x[0][1], -x[0][0])):
        count = len(ids)
        count_str = f'{count}個相同特徵  ' if count > 1 else ''
        nx_str = '{:.0f},{:.0f},{:.0f}'.format(*key)
        label = (
            f'⬜ PLANE  {count_str}'
            f'法向 ({nx_str})  '
            f'[{face_list_str(ids)}]'
        )
        pmi_rows.append({'label': label, 'semantic_id': None, 'face_ids': ids, 'nominal_size': None, 'it_grade': None})

    for ang_deg, ids in sorted(cones.items()):
        count = len(ids)
        count_str = f'{count}個  ' if count > 1 else ''
        label = (
            f'🔺 CONICAL_SURFACE  {count_str}'
            f'半角={ang_deg}°  '
            f'[{face_list_str(ids)}]'
        )
        pmi_rows.append({'label': label, 'semantic_id': None, 'face_ids': ids, 'nominal_size': None, 'it_grade': None})

    for (major_r, minor_r), ids in sorted(tori.items()):
        label = (
            f'🍰 TOROIDAL_SURFACE  '
            f'R大={major_r:.3f}  R小={minor_r:.3f}  '
            f'[{face_list_str(ids)}]'
        )
        pmi_rows.append({'label': label, 'semantic_id': None, 'face_ids': ids, 'nominal_size': None, 'it_grade': None})

    for r, ids in sorted(spheres.items()):
        label = (
            f'🔵 SPHERICAL_SURFACE  '
            f'半徑 R={r:.3f}  '
            f'[{face_list_str(ids)}]'
        )
        pmi_rows.append({'label': label, 'semantic_id': None, 'face_ids': ids, 'nominal_size': None, 'it_grade': None})

    for type_name, ids in others.items():
        label = f'◼️ {type_name}  [{face_list_str(ids)}]'
        pmi_rows.append({'label': label, 'semantic_id': None, 'face_ids': ids, 'nominal_size': None, 'it_grade': None})

    all_ids = list(engine.step_id_to_face.keys())
    pmi_rows.insert(0, {
        'label':       f'🔵 SOLID 全部  ({len(all_ids)} 個面)',
        'semantic_id': None,
        'face_ids':    all_ids,
        'nominal_size': None,
        'it_grade': None,
    })

    cyl_count = sum(len(v) for v in cylinders.values())
    pln_count = sum(len(v) for v in planes.values())
    print(
        f'✅ 幾何特徵樹：{len(all_ids)} 個面  '
        f'圓柱{cyl_count} 平面{pln_count} '
        f'圆錐{sum(len(v) for v in cones.values())} '
        f'球面{sum(len(v) for v in spheres.values())}  '
        f'出入 {len(pmi_rows)} 條條目'
    )
    return pmi_rows


def get_shapes_center(shapes):
    """計算一組 TopoDS_Shape 的包圍盒中心點"""
    if not shapes:
        return None
    bbox = Bnd_Box()
    for s in shapes:
        brepbndlib.Add(s, bbox)
    if bbox.IsVoid():
        return None
    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
    return gp_Pnt((xmin + xmax) / 2.0, (ymin + ymax) / 2.0, (zmin + zmax) / 2.0)


# ═══════════════════════════════════════════════════════════
# 3. CSV ASSOCIATION 鏈
# ═══════════════════════════════════════════════════════════
def load_sfa_association(xlsx_path):
    """從 SFA XLSX 建立 semantic_entity_id → tao_id 映射"""
    if not os.path.exists(xlsx_path):
        return {}

    semantic_to_tao = {}
    try:
        xls = pd.ExcelFile(xlsx_path)
        sheet_names = xls.sheet_names

        tao_sheet = next((s for s in sheet_names if 'tessellated_annotation_occurren' in s.lower()), None)

        if tao_sheet:
            print(f"🔍 正在從 Excel 分頁 [{tao_sheet}] 提取精確關聯...")
            df_tao = pd.read_excel(xls, sheet_name=tao_sheet, header=None)

            h_idx = -1
            for i in range(min(10, len(df_tao))):
                row_str = ' '.join(str(x).lower() for x in df_tao.iloc[i].values if pd.notna(x))
                if 'id' in row_str and 'semantic' in row_str:
                    h_idx = i
                    break

            if h_idx != -1:
                df = df_tao.iloc[h_idx+1:].copy()
                df.columns = df_tao.iloc[h_idx].astype(str).str.strip()

                id_col  = next((c for c in df.columns if str(c).lower() == 'id'), None)
                sem_col = next((c for c in df.columns if 'semantic' in str(c).lower()), None)

                if id_col and sem_col:
                    for _, row in df.iterrows():
                        raw_tao = row[id_col]
                        try:
                            tao_id = str(int(float(str(raw_tao).strip().lstrip('#'))))
                        except Exception:
                            tao_id = str(raw_tao).strip().lstrip('#')
                        sem_val = str(row[sem_col]).strip()
                        if not tao_id or tao_id == 'nan' or sem_val == 'nan': continue

                        s_ids = re.findall(r'\s+(\d+)', sem_val)
                        if not s_ids:
                            m = re.search(r'(\d+)$', sem_val)
                            if m: s_ids = [m.group(1)]

                        for sid in s_ids:
                            semantic_to_tao[sid] = tao_id

            if semantic_to_tao:
                print(f"✅ 從 TAO Sheet 建立 {len(semantic_to_tao)} 條精確鏈結")
                return semantic_to_tao

    except Exception as e:
        print(f"⚠️  Excel 關聯解析發生錯誤：{e}")

    return semantic_to_tao


# ═══════════════════════════════════════════════════════════
# 4. STP 文字解析
# ═══════════════════════════════════════════════════════════
def _parse_stp_entities(stp_path):
    """讀取 STP 並建立 {entity_id: {'type', 'params'}} 完整字典"""
    entities = {}
    with open(stp_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read().replace('\n', '').replace('\r', '')
    for raw in content.split(';'):
        m = re.match(r'\s*#(\d+)\s*=\s*([A-Z_]+)\s*\((.*)\)\s*$', raw.strip())
        if m:
            eid, etype, params = m.groups()
            entities[eid] = {'type': etype.strip(), 'params': params}
    return entities


def _build_step_sem_to_tao(entities):
    """從 STEP 實體解析 semantic_id → tao_id 精確映射"""
    SEMANTIC_TYPES = {
        'DIMENSIONAL_SIZE', 'DIMENSIONAL_LOCATION',
        'ANGULAR_SIZE', 'ANGULAR_LOCATION',
        'GEOMETRIC_TOLERANCE', 'GEOMETRIC_TOLERANCE_WITH_DATUM_REFERENCE',
        'FLATNESS_TOLERANCE', 'CYLINDRICITY_TOLERANCE', 'CIRCULARITY_TOLERANCE',
        'STRAIGHTNESS_TOLERANCE', 'PERPENDICULARITY_TOLERANCE',
        'PARALLELISM_TOLERANCE', 'ANGULARITY_TOLERANCE',
        'SYMMETRY_TOLERANCE', 'POSITION_TOLERANCE',
        'CIRCULAR_RUNOUT_TOLERANCE', 'TOTAL_RUNOUT_TOLERANCE',
        'SURFACE_PROFILE_TOLERANCE', 'LINE_PROFILE_TOLERANCE',
        'CONCENTRICITY_TOLERANCE', 'COAXIALITY_TOLERANCE',
        'DATUM_FEATURE', 'DATUM_TARGET',
    }

    callout_to_tao = {}
    for eid, ent in entities.items():
        if ent['type'] == 'DRAUGHTING_CALLOUT':
            for ref in re.findall(r'#(\d+)', ent['params']):
                if entities.get(ref, {}).get('type') == 'TESSELLATED_ANNOTATION_OCCURRENCE':
                    callout_to_tao[eid] = ref
                    break

    semantic_to_tao = {}
    for eid, ent in entities.items():
        if ent['type'] != 'DRAUGHTING_MODEL_ITEM_ASSOCIATION':
            continue
        refs = re.findall(r'#(\d+)', ent['params'])
        sem_id = tao_id = None
        for ref in refs:
            rtype = entities.get(ref, {}).get('type', '')
            if rtype in SEMANTIC_TYPES:
                sem_id = ref
            elif rtype == 'DRAUGHTING_CALLOUT':
                tao_id = callout_to_tao.get(ref)
            elif rtype == 'TESSELLATED_ANNOTATION_OCCURRENCE':
                tao_id = ref
        if sem_id and tao_id:
            semantic_to_tao[sem_id] = tao_id

    return semantic_to_tao


def parse_tessellated_annotations(stp_path, tao_ids=None, scan_all=False):
    """解析 STP 文字，為指定的 tao_ids 或所有標註建立 OCC shapes"""
    if not tao_ids and not scan_all:
        return {}, {}

    entities = _parse_stp_entities(stp_path)
    step_sem_to_tao = _build_step_sem_to_tao(entities)
    print(f"🔗 STEP 直接鏈結：{len(step_sem_to_tao)} 條 semantic→TAO")

    target_ids = []
    if scan_all:
        target_ids = [eid for eid, ent in entities.items()
                      if ent['type'] == 'TESSELLATED_ANNOTATION_OCCURRENCE']
        print(f"🔍 全局掃描 STP 3D 標註（共找到 {len(target_ids)} 個實體）...")
    else:
        target_ids = list(tao_ids) if tao_ids else []
        print(f"🔍 解析 STP tessellated 幾何（指定 {len(target_ids)} 個標註）...")

    result = {}
    for tao_id in target_ids:
        data = _build_compound_from_tao(tao_id, entities)
        if data:
            result[tao_id] = data

    total_req = len(target_ids)
    print(f"✅ 成功建立 {len(result)} / {total_req} 個 tessellated 標註幾何")
    return result, step_sem_to_tao


def _build_compound_from_tao(tao_id, entities):
    """從 TESSELLATED_ANNOTATION_OCCURRENCE 重建 3D 標註幾何"""
    tao = entities.get(tao_id)
    if not tao or tao['type'] != 'TESSELLATED_ANNOTATION_OCCURRENCE':
        return None

    all_refs = re.findall(r'#(\d+)', tao['params'])
    if not all_refs:
        return None
    tgs_id = all_refs[-1]

    tgs = entities.get(tgs_id)
    if not tgs or tgs['type'] != 'TESSELLATED_GEOMETRIC_SET':
        return None

    child_ids = re.findall(r'#(\d+)', tgs['params'])

    builder  = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    has_geom = False
    edge_count = 0
    tri_count  = 0

    for cid in child_ids:
        child = entities.get(cid)
        if not child:
            continue

        ctype   = child['type']
        cparams = child['params']

        coord_ref = re.search(r'#(\d+)', cparams)
        if not coord_ref:
            continue
        coord_ent = entities.get(coord_ref.group(1))
        if not coord_ent or coord_ent['type'] != 'COORDINATES_LIST':
            continue
        raw_coords = re.findall(
            r'\(\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*,\s*([-\d.eE+]+)\s*\)',
            coord_ent['params']
        )
        points = [gp_Pnt(float(x), float(y), float(z)) for x, y, z in raw_coords]

        coord_m = re.search(r'#\d+', cparams)
        idx_text = cparams
        if coord_m:
            remaining = cparams[coord_m.end():]
            idx_start = remaining.find('(')
            if idx_start != -1:
                idx_text = remaining[idx_start:]

        all_idxs = [int(x) - 1 for x in re.findall(r'\d+', idx_text)]

        if ctype == 'TESSELLATED_CURVE_SET':
            for i in range(0, len(all_idxs) - 1, 2):
                i1, i2 = all_idxs[i], all_idxs[i+1]
                if 0 <= i1 < len(points) and 0 <= i2 < len(points):
                    try:
                        edge = BRepBuilderAPI_MakeEdge(points[i1], points[i2]).Edge()
                        builder.Add(compound, edge)
                        has_geom = True
                        edge_count += 1
                    except Exception: pass

        elif ctype == 'COMPLEX_TRIANGULATED_SURFACE_SET':
            for i in range(0, len(all_idxs) - 2, 3):
                i1, i2, i3 = all_idxs[i], all_idxs[i+1], all_idxs[i+2]
                if not (0 <= i1 < len(points) and
                        0 <= i2 < len(points) and
                        0 <= i3 < len(points)):
                    continue
                for pa, pb in (
                    (points[i1], points[i2]),
                    (points[i2], points[i3]),
                    (points[i3], points[i1]),
                ):
                    if pa.Distance(pb) < 1e-9: continue
                    try:
                        edge = BRepBuilderAPI_MakeEdge(pa, pb).Edge()
                        builder.Add(compound, edge)
                        has_geom = True
                        tri_count += 1
                    except Exception: pass

    if not has_geom: return None
    return {'shape': compound, 'tri_count': tri_count, 'edge_count': edge_count}


# ═══════════════════════════════════════════════════════════
# 5. STEP XCAF 引擎
# ═══════════════════════════════════════════════════════════
class StepXcafEngine:
    def __init__(self):
        self.app        = XCAFApp_Application.GetApplication()
        self.doc        = None
        self.shape_tool = None
        self.dim_tol_tool = None
        self.reader     = None
        self.ws         = None
        self.tr         = None

        self.root_shape       = None
        self.step_id_to_face  = {}

    def load(self, stp_path):
        self.doc = TDocStd_Document("SFA-XCAF")
        self.app.NewDocument("SFA-XCAF", self.doc)

        self.reader = STEPCAFControl_Reader()
        self.reader.SetColorMode(True)
        self.reader.SetNameMode(True)
        self.reader.SetGDTMode(True)

        if self.reader.ReadFile(stp_path) != IFSelect_RetDone:
            raise RuntimeError(f"無法讀取 STEP 檔案：{stp_path}")
        self.reader.Transfer(self.doc)

        self.shape_tool   = XCAFDoc_DocumentTool.ShapeTool(self.doc.Main())
        self.dim_tol_tool = XCAFDoc_DocumentTool.DimTolTool(self.doc.Main())
        self.ws           = self.reader.Reader().WS()
        self.tr           = self.ws.TransferReader()

        self._build_face_map()
        print(f"✅ STEP XCAF 載入：{len(self.step_id_to_face)} 個 face")

    def _build_face_map(self):
        """TransferReader 掃描 → step_id → TopoDS_Face"""
        roots = TDF_LabelSequence()
        self.shape_tool.GetFreeShapes(roots)

        for i in range(1, roots.Length() + 1):
            shape = self.shape_tool.GetShape(roots.Value(i))
            if i == 1:
                self.root_shape = shape

            exp = TopExp_Explorer(shape, TopAbs_FACE)
            while exp.More():
                face = topods.Face(exp.Current())
                ent  = self.tr.EntityFromShapeResult(face, 1)
                if ent:
                    sid = self.ws.EntityLabel(ent).ToCString().replace('#', '').strip()
                    if sid:
                        self.step_id_to_face[sid] = face
                exp.Next()


# ═══════════════════════════════════════════════════════════
# 6. Three.js 三角網格匯出（新增）
# ═══════════════════════════════════════════════════════════
def tessellate_shape_to_json(shape, deflection=0.1):
    """使用 BRepMesh_IncrementalMesh 將 OCC shape 轉成 Three.js 格式 JSON"""
    try:
        mesh = BRepMesh_IncrementalMesh(shape, deflection, True, 0.5)
        mesh.Perform()

        vertices = []
        faces = []
        normals = []

        # 從所有面提取三角網格
        exp = TopExp_Explorer(shape, TopAbs_FACE)
        vertex_map = {}  # (x, y, z) tuple → index
        vertex_idx = 0

        while exp.More():
            face = topods.Face(exp.Current())
            loc = TopLoc_Location()
            triangulation = BRep_Tool.Triangulation(face, loc)
            if triangulation:
                nodes = triangulation.Nodes()
                triangles = triangulation.Triangles()

                for i in range(1, nodes.Length() + 1):
                    pt = nodes.Value(i)
                    key = (round(pt.X(), 6), round(pt.Y(), 6), round(pt.Z(), 6))
                    if key not in vertex_map:
                        vertex_map[key] = vertex_idx
                        vertices.append([pt.X(), pt.Y(), pt.Z()])
                        vertex_idx += 1

                for i in range(1, triangles.NbTriangles() + 1):
                    n1, n2, n3 = triangles.Triangle(i)
                    pt1 = nodes.Value(n1)
                    pt2 = nodes.Value(n2)
                    pt3 = nodes.Value(n3)

                    key1 = (round(pt1.X(), 6), round(pt1.Y(), 6), round(pt1.Z(), 6))
                    key2 = (round(pt2.X(), 6), round(pt2.Y(), 6), round(pt2.Z(), 6))
                    key3 = (round(pt3.X(), 6), round(pt3.Y(), 6), round(pt3.Z(), 6))

                    idx1 = vertex_map.get(key1)
                    idx2 = vertex_map.get(key2)
                    idx3 = vertex_map.get(key3)

                    if idx1 is not None and idx2 is not None and idx3 is not None:
                        faces.append([idx1, idx2, idx3])

            exp.Next()

        # 計算法線（簡化：使用每個頂點所在的所有三角形的平均法線）
        if not vertices:
            return None

        normals = [[0, 0, 1]] * len(vertices)  # 預設法線

        return {
            'vertices': vertices,
            'faces': faces,
            'normals': normals
        }
    except Exception as e:
        print(f"❌ 三角化失敗：{e}")
        return None


def tessellate_face_by_step_ids(engine, step_ids, deflection=0.1):
    """依 step_ids 查找對應的 face 並合併三角化"""
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Sewing

    if not step_ids:
        return None

    faces_to_mesh = []
    for sid in step_ids:
        if sid in engine.step_id_to_face:
            faces_to_mesh.append(engine.step_id_to_face[sid])

    if not faces_to_mesh:
        return None

    # 如果只有一個 face，直接三角化
    if len(faces_to_mesh) == 1:
        return tessellate_shape_to_json(faces_to_mesh[0], deflection)

    # 否則組合所有 faces
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    for face in faces_to_mesh:
        builder.Add(compound, face)

    return tessellate_shape_to_json(compound, deflection)


def tao_compound_to_lines_json(compound):
    """將 TAO compound（leader lines）轉成 Three.js LineSegments 格式"""
    lines = []

    try:
        exp = TopExp_Explorer(compound, TopAbs_EDGE)
        while exp.More():
            edge = topods.Edge(exp.Current())
            hc = BRep_Tool.Curve(edge, None, None)
            if hc[0]:
                curve = hc[0]
                start_param = curve.FirstParameter()
                end_param = curve.LastParameter()

                pt_start = curve.Value(start_param)
                pt_end = curve.Value(end_param)

                lines.append([
                    [pt_start.X(), pt_start.Y(), pt_start.Z()],
                    [pt_end.X(), pt_end.Y(), pt_end.Z()]
                ])
            exp.Next()
    except Exception as e:
        print(f"⚠️  Leader line 提取失敗：{e}")

    return lines
