"""
asm_worker.py  ─ 組合件接觸分析子進程 (魯棒版)
======================================================
本進程利用 NIST SFA CSV 數據與幾何藍圖進行實例辨識，
並增加了對異常幾何實體的錯誤處理，防止 Standard_OutOfRange 崩潰。
"""
import sys, os, json, re, traceback, csv, math
from collections import defaultdict

os.environ["CSF_GraphicDriver"] = "off"

from OCC.Core.STEPControl   import STEPControl_Reader
from OCC.Core.TopExp        import TopExp_Explorer
from OCC.Core.TopAbs        import TopAbs_FACE, TopAbs_SOLID, TopAbs_SHELL, TopAbs_REVERSED
from OCC.Core.TopoDS        import topods
from OCC.Core.BRepAdaptor   import BRepAdaptor_Surface
from OCC.Core.GeomAbs       import GeomAbs_Plane, GeomAbs_Cylinder
from OCC.Core.Bnd           import Bnd_Box
from OCC.Core.BRepBndLib    import brepbndlib
from OCC.Core.BRepExtrema   import BRepExtrema_DistShapeShape
from OCC.Core.IFSelect      import IFSelect_RetDone
from OCC.Core.gp            import gp_Pnt

FACE_CONTACT_DIST = 0.1
MIN_CONTACT_AREA = 1.0

def write_json(path, data):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except: pass

def bbox_get(bb):
    try: return bb.Get()
    except: return None

def boxes_overlap(c1, c2, tol=0.05):
    if not c1 or not c2: return False
    x1,y1,z1,X1,Y1,Z1 = c1
    x2,y2,z2,X2,Y2,Z2 = c2
    return (x1-tol<=X2 and X1+tol>=x2 and
            y1-tol<=Y2 and Y1+tol>=y2 and
            z1-tol<=Z2 and Z1+tol>=z2)

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
            fi = {'comp':name, 'bbox':c, 'stype':'其他', 'face':f}
            try:
                ad = BRepAdaptor_Surface(f); st = ad.GetType()
                if st == GeomAbs_Plane:
                    fi['stype'] = '平面'
                    d = ad.Plane().Axis().Direction()
                    fi['normal'] = (d.X(), d.Y(), d.Z())
                elif st == GeomAbs_Cylinder:
                    fi['stype'] = '孔' if f.Orientation() == TopAbs_REVERSED else '圓柱面'
                    ax = ad.Cylinder().Axis().Direction()
                    fi['cyl_axis'] = (ax.X(), ax.Y(), ax.Z())
            except: pass
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
        solid_info, nauo_data = _parse_sfa_csvs(stp_path)
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
        idx_to_inst, solid_mapping = link_occ_solids_to_instances(reader, all_solids, solid_info, nauo_data, stp_path)
        parts = []
        grp_map = defaultdict(list)
        for idx, name in idx_to_inst.items(): grp_map[name].append(all_solids[idx])
        for name, slist in grp_map.items(): parts.append((slist, name))
        unmatched = [all_solids[i] for i in range(len(all_solids)) if i not in idx_to_inst]
        for i, s in enumerate(unmatched): parts.append(([s], f"未識別_{i+1}"))
        
        comp_faces, comp_bbox = [], []
        for slist, name in parts:
            all_f, m_bb = [], None
            for s in slist:
                fs, bb = extract_faces(s, name)
                all_f.extend(fs); m_bb = merge_bbox(m_bb, bb)
            comp_faces.append(all_f); comp_bbox.append(m_bb)

        contacts = []
        for a in range(len(comp_faces)):
            for b in range(a + 1, len(comp_faces)):
                if not boxes_overlap(comp_bbox[a], comp_bbox[b], 0.5): continue
                for f1 in comp_faces[a]:
                    for f2 in comp_faces[b]:
                        if not boxes_overlap(f1['bbox'], f2['bbox'], 0.15): continue
                        try:
                            ext = BRepExtrema_DistShapeShape(f1['face'], f2['face'])
                            if ext.IsDone() and ext.Value() < FACE_CONTACT_DIST:
                                contacts.append({
                                    'comp1': parts[a][1], 'comp2': parts[b][1],
                                    'ctype': f"{f1['stype']}接合",
                                    'face_pairs': [{'bbox1':list(f1['bbox']), 'bbox2':list(f2['bbox'])}]
                                })
                        except: continue
        result.update({'status':'ok', 'contacts':contacts, 'solids':solid_mapping, 'n_parts':len(parts)})
    except Exception: result['msg'] = traceback.format_exc()
    write_json(out_json, result)

if __name__ == "__main__": main()
