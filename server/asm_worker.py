"""
asm_worker.py  ─ 組合件接觸分析子進程 (魯棒版)
======================================================
支援兩種零件辨識路徑：
  路徑 A: NIST SFA CSV（若存在 -sfa-csv 目錄）
  路徑 B: XCAF 直接從 STEP 讀取組裝層級（無需外部 CSV）
並增加了對異常幾何實體的錯誤處理，防止 Standard_OutOfRange 崩潰。
"""
import sys, os, json, re, traceback, csv, math
from collections import defaultdict

os.environ["CSF_GraphicDriver"] = "off"

from OCC.Core.STEPControl   import STEPControl_Reader
from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
from OCC.Core.TDocStd       import TDocStd_Document
from OCC.Core.XCAFApp       import XCAFApp_Application
from OCC.Core.XCAFDoc       import XCAFDoc_DocumentTool
from OCC.Core.TDF           import TDF_LabelSequence, TDF_Label
from OCC.Core.TDataStd      import TDataStd_Name
from OCC.Core.TopExp        import TopExp_Explorer
from OCC.Core.TopAbs        import TopAbs_FACE, TopAbs_SOLID, TopAbs_SHELL, TopAbs_REVERSED
from OCC.Core.TopoDS        import topods
from OCC.Core.BRepAdaptor   import BRepAdaptor_Surface
from OCC.Core.GeomAbs       import GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone
from OCC.Core.Bnd           import Bnd_Box
from OCC.Core.BRepBndLib    import brepbndlib
from OCC.Core.BRepExtrema   import BRepExtrema_DistShapeShape
from OCC.Core.IFSelect      import IFSelect_RetDone
from OCC.Core.gp            import gp_Pnt
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
from OCC.Core.GeomLProp     import GeomLProp_CLProps
from OCC.Core.BRepLProp     import BRepLProp_CLProps

FACE_CONTACT_DIST = 0.05   # mm，CAD 組合件常有 0.01~0.05mm 建模間隙
MIN_CONTACT_AREA  = 0.2    # mm²，雙面都小於此值才排除（保留小孔端面碰大平面）
MIN_SINGLE_AREA   = 0.01   # mm²，單面低於此值直接排除（退化面 / 幾何雜訊）
DOT_PARALLEL_THR  = 0.97   # |cos θ| > 0.97 → 視為平行（夾角 < ~14°）
DOT_PERP_THR      = 0.05   # |cos θ| < 0.05 → 視為垂直（夾角 > ~87°）

def write_json(path, data):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except: pass

def bbox_get(bb):
    try: return bb.Get()
    except: return None

def boxes_overlap(c1, c2, tol=0.05):
    """3 軸全部重疊才 True（用於 component-level 粗篩）"""
    if not c1 or not c2: return False
    x1,y1,z1,X1,Y1,Z1 = c1
    x2,y2,z2,X2,Y2,Z2 = c2
    return (x1-tol<=X2 and X1+tol>=x2 and
            y1-tol<=Y2 and Y1+tol>=y2 and
            z1-tol<=Z2 and Z1+tol>=z2)

def bbox_overlap_dim_count(c1, c2, tol=0.05):
    """回傳兩個 BBox 有實質重疊的軸數（0~3）"""
    if not c1 or not c2: return 0
    x1,y1,z1,X1,Y1,Z1 = c1
    x2,y2,z2,X2,Y2,Z2 = c2
    count = 0
    if x1-tol<=X2 and X1+tol>=x2: count += 1
    if y1-tol<=Y2 and Y1+tol>=y2: count += 1
    if z1-tol<=Z2 and Z1+tol>=z2: count += 1
    return count

