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
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_REVERSED, TopAbs_SOLID, TopAbs_SHELL
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

    # 移除所有 emoji 和標籤前綴（可能有多個混合）
    clean_label = re.sub(r'^(?:\[交互\]|\[個別\]|🎯|🚩|📐|\s)+', '', label)
    clean_label = clean_label.strip()

    # 模式1：提取圓形符號開頭的尺寸 (⌀ 或 Ø 或 =)
    # 注意：只取基本尺寸，不包含公差偏差
    match = re.search(r'[⌀Øø\u00d8\u00f8\u2300\u2304=]\s*(\d+\.?\d*)', clean_label)
    if match:
        nominal_size = match.group(1).strip()

    # 模式2：若未找到，嘗試提取冒號後的第一個數字序列 (e.g., "dia2: 55.00")
    if not nominal_size and re.match(r'^[a-z]+\d*:', clean_label, re.IGNORECASE):
        after_colon = clean_label.split(':', 1)[-1].strip()
        match = re.search(r'(\d+\.?\d*)', after_colon)
        if match:
            nominal_size = match.group(1).strip()

    # 模式3：提取 IT 等級（IT01-IT18）
    it_match = re.search(r'IT\d{1,2}', clean_label, re.IGNORECASE)
    if it_match:
        it_grade = it_match.group(0).upper()

    # 模式4：ISO 配合代號（如 H8, H7, f6, g6, JS5, ZA14）
    # 格式：1-3 個字母 + 1-2 位數字（等級 1-18）
    # 排除已知的公差類型縮寫，避免誤判如 dia2、par1 等
    if not it_grade:
        _EXCLUDED_CODES = {
            'IT', 'DIA', 'DIS', 'DAT', 'PAR', 'PER', 'CYL', 'CIR', 'RUN',
            'TOT', 'POS', 'ANG', 'SYM', 'FLA', 'CO', 'STR', 'FLT', 'RAD',
            'NAN', 'INF',
        }
        for fc_letter, fc_num in re.findall(r'(?:(?<=\d)|(?<!\w))([A-Za-z]{1,3})(\d{1,2})(?!\w)', clean_label):
            grade = int(fc_num)
            if 1 <= grade <= 18 and fc_letter.upper() not in _EXCLUDED_CODES:
                it_grade = f"IT{grade}"
                break

    # 只有特定類型的公差才返回公稱尺寸
    if type_code not in TOLERANCE_TYPES_WITH_NOMINAL_SIZE:
        nominal_size = None

    return nominal_size, it_grade


def extract_tolerance_value(label):
    """
    從 PMI 標籤中提取公差數值（公差帶寬度）。

    規則：
    - 單邊公差 (0 -0.08)：兩數差的絕對值 = 0.08
    - 雙邊公差 (± 0.05)：± 後的數 × 2 = 0.1
    - 幾何公差 (▱ | 0.002)：取 | 後的數 = 0.002
    - 複合公差 (-0.12 -0.18)：兩數差的絕對值 = 0.06

    Returns: tolerance_value_str or None
    """
    if not label:
        return None

    import re
    # 移除所有 emoji 和標籤前綴（可能有多個混合）
    clean_label = re.sub(r'^(?:\[交互\]|\[個別\]|🎯|🚩|📐|\s)+', '', label)
    clean_label = clean_label.strip()

    tolerance_value = None

    # 模式1：幾何公差 (含有 | 符號，取 | 後的數字)
    if '|' in clean_label:
        parts = clean_label.split('|')
        for part in parts[1:]:
            match = re.search(r'(\d+\.?\d*)', part.strip())
            if match:
                tolerance_value = match.group(1)
                break

    # 模式2：雙邊公差 (± 符號)
    if not tolerance_value:
        match = re.search(r'±\s*(\d+\.?\d*)', clean_label)
        if match:
            val = float(match.group(1))
            result = val * 2
            tolerance_value = str(result)

    # 模式3：單邊或複合公差 (兩個帶符號的數字)
    # 對於 DIA/DIS：使用最後兩個數字（公差部分），避免混入公稱尺寸
    # 如: ⌀133.50 0 -0.08 → 取 0 和 -0.08，不取 133.50
    # 排除 ISO 配合代號中的等級數字（如 H8 中的 8），避免與公稱尺寸相減得出錯誤值
    if not tolerance_value:
        # 先找出配合代號後跟的等級數字，加入排除集合
        _fit_grade_strs = set()
        for _fc_letter, _fc_num in re.findall(r'(?:(?<=\d)|(?<!\w))([A-Za-z]{1,3})(\d{1,2})(?!\w)', clean_label):
            _grade = int(_fc_num)
            if 1 <= _grade <= 18:
                _fit_grade_strs.add(_fc_num)

        nums = re.findall(r'[-+]?\d+\.?\d*', clean_label)
        # 過濾掉純等級數字（如 '8' 來自 H8），只保留帶符號或含小數點的數字
        nums = [n for n in nums if n not in _fit_grade_strs or '.' in n or n.startswith(('+', '-'))]
        if len(nums) >= 2:
            try:
                val1 = float(nums[-2])
                val2 = float(nums[-1])
                diff = abs(val1 - val2)
                if diff > 0:
                    # 四舍五入到4位小数，避免浮点精度问题
                    tolerance_value = str(round(diff, 4))
            except (ValueError, IndexError):
                pass

    return tolerance_value


