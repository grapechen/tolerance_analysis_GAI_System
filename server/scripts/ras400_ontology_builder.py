"""
ras400_ontology_builder.py
--------------------------
從 ontology_schema.csv（predicate/class 骨架）+ 11 個零件 PMI CSV
產生 ras400_ontology.csv，包含所有零件的個體層三元組。

規則：
  1. Schema rows（不含 owl__NamedIndividual）→ 原樣保留
  2. 舊個體層 rows（n 或 m 含 owl__NamedIndividual）→ 整個丟掉
  3. 從各零件 BOM CSV 重新產生：
     - RAS400 → 有零件 → 零件
     - 特徵面 → 有特徵面 → 零件
     - 個別公差：特徵面 → 有個別參考公差 → 公差
     - 交互公差：每個參與特徵面 → 有交互參考公差 → 公差

用法：
    python server/scripts/ras400_ontology_builder.py
"""
import os
import re
import sys
import csv
from collections import OrderedDict, Counter

# 讓本腳本能 import server/ 下的模組
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.dirname(THIS_DIR)
DATA_DIR = os.path.join(SERVER_DIR, 'data')
sys.path.insert(0, SERVER_DIR)

from sfa_csv_importer import SfaCsvImporter  # noqa: E402


# ─────────────────── 設定 ───────────────────
SCHEMA_CSV = os.path.join(DATA_DIR, 'ontology_schema.csv')
OUTPUT_CSV = os.path.join(DATA_DIR, 'ras400_ontology.csv')

ASSEMBLY_URI = 'RAS400'

# RAS400 全部 11 個零件 CSV（零件名, CSV 路徑）— 按組裝順序排列
RAS400_PARTS = [
    ('工作臺',      r'C:\Users\User\Downloads\工作臺.csv'),        # 1
    ('軸承座',      r'C:\Users\User\Downloads\軸承座.csv'),        # 2
    ('軸承',        r'C:\Users\User\Downloads\軸承.csv'),          # 3
    ('轉動軸',      r'C:\Users\User\Downloads\轉動軸.csv'),        # 4
    ('工作臺心軸',  r'C:\Users\User\Downloads\工作臺心軸.csv'),    # 5
    ('馬達',        r'C:\Users\User\Downloads\馬達.csv'),          # 6
    ('馬達水套',    r'C:\Users\User\Downloads\馬達水套.csv'),      # 7
    ('編碼器心軸',  r'C:\Users\User\Downloads\編碼器心軸.csv'),    # 8
    ('分流座',      r'C:\Users\User\Downloads\分流座.csv'),        # 9
    ('馬達座',      r'C:\Users\User\Downloads\馬達座.csv'),        # 10
    ('編碼器',      r'C:\Users\User\Downloads\編碼器.csv'),        # 11
]

# 公差類型 → ns0__ 類別 URI（對齊 schema 中實際的 class uri）
TOL_CLASS_MAP = {
    'co':  'ns0__同心度公差',
    'cyl': 'ns0__圓柱度公差',
    'dia': 'ns0__直徑公差',
    'fla': 'ns0__真平度公差',
    'par': 'ns0__平行度公差',
    'per': 'ns0__垂直度公差',
    'dis': 'ns0__距離公差',
    'pos': 'ns0__位置度公差',
    'cir': 'ns0__真圓度公差',
    'ang': 'ns0__角度公差',
    'sym': 'ns0__對稱度公差',
    'run': 'ns0__圓偏轉度公差',
    'tot': 'ns0__總偏轉度公差',
    'str': 'ns0__真直度公差',
}

# 特徵面字母 → ns0__ 類別 URI
FEAT_CLASS_MAP = {
    'P': 'ns0__平面',
    'S': 'ns0__外圓柱面',
    'H': 'ns0__內圓柱面',
}


# ─────────────────── 工具函式 ───────────────────
def tol_code_to_uri(code: str) -> str:
    """
    公差代號 → URI
    新格式：工作臺心軸-DIS1 → 工作臺心軸-Dis-1
    舊格式：1-FLA3           → 1-Fla-3
    """
    m = re.match(r'^(.+)-([A-Za-z]+)(\d+)$', code.strip())
    if not m:
        return code
    part, typ, idx = m.group(1), m.group(2).capitalize(), m.group(3)
    return f'{part}-{typ}-{idx}'


def node(classes, uri):
    """組裝 `(:Resource:ClassA:ClassB {uri: X})` 字串"""
    parts = ['Resource'] + list(classes)
    return f"(:{':'.join(parts)} {{uri: {uri}}})"


def rel(name):
    return f'[:{name}]'


def is_named_individual_row(n_str: str, m_str: str) -> bool:
    """任一端含 owl__NamedIndividual → 視為舊個體層資料，要丟"""
    return 'owl__NamedIndividual' in (n_str or '') or 'owl__NamedIndividual' in (m_str or '')