def passes_overlap_rule(f1, f2, tol=0.3):
    """
    型態感知的 BBox 重疊規則：
      平面–平面：需 2 軸以上重疊（面接觸需要面積）
      圓柱/孔–圓柱/孔：不要求 dim_count（同軸插配 BBox 不穩定）
      平面–圓柱/孔：需 1 軸以上（端面或側面）
      其他組合：需 1 軸以上
    """
    s1, s2 = f1.get('stype', '其他'), f2.get('stype', '其他')
    dim = bbox_overlap_dim_count(f1['bbox'], f2['bbox'], tol)
    cyl_types = ('孔', '圓柱面', '錐面')

    if s1 == '平面' and s2 == '平面':
        return dim >= 2

    if s1 in cyl_types and s2 in cyl_types:
        # 同軸插配只要 BBox 在任意軸有交集即可
        return dim >= 1

    if (s1 == '平面' and s2 in cyl_types) or \
       (s1 in cyl_types and s2 == '平面'):
        return dim >= 1

    return dim >= 1

def merge_bbox(a, b):
    if a is None: return b
    if b is None: return a
    return (min(a[0],b[0]), min(a[1],b[1]), min(a[2],b[2]),
            max(a[3],b[3]), max(a[4],b[4]), max(a[5],b[5]))

