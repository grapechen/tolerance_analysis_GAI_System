"""
view_ras400_network.py
----------------------
讀 ras400_ontology.csv，直接印出工作台公差網路的樹狀結構。
不依賴 Flask、不依賴 dsl_builder（dsl_builder 寫死「精密迴轉滑台」作組合件 URI）。

用法：
    python server/scripts/view_ras400_network.py
"""
import os
import re
import sys
import csv
import io
from collections import defaultdict, OrderedDict

# 強制 stdout 為 UTF-8（Windows cp950 無法編碼部分 Unicode 符號）
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.dirname(THIS_DIR)
ONTOLOGY = os.path.join(SERVER_DIR, 'data', 'ras400_ontology.csv')

FEAT_TYPE_LABEL = {
    'ns0__平面':     '平面',
    'ns0__外圓柱面': '外圓柱',
    'ns0__內圓柱面': '內圓柱',
}

TOL_TYPE_LABEL = {
    'ns0__同心度公差':   '同心度',
    'ns0__圓柱度公差':   '圓柱度',
    'ns0__直徑公差':     '直徑',
    'ns0__真平度公差':   '真平度',
    'ns0__平行度公差':   '平行度',
    'ns0__垂直度公差':   '垂直度',
    'ns0__距離公差':     '距離',
    'ns0__位置度公差':   '位置度',
    'ns0__真圓度公差':   '真圓度',
    'ns0__角度公差':     '角度',
    'ns0__對稱度公差':   '對稱度',
    'ns0__圓偏轉度公差': '圓偏轉',
    'ns0__總偏轉度公差': '總偏轉',
    'ns0__真直度公差':   '真直度',
}


def extract_uri(node_str):
    m = re.search(r'uri:\s*([^,}\s]+)', node_str or '')
    return m.group(1).strip('}').strip() if m else ''


def extract_ns0(node_str):
    """抽出第一個 ns0__XXX"""
    m = re.search(r':(ns0__[\u4e00-\u9fa5A-Za-z0-9_]+)', node_str or '')
    return m.group(1) if m else ''


def extract_rel(rel_str):
    return (rel_str or '').strip('[]:')


def is_individual(node_str):
    return 'owl__NamedIndividual' in (node_str or '')


