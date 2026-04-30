"""feature_recommender.py — 特徵面推薦：製程 + 機台 + 公差等級
================================================================
給定特徵類型（P/H/S/C）與該特徵上的尺寸/幾何公差需求，
推薦適合的製程鏈與機台型號。

資料來源：
  - process_capability.csv     製程能力（含粗/細/精分級 + 各幾何公差類型 IT 範圍）
  - process_chain.csv          製程順序
  - geo_tolerance_grade.csv    幾何公差等級對應應用實例（教材表 3.2）
  - machines_process_map.csv   機台屬性 ↔ 可執行製程
  - machines.csv               個別機台規格（含 mock 通用設備）
"""

from __future__ import annotations

import csv
import os
from typing import Iterable

_DATA_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
)

# 業界慣用 safety factor：機台重現精度 ≤ IT 公差 / SAFETY_FACTOR
SAFETY_FACTOR = 1.7


# ── 載入資料（lazy） ────────────────────────────────────────────────────
_capability: list[dict] = []
_chain: list[dict] = []
_geo_grade: list[dict] = []
_machine_proc_map: dict = {}   # {machine_attr: [process_en, ...]}
_machines: list[dict] = []
_loaded = False


def _to_int(v, default=None):
    try:
        return int(v) if v not in ('', None) else default
    except (TypeError, ValueError):
        return default


def _to_float(v, default=None):
    try:
        return float(v) if v not in ('', None) else default
    except (TypeError, ValueError):
        return default