def _build_rank_to_id(stp_path):
    rank_to_id = {}
    try:
        with open(stp_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            data_sec = re.search(r'DATA;\s*(.*?)\s*ENDSEC;', content, re.DOTALL | re.IGNORECASE)
            if data_sec:
                all_ids = re.findall(r'#(\d+)\s*=', data_sec.group(1))
                for i, eid in enumerate(all_ids): rank_to_id[i + 1] = eid
    except: pass
    return rank_to_id

def _parse_sfa_csvs(stp_path):
    csv_dir = stp_path.replace('.STP', '-sfa-csv').replace('.stp', '-sfa-csv')
    if not os.path.exists(csv_dir): return None, None
    
    def read_csv(name):
        path = os.path.join(csv_dir, name)
        if not os.path.exists(path): return []
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            start = 0
            for i, l in enumerate(lines):
                if l.strip().startswith('ID,'): start = i; break
            return list(csv.DictReader(lines[start:]))

    p_rows = read_csv('product.csv')
    prod_to_name = {r['ID']: re.sub(r'\.stp(-\d+)?$', '', r.get('name', '').strip(), flags=re.IGNORECASE).strip() for r in p_rows}

    nauo_list = read_csv('next_assembly_usage_occurrence.csv')
    pd_to_nauos = defaultdict(list)
    nauo_to_data = {}
    for r in nauo_list:
        nid = r['ID']
        c_pd = re.search(r'product_definition\s+(\d+)', r.get('related_product_definition',''))
        if c_pd:
            pd_id = c_pd.group(1)
            pd_to_nauos[pd_id].append(nid)
            nauo_to_data[nid] = r

    pds_to_pd = {}
    for r in read_csv('product_definition_shape.csv'):
        pd_m = re.search(r'product_definition\s+(\d+)', r.get('definition',''))
        if pd_m: pds_to_pd[r['ID']] = pd_m.group(1)

    sr_to_pd = {}
    for r in read_csv('shape_definition_representation.csv'):
        pds_m = re.search(r'product_definition_shape\s+(\d+)', r.get('definition',''))
        sr_m = re.search(r'shape_representation\s+(\d+)', r.get('used_representation',''))
        if pds_m and sr_m:
            pds_id = pds_m.group(1)
            sr_to_pd[sr_m.group(1)] = pds_to_pd.get(pds_id)

    absr_list = read_csv('advanced_brep_shape_representation.csv')
    solid_to_instance = {}
    for r in absr_list:
        sr_id = r['ID']
        if sr_id not in sr_to_pd: continue
        pd_id = sr_to_pd[sr_id]
        m_ids = re.findall(r'\b(\d+)\b', r.get('items',''))
        for eid in m_ids:
            solid_to_instance[eid] = {'name': prod_to_name.get(pd_id, "Unknown"), 'pd_id': pd_id}

    return solid_to_instance, nauo_to_data


def _get_label_name(label):
    """從 XCAF label 取得名稱"""
    try:
        name_attr = TDataStd_Name()
        if label.FindAttribute(TDataStd_Name.GetID(), name_attr):
            raw = name_attr.Get().ToExtString()
            # 清理名稱：移除 .stp 後綴
            return re.sub(r'\.stp(-\d+)?$', '', raw.strip(), flags=re.IGNORECASE).strip()
    except Exception:
        pass
    return None


def _xcaf_identify_solids(stp_path):
    """
    路徑 B: 直接用 XCAF 從 STEP 讀取組裝層級。
    回傳 (solid_to_name, xcaf_solids)：
      solid_to_name  {idx: part_name}
      xcaf_solids    對應的 TopoDS_Solid 列表（世界座標，含 location）

    關鍵：用 GetShape(comp_label) 而非 GetShape(ref)——
    comp_label 包含 location，回傳世界座標的 instance shape。
    """
    try:
        app = XCAFApp_Application.GetApplication()
        doc = TDocStd_Document("XCAF-ASM")
        app.NewDocument("XCAF-ASM", doc)

        reader = STEPCAFControl_Reader()
        reader.SetColorMode(True)
        reader.SetNameMode(True)
        if reader.ReadFile(stp_path) != IFSelect_RetDone:
            return {}, []
        reader.Transfer(doc)

        shape_tool = XCAFDoc_DocumentTool.ShapeTool(doc.Main())
        roots = TDF_LabelSequence()
        shape_tool.GetFreeShapes(roots)

        # 收集 (name, world_coord_shape)
        comp_list = []
        for i in range(1, roots.Length() + 1):
            root_label = roots.Value(i)
            root_name  = _get_label_name(root_label)

            comp_labels = TDF_LabelSequence()
            shape_tool.GetComponents(root_label, comp_labels)

            if comp_labels.Length() > 0:
                for ci in range(1, comp_labels.Length() + 1):
                    comp_label = comp_labels.Value(ci)
                    # 名稱：優先取 instance label，其次取 referred shape label
                    comp_name = _get_label_name(comp_label)
                    if not comp_name and shape_tool.IsReference(comp_label):
                        ref_out = TDF_Label()
                        if shape_tool.GetReferredShape(comp_label, ref_out):
                            comp_name = _get_label_name(ref_out)
                    # GetShape(comp_label) 包含 location → 世界座標
                    inst_shape = shape_tool.GetShape(comp_label)
                    if inst_shape and not inst_shape.IsNull():
                        comp_list.append((comp_name or f"零件_{ci}", inst_shape))
            else:
                root_shape = shape_tool.GetShape(root_label)
                if root_shape and not root_shape.IsNull():
                    comp_list.append((root_name or "單一零件", root_shape))

        # 提取 solid（世界座標）
        xcaf_solids   = []
        solid_to_name = {}
        for comp_name, comp_shape in comp_list:
            exp = TopExp_Explorer(comp_shape, TopAbs_SOLID)
            while exp.More():
                s = topods.Solid(exp.Current())
                if not s.IsNull():
                    solid_to_name[len(xcaf_solids)] = comp_name
                    xcaf_solids.append(s)
                exp.Next()

        print(f"[XCAF] 從 STEP 直接辨識到 {len(comp_list)} 個元件，{len(xcaf_solids)} 個 solid", flush=True)
        return solid_to_name, xcaf_solids

    except Exception as e:
        print(f"[XCAF] 備援辨識失敗: {e}", flush=True)
        traceback.print_exc()
        return {}, []


def link_occ_solids_to_instances(reader, all_solids, solid_info, nauo_data, stp_path):
    ws = reader.WS(); model = ws.Model(); tr = ws.TransferReader()
    rank_to_id = _build_rank_to_id(stp_path)
    blueprints = {}
    if solid_info:
        nb = model.NbEntities()
        for i in range(1, nb + 1):
            eid = rank_to_id.get(i)
            if eid and eid in solid_info:
                ent = model.Value(i)
                shp = tr.ShapeResult(ent)
                if not shp or shp.IsNull():
                    reader.TransferEntity(ent)
                    shp = tr.ShapeResult(ent)
                if shp and not shp.IsNull():
                    blueprints[eid] = (shp, solid_info[eid])

    idx_to_instance = {}
    solid_mapping_out = []
    for idx, solid in enumerate(all_solids):
        found = False
        for eid, (ref_shp, info) in blueprints.items():
            if solid.IsPartner(ref_shp):
                idx_to_instance[idx] = info['name']
                found = True; break
        
        name = idx_to_instance.get(idx, f"未識別_{idx}")
        bb = Bnd_Box()
        try:
            brepbndlib.Add(solid, bb)
        except Exception: pass # 忽略無法計算 BBox 的實體
        
        solid_mapping_out.append({'name': name, 'bbox': list(bb.Get()) if not bb.IsVoid() else None})
    return idx_to_instance, solid_mapping_out

def dot3(a, b):
    """兩個 (x,y,z) tuple 的點積"""
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]

