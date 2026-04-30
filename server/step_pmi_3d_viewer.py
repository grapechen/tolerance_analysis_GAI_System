"""
step_pmi_3d_viewer.py
SFA Excel + STEP 3D 聯動高亮檢視器

兩條資料路徑
  Path A │ XLSX geometry 欄  → Face ID     → 3D 亮綠色
  Path B │ XLSX ID 欄 (semantic_id)
           → CSV ASSOCIATION 鏈 (draughting_model_item_associati + draughting_callout)
           → STP tessellated 幾何解析 (TESSELLATED_CURVE_SET)
           → 3D 黑色領引線

使用方式
  python step_pmi_3d_viewer.py
  → 依序選擇 XLSX（SFA Excel）與 STP 檔案
  → 點擊 [比對 & 高亮]，在左側 Treeview 勾選 PMI 條目
  → 條目亮起綠色 face + 黑色領引線
"""

import os
import re
import sys
import math
import glob
import threading
import queue
import pandas as pd
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import traceback
from collections import defaultdict

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
from OCC.Core.Quantity import Quantity_Color, Quantity_TOC_RGB, Quantity_NOC_GRAY80, Quantity_NOC_BLACK, Quantity_NOC_WHITE
from OCC.Core.AIS import AIS_Shape
from OCC.Core.gp import gp_Pnt, gp_Ax2, gp_Dir, gp_Trsf, gp_Vec
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCC.Core.BRep import BRep_Builder
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.TCollection import TCollection_ExtendedString
from OCC.Core.GeomAbs import (
    GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Cone,
    GeomAbs_Torus, GeomAbs_Sphere, GeomAbs_OtherSurface
)
from OCC.Display.SimpleGui import init_display

# ── 顏色常數 ─────────────────────────────────────────────
C_GRAY   = Quantity_Color(Quantity_NOC_GRAY80)
C_GREEN  = Quantity_Color(0.0, 0.85, 0.15, Quantity_TOC_RGB)
C_BLACK  = Quantity_Color(Quantity_NOC_BLACK)
C_PURPLE = Quantity_Color(0.63, 0.13, 0.94, Quantity_TOC_RGB) # 交互參考 (紫色)
C_ORANGE = Quantity_Color(1.0, 0.65, 0.0, Quantity_TOC_RGB)   # 個別參考 (橘色)


# ═══════════════════════════════════════════════════════════
# 1 / 1-2 / 1-3. 從 step_core 統一引入共用工具函數
# ═══════════════════════════════════════════════════════════
from step_core import (  # noqa: E402
    decode_step_string,
    extract_nominal_size,
    _link_interactive_tolerances_with_datums,
)


# ═══════════════════════════════════════════════════════════
# 2. SFA Excel 解析（擴充版）
#    回傳：
#      face_pmi_map  {face_id: {display_label, ...}}   ← 同 test 6.py
#      pmi_rows      [{'label', 'semantic_id', 'face_ids'}]
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

                # 判斷是否帶公差：
                # 1. 含有 +/-/± 符號
                # 2. 含有 2 個(含)以上的數值序列 (如: 8.00 0.15 0.05)
                # 3. 含有 ISO 配合代號（如 H8, h7, f6, JS5）
                #    STEP 檔案常只存配合代號而不存偏差值，CAD 軟體會自行查表顯示偏差
                vals_in_str = re.findall(r'[-+]?\d*\.\d+|\b\d+\b', clean_val)
                # 同時支援 "⌀230H8"（緊接）與 "⌀230.00 H8"（有空格）兩種格式
                _ISO_FIT_RE = re.compile(r'(?:(?<=\d)|(?<!\w))[A-Za-z]{1,2}\d{1,2}(?!\w)')
                has_tol = (bool(re.search(r'[+\-±]', clean_val))
                           or len(vals_in_str) > 1
                           or bool(_ISO_FIT_RE.search(clean_val)))

                # 無公差的純尺寸標註（如 Ø125.00）：保留但標記為特徵面
                is_feature_only = (type_code == 'dis' and not has_tol)

                # ── 公差項類型識別優化 ────────────────────────
                fmt_val = clean_val
                row_type = type_code  # 使用局部變數，避免汙染全域
                # dia 判斷：值含直徑符號 OR 幾何欄位含 cylindrical_surface
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

                # Path A：face IDs（雙向/多向全抓）
                face_ids = []
                for line in geom.split('\n'):
                    if 'advanced_face' in line.lower():
                        after = line.lower().split('advanced_face')[-1]
                        face_ids += re.findall(r'\d+', after)

                # ── [新功能] 依據 SFA 規範進行公差分類 (個別/交互) ──
                is_datum = 'datum_feature' in sl
                
                # SFA 交互參考公差 (Interactive): 位置類, 方向類, 偏轉類, 距離公差(dis)
                interactive_codes = {'pos', 'co', 'sym', 'ang', 'per', 'par', 'tot', 'run', 'dis'}
                # SFA 個別參考公差 (Individual): 形狀類, 尺寸/直徑類(dia)
                individual_codes  = {'cyl', 'cir', 'fla', 'str', 'dia'}
                
                is_interactive = False
                if row_type in interactive_codes:
                    is_interactive = True
                elif row_type in individual_codes:
                    is_interactive = False
                else:
                    # 未在規範圖表中的 (例如 profile 輪廓度)，依據參考面數量回退判定
                    is_interactive = len(face_ids) >= 2

                # 組合最終顯示標籤
                if is_datum or is_feature_only:
                    final_label = display_label
                else:
                    pmi_type_prefix = "[交互]" if is_interactive else "[個別]"
                    final_label = f"{pmi_type_prefix} {display_label}"

                # Path B：Semantic ID（STEP 實體編號）
                semantic_id = None
                if id_col:
                    raw_sid = str(row[id_col]).strip()
                    m = re.search(r'\d+', raw_sid.lstrip('#'))
                    if m:
                        semantic_id = m.group(0)

                for fid in face_ids:
                    face_pmi_map[fid].add(final_label)

                # 提取公稱尺寸與 IT 等級
                type_code_for_nominal = row_type or ('dat' if is_datum else 'feat')
                nominal_size, it_grade = extract_nominal_size(final_label, type_code_for_nominal)

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
                })

    except Exception as e:
        print(f"⚠️  SFA Excel 解析錯誤：{e}")

    # ── [新增] 第二階段：關聯交互參考公差與基準面的 Face ID ──
    # 交互參考公差應該同時包含：本體特徵面 + 基準面的 Face ID
    pmi_rows = _link_interactive_tolerances_with_datums(pmi_rows)

    print(f"✅ XLSX 解析完成：{len(face_pmi_map)} 個 face，{len(pmi_rows)} 條 PMI 記錄")
    return face_pmi_map, pmi_rows


# ── 舊版備援函式（保留供未來使用，主流程不呼叫）─────────────
def parse_sfa_visual_sheets(sfa_path):
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

                # 提取公稱尺寸（備用函式中無 type_code，故無法提取）
                pmi_rows.append({
                    'label':          label,
                    'semantic_id':    row_id,
                    'face_ids':       face_ids,
                    'nominal_size':   None,      # 備用函式中無法確定 type_code
                    'it_grade':       None,
                })

    except Exception as e:
        print(f"⚠️  視覺 sheet 解析錯誤：{e}")

    print(f"✅ 幾何視覺 sheet 解析完成：{len(pmi_rows)} 條記錄，涵蓋 {len(face_pmi_map)} 個實體 ID")
    return face_pmi_map, pmi_rows