def main():
    print(f'[INFO] ontology : {ONTOLOGY}\n')

    # 蒐集個體層三元組
    part_of_feat   = {}                 # feature_uri -> part_uri
    feat_ns0       = {}                 # feature_uri -> ns0__class
    tol_ns0        = {}                 # tol_uri -> ns0__class
    feat_ind_tols  = defaultdict(list)  # feature_uri -> [tol_uri]（個別）
    feat_itr_tols  = defaultdict(list)  # feature_uri -> [tol_uri]（交互）
    assembly_parts = []                 # [(assembly_uri, part_uri)]

    with open(ONTOLOGY, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        next(reader)  # header
        for row in reader:
            if len(row) < 3:
                continue
            n, r, m = row[0], row[1], row[2]
            if not (is_individual(n) and is_individual(m)):
                continue
            rel = extract_rel(r)
            n_uri, m_uri = extract_uri(n), extract_uri(m)
            n_cls, m_cls = extract_ns0(n), extract_ns0(m)
            if not n_uri or not m_uri:
                continue

            if '有零件' in rel:
                assembly_parts.append((n_uri, m_uri))

            elif '有特徵面' in rel:
                if n_cls in FEAT_TYPE_LABEL:
                    part_of_feat[n_uri] = m_uri
                    feat_ns0[n_uri] = n_cls

            elif '有個別參考公差' in rel:
                if n_cls in FEAT_TYPE_LABEL and m_cls in TOL_TYPE_LABEL:
                    feat_ind_tols[n_uri].append(m_uri)
                    tol_ns0[m_uri] = m_cls

            elif '有交互參考公差' in rel:
                if n_cls in FEAT_TYPE_LABEL and m_cls in TOL_TYPE_LABEL:
                    feat_itr_tols[n_uri].append(m_uri)
                    tol_ns0[m_uri] = m_cls

    # 組合件 → 零件
    parts_by_assembly = defaultdict(list)
    for a, p in assembly_parts:
        if p not in parts_by_assembly[a]:
            parts_by_assembly[a].append(p)

    # 零件 → 特徵面
    feats_by_part = defaultdict(list)
    for f, p in part_of_feat.items():
        feats_by_part[p].append(f)

    # 排序鍵
    def feat_sort_key(name):
        m = re.search(r'-([PSHpsh])-(\d+)', name)
        if m:
            order = {'P': 0, 'S': 1, 'H': 2}
            return (order.get(m.group(1).upper(), 9), int(m.group(2)))
        return (9, 0)

    def tol_sort_key(name):
        m = re.match(r'^(\d+)-([A-Za-z]+)-(\d+)$', name)
        return (m.group(2) if m else 'zzz', int(m.group(3)) if m else 0)

    # 印出樹狀公差網路
    print('═══════════════════════════════════════════════════════')
    print('  RAS400 工作台公差網路')
    print('═══════════════════════════════════════════════════════\n')

    cross_refs = defaultdict(list)  # tol_uri -> [feature_uri]（交互公差涉及的特徵）
    for f, tols in feat_itr_tols.items():
        for t in tols:
            cross_refs[t].append(f)

    for assembly in sorted(parts_by_assembly.keys()):
        print(f'◇ 組合件：{assembly}')
        for part in sorted(parts_by_assembly[assembly]):
            print(f'  ├─ 零件：{part}')
            feats = sorted(feats_by_part.get(part, []), key=feat_sort_key)
            for i, feat in enumerate(feats):
                is_last_feat = (i == len(feats) - 1)
                branch = '└─' if is_last_feat else '├─'
                indent = '    '
                fcls = FEAT_TYPE_LABEL.get(feat_ns0.get(feat, ''), '?')
                print(f'  │  {branch} [{fcls}] {feat}')

                ind_tols = sorted(feat_ind_tols.get(feat, []), key=tol_sort_key)
                itr_tols = sorted(feat_itr_tols.get(feat, []), key=tol_sort_key)
                prefix = '  │  ' + ('   ' if is_last_feat else '│  ')

                for t in ind_tols:
                    tlabel = TOL_TYPE_LABEL.get(tol_ns0.get(t, ''), '?')
                    print(f'{prefix}├─ 個別 ({tlabel}) → {t}')
                for j, t in enumerate(itr_tols):
                    last = (j == len(itr_tols) - 1) and not ind_tols  # 簡化
                    tlabel = TOL_TYPE_LABEL.get(tol_ns0.get(t, ''), '?')
                    # 交互公差列出所有共用該公差的特徵面
                    partners = [x for x in cross_refs.get(t, []) if x != feat]
                    partner_str = f'  <-> {", ".join(partners)}' if partners else ''
                    print(f'{prefix}├─ 交互 [{tlabel}] → {t}{partner_str}')
        print()

    # 統計
    print('─── 統計 ───')
    total_feats = sum(len(v) for v in feats_by_part.values())
    total_ind = sum(len(v) for v in feat_ind_tols.values())
    # 交互公差去重
    unique_itr = {t for tols in feat_itr_tols.values() for t in tols}
    print(f'零件數     : {sum(len(v) for v in parts_by_assembly.values())}')
    print(f'特徵面數   : {total_feats}')
    print(f'個別公差   : {total_ind}')
    print(f'交互公差   : {len(unique_itr)}（連線條目：{sum(len(v) for v in feat_itr_tols.values())}）')

    # 公差類型分布
    from collections import Counter
    all_tols = list(tol_ns0.values())
    dist = Counter(TOL_TYPE_LABEL.get(t, t) for t in all_tols)
    print(f'公差類型   : {dict(dist)}')


if __name__ == '__main__':
    main()