def sub3(a, b):
    """向量相減 a - b"""
    return (a[0]-b[0], a[1]-b[1], a[2]-b[2])

def norm3(a):
    """向量長度"""
    return math.sqrt(a[0]*a[0] + a[1]*a[1] + a[2]*a[2])

def cross3(a, b):
    """向量外積"""
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])

# ── 共軸性閾值 ──
COAXIAL_DIST_THR   = 1.0    # mm，兩軸線的橫向距離上限
RADIUS_RATIO_MIN   = 0.3    # 半徑比最小值（小半徑/大半徑 > 0.3）
RADIUS_RATIO_MAX   = 3.0    # 半徑比最大值（避免螺絲孔配大軸）
AXIAL_OVERLAP_THR  = 0.1    # mm，軸向投影重疊下限（放寬以捕獲短孔/局部插入）


def _axis_lateral_dist(o1, d1, o2, d2):
    """
    計算兩軸線的橫向距離（最近距離）。
    d1, d2 必須近似平行。
    返回兩軸線之間的垂直距離。
    """
    delta = sub3(o2, o1)
    # 沿 d1 方向的投影分量
    proj = dot3(delta, d1)
    # 橫向分量 = delta - proj * d1
    lateral = (delta[0] - proj*d1[0], delta[1] - proj*d1[1], delta[2] - proj*d1[2])
    return norm3(lateral)


def _axial_overlap(f1, f2):
    """
    計算兩個圓柱/孔面在軸線方向上的投影重疊長度。
    利用 BBox 在軸線方向的投影來估算。
    """
    ax = f1.get('cyl_axis')
    if not ax:
        return 1.0  # 無法計算時預設通過

    bb1, bb2 = f1['bbox'], f2['bbox']
    # BBox 八個角點投影到軸線方向，取 min/max
    def proj_range(bb):
        corners = [
            (bb[0], bb[1], bb[2]), (bb[3], bb[1], bb[2]),
            (bb[0], bb[4], bb[2]), (bb[3], bb[4], bb[2]),
            (bb[0], bb[1], bb[5]), (bb[3], bb[1], bb[5]),
            (bb[0], bb[4], bb[5]), (bb[3], bb[4], bb[5]),
        ]
        projs = [dot3(c, ax) for c in corners]
        return min(projs), max(projs)

    lo1, hi1 = proj_range(bb1)
    lo2, hi2 = proj_range(bb2)
    overlap = min(hi1, hi2) - max(lo1, lo2)
    return overlap


def _classify_plane_cyl(dot_val):
    """
    判斷平面與圓柱/孔/錐面的接觸類型：
      dot ≈ 0 → 平面碰觸側面（法向 ⊥ 軸線）
      dot ≈ 1 → 平面碰觸端面/肩部（法向 ∥ 軸線）
    兩種都是合法接觸，中間角度才拒絕。
    """
    d = abs(dot_val)
    if d < DOT_PERP_THR:
        return True, '側面接觸'
    if d > DOT_PARALLEL_THR:
        return True, '端面接觸'
    return False, ''