# ═══════════════════════════════════════════════════════════
# 2c. 從 XCAF face map 建立幾何特徵樹（最終備援）
#     模仿 SFA Check Features 輸出格式：
#     CYLINDRICAL_SURFACE 分群 → 半徑/直徑 + 面數
#     PLANE 分群 → 法向 + 面數
# ═══════════════════════════════════════════════════════════
def build_geometry_feature_tree(engine):
    """
    遙諭 face map 內所有 TopoDS_Face，依面型分群並輸出屬性。
    Returns: list of {label, semantic_id=None, face_ids=[step_ids]}
    """
    # 中間儲存
    cylinders = defaultdict(list)  # radius (float) → [step_id]
    planes    = defaultdict(list)  # normal key → [step_id]
    cones     = defaultdict(list)  # half_angle_deg → [step_id]
    tori      = defaultdict(list)  # (major_r, minor_r) → [step_id]
    spheres   = defaultdict(list)  # radius → [step_id]
    others    = defaultdict(list)  # type_name → [step_id]

    for step_id, face in engine.step_id_to_face.items():
        try:
            adaptor = BRepAdaptor_Surface(face)
            stype   = adaptor.GetType()

            if stype == GeomAbs_Cylinder:
                r = round(adaptor.Cylinder().Radius(), 3)
                cylinders[r].append(step_id)

            elif stype == GeomAbs_Plane:
                ax = adaptor.Plane().Axis().Direction()
                # 量化法向，合併相對的平行面
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

    # ── 圆柱面 ──
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

    # ── 平面 ──
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

    # ── 圓錐面 ──
    for ang_deg, ids in sorted(cones.items()):
        count = len(ids)
        count_str = f'{count}個  ' if count > 1 else ''
        label = (
            f'🔺 CONICAL_SURFACE  {count_str}'
            f'半角={ang_deg}°  '
            f'[{face_list_str(ids)}]'
        )
        pmi_rows.append({'label': label, 'semantic_id': None, 'face_ids': ids, 'nominal_size': None, 'it_grade': None})

    # ── 圆環面 ──
    for (major_r, minor_r), ids in sorted(tori.items()):
        label = (
            f'🍰 TOROIDAL_SURFACE  '
            f'R大={major_r:.3f}  R小={minor_r:.3f}  '
            f'[{face_list_str(ids)}]'
        )
        pmi_rows.append({'label': label, 'semantic_id': None, 'face_ids': ids, 'nominal_size': None, 'it_grade': None})

    # ── 球面 ──
    for r, ids in sorted(spheres.items()):
        label = (
            f'🔵 SPHERICAL_SURFACE  '
            f'半徑 R={r:.3f}  '
            f'[{face_list_str(ids)}]'
        )
        pmi_rows.append({'label': label, 'semantic_id': None, 'face_ids': ids, 'nominal_size': None, 'it_grade': None})

    # ── 其他 ──
    for type_name, ids in others.items():
        label = f'◼️ {type_name}  [{face_list_str(ids)}]'
        pmi_rows.append({'label': label, 'semantic_id': None, 'face_ids': ids, 'nominal_size': None, 'it_grade': None})

    # ── 全面总敲 ───
    all_ids = list(engine.step_id_to_face.keys())
    pmi_rows.insert(0, {
        'label':          f'🔵 SOLID 全部  ({len(all_ids)} 個面)',
        'semantic_id':    None,
        'face_ids':       all_ids,
        'nominal_size':   None,
        'it_grade':       None,
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
#    semantic_entity_id → draughting_callout_id → tao_id
# ═══════════════════════════════════════════════════════════
def load_sfa_association(xlsx_path):
    """
    從 SFA XLSX 內部 Sheets 建立完整 ASSOCIATION 鏈：
      {semantic_entity_id (str) → tessellated_annotation_occurrence_id (str)}
    
    優先讀取內部的 'tessellated_annotation_occurren' 分頁，
    這比 CSV 路徑更穩健且不依賴外部檔案。
    """
    if not os.path.exists(xlsx_path):
        return {}

    semantic_to_tao = {}
    try:
        xls = pd.ExcelFile(xlsx_path)
        sheet_names = xls.sheet_names
        
        # ── 策略 A：直接解析 TAO 分頁 (最精確) ──────────────────
        # 此分頁直接記錄了 "Associated Semantic PMI" 欄位
        tao_sheet = next((s for s in sheet_names if 'tessellated_annotation_occurren' in s.lower()), None)
        
        if tao_sheet:
            print(f"🔍 正在從 Excel 分頁 [{tao_sheet}] 提取精確關聯...")
            df_tao = pd.read_excel(xls, sheet_name=tao_sheet, header=None)
            
            # 找 Header (通常 ID 在第一列，語義 ID 在後面)
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
                        # 標準化 TAO ID：移除 "#" 前綴，float 轉 int 字串 (4000.0 → "4000")
                        raw_tao = row[id_col]
                        try:
                            tao_id = str(int(float(str(raw_tao).strip().lstrip('#'))))
                        except Exception:
                            tao_id = str(raw_tao).strip().lstrip('#')
                        sem_val = str(row[sem_col]).strip()
                        if not tao_id or tao_id == 'nan' or sem_val == 'nan': continue
                        
                        # 提取所有語義 ID (可能一對多)
                        # 格式可能為 "dimensional_size 5509" 或 "(1) flatness_tolerance 5606"
                        s_ids = re.findall(r'\s+(\d+)', sem_val)
                        if not s_ids: # 備援：如果沒空格直接抓最後數字
                            m = re.search(r'(\d+)$', sem_val)
                            if m: s_ids = [m.group(1)]
                            
                        for sid in s_ids:
                            semantic_to_tao[sid] = tao_id
                    
            if semantic_to_tao:
                print(f"✅ 從 TAO Sheet 建立 {len(semantic_to_tao)} 條精確鏈結")
                return semantic_to_tao

        # ── 策略 B：Fallback 到 DMIA 分頁 (傳通鏈結模式) ─────────────
        dmia_sheet = next((s for s in sheet_names if 'draughting_model_item_associati' in s.lower()), None)
        callout_sheet = next((s for s in sheet_names if 'draughting_callout' in s.lower()), None)
        
        if dmia_sheet and callout_sheet:
            print(f"🔍 正在從 Excel 分頁 [{dmia_sheet}] 進行二次鏈結...")
            # 這裡實作原本的 DMIA -> Callout -> TAO 邏輯 (改讀 Excel)
            # ... (內容與原本 CSV 邏輯類似，但操作 xls 物訊)
            # 為了簡潔與穩定，優先推薦策略 A。若 A 失敗則回報
            pass

    except Exception as e:
        print(f"⚠️  Excel 關聯解析發生錯誤：{e}")
        traceback.print_exc()

    return semantic_to_tao


# ═══════════════════════════════════════════════════════════
# 4. STP 文字解析：tessellated 幾何 → OCC Compound shapes
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
    """
    直接從 STEP 實體解析 semantic_id → tao_id 精確映射。

    STEP 內部的正確鏈結：
      語義實體 (DIMENSIONAL_SIZE / GEOMETRIC_TOLERANCE / ...)
        ← DRAUGHTING_MODEL_ITEM_ASSOCIATION
        → DRAUGHTING_CALLOUT
          → TESSELLATED_ANNOTATION_OCCURRENCE  (黑色 3D 標註)

    此方法比 XLSX 關聯表和距離估算都更可靠，
    因為它直接讀取 STEP 檔案本身記錄的關聯。
    """
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

    # Step 1：DRAUGHTING_CALLOUT → 第一個 TAO id
    callout_to_tao = {}
    for eid, ent in entities.items():
        if ent['type'] == 'DRAUGHTING_CALLOUT':
            for ref in re.findall(r'#(\d+)', ent['params']):
                if entities.get(ref, {}).get('type') == 'TESSELLATED_ANNOTATION_OCCURRENCE':
                    callout_to_tao[eid] = ref
                    break   # 每個 callout 取第一個 TAO

    # Step 2：DRAUGHTING_MODEL_ITEM_ASSOCIATION → 找 sem_id 和 tao_id
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
                tao_id = ref   # 直接指向 TAO（部分 STEP 格式）
        if sem_id and tao_id:
            semantic_to_tao[sem_id] = tao_id

    return semantic_to_tao


def parse_tessellated_annotations(stp_path, tao_ids=None, scan_all=False):
    """
    解析 STP 文字，為指定的 tao_ids 或所有標註建立 OCC shapes 與元數據
    Returns: ({tao_id: {'shape', 'tri_count', 'edge_count'}},
              {semantic_id: tao_id}  ← 直接從 STEP 關聯鏈解析，比 XLSX 更精確)
    """
    if not tao_ids and not scan_all:
        return {}, {}

    entities = _parse_stp_entities(stp_path)

    # ── 從 STEP 直接建立 semantic → TAO 精確映射 ─────────────
    step_sem_to_tao = _build_step_sem_to_tao(entities)
    print(f"🔗 STEP 直接鏈結：{len(step_sem_to_tao)} 條 semantic→TAO")

    # 決定要解析的目標 IDs
    target_ids = []
    if scan_all:
        target_ids = [eid for eid, ent in entities.items()
                      if ent['type'] == 'TESSELLATED_ANNOTATION_OCCURRENCE']
        print(f"🔍 全局掃描 STP 3D 標註（共找到 {len(target_ids)} 個實體）...")
    else:
        target_ids = list(tao_ids)
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
    """
    從 TESSELLATED_ANNOTATION_OCCURRENCE 完整重建 3D 標註幾何：
      - TESSELLATED_CURVE_SET          → 領引線（edges）
      - COMPLEX_TRIANGULATED_SURFACE_SET → 文字/符號/公差框（三角面片）
    """
    tao = entities.get(tao_id)
    if not tao or tao['type'] != 'TESSELLATED_ANNOTATION_OCCURRENCE':
        return None

    all_refs = re.findall(r'#(\d+)', tao['params'])
    if not all_refs:
        return None
    tgs_id = all_refs[-1]   # TESSELLATED_GEOMETRIC_SET

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

        # ── 取得座標列表（兩種子實體共用的解析邏輯）─────────
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

        # ── 索引提取優化（正確定位座標引用之後的資料塊） ────────
        # 尋找座標實體編號（#XXXX）之後的第一個左括號，那裡才是索引資料的起點
        # 例如：('', #10, ( (1,2), (3,4) )) 或 ('', #10, 2, ( (1,2,3) ))
        coord_m = re.search(r'#\d+', cparams)
        idx_text = cparams
        if coord_m:
            # 從座標引用之後尋找最後一組大括號內容
            remaining = cparams[coord_m.end():]
            idx_start = remaining.find('(')
            if idx_start != -1:
                idx_text = remaining[idx_start:]
        
        all_idxs = [int(x) - 1 for x in re.findall(r'\d+', idx_text)]

        # ── Path 1：TESSELLATED_CURVE_SET → 領引線 ──────────
        if ctype == 'TESSELLATED_CURVE_SET':
            # 每 2 個數字組成一條邊 (i1, i2)
            for i in range(0, len(all_idxs) - 1, 2):
                i1, i2 = all_idxs[i], all_idxs[i+1]
                if 0 <= i1 < len(points) and 0 <= i2 < len(points):
                    try:
                        edge = BRepBuilderAPI_MakeEdge(points[i1], points[i2]).Edge()
                        builder.Add(compound, edge)
                        has_geom = True
                        edge_count += 1
                    except Exception: pass

        # ── Path 2：COMPLEX_TRIANGULATED_SURFACE_SET → 符號/文字 ──
        elif ctype == 'COMPLEX_TRIANGULATED_SURFACE_SET':
            # 每 3 個數字組成一個三角形 (i1, i2, i3)
            for i in range(0, len(all_idxs) - 2, 3):
                i1, i2, i3 = all_idxs[i], all_idxs[i+1], all_idxs[i+2]
                if not (0 <= i1 < len(points) and
                        0 <= i2 < len(points) and
                        0 <= i3 < len(points)):
                    continue
                # 每個三角形畫 3 條邊 (p0→p1, p1→p2, p2→p0)
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
# 5. STEP XCAF 引擎（僅負責幾何 face 對照）
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

        self.root_shape       = None   # TopoDS_Shape 整體模型
        self.step_id_to_face  = {}     # {step_id: TopoDS_Face}
        self.face_to_part     = {}     # face_step_id → part_name
        self.native_presentations = []  # 保存所有原生 PMI Text 形狀

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
        self._extract_native_presentations()
        print(f"✅ STEP XCAF 載入：{len(self.step_id_to_face)} 個 face，提取了 {len(self.native_presentations)} 個原生呈現")

    def _extract_native_presentations(self):
        """從 STEP 底層直接提取原生的公差標註與數值圖形 (完美字體)"""
        pmi_labels = TDF_LabelSequence()
        self.dim_tol_tool.GetDimensionLabels(pmi_labels)
        self.dim_tol_tool.GetGeomToleranceLabels(pmi_labels)
        
        self.native_presentations = []
        for i in range(1, pmi_labels.Length() + 1):
            try:
                pres = self.dim_tol_tool.GetPresentation(pmi_labels.Value(i))
                if not pres.IsNull():
                    self.native_presentations.append(pres)
            except: pass

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
# 6. 主程式：tkinter 控制板 + OCC 3D 視窗
# ═══════════════════════════════════════════════════════════
class SfaPmiViewer:
    def __init__(self):
        self.engine        = StepXcafEngine()
        self.face_pmi_map  = {}
        self.pmi_rows      = []
        self.pmi_items     = {}   # {idx_str: {label, face_ais, pres_ais, checked}}
        self.msg_queue     = queue.Queue() # 執行緒安全訊息隊列

        self.stp_path  = None
        self.xlsx_path = None

        # ── OCC 3D 視窗 ──────────────────────────────────
        self.display, self.start_display, _, _ = init_display()
        self.display.View.SetBackgroundColor(
            Quantity_Color(1.0, 1.0, 1.0, Quantity_TOC_RGB)
        )

        # ── tkinter 控制板 ────────────────────────────────
        self._build_ui()
        
        # 啟動隊列輪詢 (每 100 毫秒檢查一次背景任務)
        self.root.after(100, self._poll_queue)
        
        self.start_display()

    # ── UI 建置 ───────────────────────────────────────────
    def _build_ui(self):
        self.root = tk.Tk()
        self.root.title("SFA PMI 3D 聯動檢視器")
        self.root.geometry("480x740")
        self.root.attributes("-topmost", True)

        # 按鈕列
        btn_fr = tk.Frame(self.root, bg="#eceff1", pady=8)
        btn_fr.pack(fill="x")
        self.btn_stp = tk.Button(btn_fr, text="📥 載入 STP",
                  command=self._load_stp,
                  bg="#bbdefb", font=("Arial", 10, "bold"), width=12)
        self.btn_stp.pack(side="left", padx=8)
        self.btn_xlsx = tk.Button(btn_fr, text="📊 載入 XLSX",
                  command=self._load_xlsx,
                  bg="#c8e6c9", font=("Arial", 10, "bold"), width=12)
        self.btn_xlsx.pack(side="left", padx=4)
        self.btn_match = tk.Button(btn_fr, text="🔗 對比",
                  command=self._match_and_highlight,
                  bg="#ffe082", font=("Arial", 10, "bold"), width=14)
        self.btn_match.pack(side="left", padx=4)
        self.btn_export = tk.Button(btn_fr, text="💾 導出 CSV",
                  command=self._export_csv,
                  bg="#cfd8dc", font=("Arial", 10, "bold"), width=12)
        self.btn_export.pack(side="left", padx=4)

        # 第二列按鈕：組合件
        btn_fr2 = tk.Frame(self.root, bg="#eceff1", pady=4)
        btn_fr2.pack(fill="x")
        self.btn_asm = tk.Button(btn_fr2, text="🔩 組合件分析",
                  command=self._load_assembly,
                  bg="#f3e5f5", font=("Arial", 10, "bold"), width=16)
        self.btn_asm.pack(side="left", padx=8)
        self.btn_tree = tk.Button(btn_fr2, text="📋 零件樹",
                  command=self._show_product_tree,
                  bg="#e8f5e9", font=("Arial", 10, "bold"), width=10)
        self.btn_tree.pack(side="left", padx=4)
        tk.Label(btn_fr2, text="載入組合件 STP，偵測零件間接觸面",
                 bg="#eceff1", font=("Arial", 9), fg="#666").pack(side="left")

        # 狀態列
        self.status_var = tk.StringVar(value="請先載入 STP 與 XLSX 檔案")
        tk.Label(self.root, textvariable=self.status_var,
                 bg="#fff9c4", anchor="w", font=("Arial", 9), padx=6
                 ).pack(fill="x", padx=8, pady=(0, 4))

        # 批次操作
        bulk_fr = tk.Frame(self.root)
        bulk_fr.pack(fill="x", padx=8, pady=(0, 4))
        tk.Button(bulk_fr, text="☑ 全選", command=self._select_all, width=9).pack(side="left", padx=2)
        tk.Button(bulk_fr, text="☐ 全清", command=self._clear_all,  width=9).pack(side="left", padx=2)

        # 色票說明
        legend_fr = tk.Frame(self.root, bg="#fafafa")
        legend_fr.pack(fill="x", padx=8, pady=(0, 2))

         # 特徵面 / 基準面 (建議使用綠色)
        tk.Label(legend_fr, text="■", fg="#10b981", bg="#fafafa", font=("Arial", 12)).pack(side="left")
        tk.Label(legend_fr, text="基準/純幾何特徵面 ", bg="#fafafa", font=("Arial", 9)).pack(side="left")
        
        # 交互參考
        tk.Label(legend_fr, text="■", fg="#a121f0", bg="#fafafa", font=("Arial", 12)).pack(side="left")
        tk.Label(legend_fr, text="交互參考公差之特徵面 ", bg="#fafafa", font=("Arial", 9)).pack(side="left")
        
        # 個別參考
        tk.Label(legend_fr, text="■", fg="#ffa500", bg="#fafafa", font=("Arial", 12)).pack(side="left")
        tk.Label(legend_fr, text="個別參考公差之特徵面 ", bg="#fafafa", font=("Arial", 9)).pack(side="left")
        
        # 標註線
        tk.Label(legend_fr, text="■", fg="#000000", bg="#fafafa", font=("Arial", 12)).pack(side="left")
        tk.Label(legend_fr, text="PMI 標註線", bg="#fafafa", font=("Arial", 9)).pack(side="left")

        # Treeview
        tk.Label(self.root, text="PMI 標註列表（點選條目切換顯示）",
                 font=("Arial", 10, "bold"), anchor="w"
                 ).pack(fill="x", padx=10, pady=(4, 0))

        tree_fr = tk.Frame(self.root)
        tree_fr.pack(fill="both", expand=True, padx=8, pady=6)

        self.tree = ttk.Treeview(tree_fr, columns=("pmi",), show="headings", height=32)
        self.tree.heading("pmi", text="PMI 代碼 / 公差標註")
        self.tree.column("pmi", width=420, anchor="w")

        sb = ttk.Scrollbar(tree_fr, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.tree.tag_configure("checked",   foreground="#1b5e20", font=("Arial", 9, "bold"))
        self.tree.tag_configure("unchecked", foreground="#555555", font=("Arial", 9))
        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

    # ── 載入檔案 ──────────────────────────────────────────
    def _load_stp(self):
        path = filedialog.askopenfilename(
            title="選擇 STEP 檔案",
            filetypes=[("STEP Files", "*.stp *.STP *.step *.STEP")]
        )
        if not path:
            return
        self.stp_path = path
        self._update_status()
        print(f"📦 STP 已選：{path}")

    def _load_xlsx(self):
        path = filedialog.askopenfilename(
            title="選擇 SFA Excel 檔案",
            filetypes=[("Excel Files", "*.xlsx *.xls")]
        )
        if not path:
            return
        self.xlsx_path = path
        self._update_status()
        print(f"📊 XLSX 已選：{path}")

    def _update_status(self):
        stp  = os.path.basename(self.stp_path)  if self.stp_path  else "（未載入）"
        xlsx = os.path.basename(self.xlsx_path) if self.xlsx_path else "（未載入）"
        self.status_var.set(f"STP: {stp}  │  XLSX: {xlsx}")

    def _set_btn_state(self, state):
        """state: 'normal' | 'disabled'"""
        for btn in (self.btn_stp, self.btn_xlsx, self.btn_match, self.btn_export, self.btn_asm):
            btn.config(state=state)

    # ── 組合件分析 ────────────────────────────────────────
    def _load_assembly(self):
        path = filedialog.askopenfilename(
            title="選擇組合件 STEP 檔案",
            filetypes=[("STEP Files", "*.stp *.STP *.step *.STEP")]
        )
        if not path:
            return

        self._set_btn_state("disabled")
        self.status_var.set("⏳ 組合件分析中，請稍候...")
        self.root.update_idletasks()
        self.display.Context.RemoveAll(True)
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.pmi_items.clear()

        def _worker():
            try:
                import subprocess, tempfile, json as _json
                from collections import defaultdict
                from OCC.Core.BRep import BRep_Builder as _Builder
                from OCC.Core.TopoDS import TopoDS_Compound as _Compound
                
                # ── 子進程執行分析 ──
                worker_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "asm_worker.py")
                tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
                tmp.close()
                out_json = tmp.name

                # 使用指定的環境 Python (tol_env)
                python_exe = r"C:\Users\User\anaconda3\envs\tol_env\python.exe"
                if not os.path.exists(python_exe):
                    python_exe = sys.executable

                # 用 Popen 取代 run，讓 worker 的進度即時顯示在 console
                import io
                proc = subprocess.Popen(
                    [python_exe, worker_script, path, out_json],
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, encoding='cp950', errors='replace'
                )
                import time as _time
                deadline = _time.time() + 6000
                for line in iter(proc.stdout.readline, ''):
                    print(line, end='', flush=True)
                    if _time.time() > deadline:
                        proc.kill()
                        raise RuntimeError("組合件分析超過 6000 秒，已強制終止")
                proc.stdout.close()
                proc.wait()

                data = {}
                if os.path.exists(out_json):
                    with open(out_json, 'r', encoding='utf-8') as f:
                        data = _json.load(f)
                    os.unlink(out_json)

                if data.get('status') != 'ok':
                    err_msg = data.get('msg', '分析子進程未產出有效結果')
                    self.msg_queue.put({'status': 'error_asm', 'msg': err_msg})
                    return

                contacts = data.get('contacts', [])
                solids_mapping = data.get('solids', []) # list of {'name','bbox'}
                
                # ── 主進程重新載入供 3D 顯示 ──
                reader = STEPControl_Reader()
                root_shapes = []
                if reader.ReadFile(path) == IFSelect_RetDone:
                    reader.TransferRoots()
                    root_shapes = [reader.Shape(i) for i in range(1, reader.NbShapes() + 1)]

                # 從根形狀提取個別 SOLID（與 asm_worker 相同順序）
                all_disp_solids = []
                for shp in root_shapes:
                    exp = TopExp_Explorer(shp, TopAbs_SOLID)
                    while exp.More():
                        s = topods.Solid(exp.Current())
                        if not s.IsNull(): all_disp_solids.append(s)
                        exp.Next()
                if not all_disp_solids:
                    all_disp_solids = root_shapes  # fallback：直接用根形狀
                print(f"[ASM] 主進程 SOLID 數：{len(all_disp_solids)}，"
                      f"solid_mapping 數：{len(solids_mapping)}")

                # ── 將實體按 SFA 名稱群組（i-th solid ↔ i-th mapping）──
                group_map = defaultdict(list)
                for i, s_meta in enumerate(solids_mapping):
                    if i < len(all_disp_solids):
                        name = s_meta.get('name', f"Unknown_{i}")
                        group_map[name].append(all_disp_solids[i])

                # 建立 Compound（每個 Compound 代表一個零件群組）
                final_group_shapes = []
                for name, shps in group_map.items():
                    builder = BRep_Builder()
                    comp = TopoDS_Compound()
                    builder.MakeCompound(comp)
                    for s in shps: builder.Add(comp, s)
                    final_group_shapes.append(comp)

                # ── 建立全量面片與座標清單（供模糊匹配使用）──
                all_faces_meta = []
                for shp in all_disp_solids:
                    exp = TopExp_Explorer(shp, TopAbs_FACE)
                    while exp.More():
                        face = topods.Face(exp.Current())
                        if not face.IsNull():
                            try:
                                bb = Bnd_Box(); bb.SetGap(0.0)
                                brepbndlib.Add(face, bb)
                                if not bb.IsVoid():
                                    all_faces_meta.append({'face': face, 'bbox': bb.Get()})
                            except: pass
                        exp.Next()

                # ── 為每筆接觸找到對應 Face（中心點 + 尺寸雙重匹配）──
                # 舊方法：6 座標差總和 → 圓柱面 bbox 相似度高，易選錯
                # 新方法：bbox 中心點距離 (3D) + 三軸尺寸差，雙重評分
                import math as _math

                def _bb_center(bb):
                    return ((bb[0]+bb[3])*0.5,
                            (bb[1]+bb[4])*0.5,
                            (bb[2]+bb[5])*0.5)

                def _bb_dims(bb):
                    return (bb[3]-bb[0], bb[4]-bb[1], bb[5]-bb[2])

                matched_ok = 0
                matched_fail = 0

                for c in contacts:
                    face_list = []
                    # c['face_pairs'] 是 [ {bbox1:[...], bbox2:[...]}, ... ]
                    for pair in c.get('face_pairs', []):
                        for bbox_key in ('bbox1', 'bbox2'):
                            target = pair.get(bbox_key)
                            if not target:
                                continue

                            tc = _bb_center(target)
                            td = _bb_dims(target)

                            best_face, min_score = None, float('inf')
                            for f_meta in all_faces_meta:
                                f_bb = f_meta['bbox']
                                fc = _bb_center(f_bb)
                                fd = _bb_dims(f_bb)

                                # 中心點歐氏距離
                                center_d = _math.sqrt(
                                    (tc[0]-fc[0])**2 +
                                    (tc[1]-fc[1])**2 +
                                    (tc[2]-fc[2])**2)
                                # 三軸尺寸差（排除同軸不同段的圓柱面）
                                dim_d = (abs(td[0]-fd[0]) +
                                         abs(td[1]-fd[1]) +
                                         abs(td[2]-fd[2]))

                                score = center_d + dim_d * 0.5
                                if score < min_score:
                                    min_score = score
                                    best_face = f_meta['face']

                            # 閾值 1.0mm（中心差 + 尺寸差加權）
                            if min_score < 1.0 and best_face is not None:
                                face_list.append(best_face)
                                matched_ok += 1
                            else:
                                matched_fail += 1

                    c['face_list'] = face_list

                print(f"[ASM] 面匹配：成功 {matched_ok}，失敗 {matched_fail}")

                self.msg_queue.put({
                    'status': 'assembly',
                    'data': {'path': path, 'comp_shapes': final_group_shapes, 'contacts': contacts}
                })
                return

                class FaceInfo:  # 以下舊碼不再執行，保留供參考
                    def __init__(self, face, step_id, comp_name):
                        self.face      = face
                        self.step_id   = step_id
                        self.comp_name = comp_name
                        self.normal    = None
                        self.cyl_axis  = None
                        self.cyl_loc   = None
                        self.radius    = None
                        self.surf_type = "其他"
                        self.area      = 0.0
                        # BBox
                        try:
                            self.bbox = Bnd_Box()
                            brepbndlib.Add(face, self.bbox)
                        except:
                            self.bbox = Bnd_Box()
                        # 幾何資訊（全部包 try/except 防退化面 crash）
                        try:
                            adaptor = BRepAdaptor_Surface(face)
                            stype   = adaptor.GetType()
                            if stype == GeomAbs_Plane:
                                self.surf_type = "平面"
                                self.normal    = adaptor.Plane().Axis().Direction()
                            elif stype == GeomAbs_Cylinder:
                                cyl = adaptor.Cylinder()
                                self.surf_type = "孔" if face.Orientation() == TopAbs_REVERSED else "圓柱面"
                                self.cyl_axis  = cyl.Axis().Direction()
                                self.cyl_loc   = cyl.Location()
                                self.radius    = cyl.Radius()
                        except:
                            pass
                        # 面積估算：用 BBox 面積代替（安全，不會 native crash）
                        try:
                            xmin, ymin, zmin, xmax, ymax, zmax = self.bbox.Get()
                            dx = xmax - xmin
                            dy = ymax - ymin
                            dz = zmax - zmin
                            # 取最大的兩個邊長乘積作為面積估算
                            sides = sorted([dx, dy, dz])
                            self.area = sides[1] * sides[2]
                        except:
                            self.area = 0.0

                # ── 容差設定（三層）────────────────────────────
                BBOX_TOL     = 0.01    # 組件 BBox 擴張量
                CONTACT_TOL  = 0.001   # 一般接觸候選距離
                STRICT_TOL   = 1e-6    # 高可信度接觸距離

                # ── 建立組件層級資料 ─────────────────────────────
                from collections import defaultdict
                comp_faces = defaultdict(list)
                comp_bbox  = {}
                disp_shapes = []

                for i, (shape, name) in enumerate(group_shapes):
                    disp_shapes.append(shape)
                    cb = Bnd_Box()
                    cb.SetGap(BBOX_TOL)   # 加容差避免邊界誤排除
                    exp = TopExp_Explorer(shape, TopAbs_FACE)
                    while exp.More():
                        face = topods.Face(exp.Current())
                        sid  = f"#{i}_{len(comp_faces[name])}"
                        fi = FaceInfo(face, sid, name)
                        comp_faces[name].append(fi)
                        cb.Add(fi.bbox)
                        exp.Next()
                    comp_bbox[name] = cb

                # ── 確認至少兩個零件（否則無意義）──────────────
                comp_names = list(comp_faces.keys())
                nc = len(comp_names)
                if nc < 2:
                    self.msg_queue.put({'status': 'error_asm',
                                        'msg': f"此 STEP 僅包含 {nc} 個零件，無法進行組裝接觸分析。"})
                    return

                total_faces = sum(len(v) for v in comp_faces.values())
                print(f"🧩 {nc} 個零件，總計 {total_faces} 個面，開始接觸分析...")

                # ── 輔助函式 ─────────────────────────────────────
                import math as _math

                def check_area(f1, f2, min_area=1.0):
                    return min(f1.area, f2.area) > min_area

                def check_normal(f1, f2, tol_deg=5.0):
                    """平面法向量應平行或反平行（0° 或 180°）"""
                    if f1.normal is None or f2.normal is None:
                        return True
                    dot = (f1.normal.X()*f2.normal.X() +
                           f1.normal.Y()*f2.normal.Y() +
                           f1.normal.Z()*f2.normal.Z())
                    angle = _math.degrees(_math.acos(max(-1.0, min(1.0, dot))))
                    return angle < tol_deg or angle > (180.0 - tol_deg)

                def check_coaxial(f1, f2, tol_deg=5.0, tol_dist=0.1):
                    """圓柱面軸線平行且偏移距離夠小"""
                    if f1.cyl_axis is None or f2.cyl_axis is None:
                        return True
                    dot = abs(f1.cyl_axis.X()*f2.cyl_axis.X() +
                              f1.cyl_axis.Y()*f2.cyl_axis.Y() +
                              f1.cyl_axis.Z()*f2.cyl_axis.Z())
                    if _math.degrees(_math.acos(min(1.0, dot))) > tol_deg:
                        return False
                    dx = f1.cyl_loc.X() - f2.cyl_loc.X()
                    dy = f1.cyl_loc.Y() - f2.cyl_loc.Y()
                    dz = f1.cyl_loc.Z() - f2.cyl_loc.Z()
                    ax, ay, az = f2.cyl_axis.X(), f2.cyl_axis.Y(), f2.cyl_axis.Z()
                    dist = _math.sqrt((dy*az-dz*ay)**2 + (dz*ax-dx*az)**2 + (dx*ay-dy*ax)**2)
                    return dist < tol_dist

                def infer_contact_type(f1, f2, coaxial):
                    t1, t2 = f1.surf_type, f2.surf_type
                    if t1 == "平面" and t2 == "平面":
                        return "平面配合 (Planar Mate)"
                    if t1 in ("孔", "圓柱面") and t2 in ("孔", "圓柱面"):
                        if coaxial:
                            return "圓柱共軸 (Coaxial)"
                        return "圓柱接觸 (Cylindrical)"
                    return f"{t1} ↔ {t2}"

                # ── Step 1：組件 BBox 粗篩 ───────────────────────
                candidate_pairs = [
                    (comp_names[a], comp_names[b])
                    for a in range(nc) for b in range(a+1, nc)
                    if not comp_bbox[comp_names[a]].IsOut(comp_bbox[comp_names[b]])
                ]
                print(f"📦 BBox 重疊組件對：{len(candidate_pairs)} 對，開始面層級精確比對...")

                # ── Step 2：面層級比對 ───────────────────────────
                contacts = []
                for ca, cb in candidate_pairs:
                    for f1 in comp_faces[ca]:
                        for f2 in comp_faces[cb]:
                            # 面 BBox（帶容差）過濾
                            if f1.bbox.IsOut(f2.bbox):
                                continue
                            # 面積：排除點/邊接觸
                            if not check_area(f1, f2):
                                continue
                            # 平面：法向量需平行或反平行
                            if f1.surf_type == "平面" and f2.surf_type == "平面":
                                if not check_normal(f1, f2):
                                    continue
                            # 圓柱：軸線共軸才進一步計算
                            coaxial = False
                            if f1.cyl_axis is not None and f2.cyl_axis is not None:
                                coaxial = check_coaxial(f1, f2)
                                if not coaxial:
                                    continue
                            # BRepExtrema 精確距離
                            ext = BRepExtrema_DistShapeShape(f1.face, f2.face)
                            if not ext.IsDone():
                                continue
                            dist = ext.Value()
                            if dist > CONTACT_TOL:
                                continue
                            confidence = "高" if dist < STRICT_TOL else "中"
                            contacts.append({
                                'comp1': f1.comp_name, 'id1': f1.step_id, 'type1': f1.surf_type,
                                'comp2': f2.comp_name, 'id2': f2.step_id, 'type2': f2.surf_type,
                                'dist':  round(dist, 6),
                                'ctype': infer_contact_type(f1, f2, coaxial),
                                'conf':  confidence,
                                'face1': f1.face, 'face2': f2.face,
                            })

                print(f"✅ 接觸分析完成，偵測到 {len(contacts)} 組接觸面")

                self.msg_queue.put({
                    'status': 'assembly',
                    'data': {'path': path, 'comp_shapes': disp_shapes, 'contacts': contacts}
                })

            except Exception as e:
                self.msg_queue.put({'status': 'error_asm', 'msg': traceback.format_exc()})

        threading.Thread(target=_worker, daemon=True).start()

    # ── STEP 零件層級解析 ─────────────────────────────────────
    @staticmethod
    def _parse_step_product_tree(stp_path):
        """解析 STEP 文字，回傳 (pd_names, relationships)"""
        import re as _re
        entities = {}
        try:
            with open(stp_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().replace('\n','').replace('\r','')
            for raw in content.split(';'):
                m = _re.match(r'\s*#(\d+)\s*=\s*([A-Z_]+)\s*\((.*)\)\s*$', raw.strip())
                if m:
                    eid, etype, params = m.groups()
                    entities[eid] = {'type': etype.strip(), 'params': params}
        except Exception:
            return {}, []

        product_names = {}
        for eid, ent in entities.items():
            if ent['type'] == 'PRODUCT':
                m = _re.match(r"\s*'([^']*)'", ent['params'])
                if m:
                    name = m.group(1).strip()
                    name = _re.sub(r'\.stp(-\d+)?$', '', name, flags=_re.IGNORECASE).strip()
                    product_names[eid] = name or f'P#{eid}'

        pdf_to_prod = {}
        for eid, ent in entities.items():
            if 'PRODUCT_DEFINITION_FORMATION' in ent['type']:
                for ref in _re.findall(r'#(\d+)', ent['params']):
                    if ref in product_names:
                        pdf_to_prod[eid] = ref; break

        pd_names = {}
        for eid, ent in entities.items():
            if ent['type'] == 'PRODUCT_DEFINITION':
                for ref in _re.findall(r'#(\d+)', ent['params']):
                    if ref in pdf_to_prod:
                        prod_id = pdf_to_prod[ref]
                        pd_names[eid] = product_names.get(prod_id, f'Part#{eid}')
                        break

        # NEXT_ASSEMBLY_USAGE_OCCURRENCE → (parent_pd, child_pd, occurrence_name)
        relationships = []
        for eid, ent in entities.items():
            if ent['type'] == 'NEXT_ASSEMBLY_USAGE_OCCURRENCE':
                refs    = _re.findall(r'#(\d+)', ent['params'])
                strings = _re.findall(r"'([^']*)'", ent['params'])
                if len(refs) >= 2:
                    occ_name = strings[1] if len(strings) > 1 else ''
                    relationships.append((refs[0], refs[1], occ_name))

        return pd_names, relationships

    def _show_product_tree(self):
        """彈出視窗顯示組合件零件層級樹"""
        stp_path = getattr(self, '_asm_stp_path', None) or self.stp_path
        if not stp_path:
            messagebox.showinfo("提示", "請先載入或分析一個 STP 組合件檔案")
            return

        self.status_var.set("⏳ 解析零件層級中...")
        self.root.update_idletasks()

        try:
            pd_names, relationships = self._parse_step_product_tree(stp_path)
        except Exception as e:
            messagebox.showerror("錯誤", f"解析失敗：{e}")
            self.status_var.set("❌ 零件樹解析失敗")
            return

        if not pd_names:
            messagebox.showinfo("提示", "無法從此 STEP 檔提取零件資訊（可能缺少 PRODUCT 實體）")
            self.status_var.set("")
            return

        # ── 建立對話框 ────────────────────────────────────────
        dlg = tk.Toplevel(self.root)
        dlg.title(f"組合件零件層級 — {os.path.basename(stp_path)}")
        dlg.geometry("640x520")

        frm = tk.Frame(dlg); frm.pack(fill="both", expand=True, padx=8, pady=8)

        # 統計資訊
        n_parts  = len(pd_names)
        n_rel    = len(relationships)
        tk.Label(frm, text=f"共 {n_parts} 個產品定義，{n_rel} 條組合關係",
                 font=("Arial", 10), anchor="w").pack(fill="x", pady=(0, 4))

        # Treeview
        cols = ('name',)
        tv = ttk.Treeview(frm, columns=cols, show='tree headings', selectmode='browse')
        tv.heading('#0',   text='PD 實體 ID')
        tv.heading('name', text='零件名稱')
        tv.column('#0',   width=120, stretch=False)
        tv.column('name', width=460)

        sb_y = ttk.Scrollbar(frm, orient='vertical',   command=tv.yview)
        sb_x = ttk.Scrollbar(frm, orient='horizontal', command=tv.xview)
        tv.configure(yscrollcommand=sb_y.set, xscrollcommand=sb_x.set)
        sb_y.pack(side='right', fill='y')
        sb_x.pack(side='bottom', fill='x')
        tv.pack(fill='both', expand=True)

        # ── 建立樹狀結構 ──────────────────────────────────────
        child_ids = {child for _, child, _ in relationships}
        root_pds  = [pid for pid in pd_names if pid not in child_ids]

        # 記錄已插入的 pd（防止循環）
        inserted = set()

        def insert_node(parent_iid, pd_id, occ_label='', depth=0):
            if depth > 30 or pd_id in inserted:
                return
            inserted.add(pd_id)
            display = occ_label or pd_names.get(pd_id, f'#{pd_id}')
            full_name = pd_names.get(pd_id, f'#{pd_id}')
            # 若 occurrence label 與零件名不同，同時顯示
            if occ_label and occ_label != full_name:
                display = f"{occ_label}  ({full_name})"
            iid = tv.insert(parent_iid, 'end',
                            text=f'#{pd_id}',
                            values=(display,),
                            open=(depth < 2))
            for p, c, occ in relationships:
                if p == pd_id:
                    insert_node(iid, c, occ, depth + 1)

        if relationships:
            for rpd in sorted(root_pds, key=lambda x: int(x) if x.isdigit() else 0):
                insert_node('', rpd)
            # 若有孤立節點（沒有 NAUO 關係），也列出
            for pid in sorted(pd_names, key=lambda x: int(x) if x.isdigit() else 0):
                if pid not in inserted:
                    tv.insert('', 'end', text=f'#{pid}',
                              values=(pd_names[pid],))
        else:
            # 無 NAUO，直接平鋪所有零件
            for pid in sorted(pd_names, key=lambda x: int(x) if x.isdigit() else 0):
                tv.insert('', 'end', text=f'#{pid}', values=(pd_names[pid],))

        self.status_var.set(f"✅ 零件樹：{n_parts} 個零件，{n_rel} 條關係")

    def _finish_assembly(self, path, comp_shapes, contacts):
        self._asm_stp_path = path   # 供 _show_product_tree 使用
        # ── 顯示組合件形狀（灰藍色）────────────────────────────
        COMP_COLORS = [
            Quantity_Color(0.7, 0.85, 1.0, Quantity_TOC_RGB),
            Quantity_Color(1.0, 0.85, 0.7, Quantity_TOC_RGB),
            Quantity_Color(0.8, 1.0,  0.8, Quantity_TOC_RGB),
            Quantity_Color(1.0, 0.8,  0.9, Quantity_TOC_RGB),
            Quantity_Color(0.9, 0.9,  0.6, Quantity_TOC_RGB),
        ]
        for i, shape in enumerate(comp_shapes):
            ais = AIS_Shape(shape)
            ais.SetColor(COMP_COLORS[i % len(COMP_COLORS)])
            ais.SetTransparency(0.3)
            self.display.Context.Display(ais, False)

        # ── 每筆 contact 獨立一行（不合併）──────────────────────
        # asm_worker 已按 (comp1, comp2, ctype) 分組，每筆代表一個獨立的約束介面
        # 合併會遺失各介面的位置資訊與獨立高亮能力，故直接逐條列出

        C_RED = Quantity_Color(1.0, 0.1, 0.1, Quantity_TOC_RGB)

        # 依 (comp1, comp2, ctype) 排序，讓同一零件對的不同介面相鄰
        sorted_contacts = sorted(
            contacts,
            key=lambda c: (c.get('comp1', ''), c.get('comp2', ''), c.get('ctype', ''))
        )

        for idx, c in enumerate(sorted_contacts):
            c1    = c.get('comp1', '?')
            c2    = c.get('comp2', '?')
            ctype = c.get('ctype', '?')
            n_faces = len(c.get('face_list', []))
            label = f"{c1} ─ {c2}  [{ctype}]  ({n_faces} 個接觸面)"
            key   = f"asm_{idx}"

            # 為此接觸介面的所有面預建 AIS_Shape（紅色），勾選時顯示
            face_ais_list = []
            for face in c.get('face_list', []):
                if face is not None:
                    try:
                        ais = AIS_Shape(face)
                        ais.SetColor(C_RED)
                        ais.SetTransparency(0.0)
                        face_ais_list.append(ais)
                    except Exception:
                        pass

            self.pmi_items[key] = {
                'label':    label,
                'face_ais': face_ais_list,
                'pres_ais': None,
                'checked':  False,
            }
            self.tree.insert("", "end", iid=key, values=(f"☐   {label}",))

        self.display.FitAll()
        self.display.Context.UpdateCurrentViewer()
        n_contacts = len(sorted_contacts)
        self.status_var.set(
            f"組合件：{os.path.basename(path)}  │  "
            f"{n_contacts} 個獨立接觸介面"
        )
        self._set_btn_state("normal")

    def _asm_error(self, msg):
        messagebox.showerror("組合件分析錯誤", msg)
        self._set_btn_state("normal")
        self.status_var.set("組合件分析失敗")


    # ── 比對 & 高亮 ───────────────────────────────────────
    def _match_and_highlight(self):
        if not self.stp_path or not self.xlsx_path:
            messagebox.showwarning("缺少檔案", "請先分別載入 STP 與 XLSX 檔案！")
            return

        # 鎖定按鈕，清除舊資料
        self._set_btn_state("disabled")
        self.status_var.set("⏳ 解析中，請稍候...")
        self.root.update_idletasks()

        self.display.Context.RemoveAll(True)
        self.pmi_items.clear()
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        # 純 Python 重計算全丟 background thread，避免 UI 凍結
        stp_path  = self.stp_path
        xlsx_path = self.xlsx_path

        def _worker():
            try:
                # Step 1：解析 XLSX
                face_pmi_map, pmi_rows = parse_sfa_excel(xlsx_path)

                # Step 2：XCAF 載入（face map）
                engine = StepXcafEngine()
                engine.load(stp_path)

                # Step 3：CSV ASSOCIATION 鏈
                semantic_to_tao = load_sfa_association(xlsx_path)

                # Step 3b：Fallback
                if not pmi_rows:
                    extra_map, extra_rows = parse_sfa_visual_sheets(xlsx_path)
                    if extra_rows:
                        face_pmi_map.update(extra_map)
                        pmi_rows.extend(extra_rows)
                    if semantic_to_tao:
                        existing_sids = {r['semantic_id'] for r in pmi_rows
                                         if r['semantic_id'] is not None}
                        for i, (sem_id, tao_id) in enumerate(
                            sorted(semantic_to_tao.items(), key=lambda x: int(x[0])), 1
                        ):
                            if sem_id not in existing_sids:
                                pmi_rows.append({
                                    'label':       f"annotation_{i:02d} (sem#{sem_id})",
                                    'semantic_id': sem_id,
                                    'face_ids':    [],
                                })
                    if not pmi_rows:
                        geo_rows = build_geometry_feature_tree(engine)
                        pmi_rows.extend(geo_rows)

                # Step 4：全局 tessellated 標註解析
                # 第二個回傳值現在是從 STEP 直接解析的精確 semantic→TAO 映射
                tao_to_data, step_sem_to_tao = parse_tessellated_annotations(stp_path, scan_all=True)

                # ── Step 4a：STEP 直接鏈結（最高優先，比 XLSX 和距離都準）──
                # 以 STEP 內的 DRAUGHTING_MODEL_ITEM_ASSOCIATION 鏈覆蓋 / 補充 XLSX 映射
                if step_sem_to_tao:
                    merged = 0
                    for sid, tao_id in step_sem_to_tao.items():
                        if tao_id in tao_to_data:   # 確保 TAO 幾何已解析
                            semantic_to_tao[sid] = tao_id
                            merged += 1
                    print(f"🔗 STEP 直接鏈結補入 {merged} 條（覆蓋 XLSX 與 Hook）")

                # ── Step 4b：智能匹配邏輯 (Smart Proximity Hook) ────────
                # 只對 STEP 直接鏈結也找不到的剩餘項目執行距離估算
                # 當 CSV 斷鏈時，透過物理距離聯繫「面」與「線」
                if pmi_rows:
                    mapped_tao_ids = {semantic_to_tao.get(r['semantic_id']) for r in pmi_rows 
                                      if r['semantic_id'] and r['semantic_id'] in semantic_to_tao}
                    available_taos = {tid: data for tid, data in tao_to_data.items() if tid not in mapped_tao_ids}
                    
                    auto_links = 0
                    for row in pmi_rows:
                        # 如果這條公差沒有線（CSV 沒記或是沒連上）
                        sid = row['semantic_id']
                        # 優先用 parse_sfa_excel 已解析的 type_code（dis/dia/dat/...）
                        # sid[:3] 若 sid 是純數字（e.g."5509"）會得到"550"，型別判斷完全錯誤
                        type_code = row.get('type_code') or 'dis'
                        
                        if not sid or sid not in semantic_to_tao or not semantic_to_tao.get(sid):
                            target_fids = row.get('face_ids', [])
                            target_faces = [engine.step_id_to_face[fid] for fid in target_fids
                                            if fid in engine.step_id_to_face]
                            if not target_faces or not available_taos:
                                continue
                            
                            # 合併 target_faces 為一個 compound 以計算距離
                            face_comp = TopoDS_Compound()
                            fb = BRep_Builder()
                            fb.MakeCompound(face_comp)
                            for f in target_faces: fb.Add(face_comp, f)
                            
                            # ── [Precision Hook v5] 以面找線 ─────────────────
                            # 搜尋範圍僅限於當前項目的 target_faces 周邊
                            best_tid, min_dist = None, float('inf')
                            
                            for tid, data in available_taos.items():
                                tshape = data['shape']
                                # 結構密度：複雜框 = 大量線段或三角面片
                                is_frame = (data['tri_count'] > 10 or data['edge_count'] > 40)

                                # dia/dis 的 3D 標註本身就是複雜框（leader+文字）
                                # 所以對 dis/dia 不做任何排除
                                is_size_item = (type_code in ['dis', 'dia'])
                                if not is_size_item and not is_frame:
                                    # 幾何公差項目優先找複雜結構（公差框），
                                    # 排除純線段（單一 leader）
                                    if type_code not in ['dat']:
                                        continue

                                try:
                                    dist_tool = BRepExtrema_DistShapeShape(face_comp, tshape)
                                    if dist_tool.IsDone():
                                        d = dist_tool.Value()
                                        if d < min_dist:
                                            min_dist = d
                                            best_tid = tid
                                except Exception:
                                    pass
                                
                            # 若距離在極近範圍內（縮緊為 2.0mm，降低張冠李戴機率）
                            if best_tid and min_dist < 2.0:
                                print(f"  [Hook] {row.get('label','?')} → TAO#{best_tid} (dist={min_dist:.3f})")
                                if sid:
                                    semantic_to_tao[sid] = best_tid
                                else:
                                    # 為完全無 ID 的項目建立虛擬連結
                                    fake_sid = f"auto_pmi_{best_tid}"
                                    row['semantic_id'] = fake_sid
                                    semantic_to_tao[fake_sid] = best_tid
                                auto_links += 1
                                # 為了防呆，被勾走的 Tao 不再給別人用
                                del available_taos[best_tid]

                    if auto_links:
                        print(f"ℹ️  智能掛鉤：透過空間距離自動聯繫了 {auto_links} 條導引線")

                # Step 4c：後備計畫 ────────
                if not pmi_rows:
                    for tao_id in sorted(tao_to_data.keys(), key=lambda x: int(x)):
                        sid_key = f"unmapped_{tao_id}"
                        pmi_rows.append({
                            'label':       f"3D annotation #{tao_id}",
                            'semantic_id': sid_key,
                            'face_ids':    [],
                        })
                        semantic_to_tao[sid_key] = tao_id

                # 回報成功結果
                self.msg_queue.put({
                    'status':  'success',
                    'data': {
                        'engine':       engine,
                        'face_pmi_map': face_pmi_map,
                        'pmi_rows':     pmi_rows,
                        'semantic_to_tao': semantic_to_tao,
                        'tao_to_shape':  tao_to_data
                    }
                })
            except Exception as e:
                self.msg_queue.put({
                    'status': 'error',
                    'msg':    f"背景運算發生錯誤：{str(e)}\n{traceback.format_exc()}"
                })

        threading.Thread(target=_worker, daemon=True).start()

    def _poll_queue(self):
        """定時掃描訊息隊列，將背景資料分發給主執行緒執行"""
        try:
            while not self.msg_queue.empty():
                msg = self.msg_queue.get_nowait()
                if msg['status'] == 'success':
                    d = msg['data']
                    self._finish_highlight(
                        d['engine'], d['face_pmi_map'], d['pmi_rows'],
                        d['semantic_to_tao'], d['tao_to_shape']
                    )
                elif msg['status'] == 'assembly':
                    d = msg['data']
                    self._finish_assembly(d['path'], d['comp_shapes'], d['contacts'])
                elif msg['status'] in ('error', 'error_asm'):
                    self._highlight_error(msg['msg'])
                else:
                    self._highlight_error(msg.get('msg', '未知錯誤'))
        except Exception: pass
        finally:
            try:
                self.root.after(100, self._poll_queue)
            except Exception: pass  # 視窗已關閉時忽略

    def _highlight_error(self, msg):
        print(f"❌ 解析失敗：{msg}")
        messagebox.showerror("解析失敗", msg)
        self.status_var.set("❌ 解析失敗")
        self._set_btn_state("normal")

    def _finish_highlight(self, engine, face_pmi_map, pmi_rows,
                          semantic_to_tao, tao_to_shape):
        """background thread 完成後，在主執行緒進行所有 OCC/UI 操作"""
        self.engine       = engine
        self.face_pmi_map = face_pmi_map
        self.pmi_rows     = pmi_rows

        # ── Step 0：大掃除 (避免新舊資料混雜) ──
        self.tree.delete(*self.tree.get_children()) # 清空列表 UI
        self.pmi_items.clear()                      # 清空後台映射
        self.display.Context.RemoveAll(True)       # 清空 3D 視窗

        # ── Step 5：顯示灰色底圖 ──
        if self.engine.root_shape:
            ais_model = AIS_Shape(self.engine.root_shape)
            ais_model.SetColor(C_GRAY)
            ais_model.SetTransparency(0.6)
            self.display.Context.Display(ais_model, False)

        # ── Step 6：建立 pmi_items ──
        print("🔍 正在準備 3D 項目與標籤...")
        try:
            self._build_pmi_items(semantic_to_tao, tao_to_shape)
        except Exception as e:
            print(f"❌ 建立 3D 項目發生嚴重錯誤：{e}")
            traceback.print_exc()

        # ── Step 7：填入 Treeview ──
        print(f"✅ 正在載入 Treeview ({len(self.pmi_items)} 條)...")
        for key, data in self.pmi_items.items():
            self.tree.insert("", "end", iid=key,
                             values=(f"☐   {data['label']}",),
                             tags=("unchecked",))

        self.display.FitAll()
        self.display.Context.UpdateCurrentViewer()

        matched_face = sum(1 for v in self.pmi_items.values() if v['face_ais'])
        matched_pres = sum(1 for v in self.pmi_items.values() if v['pres_ais'])
        self.status_var.set(
            f"✅ {len(self.pmi_items)} 條 PMI | "
            f"綠 face: {matched_face} | 黑線: {matched_pres}"
        )
        self._set_btn_state("normal")

    def _build_pmi_items(self, semantic_to_tao, tao_to_shape):
        """
        ASSOCIATION 橋接：
          Path A  face_ids (XLSX geometry 欄) → step_id_to_face → AIS_Shape (綠)
          Path B  semantic_id (XLSX ID 欄)
                    → semantic_to_tao (CSV 鏈)
                    → tao_to_shape (STP tessellated 解析)
                    → AIS_Shape (黑線 + 符號)

        Key 設計：用數字 index 字串 "0","1","2"... 作為 pmi_items 的 key 和
                  Treeview 的 iid，避免相同 label 造成 dict 覆蓋與 iid 衝突。
        """
        for idx, row in enumerate(self.pmi_rows):
            key = str(idx)
            label = row['label']
            is_interactive  = row.get('is_interactive', False)
            is_datum_row    = row.get('is_datum', False)
            is_feat_only    = row.get('is_feature_only', False)

            # 顏色規則：基準面/純特徵面 → 綠色；交互 → 紫色；個別 → 橘色
            if is_datum_row or is_feat_only:
                pmi_color = C_GREEN
            elif is_interactive:
                pmi_color = C_PURPLE
            else:
                pmi_color = C_ORANGE

            # Path A：面高亮（依類型著色）
            face_ais_list = []
            
            # 1. 高亮自己關聯的面
            for fid in row['face_ids']:
                topo = self.engine.step_id_to_face.get(fid)
                if topo:
                    ais = AIS_Shape(topo)
                    ais.SetColor(pmi_color)
                    ais.SetTransparency(0.0)
                    face_ais_list.append(ais)

            # 2. [新增功能] 聯動高亮參考的基準面 (Datum)
            # 例如: "[交互] 🎯 par4: // | 0.002 | C" 
            if is_interactive and '|' in label:
                parts = label.split('|')
                raw_refs = [p.strip() for p in parts[1:]] 
                
                # 掃描所有的基準面 (Datum features)，比對是否有被參考
                for d_row in self.pmi_rows:
                    if d_row.get('is_datum'):
                        # datum 的 label 通常為 "🚩 dat: [C]"
                        dm = re.search(r'\[([A-Z0-9_-]+)\]', d_row['label'])
                        if dm:
                            datum_name = dm.group(1)
                            # 如果基準名稱出現在公差標示的後段參數中
                            if any(datum_name in r for r in raw_refs):
                                # 找到被參考的基準面！聯動顯示為綠色
                                for d_fid in d_row['face_ids']:
                                    d_topo = self.engine.step_id_to_face.get(d_fid)
                                    if d_topo:
                                        d_ais = AIS_Shape(d_topo)
                                        d_ais.SetColor(C_GREEN)
                                        d_ais.SetTransparency(0.0)
                                        face_ais_list.append(d_ais)

            # Path B：完整 3D 標註（領引線 + 符號輪廓）
            # 基準面與純特徵面(無公差)不顯示黑色標註
            pres_ais = None
            sid = row['semantic_id']
            if sid and not is_datum_row and not is_feat_only:
                tao_id = semantic_to_tao.get(sid)
                if tao_id:
                    pmi_data = tao_to_shape.get(tao_id)
                    # 相容性檢查：如果回傳的是字典（新版元數據結構）
                    t_shape = pmi_data['shape'] if isinstance(pmi_data, dict) else pmi_data
                    if t_shape:
                        pres_ais = AIS_Shape(t_shape)
                        pres_ais.SetColor(C_BLACK)
                        pres_ais.SetWidth(1.5)

            self.pmi_items[key] = {
                'label':    label,
                'face_ais': face_ais_list,
                'pres_ais': pres_ais,
                'checked':  False,
            }

    # ── Treeview 互動 ─────────────────────────────────────
    def _on_tree_click(self, event):
        key = self.tree.identify_row(event.y)
        if not key or key not in self.pmi_items:
            return
        data    = self.pmi_items[key]
        is_on   = not data['checked']
        data['checked'] = is_on
        icon = "☑" if is_on else "☐"
        tag  = "checked" if is_on else "unchecked"
        self.tree.item(key, values=(f"{icon}   {data['label']}",), tags=(tag,))
        self._apply_visibility(key, is_on)

    def _on_tree_select(self, event):
        """單擊選取條目時，暫時高亮並自動縮放（不切換勾選狀態）"""
        selected = self.tree.selection()
        if not selected: return
        key = selected[0]
        if key not in self.pmi_items: return
        
        data = self.pmi_items[key]
        ctx  = self.display.Context
        
        # 1. 確保相關幾何顯示出來 (即使沒勾選也會暫時顯示一下)
        shown_any = False
        for ais in data['face_ais']:
            ctx.Display(ais, False)
            try: ctx.SetZLayer(ais, 2)
            except: pass
            shown_any = True
            
        if data['pres_ais']:
            ctx.Display(data['pres_ais'], False)
            try: ctx.SetZLayer(data['pres_ais'], 2)
            except: pass
            shown_any = True
            
        if shown_any:
            ctx.UpdateCurrentViewer()
            # 2. 自動縮放到該零件/接觸位置
            # 使用第一個幾何的 Bounding Box 進行視角追蹤
            all_ais = data['face_ais'] + ([data['pres_ais']] if data['pres_ais'] else [])
            if all_ais:
                self.display.FitAll() # 簡易版：FitAll。進階版可計算局部 BBox

    def _apply_visibility(self, key, show):
        data = self.pmi_items[key]
        ctx  = self.display.Context

        for ais in data['face_ais']:
            if show:
                ctx.Display(ais, False)
                try: ctx.SetZLayer(ais, 2)
                except: pass
            else:
                ctx.Erase(ais, False)

        if data['pres_ais']:
            if show:
                ctx.Display(data['pres_ais'], False)
                try: ctx.SetZLayer(data['pres_ais'], 2)
                except: pass
            else:
                ctx.Erase(data['pres_ais'], False)

        ctx.UpdateCurrentViewer()

    # ── 批次操作 ──────────────────────────────────────────
    # ── 報表導出 ──────────────────────────────────────────
    def _export_csv(self):
        """自動偵測模式，導出對應 CSV：組合件→接觸介面報表 / PMI→BOM對照表"""
        if not self.pmi_items:
            messagebox.showwarning("警告", "清單是空的，請先執行分析。")
            return

        is_asm_mode = any(k.startswith("asm_") for k in self.pmi_items)

        if is_asm_mode:
            # ── 組合件接觸介面報表 ────────────────────────────────
            path = filedialog.asksaveasfilename(
                defaultextension=".csv", filetypes=[("CSV Files", "*.csv")],
                initialfile="Assembly_Contact_Report.csv"
            )
            if not path: return
            data_rows = []
            for key, item in sorted(self.pmi_items.items(),
                                    key=lambda x: int(x[0].replace("asm_", ""))):
                label = item['label']
                m = re.match(r'^(.+?)\s*─\s*(.+?)\s*\[(.+?)\]\s*\((\d+)', label)
                if m:
                    comp1, comp2, ctype, n_faces = (m.group(1).strip(), m.group(2).strip(),
                                                    m.group(3), int(m.group(4)))
                else:
                    comp1, comp2, ctype, n_faces = label, '', '?', 0
                data_rows.append({
                    "序號":     len(data_rows) + 1,
                    "零件 A":   comp1,
                    "零件 B":   comp2,
                    "接觸類型": ctype,
                    "接觸面數": n_faces,
                    "是否勾選": "✓" if item.get('checked') else "",
                    "標籤全文": label,
                })
            try:
                pd.DataFrame(data_rows).to_csv(path, index=False, encoding='utf-8-sig')
                messagebox.showinfo("成功", f"組合件接觸報表已導出：\n{path}\n共 {len(data_rows)} 筆介面")
            except Exception as e:
                messagebox.showerror("錯誤", f"導出失敗：{e}")

        else:
            # ── PMI BOM 對照表 ────────────────────────────────────
            if not self.engine.step_id_to_face:
                messagebox.showwarning("警告", "尚未載入 STP 檔案，無幾何資料可導出。")
                return
            path = filedialog.asksaveasfilename(
                defaultextension=".csv", filetypes=[("CSV Files", "*.csv")],
                initialfile="SFA_PMI_BOM_Report.csv"
            )
            if not path: return
            face_info = {}
            for fid, face in self.engine.step_id_to_face.items():
                try:
                    surf = BRepAdaptor_Surface(face); stype = surf.GetType()
                    g_type, params, sym = 'OTHER', '-', 'F'
                    if stype == GeomAbs_Plane:
                        g_type, params, sym = 'PLANE', 'ideal', 'P'
                    elif stype == GeomAbs_Cylinder:
                        r = surf.Cylinder().Radius()
                        sym = 'H' if (face.Orientation() == TopAbs_REVERSED) else 'S'
                        g_type, params = 'CYLINDRICAL_SURFACE', f"R={r:.3f} (D={r*2:.3f})"
                    face_info[fid] = {'type': g_type, 'params': params}
                except Exception:
                    face_info[fid] = {'type': 'ERROR', 'params': '-'}
            data_rows = []; type_counters = defaultdict(int)
            part_prefix = os.path.splitext(os.path.basename(self.stp_path))[0] if self.stp_path else "X"
            for key, item_data in self.pmi_items.items():
                try: idx = int(key)
                except ValueError: continue
                row_info = self.pmi_rows[idx] if idx < len(self.pmi_rows) else {}
                label  = item_data['label']; fids = row_info.get('face_ids', [])
                t_code = row_info.get('type_code', 'tol').upper()
                type_counters[t_code] += 1
                g = face_info.get(fids[0] if fids else None, {'type': '-', 'params': '-'})
                data_rows.append({
                    "公差代號":      f"{part_prefix}-{t_code}{type_counters[t_code]}",
                    "名稱/幾何類型": g['type'],   "數量/面數": len(fids),
                    "幾何參數":      g['params'],  "公差標註(PMI)": label,
                    "Face ID":       ", ".join(fids),
                    "是否勾選":      "✓" if item_data.get('checked') else "",
                })
            try:
                pd.DataFrame(data_rows).to_csv(path, index=False, encoding='utf-8-sig')
                messagebox.showinfo("成功", f"PMI 報表已導出：\n{path}\n共 {len(data_rows)} 筆")
            except Exception as e:
                messagebox.showerror("錯誤", f"導出失敗：{e}")


    def _select_all(self):
        for key, data in self.pmi_items.items():
            data['checked'] = True
            self.tree.item(key, values=(f"☑   {data['label']}",), tags=("checked",))
            self._apply_visibility(key, True)

    def _clear_all(self):
        for key, data in self.pmi_items.items():
            data['checked'] = False
            self.tree.item(key, values=(f"☐   {data['label']}",), tags=("unchecked",))
            self._apply_visibility(key, False)


# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    SfaPmiViewer()