def _load():
    global _loaded
    if _loaded:
        return

    # process_capability
    with open(os.path.join(_DATA_DIR, 'process_capability.csv'),
              encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            _capability.append({
                'process_en':       r['process_en'].strip(),
                'process_zh':       r['process_zh'].strip(),
                'category':         r.get('category', '').strip(),
                'equipment':        r.get('typical_equipment', '').strip(),
                'feature_types':    [t.strip() for t in r.get('feature_types', '').split(';') if t.strip()],
                'external':         (r.get('external', '').strip().upper() == 'TRUE'),
                'note':             r.get('note', '').strip(),
                'it_dim':           (_to_int(r.get('it_grade_min')), _to_int(r.get('it_grade_max'))),
                'it_circ':          (_to_int(r.get('it_circ_min')), _to_int(r.get('it_circ_max'))),
                'it_par_perp':      (_to_int(r.get('it_par_perp_min')), _to_int(r.get('it_par_perp_max'))),
                'it_concentric':    (_to_int(r.get('it_concentric_min')), _to_int(r.get('it_concentric_max'))),
                'Ra':               (_to_float(r.get('Ra_min_um')), _to_float(r.get('Ra_max_um'))),
            })

    # process_chain
    with open(os.path.join(_DATA_DIR, 'process_chain.csv'),
              encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            _chain.append({
                'process':      r['process_en'].strip(),
                'prerequisite': r['prerequisite_en'].strip(),
                'reason':       r.get('reason_zh', '').strip(),
            })

    # geo_tolerance_grade
    with open(os.path.join(_DATA_DIR, 'geo_tolerance_grade.csv'),
              encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            _geo_grade.append({
                'geo_type_zh':       r['geo_type_zh'].strip(),
                'geo_type_code':     r['geo_type_code'].strip(),
                'grade_min':         int(r['grade_min']),
                'grade_max':         int(r['grade_max']),
                'application_zh':    r['application_zh'].strip(),
                'it_dim_recommend':  r.get('it_dim_recommend', '').strip(),
            })

    # machines_process_map
    with open(os.path.join(_DATA_DIR, 'machines_process_map.csv'),
              encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            attr = r['machine_attr'].strip()
            procs = [p.strip() for p in r['process_en_list'].split(';') if p.strip()]
            _machine_proc_map[attr] = procs

    # machines
    with open(os.path.join(_DATA_DIR, 'machines.csv'),
              encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            _machines.append({
                'model':       (r.get('型號') or '').strip(),
                'pos_acc_mm':  _to_float(r.get('定位精度(mm)')),
                'repeat_mm':   _to_float(r.get('重現精度(mm)')),
                'company':     (r.get('公司') or '').strip(),
                'attr':        (r.get('屬性') or '').strip(),
                'note':        (r.get('備註') or '').strip(),
                'X':           _to_float(r.get('X行程(mm)')),
                'Y':           _to_float(r.get('Y行程(mm)')),
                'Z':           _to_float(r.get('Z行程(mm)')),
            })

    _loaded = True


# ── 公開 API ────────────────────────────────────────────────────────────

def feature_type_to_zh(code: str) -> str:
    """P/H/S/C → 中文。"""
    return {'P': '平面', 'H': '內圓柱面', 'S': '外圓柱面', 'C': '錐面'}.get(code, code)


def list_processes_for_feature(feature_type: str) -> list[dict]:
    """列出能加工這種特徵類型的所有製程（不過濾 IT 等級）。"""
    _load()
    ft = feature_type.upper()
    return [p for p in _capability if not p['feature_types'] or ft in p['feature_types']]


def grade_for_geo_value(geo_code: str, value_mm: float, nominal_mm: float = 50) -> dict | None:
    """估算給定的幾何公差值對應的等級。

    用 ISO 286 IT 表的 IT5/IT6/... 對 nominal 尺寸的公差值反查最接近者。
    Args:
        geo_code: 'Cir', 'Cyl', 'Per', 'Par', 'Co', ...
        value_mm: 公差值（mm）
        nominal_mm: 公稱尺寸（影響 IT 表查值）
    """
    _load()
    # 用 ISO 286 標準 IT 公差表（μm）按 nominal 大小查 IT1~IT12
    iso = _iso_it_table(nominal_mm)
    target_um = value_mm * 1000.0
    best_grade = None
    best_diff = float('inf')
    for grade, um in iso.items():
        diff = abs(um - target_um)
        if diff < best_diff:
            best_diff = diff
            best_grade = grade

    # 在 geo_tolerance_grade 找對應應用敘述
    matches = [g for g in _geo_grade if g['geo_type_code'] == geo_code
               and g['grade_min'] <= best_grade <= g['grade_max']]
    application = matches[0]['application_zh'] if matches else ''
    return {
        'estimated_grade': best_grade,
        'value_um':        round(target_um, 3),
        'iso_it_um':       iso.get(best_grade),
        'application_zh':  application,
    }


def _iso_it_table(nominal_mm: float) -> dict:
    """ISO 286 IT1~IT12 in μm at given nominal size."""
    # 簡化表（中段值）：對 1-50mm 適用 IT1=0.6 IT2=1 IT3=1.5 IT4=2.5 ...
    # 實務值依尺寸帶不同；這裡用「30~50 mm」段做為通用近似
    if nominal_mm <= 3:
        base = [0.4, 0.6, 1.0, 1.5, 2.5, 4, 6, 10, 14, 25, 40, 60]
    elif nominal_mm <= 10:
        base = [0.6, 1.0, 1.5, 2.5, 4, 6, 9, 15, 22, 36, 58, 90]
    elif nominal_mm <= 30:
        base = [1.0, 1.5, 2.5, 4, 6, 9, 13, 21, 33, 52, 84, 130]
    elif nominal_mm <= 80:
        base = [1.5, 2.5, 4, 6, 9, 13, 19, 30, 46, 74, 120, 190]
    elif nominal_mm <= 250:
        base = [2.5, 4, 7, 10, 14, 20, 29, 46, 72, 115, 185, 290]
    else:
        base = [3, 5, 8, 12, 18, 25, 36, 57, 89, 140, 230, 360]
    return {i + 1: base[i] for i in range(12)}


def filter_processes_by_requirements(
    feature_type,
    nominal_mm=50.0,
    it_dim=None,
    it_circ=None,
    it_par_perp=None,
    it_concentric=None,
):
    """過濾出能滿足所有要求的製程。

    判定原則：「製程最佳精度（it_*_min）≤ 使用者要求 IT 等級」即勝任。
    （IT 數字越小越精密；製程能達到 IT3 的也能達到 IT5/7…只是「過剩」但可用）
    """
    _load()
    candidates = list_processes_for_feature(feature_type)
    out = []
    for p in candidates:
        ok = True
        if it_dim is not None and p['it_dim'][0] is not None:
            if p['it_dim'][0] > it_dim:
                ok = False
        if ok and it_circ is not None and p['it_circ'][0] is not None:
            if p['it_circ'][0] > it_circ:
                ok = False
        if ok and it_par_perp is not None and p['it_par_perp'][0] is not None:
            if p['it_par_perp'][0] > it_par_perp:
                ok = False
        if ok and it_concentric is not None and p['it_concentric'][0] is not None:
            if p['it_concentric'][0] > it_concentric:
                ok = False
        if ok:
            out.append(p)
    return out


def list_machines_for_process(
    process_en: str,
    nominal_mm: float | None = None,
    target_it: int | None = None,
    safety_factor: float = SAFETY_FACTOR,
) -> list[dict]:
    """列出能執行此製程的機台型號（含 mock 外部設備）。

    若給 target_it + nominal_mm，會用 IT/safety_factor 篩重現精度。
    """
    _load()
    suitable_attrs = [attr for attr, procs in _machine_proc_map.items() if process_en in procs]
    candidates = [m for m in _machines if m['attr'] in suitable_attrs]

    if target_it is not None and nominal_mm is not None:
        iso = _iso_it_table(nominal_mm)
        it_um = iso.get(target_it)
        if it_um:
            it_mm = it_um / 1000.0
            need_repeat_mm = it_mm / safety_factor
            candidates = [m for m in candidates
                          if m['repeat_mm'] is not None and m['repeat_mm'] <= need_repeat_mm]

    return candidates


def recommend_for_feature(
    feature_type: str,
    nominal_mm: float = 50.0,
    geo_tolerances: dict | None = None,   # e.g. {'Cir': 0.005, 'Per': 0.01}
    it_dim: int | None = None,
    safety_factor: float = SAFETY_FACTOR,
) -> dict:
    """主 API：給特徵類型 + 公稱尺寸 + 各種公差需求 → 推薦製程鏈與機台。

    Returns:
        {
          'feature_type':   'H',
          'feature_zh':     '內圓柱面',
          'nominal_mm':     47,
          'requirements':   {...},
          'geo_grades':     [{geo_code, value_um, estimated_grade, application_zh}, ...],
          'processes':      [{process_zh, ..., machines: [...], chain: [...]}, ...],
        }
    """
    _load()
    geo_tolerances = geo_tolerances or {}

    # 1. 推幾何公差等級
    geo_grades = []
    geo_grade_max = {}  # geo_code → estimated grade（取最嚴格 = 最小）
    for code, val in geo_tolerances.items():
        info = grade_for_geo_value(code, val, nominal_mm)
        if info:
            geo_grades.append({'geo_code': code, **info})
            geo_grade_max[code] = info['estimated_grade']

    # 將幾何代碼歸類到 process_capability 的欄位
    # 形狀類（Cir/Cyl/Fla）共用 it_circ 欄位（圓度、圓柱度、平面度都是形狀偏差）
    it_circ = min((geo_grade_max[c] for c in ('Cir', 'Cyl', 'Fla') if c in geo_grade_max), default=None)
    it_par_perp = min((geo_grade_max[c] for c in ('Per', 'Par') if c in geo_grade_max), default=None)
    it_concentric = min((geo_grade_max[c] for c in ('Co', 'Sym', 'Run') if c in geo_grade_max), default=None)

    # 2. 過濾製程
    procs = filter_processes_by_requirements(
        feature_type, nominal_mm,
        it_dim=it_dim, it_circ=it_circ,
        it_par_perp=it_par_perp, it_concentric=it_concentric,
    )

    # 3. 排序：external=False 在前（內部設備優先）；same → category 順序 finishing/grinding/machining/roughing/forming
    cat_pri = {'finishing': 0, 'grinding': 1, 'machining': 2, 'roughing': 3, 'forming': 4}
    procs.sort(key=lambda p: (1 if p['external'] else 0, cat_pri.get(p['category'], 99)))

    # 4. 為每個製程附上機台清單與製程鏈
    target_it_for_machine = it_dim if it_dim is not None else 7
    output_processes = []
    for p in procs[:8]:
        machines = list_machines_for_process(
            p['process_en'], nominal_mm=nominal_mm,
            target_it=target_it_for_machine, safety_factor=safety_factor,
        )
        chain = _trace_chain(p['process_en'])
        output_processes.append({
            'process_en':    p['process_en'],
            'process_zh':    p['process_zh'],
            'category':      p['category'],
            'equipment':     p['equipment'],
            'external':      p['external'],
            'note':          p['note'],
            'it_dim':        p['it_dim'],
            'it_circ':       p['it_circ'],
            'it_par_perp':   p['it_par_perp'],
            'it_concentric': p['it_concentric'],
            'Ra':            p['Ra'],
            'machines':      [{'model': m['model'], 'attr': m['attr'],
                               'company': m['company'],
                               'repeat_mm': m['repeat_mm'],
                               'note': m['note']}
                              for m in machines[:5]],
            'chain':         chain,
        })

    return {
        'feature_type':   feature_type,
        'feature_zh':     feature_type_to_zh(feature_type),
        'nominal_mm':     nominal_mm,
        'requirements': {
            'it_dim': it_dim,
            'geo_tolerances': geo_tolerances,
        },
        'geo_grades':     geo_grades,
        'processes':      output_processes,
        'safety_factor':  safety_factor,
    }


def _trace_chain(target_en: str) -> list[dict]:
    """回溯製程鏈（從毛坯到目標製程）。"""
    _load()
    chain = []
    visited = set()

    def _walk(p):
        if p in visited:
            return
        visited.add(p)
        for c in _chain:
            if c['process'] == p:
                _walk(c['prerequisite'])
                chain.append({
                    'process_en': c['prerequisite'],
                    'reason':     c['reason'],
                })
                return

    _walk(target_en)
    chain.append({'process_en': target_en, 'reason': '最終加工'})
    return chain