def check_geometry_compatible(f1, f2):
    """
    根據面型組合進行幾何相容性檢查。
    回傳 (pass: bool, ctype: str, reject_reason: str)
      reject_reason 只在 pass=False 時有值，用於分層診斷。
    """
    s1, s2 = f1['stype'], f2['stype']
    cyl_types = ('孔', '圓柱面', '錐面')

    # ── Plane–Plane ──
    if s1 == '平面' and s2 == '平面':
        n1 = f1.get('normal'); n2 = f2.get('normal')
        if n1 and n2:
            if abs(dot3(n1, n2)) < DOT_PARALLEL_THR:
                return False, '', 'plane'
        return True, '平面接合', ''

    # ── Cyl/孔/Cone–Cyl/孔/Cone ──
    if s1 in cyl_types and s2 in cyl_types:
        ax1 = f1.get('cyl_axis'); ax2 = f2.get('cyl_axis')

        # (1) 軸線平行性
        if ax1 and ax2:
            if abs(dot3(ax1, ax2)) < DOT_PARALLEL_THR:
                return False, '', 'axis'

        # (2) 共軸性：兩軸線的橫向距離
        o1 = f1.get('cyl_origin'); o2 = f2.get('cyl_origin')
        if o1 and o2 and ax1:
            lat_dist = _axis_lateral_dist(o1, ax1, o2, ax2 or ax1)
            if lat_dist > COAXIAL_DIST_THR:
                return False, '', 'coaxial'

        # (3) 半徑比合理性
        r1 = f1.get('cyl_radius'); r2 = f2.get('cyl_radius')
        if r1 and r2 and r1 > 0 and r2 > 0:
            ratio = r1 / r2 if r1 < r2 else r2 / r1
            if ratio < RADIUS_RATIO_MIN:
                return False, '', 'radius'

        # (4) 軸向重疊
        overlap = _axial_overlap(f1, f2)
        if overlap < AXIAL_OVERLAP_THR:
            return False, '', 'overlap'

        label = '圓柱/孔同軸接合' if '錐面' not in (s1, s2) else '錐面同軸接合'
        return True, label, ''

    # ── Plane–Cyl/Cone ──
    if s1 == '平面' and s2 in cyl_types:
        n1 = f1.get('normal'); ax2 = f2.get('cyl_axis')
        if n1 and ax2:
            ok, sub = _classify_plane_cyl(dot3(n1, ax2))
            if not ok:
                return False, '', 'plane_cyl'
            return True, f'平面/{s2}{sub}', ''
        return True, f'平面/{s2}接合', ''

    if s1 in cyl_types and s2 == '平面':
        ax1 = f1.get('cyl_axis'); n2 = f2.get('normal')
        if ax1 and n2:
            ok, sub = _classify_plane_cyl(dot3(ax1, n2))
            if not ok:
                return False, '', 'plane_cyl'
            return True, f'{s1}/平面{sub}', ''
        return True, f'{s1}/平面接合', ''

    # ── 其他組合（Sphere / Torus / BSpline 等）不做角度限制 ──
    return True, f"{s1}/{s2}接合", ''

def calc_face_area(face):
    """計算面的面積"""
    try:
        from OCC.Core.GProp import GProp_GProps
        from OCC.Core.BRepGProp import brepgprop
        props = GProp_GProps()
        brepgprop.SurfaceProperties(face, props)
        return props.Mass()  # Mass 就是面積
    except:
        return 0.0