# ═══════════════════════════════════════════════════════════
# 3. SFA Excel 解析
# ═══════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════
# 1-3. 關聯交互參考公差與基準面的 Face ID
#      交互參考公差 = 本體特徵面 + 基準參考面的 Face ID
# ═══════════════════════════════════════════════════════════
def _link_interactive_tolerances_with_datums(pmi_rows):
    """
    第二階段處理：為交互參考公差關聯其基準面的 Face ID。

    交互參考公差應包含：
    - 本體特徵面 (feature)
    - 基準面 (datum reference)

    方法：
    1. 掃描標籤中的基準代號 (如 "| C" 或 "| A | B" 或 "| A ▽ ⎹ [B]")
    2. 查找對應的基準面行 (is_datum=True)
    3. 將基準面的 Face ID 添加到交互參考公差的 face_ids
    """
    # 首先建立基準面的查找表
    datum_lookup = {}  # datum_name -> {label, face_ids, ...}
    for row in pmi_rows:
        if row.get('is_datum'):
            # 從 label 提取基準代號，通常格式為 "🚩 dat: [C]" 或 "🚩 dat: [A]"
            dm = re.search(r'\[([A-Z0-9_-]+)\]', row['label'])
            if dm:
                datum_name = dm.group(1)
                datum_lookup[datum_name] = row

    # 掃描交互參考公差，關聯其基準面
    linked_count = 0
    for row in pmi_rows:
        if row.get('is_interactive'):
            label = row['label']
            original_fids = len(row.get('face_ids', []))

            # 格式範例：
            # - "[交互] 🎯 pos1: // | 0.002 | A"
            # - "[交互] 🎯 par2: // | 0.05 | A | B"
            # - "[交互] 🎯 per1: ... | 0.01 | A ▽ ⎹ [B]"   ← 基準 = A
            # - "[交互] 🎯 per3: Ø0.1 | A"

            found_datums = set()

            # 方法1：提取 "|" 與 "▽/⏊" 之間的字母（最精確）
            datum_matches = re.findall(r'\|\s*([A-Z])\s*[▽⏊]', label)
            for datum_name in datum_matches:
                if datum_name in datum_lookup and datum_name not in found_datums:
                    found_datums.add(datum_name)
                    datum_row = datum_lookup[datum_name]
                    for fid in datum_row['face_ids']:
                        if fid not in row['face_ids']:
                            row['face_ids'].append(fid)
                            linked_count += 1

            # 方法2：如果方法1沒找到，提取 "|" 後跟字母的部分（處理 "| A | B" 格式）
            if not found_datums and '|' in label:
                parts = label.split('|')
                for part in parts[1:]:  # 跳過第一個部分（公差值）
                    # 提取該部分開頭的純字母
                    m = re.match(r'\s*([A-Z])\s*', part)
                    if m:
                        datum_name = m.group(1)
                        if datum_name in datum_lookup and datum_name not in found_datums:
                            found_datums.add(datum_name)
                            datum_row = datum_lookup[datum_name]
                            for fid in datum_row['face_ids']:
                                if fid not in row['face_ids']:
                                    row['face_ids'].append(fid)
                                    linked_count += 1

    print(f"[二階段] 交互參考公差關聯完成：共添加 {linked_count} 個基準面 Face ID")
    return pmi_rows