# ─────────────────── Schema ───────────────────
def load_schema_rows(path):
    """讀 schema CSV，保留 non-NamedIndividual rows（class/predicate 骨架）"""
    kept = []
    with open(path, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if len(row) < 3:
                continue
            n, r, m = row[0], row[1], row[2]
            if is_named_individual_row(n, m):
                continue
            kept.append((n, r, m))
    return header, kept


# ─────────────────── 特徵面類別推導 ───────────────────
def feat_class_for(feat_code: str, geo_type: str) -> str:
    """從特徵代號字母 + 幾何類型 推導 ns0__ 類別"""
    m = re.search(r'-([PSH])-\d+', feat_code)
    letter = m.group(1) if m else ''
    if letter in FEAT_CLASS_MAP:
        return FEAT_CLASS_MAP[letter]
    gt = (geo_type or '').upper()
    if 'PLANE' in gt:
        return 'ns0__平面'
    if 'CYLIND' in gt:
        return 'ns0__外圓柱面'
    return 'ns0__平面'


# ─────────────────── 單零件三元組生成 ───────────────────
def build_part_triples(part_name: str, bom_csv: str):
    """
    從一個零件 BOM CSV 產生個體層三元組列表 [(n, r, m), ...]
    """
    imp = SfaCsvImporter(ontology_csv_path=None)
    rows = imp.load_csv(bom_csv)

    triples = []

    # 1. 組合件 → 零件
    triples.append((
        node(['ns0__組合件', 'owl__NamedIndividual'], ASSEMBLY_URI),
        rel('ns0__有零件'),
        node(['ns0__零件', 'owl__NamedIndividual'], part_name),
    ))

    # 2. 特徵面 → 零件（蒐集每個特徵的幾何類型）
    feat_geo = OrderedDict()  # feat_code → ns0__class
    for row in rows:
        if row.is_datum():
            continue
        for feat in row.features:
            if feat and feat not in feat_geo:
                feat_geo[feat] = feat_class_for(feat, row.geo_type)

    for feat, cls in feat_geo.items():
        triples.append((
            node([cls, 'owl__NamedIndividual'], feat),
            rel('ns0__有特徵面'),
            node(['ns0__零件', 'owl__NamedIndividual'], part_name),
        ))

    # 3. 公差三元組（個別 / 交互）— 依公差代號去重
    seen_tols = set()
    for row in rows:
        if row.is_datum() or row.is_feature_only:
            continue
        code = row.code
        if not code or code in seen_tols:
            continue
        seen_tols.add(code)

        tol_cls = TOL_CLASS_MAP.get(row.tol_type)
        if not tol_cls:
            continue
        tol_uri = tol_code_to_uri(code)

        # 判斷個別 / 交互
        pmi = row.pmi_text or ''
        if '[個別]' in pmi:
            predicate = 'ns0__有個別參考公差'
        elif '[交互]' in pmi:
            predicate = 'ns0__有交互參考公差'
        else:
            predicate = 'ns0__有交互參考公差' if len(row.features) >= 2 else 'ns0__有個別參考公差'

        for feat in row.features:
            if not feat:
                continue
            feat_cls = feat_geo.get(feat, feat_class_for(feat, row.geo_type))
            triples.append((
                node([feat_cls, 'owl__NamedIndividual'], feat),
                rel(predicate),
                node([tol_cls, 'owl__NamedIndividual'], tol_uri),
            ))

    return triples, rows


# ─────────────────── 輸出 ───────────────────
def write_output(header, schema_rows, all_triples, out_path):
    with open(out_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        writer.writerow(header)
        for n, r, m in schema_rows:
            writer.writerow([n, r, m])
        for n, r, m in all_triples:
            writer.writerow([n, r, m])


# ─────────────────── Main ───────────────────
def main():
    print(f'[INFO] schema : {SCHEMA_CSV}')
    print(f'[INFO] output : {OUTPUT_CSV}')
    print(f'[INFO] parts  : {len(RAS400_PARTS)} 個零件')
    print()

    header, schema_rows = load_schema_rows(SCHEMA_CSV)
    print(f'[OK] schema rows kept : {len(schema_rows)}')

    all_triples = []
    total_rows = 0
    total_feats = set()

    for part_name, csv_path in RAS400_PARTS:
        if not os.path.exists(csv_path):
            print(f'[WARN] 找不到 {csv_path}，跳過')
            continue

        triples, rows = build_part_triples(part_name, csv_path)
        all_triples.extend(triples)
        total_rows += len(rows)

        feats = set(f for r in rows if not r.is_datum() for f in r.features)
        total_feats.update(feats)

        n_tol = sum(1 for r in rows if r.tol_value and r.tol_value > 0 and not r.is_datum())
        print(f'  {part_name:10s}  rows={len(rows):2d}  has_tol={n_tol:2d}  feats={len(feats):2d}  triples={len(triples)}')

    write_output(header, schema_rows, all_triples, OUTPUT_CSV)

    print()
    print(f'[OK] wrote {OUTPUT_CSV}')
    print(f'[SUMMARY] 零件數     : {len(RAS400_PARTS)}')
    print(f'[SUMMARY] BOM 總條目 : {total_rows}')
    print(f'[SUMMARY] 特徵面數   : {len(total_feats)}')
    print(f'[SUMMARY] 三元組數   : {len(schema_rows) + len(all_triples)} (schema {len(schema_rows)} + instance {len(all_triples)})')


if __name__ == '__main__':
    main()