def extract_faces(shp, name):
    faces, bb_total = [], Bnd_Box()
    exp = TopExp_Explorer(shp, TopAbs_FACE)
    while exp.More():
        f = topods.Face(exp.Current())
        if f.IsNull(): exp.Next(); continue
        bb = Bnd_Box()
        try:
            brepbndlib.Add(f, bb)
        except Exception:
            exp.Next(); continue
        c = bbox_get(bb)
        if c:
            bb_total.Add(bb)
            fi = {'comp':name, 'bbox':c, 'stype':'其他', 'face':f, 'area': 0.0}
            try:
                ad = BRepAdaptor_Surface(f); st = ad.GetType()
                if st == GeomAbs_Plane:
                    fi['stype'] = '平面'
                    pln = ad.Plane()
                    d = pln.Axis().Direction()
                    fi['normal'] = (d.X(), d.Y(), d.Z())
                elif st == GeomAbs_Cylinder:
                    fi['stype'] = '孔' if f.Orientation() == TopAbs_REVERSED else '圓柱面'
                    cyl = ad.Cylinder()
                    ax = cyl.Axis()
                    d = ax.Direction()
                    loc = ax.Location()
                    fi['cyl_axis']   = (d.X(), d.Y(), d.Z())
                    fi['cyl_origin'] = (loc.X(), loc.Y(), loc.Z())
                    fi['cyl_radius'] = cyl.Radius()
                elif st == GeomAbs_Cone:
                    fi['stype'] = '錐面'
                    cone = ad.Cone()
                    ax = cone.Axis()
                    d = ax.Direction()
                    loc = ax.Location()
                    fi['cyl_axis']   = (d.X(), d.Y(), d.Z())
                    fi['cyl_origin'] = (loc.X(), loc.Y(), loc.Z())
                    fi['cyl_radius'] = cone.RefRadius()
            except: pass
            # 計算面積
            fi['area'] = calc_face_area(f)
            faces.append(fi)
        exp.Next()
    return faces, bbox_get(bb_total)