# GD&T type-name (Sec. 8.4) → type_code  (for tessellated supplement)
_TAO_TYPE_MAP = {
    'parallelism':          'par',
    'perpendicularity':     'per',
    'angularity':           'ang',
    'flatness':             'fla',
    'straightness':         'str',
    'circularity':          'cir',
    'roundness':            'cir',
    'cylindricity':         'cyl',
    'position':             'pos',
    'concentricity':        'co',
    'coaxiality':           'co',
    'symmetry':             'sym',
    'total runout':         'tot',
    'total_runout':         'tot',
    'circular runout':      'run',
    'runout':               'run',
    'profile of line':      'profl',
    'profile of surface':   'profs',
}
# GD&T unicode symbols
_TYPE_SYMBOL = {
    'par':   '⫽',
    'per':   '⟂',
    'ang':   '∠',
    'fla':   '⏥',
    'str':   '⏤',
    'cir':   '○',
    'cyl':   '⌭',
    'pos':   '⊕',
    'co':    '◎',
    'sym':   '⌯',
    'tot':   '⌮',
    'run':   '↗',
    'profl': '⌒',
    'profs': '⌓',
}


def _supplement_graphic_pmi(xls, pmi_rows, face_pmi_map, tol_counters, sheet_code_map):
    """
    第三階段補充：掃描 tessellated_annotation_occurren 分頁，
    找出「只有圖形PMI、沒有語意PMI連結」的 GD&T 標註（Associated Semantic PMI 欄為空）。
    為這些標註建立佔位 PMI 記錄，使它們出現在 PMI 列表中並可連結至幾何面。
    """
    sheet_lower_map = {s.lower(): s for s in xls.sheet_names}
    tao_sheet_key = next(
        (orig for low, orig in sheet_lower_map.items() if 'tessellated_annotation' in low),
        None
    )
    if not tao_sheet_key:
        return

    df_raw = pd.read_excel(xls, sheet_name=tao_sheet_key, header=None)

    # 找 header 行（包含 'id'）
    header_idx = -1
    for i in range(min(5, len(df_raw))):
        if 'id' in str(df_raw.iloc[i, 0]).lower():
            header_idx = i
            break
    if header_idx == -1:
        return

    df = df_raw.iloc[header_idx + 1:].reset_index(drop=True)
    df.columns = df_raw.iloc[header_idx].astype(str).str.strip()

    # 定位欄位（欄名是多行標題，用包含關鍵字定位）
    id_col      = next((c for c in df.columns if str(c).strip().lower() == 'id'), None)
    name_col    = next((c for c in df.columns if str(c).strip().lower() == 'name'), None)
    type_col    = next((c for c in df.columns
                        if 'name' in str(c).lower() and 'sec' in str(c).lower()), None)
    geom_col    = next((c for c in df.columns
                        if 'associated geometry' in str(c).lower()
                        or ('associated' in str(c).lower() and 'geometry' in str(c).lower())), None)
    sem_col     = next((c for c in df.columns
                        if 'semantic' in str(c).lower()
                        or ('associated' in str(c).lower() and 'semantic' in str(c).lower())), None)

    if not all([id_col, type_col, geom_col]):
        print(f"  [TAO-SUPP] 無法定位欄位 id={id_col!r}, type={type_col!r}, geom={geom_col!r}")
        return

    # 已有語意PMI記錄的 type_code 集合（避免重複）
    existing_type_codes = {r.get('type_code') for r in pmi_rows if r.get('type_code')}

    added = 0
    for _, row in df.iterrows():
        tao_id_raw = str(row[id_col]).strip()
        if tao_id_raw == 'nan':
            continue

        # 只補充「沒有語意PMI連結」的標註
        sem_val = str(row[sem_col]).strip() if sem_col else 'nan'
        if sem_val and sem_val.lower() != 'nan':
            continue  # 已有語意PMI，不需補充

        # 取 GD&T 類型
        type_raw = str(row[type_col]).strip().lower()
        type_code = _TAO_TYPE_MAP.get(type_raw)
        if not type_code:
            continue  # 非 GD&T 形位公差（如 diameter dimension, datum 等），跳過

        # 如果語意PMI已有同類型記錄，跳過（語意 > 圖形）
        if type_code in existing_type_codes:
            continue

        # 從 Associated Geometry 欄提取 advanced_face ID
        geom_str = str(row[geom_col])
        face_ids = []
        for line in geom_str.split('\n'):
            if 'advanced_face' in line.lower():
                after = re.sub(r'.*advanced_face\s*', '', line, flags=re.IGNORECASE)
                ids = re.findall(r'\d+', after)
                face_ids.extend(ids)

        # 標註顯示名稱
        ann_name = str(row[name_col]).strip() if name_col else ''
        tol_counters[type_code] += 1
        sym = _TYPE_SYMBOL.get(type_code, '?')
        label = f"[交互] 📐 {type_code}{tol_counters[type_code]}: {sym} [圖形PMI]  {ann_name}"

        for fid in face_ids:
            face_pmi_map[fid].add(label)

        nominal_size, it_grade = extract_nominal_size(label, type_code)
        pmi_rows.append({
            'label':           label,
            'type_code':       type_code,
            'semantic_id':     None,
            'face_ids':        face_ids,
            'is_datum':        False,
            'is_feature_only': False,
            'is_interactive':  True,
            'nominal_size':    nominal_size,
            'it_grade':        it_grade,
            'tolerance_value': None,
        })
        added += 1
        print(f"  [TAO-SUPP] 補充圖形PMI: {label} → faces {face_ids}")

    if added:
        print(f"  [TAO-SUPP] 共補充 {added} 條圖形PMI記錄")


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
    xls = None

    try:
        xls = pd.ExcelFile(sfa_path)
        pmi_sheets_found = []
        all_sheets = xls.sheet_names

        # ── 預處理：讀取 datum_feature 表，建立 ID → face_ids 對應 ──
        sheet_lower_map = {s.lower(): s for s in all_sheets}
        datum_feature_faces = {}  # {datum_feature_id: face_id}

        # ── 預處理：從 dimensional_characteristic_repr 建立 shape_aspect_id → 公稱長度(mm) ──
        # 用於後續交叉查詢 PAR/FLA 等幾何公差的參考長度
        shape_aspect_length_map = {}  # {shape_aspect_id_str: float mm}
        _dcr_key = next((k for k in sheet_lower_map if 'dimensional_characteristic_repr' in k), None)
        if _dcr_key:
            try:
                df_dcr_raw = pd.read_excel(xls, sheet_name=sheet_lower_map[_dcr_key], header=None)
                _h = -1
                for _i in range(min(10, len(df_dcr_raw))):
                    _row_s = ' '.join(str(x).lower() for x in df_dcr_raw.iloc[_i].values)
                    if 'dimension' in _row_s and ('geometry' in _row_s or 'length' in _row_s):
                        _h = _i
                        break
                if _h >= 0:
                    df_dcr = df_dcr_raw.iloc[_h + 1:].copy()
                    df_dcr.columns = df_dcr_raw.iloc[_h].astype(str)
                    # 找「length/angle」欄（公稱值）與「Associated Geometry」欄
                    _len_col = next(
                        (c for c in df_dcr.columns
                         if 'length' in str(c).lower() and 'angle' in str(c).lower()
                         and 'name' not in str(c).lower() and 'prec' not in str(c).lower()),
                        None
                    )
                    _geo_col = next(
                        (c for c in df_dcr.columns
                         if 'associated' in str(c).lower() and 'geometry' in str(c).lower()),
                        None
                    )
                    if _len_col and _geo_col:
                        for _, _r in df_dcr.iterrows():
                            _len_val = _r.get(_len_col)
                            _geo_val = str(_r.get(_geo_col, ''))
                            if pd.isna(_len_val) or not _geo_val or _geo_val.lower() == 'nan':
                                continue
                            try:
                                _length_mm = float(_len_val)
                            except (ValueError, TypeError):
                                continue
                            # 每個 shape_aspect 只取第一次出現的公稱長度
                            for _sa_id in re.findall(r'shape_aspect\s+(\d+)', _geo_val, re.IGNORECASE):
                                if _sa_id not in shape_aspect_length_map:
                                    shape_aspect_length_map[_sa_id] = _length_mm
                        print(f"  [DCR] shape_aspect 公稱長度映射：{len(shape_aspect_length_map)} 筆")
            except Exception as _e:
                print(f"  [WARN] 無法載入 dimensional_characteristic_repr：{_e}")

        if 'datum_feature' in sheet_lower_map:
            try:
                df_raw = pd.read_excel(xls, sheet_name=sheet_lower_map['datum_feature'], header=None)
                header_idx = -1
                for i in range(min(5, len(df_raw))):
                    if 'id' in str(df_raw.iloc[i].values).lower():
                        header_idx = i
                        break
                if header_idx >= 0:
                    df_datum = df_raw.iloc[header_idx+1:].copy()
                    df_datum.columns = df_raw.iloc[header_idx].astype(str)
                    geom_col = next((c for c in df_datum.columns if 'geometry' in str(c).lower()), None)
                    id_col = next((c for c in df_datum.columns if str(c).strip().lower() == 'id'), None)
                    if geom_col and id_col:
                        for _, row in df_datum.iterrows():
                            df_id = str(row[id_col]).strip()
                            geom = str(row[geom_col])
                            # 精確提取 advanced_face ID
                            match = re.search(r'advanced_face\s+(\d+)', geom, re.IGNORECASE)
                            if match:
                                face_id = match.group(1)
                                datum_feature_faces[df_id] = face_id
            except Exception:
                pass

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
                # 判斷是否帶公差：
                # 1. 含有 +/-/± 符號
                # 2. 含有 2 個(含)以上的數值序列
                # 3. 含有 ISO 配合代號（如 H8, h7, f6, JS5）
                #    - \b[A-Za-z]{1,2}\d{1,2}\b 可捕捉 H8、JS5 等
                #    - 三字母的公差代號(dia/par/dis等)不會被誤判，因為無法同時滿足{1,2}
                # 同時支援 "⌀230H8"（緊接）與 "⌀230.00 H8"（有空格）兩種格式
                _ISO_FIT_RE = re.compile(r'(?:(?<=\d)|(?<!\w))[A-Za-z]{1,2}\d{1,2}(?!\w)')
                has_tol = (bool(re.search(r'[+\-±]', clean_val))
                           or len(vals_in_str) > 1
                           or bool(_ISO_FIT_RE.search(clean_val)))

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

                # Path A：提取本體面 ID（被標註的面）
                # dimensional_size     格式: "(1) advanced_face 4881"        → [4881]
                # dimensional_location 格式: "(2) advanced_face 587 661"     → [587, 661]（特徵面+基準面）
                face_ids = []
                primary_face = None
                for line in geom.split('\n'):
                    if 'advanced_face' in line.lower():
                        # 取 'advanced_face' 之後所有數字（支援同行多個 ID）
                        after = re.sub(r'.*advanced_face\s*', '', line, flags=re.IGNORECASE)
                        ids = re.findall(r'\d+', after)
                        for fid in ids:
                            if fid not in face_ids:
                                face_ids.append(fid)
                        if not primary_face and ids:
                            primary_face = ids[0]
                        break

                # ── 追踪基準面 ID（用於交互參考公差）──
                datum_face = None

                # 方法1：檢查是否有 "Datum Feature" 列（如 perpendicularity_tolerance）
                datum_feat_col = next((c for c in df.columns if 'datum_feature' in str(c).lower() and
                                      'datum_system' not in str(c).lower()), None)
                if datum_feat_col:
                    datum_feat_val = str(row.get(datum_feat_col, ''))
                    # 提取 datum_feature ID（如 "datum_feature 5527"）
                    m = re.search(r'datum_feature\s+(\d+)', datum_feat_val, re.IGNORECASE)
                    if m:
                        df_id = m.group(1)
                        # 查詢該 datum_feature 對應的 face ID
                        if df_id in datum_feature_faces:
                            datum_face = datum_feature_faces[df_id]

                # 方法2：檢查是否有直接包含 advanced_face 的基準面幾何列
                if not datum_face:
                    for col in df.columns:
                        col_lower = str(col).lower()
                        if ('associated' in col_lower and 'geometry' in col_lower) and 'datum_system' not in col_lower:
                            datum_geom_val = str(row.get(col, ''))
                            if datum_geom_val and 'advanced_face' in datum_geom_val.lower():
                                match = re.search(r'advanced_face\s+(\d+)', datum_geom_val, re.IGNORECASE)
                                if match:
                                    datum_face = match.group(1)
                                    break

                # 添加基準面 ID（如果找到且不重複）
                if datum_face and datum_face != primary_face:
                    face_ids.append(datum_face)

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

                # 提取公稱尺寸、IT 等級與公差數值
                # type_code 先正規化，確保與 pmi_rows 儲存值一致，避免 extract_nominal_size 拿到 None
                type_code_for_nominal = row_type or ('dat' if is_datum else 'feat')
                nominal_size, it_grade = extract_nominal_size(final_label, type_code_for_nominal)
                tolerance_value = extract_tolerance_value(final_label)

                # ── [新增] PAR/FLA 幾何公差：交叉查詢 dimensional_characteristic_repr 取得參考長度 ──
                # 幾何公差標籤中不含參考長度，需從 toleranced_shape_aspect 欄位交叉查詢
                if type_code_for_nominal in ('par', 'fla', 'str', 'per', 'sym', 'cyl') and shape_aspect_length_map:
                    # 找 toleranced_shape_aspect 欄（parallelism/flatness 等表均有此欄）
                    _tsa_col = next(
                        (c for c in df.columns
                         if 'toleranced_shape_aspect' in str(c).lower()
                         or ('toleranced' in str(c).lower() and 'shape' in str(c).lower())),
                        None
                    )
                    if _tsa_col is None:
                        # 部分 sheet 以「Toleranced Geometry」命名
                        _tsa_col = next(
                            (c for c in df.columns
                             if 'toleranced' in str(c).lower() and 'geometry' in str(c).lower()),
                            None
                        )
                    if _tsa_col is not None:
                        _tsa_val = str(row.get(_tsa_col, ''))
                        _sa_match = re.search(r'shape_aspect\s+(\d+)', _tsa_val, re.IGNORECASE)
                        if _sa_match:
                            _sa_id = _sa_match.group(1)
                            _ref_len = shape_aspect_length_map.get(_sa_id)
                            if _ref_len is not None:
                                # 格式化：整數不顯示小數點
                                nominal_size = (
                                    str(int(_ref_len)) if _ref_len == int(_ref_len) else str(_ref_len)
                                )

                pmi_rows.append({
                    'label':          final_label,
                    'type_code':      type_code_for_nominal,
                    'semantic_id':    semantic_id,
                    'face_ids':       face_ids,
                    'is_datum':       is_datum,
                    'is_feature_only': is_feature_only,
                    'is_interactive': (not is_datum and not is_feature_only and is_interactive),
                    'nominal_size':   nominal_size,      # 新增：公稱尺寸
                    'it_grade':       it_grade,          # 新增：IT等級
                    'tolerance_value': tolerance_value,  # 新增：公差數值
                })

    except Exception as e:
        import traceback
        print(f"⚠️  SFA Excel 解析錯誤：{e}")
        traceback.print_exc()

    # ── [新增] 第二階段：關聯交互參考公差與基準面的 Face ID ──
    # 交互參考公差應該同時包含：本體特徵面 + 基準面的 Face ID
    pmi_rows = _link_interactive_tolerances_with_datums(pmi_rows)

    # ── [新增] 第三階段：補充圖形PMI（tessellated_annotation_occurren 中未連結語意PMI的標註）──
    # 當 STEP 檔只有圖形 PMI（無語意 PARALLELISM_TOLERANCE 等實體）時，補充這些標註。
    if xls is not None:
        try:
            _supplement_graphic_pmi(xls, pmi_rows, face_pmi_map, tol_counters, sheet_code_map)
        except Exception as _e:
            print(f"  [WARN] 補充圖形PMI時發生錯誤：{_e}")

    print(f"[OK] XLSX 解析完成：{len(face_pmi_map)} 個 face，{len(pmi_rows)} 條 PMI 記錄")
    return face_pmi_map, pmi_rows