def main():
    if len(sys.argv) < 3: sys.exit(1)
    stp_path, out_json = sys.argv[1], sys.argv[2]
    result = {'status':'error','msg':'','contacts':[],'n_parts':0,'n_faces':0}
    try:
        reader = STEPControl_Reader()
        if reader.ReadFile(stp_path) != IFSelect_RetDone:
            result['msg'] = "無法讀取 STEP"; write_json(out_json, result); return
        reader.TransferRoots()

        # ── 零件辨識：路徑 A (SFA CSV) 或 路徑 B (XCAF) ──
        solid_info, nauo_data = _parse_sfa_csvs(stp_path)
        id_source = 'csv' if solid_info else 'xcaf'

        all_solids = []
        for i in range(1, reader.NbShapes() + 1):
            root = reader.Shape(i)
            exp = TopExp_Explorer(root, TopAbs_SOLID)
            while exp.More():
                s = topods.Solid(exp.Current())
                if not s.IsNull(): all_solids.append(s)
                exp.Next()
        if not all_solids:
            for i in range(reader.NbShapes()):
                exp = TopExp_Explorer(reader.Shape(i+1), TopAbs_SHELL)
                while exp.More():
                    s = topods.Shell(exp.Current())
                    if not s.IsNull(): all_solids.append(s)
                    exp.Next()

        if solid_info:
            # 路徑 A: 使用 SFA CSV 辨識
            print(f"[ID] 路徑 A: 使用 SFA CSV 辨識零件", flush=True)
            idx_to_inst, solid_mapping = link_occ_solids_to_instances(
                reader, all_solids, solid_info, nauo_data, stp_path)
        else:
            # 路徑 B: 直接使用 XCAF reader 的 solid（世界座標，已含 location）
            # 不做跨 reader 比對，XCAF 的 GetShape(comp_label) 已是組裝後座標
            print(f"[ID] 路徑 B: 無 SFA CSV，使用 XCAF 直接辨識零件", flush=True)
            xcaf_name_map, xcaf_solids = _xcaf_identify_solids(stp_path)

            if xcaf_solids:
                # 直接以 XCAF solid 取代 STEPControl solid，名字已對應
                all_solids  = xcaf_solids
                idx_to_inst = xcaf_name_map   # {idx: name}，已完整
            else:
                idx_to_inst = {}

            solid_mapping = []
            for idx, solid in enumerate(all_solids):
                name = idx_to_inst.get(idx, f"未識別_{idx}")
                bb = Bnd_Box()
                try:
                    brepbndlib.Add(solid, bb)
                except Exception:
                    pass
                solid_mapping.append({
                    'name': name,
                    'bbox': list(bb.Get()) if not bb.IsVoid() else None
                })

        n_identified = len(idx_to_inst)
        n_total = len(all_solids)
        print(f"[ID] 辨識結果: {n_identified}/{n_total} 個 solid 已辨識 (來源: {id_source})", flush=True)

        parts = []
        grp_map = defaultdict(list)
        for idx, name in idx_to_inst.items(): grp_map[name].append(all_solids[idx])
        for name, slist in grp_map.items(): parts.append((slist, name))
        unmatched = [all_solids[i] for i in range(len(all_solids)) if i not in idx_to_inst]
        for i, s in enumerate(unmatched): parts.append(([s], f"未識別_{i+1}"))

        # ── 建立 face_id → part_name 映射 ──
        ws = reader.WS(); tr = ws.TransferReader()
        face_to_part = {}
        for slist, name in parts:
            for solid in slist:
                fexp = TopExp_Explorer(solid, TopAbs_FACE)
                while fexp.More():
                    face = topods.Face(fexp.Current())
                    ent = tr.EntityFromShapeResult(face, 1)
                    if ent:
                        sid = ws.EntityLabel(ent).ToCString().replace('#', '').strip()
                        if sid:
                            face_to_part[sid] = name
                    fexp.Next()

        comp_faces, comp_bbox = [], []
        for slist, name in parts:
            all_f, m_bb = [], None
            for s in slist:
                fs, bb = extract_faces(s, name)
                all_f.extend(fs); m_bb = merge_bbox(m_bb, bb)
            comp_faces.append(all_f); comp_bbox.append(m_bb)

        # ── 面型分布統計（早期診斷）──
        stype_counter = defaultdict(int)
        total_faces = 0
        for cf in comp_faces:
            for fi in cf:
                stype_counter[fi['stype']] += 1
                total_faces += 1
        print(f"[STYPE] 面型分布 ({total_faces} 個面): {dict(stype_counter)}", flush=True)
        if stype_counter.get('其他', 0) > total_faces * 0.3:
            print(f"[WARN] '其他'面佔比 > 30%，可能有面型分類失效", flush=True)

        # ── 診斷統計（分層細化）──
        diag = {
            'comp_pairs_total': 0,
            'comp_pairs_bbox_skip': 0,
            'comp_pairs_checked': 0,
            'face_pairs_checked': 0,
            'bbox_skip': 0,
            'area_skip': 0,
            'geom_skip_axis': 0,      # 軸線不平行
            'geom_skip_coaxial': 0,   # 非共軸
            'geom_skip_radius': 0,    # 半徑比不合理
            'geom_skip_overlap': 0,   # 軸向重疊不足
            'geom_skip_plane': 0,     # 平面法向不平行
            'geom_skip_plane_cyl': 0, # 平面-圓柱角度中間
            'geom_skip_other': 0,     # 其他幾何拒絕
            'dist_skip': 0,
            'dist_fail': 0,
            'accepted': 0,
        }

        # ── 第一階段：收集所有原始 hit ──
        # key = (comp1, comp2, ctype) → list of face_pair dicts
        raw_hits = defaultdict(list)
        n_comp = len(comp_faces)
        total_pairs = n_comp * (n_comp - 1) // 2
        print(f"[PROG] 開始接觸分析：{n_comp} 個零件，{total_pairs} 組零件對", flush=True)

        for a in range(len(comp_faces)):
            print(f"[PROG] 零件 {a+1}/{n_comp}：{parts[a][1]} ({len(comp_faces[a])} 個面)", flush=True)
            for b in range(a + 1, len(comp_faces)):
                diag['comp_pairs_total'] += 1
                if not boxes_overlap(comp_bbox[a], comp_bbox[b], 0.5):
                    diag['comp_pairs_bbox_skip'] += 1
                    continue
                diag['comp_pairs_checked'] += 1

                # 統一零件名稱順序（字典序），避免 (A,B) 和 (B,A) 重複
                c1, c2 = parts[a][1], parts[b][1]
                if c1 > c2:
                    c1, c2 = c2, c1
                    swap = True
                else:
                    swap = False

                for f1 in comp_faces[a]:
                    for f2 in comp_faces[b]:
                        diag['face_pairs_checked'] += 1

                        # ── 型態感知 BBox 預篩 ──────────────────────
                        if not passes_overlap_rule(f1, f2, tol=0.3):
                            diag['bbox_skip'] += 1
                            continue

                        # ── 面積門檻 ──
                        a1 = f1.get('area', 0); a2 = f2.get('area', 0)
                        # 單面低於 0.01 mm² → 退化面/幾何雜訊，直接排除
                        if a1 < MIN_SINGLE_AREA or a2 < MIN_SINGLE_AREA:
                            diag['area_skip'] += 1
                            continue
                        # 雙面都小於門檻 → 兩個微小面，排除
                        if a1 < MIN_CONTACT_AREA and a2 < MIN_CONTACT_AREA:
                            diag['area_skip'] += 1
                            continue

                        # ── 幾何相容性（法向/軸線/共軸/半徑/重疊）──
                        compatible, ctype, reject = check_geometry_compatible(f1, f2)
                        if not compatible:
                            key = f'geom_skip_{reject}' if reject else 'geom_skip_other'
                            diag[key] = diag.get(key, 0) + 1
                            continue

                        # ── 精密距離計算 ─────────────────────────────
                        try:
                            ext = BRepExtrema_DistShapeShape(f1['face'], f2['face'])
                            if ext.IsDone() and ext.Value() < FACE_CONTACT_DIST:
                                diag['accepted'] += 1
                                fp = {'bbox1': list(f1['bbox']), 'bbox2': list(f2['bbox']),
                                      'area1': f1.get('area', 0), 'area2': f2.get('area', 0),
                                      'dist': round(ext.Value(), 4)}
                                if swap:
                                    fp['bbox1'], fp['bbox2'] = fp['bbox2'], fp['bbox1']
                                    fp['area1'], fp['area2'] = fp['area2'], fp['area1']
                                raw_hits[(c1, c2, ctype)].append(fp)
                            else:
                                diag['dist_skip'] += 1
                        except:
                            diag['dist_fail'] += 1
                            continue

        # ── 第二階段：合併同零件對+同類型 → 一筆接觸群組 ──
        contacts = []
        for (c1, c2, ctype), fps in raw_hits.items():
            # 計算群組整體 BBox（所有 face pair 的聯集）
            group_bbox1 = None
            group_bbox2 = None
            total_area1 = 0.0
            total_area2 = 0.0
            for fp in fps:
                group_bbox1 = merge_bbox(group_bbox1, tuple(fp['bbox1']))
                group_bbox2 = merge_bbox(group_bbox2, tuple(fp['bbox2']))
                total_area1 += fp.get('area1', 0)
                total_area2 += fp.get('area2', 0)

            contacts.append({
                'comp1': c1,
                'comp2': c2,
                'ctype': ctype,
                'n_face_pairs': len(fps),
                'total_area1': round(total_area1, 2),
                'total_area2': round(total_area2, 2),
                'group_bbox1': list(group_bbox1) if group_bbox1 else None,
                'group_bbox2': list(group_bbox2) if group_bbox2 else None,
                'face_pairs': fps
            })

        # 按 face_pair 數量降序排列（最重要的接觸在前）
        contacts.sort(key=lambda c: c['n_face_pairs'], reverse=True)

        raw_count = diag['accepted']
        merged_count = len(contacts)
        print(f"[DIAG] 接觸分析統計: {json.dumps(diag, ensure_ascii=False)}", flush=True)
        print(f"[MERGE] 合併: {raw_count} 筆原始 hit → {merged_count} 筆接觸群組", flush=True)

        # 統計各面類型
        stype_counts = defaultdict(int)
        for cf in comp_faces:
            for fi in cf:
                stype_counts[fi['stype']] += 1

        result.update({'status':'ok', 'contacts':contacts, 'solids':solid_mapping,
                       'n_parts':len(parts), 'face_to_part': face_to_part,
                       'id_source': id_source,
                       'n_identified': n_identified, 'n_solids': n_total,
                       'diagnostics': diag,
                       'stype_counts': dict(stype_counts),
                       'n_total_faces': sum(len(cf) for cf in comp_faces)})
    except Exception: result['msg'] = traceback.format_exc()
    write_json(out_json, result)

if __name__ == "__main__": main()