def parse_sfa_visual_sheets(sfa_path):
    """
    Layer 1 備援：從 SFA XLSX 的「視覺表單」提取 PMI 引用。
    當 tolerance 分頁沒東西可解析時，從 styled_item / draughting_model /
    advanced_brep_shape_representat 等分頁反向抓 entity 引用做標註列表。
    """
    face_pmi_map = defaultdict(set)
    pmi_rows     = []

    # Sheet 名稱關鍵字 → (icon, 優先擷取欄位關鍵字)
    TARGET_SHEETS = [
        ('styled_item',                    '🎨', ['item']),
        ('draughting_model',               '🖊️',  ['items']),
        ('mechanical_design_geometric_pre', '📐', ['items']),
        ('mechanical_design_and_draughtin', '🔗', ['rep_1', 'rep_2']),
        ('advanced_brep_shape_representat', '🧊', ['items']),
    ]

    try:
        xls = pd.ExcelFile(sfa_path)
        sheet_names_lower = {s.lower(): s for s in xls.sheet_names}
        counter = 0

        for key, icon, item_col_keys in TARGET_SHEETS:
            # 部分前綴匹配（SFA 會截斷長名稱）
            matched = next(
                (orig for low, orig in sheet_names_lower.items() if key in low),
                None
            )
            if not matched:
                continue

            df_raw = pd.read_excel(xls, sheet_name=matched, header=None)
            # 找 header 行（含 'id'）
            header_idx = -1
            for i in range(min(5, len(df_raw))):
                row_str = ' '.join(str(x).lower() for x in df_raw.iloc[i].values)
                if 'id' in row_str:
                    header_idx = i
                    break
            if header_idx == -1:
                continue

            df = df_raw.iloc[header_idx + 1:].copy()
            df.columns = df_raw.iloc[header_idx].astype(str).str.strip()

            id_col   = next((c for c in df.columns if str(c).strip().lower() == 'id'), None)
            item_col = next(
                (c for c in df.columns
                 if any(k in str(c).lower() for k in item_col_keys)),
                None
            )
            name_col = next(
                (c for c in df.columns if 'name' in str(c).lower()), None
            )

            if not id_col or not item_col:
                continue

            for _, row in df.iterrows():
                row_id   = str(row[id_col]).strip()
                item_str = str(row[item_col]).strip()
                name_str = str(row[name_col]).strip() if name_col else ''

                if row_id == 'nan' or item_str == 'nan':
                    continue

                # 從 item 欄提取所有 "entity_type NNNN" 引用
                refs = re.findall(r'([A-Za-z][A-Za-z0-9_]*)\s+(\d+)', item_str)
                face_ids = [eid for _, eid in refs]

                # 組合短標籤
                item_short = item_str[:70] + ('...' if len(item_str) > 70 else '')
                name_part  = f' "{name_str}"' if name_str and name_str != 'nan' else ''
                counter   += 1
                label = (
                    f"{icon} [{matched}] #{row_id}{name_part}: {item_short}"
                )

                for fid in face_ids:
                    face_pmi_map[fid].add(label)

                pmi_rows.append({
                    'label':           label,
                    'semantic_id':     row_id,
                    'face_ids':        face_ids,
                    'nominal_size':    None,
                    'it_grade':        None,
                    'tolerance_value': None,
                })

    except Exception as e:
        print(f"⚠️  視覺 sheet 解析錯誤：{e}")

    print(f"[OK] 幾何視覺 sheet 解析完成：{len(pmi_rows)} 條記錄，涵蓋 {len(face_pmi_map)} 個實體 ID")
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
                print(f"[OK] 從 TAO Sheet 建立 {len(semantic_to_tao)} 條精確鏈結")
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
    print(f"[OK] 成功建立 {len(result)} / {total_req} 個 tessellated 標註幾何")
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
        self.face_to_part     = {}   # face_step_id → part_name

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
        print(f"[OK] STEP XCAF 載入：{len(self.step_id_to_face)} 個 face，{len(self.face_to_part)} 個面已映射到零件")

    def _get_label_name(self, label):
        """從 XCAF label 取得零件名稱"""
        try:
            from OCC.Core.TDataStd import TDataStd_Name
            name_attr = TDataStd_Name()
            if label.FindAttribute(TDataStd_Name.GetID(), name_attr):
                return name_attr.Get().ToExtString()
        except Exception:
            pass
        return None

    def _build_face_map(self):
        """TransferReader 掃描 → step_id → TopoDS_Face，同時建立 face → part 映射"""
        roots = TDF_LabelSequence()
        self.shape_tool.GetFreeShapes(roots)

        for i in range(1, roots.Length() + 1):
            shape = self.shape_tool.GetShape(roots.Value(i))
            if i == 1:
                self.root_shape = shape

            # ── 遍歷 solid 層級，建立 face → part 映射 ──
            solid_exp = TopExp_Explorer(shape, TopAbs_SOLID)
            has_solids = False
            while solid_exp.More():
                has_solids = True
                solid = topods.Solid(solid_exp.Current())

                # 透過 shape_tool 查找此 solid 對應的 XCAF label → 取得零件名稱
                part_name = None
                solid_label = self.shape_tool.FindShape(solid)
                if solid_label and not solid_label.IsNull():
                    part_name = self._get_label_name(solid_label)
                if not part_name:
                    # 嘗試透過上層 component 取得名稱
                    comp_labels = TDF_LabelSequence()
                    self.shape_tool.GetComponents(roots.Value(i), comp_labels)
                    for ci in range(1, comp_labels.Length() + 1):
                        comp_label = comp_labels.Value(ci)
                        ref = comp_label
                        if self.shape_tool.IsReference(comp_label):
                            from OCC.Core.TDF import TDF_Label
                            ref_out = TDF_Label()
                            if self.shape_tool.GetReferredShape(comp_label, ref_out):
                                ref = ref_out
                        comp_shape = self.shape_tool.GetShape(ref)
                        if comp_shape and solid.IsPartner(comp_shape):
                            part_name = self._get_label_name(comp_label) or self._get_label_name(ref)
                            break

                # 遍歷此 solid 中的所有 face
                face_exp = TopExp_Explorer(solid, TopAbs_FACE)
                while face_exp.More():
                    face = topods.Face(face_exp.Current())
                    ent = self.tr.EntityFromShapeResult(face, 1)
                    if ent:
                        sid = self.ws.EntityLabel(ent).ToCString().replace('#', '').strip()
                        if sid:
                            self.step_id_to_face[sid] = face
                            if part_name:
                                self.face_to_part[sid] = part_name
                    face_exp.Next()
                solid_exp.Next()

            # ── 如果沒有 solid（單零件），退回原始 face 遍歷 ──
            if not has_solids:
                face_exp = TopExp_Explorer(shape, TopAbs_FACE)
                while face_exp.More():
                    face = topods.Face(face_exp.Current())
                    ent = self.tr.EntityFromShapeResult(face, 1)
                    if ent:
                        sid = self.ws.EntityLabel(ent).ToCString().replace('#', '').strip()
                        if sid:
                            self.step_id_to_face[sid] = face
                    face_exp.Next()

        print(f"[OK] face_to_part 映射：{len(self.face_to_part)} 個面已對應到零件")


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
                # OCC 7.9.0 API: use .NbNodes() and .Node(i) instead of .Nodes()
                nb_nodes = triangulation.NbNodes()
                nb_triangles = triangulation.NbTriangles()

                for i in range(1, nb_nodes + 1):
                    pt = triangulation.Node(i)
                    key = (round(pt.X(), 6), round(pt.Y(), 6), round(pt.Z(), 6))
                    if key not in vertex_map:
                        vertex_map[key] = vertex_idx
                        vertices.append([pt.X(), pt.Y(), pt.Z()])
                        vertex_idx += 1

                for i in range(1, nb_triangles + 1):
                    tri = triangulation.Triangle(i)
                    n1, n2, n3 = tri.Value(1), tri.Value(2), tri.Value(3)
                    pt1 = triangulation.Node(n1)
                    pt2 = triangulation.Node(n2)
                    pt3 = triangulation.Node(n3)

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
        print(f"[ERROR] 三角化失敗：{e}")
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
    """將 TAO compound（leader lines）轉成 Three.js LineSegments 格式（edges 僅）"""
    lines = []

    exp = TopExp_Explorer(compound, TopAbs_EDGE)
    while exp.More():
        edge = topods.Edge(exp.Current())
        try:
            # BRep_Tool.Curve(edge) → (Handle_Geom_Curve, first_param, last_param)
            result = BRep_Tool.Curve(edge)
            curve, first, last = result[0], result[1], result[2]
            if curve:
                pt_start = curve.Value(first)
                pt_end   = curve.Value(last)
                lines.append([
                    [pt_start.X(), pt_start.Y(), pt_start.Z()],
                    [pt_end.X(),   pt_end.Y(),   pt_end.Z()]
                ])
        except Exception:
            pass
        exp.Next()

    return lines


def tao_compound_to_geometry_json(compound, deflection=0.1):
    """
    將 TAO compound 轉成 Three.js 幾何格式。

    重要：_build_compound_from_tao 把 TESSELLATED_CURVE_SET 與
    COMPLEX_TRIANGULATED_SURFACE_SET 通通轉成 **edges**（三角形拆成 3 條邊），
    compound 裡不含 face。舊 Tkinter 版靠 AIS_Shape(compound) 把所有 edges
    畫成線，GDT 框/符號/文字就是這些邊的集合。

    所以這裡只需輸出 leader_lines（= 所有 edges），不用再三角化。

    Returns:
        {
            "leader_lines": [[[x,y,z],[x,y,z]], ...],  # 所有邊（含 GDT 框/符號/文字與引線）
            "triangles":    None  # TAO 無面，保留欄位供未來擴充
        }
    """
    return {
        "leader_lines": tao_compound_to_lines_json(compound),
        "triangles":    None,
    }
