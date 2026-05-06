"""tolerance_bp.py - ISO 286 公差查詢 Blueprint

路由職責：參數驗證 → 呼叫 Service → 回傳 JSON。
業務邏輯全部委派給 ToleranceService / FitService。
"""

from flask import Blueprint, jsonify, request
from middleware import rate_limit, api_limiter
from logger import app_logger
from services.tolerance_service import ToleranceService
from services.fit_service import FitService
from recommendation import smart_fit, machine_check
from analysis_service import generate_fit_recommendation
import json
import os
import re
import csv as _csv
import math

# ── 製程/機台查詢快取（來源：沈哲民參考 → process_capability + machines_process_map）──
_PROC_CAP  = None
_MACH_MAP  = None   # process_en → [machine_attr]

_DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

def _load_proc_cap():
    global _PROC_CAP
    if _PROC_CAP is not None:
        return _PROC_CAP
    _PROC_CAP = []
    try:
        with open(os.path.join(_DATA_DIR, 'process_capability.csv'), encoding='utf-8-sig') as f:
            _PROC_CAP = list(_csv.DictReader(f))
    except Exception:
        pass
    return _PROC_CAP

def _load_mach_map():
    """回傳 {process_en: [machine_attr, ...]}"""
    global _MACH_MAP
    if _MACH_MAP is not None:
        return _MACH_MAP
    _MACH_MAP = {}
    try:
        with open(os.path.join(_DATA_DIR, 'machines_process_map.csv'), encoding='utf-8-sig') as f:
            for row in _csv.DictReader(f):
                for proc in row['process_en_list'].split(';'):
                    proc = proc.strip()
                    _MACH_MAP.setdefault(proc, []).append(row['machine_attr'])
    except Exception:
        pass
    return _MACH_MAP

_MACHINES_BY_ATTR = None   # { machine_attr: [{ 型號, 公司, 重現精度, ... }, ...] }

def _load_machines_by_attr():
    """從 machines.csv 建立 屬性→機台清單 的索引，每屬性取重現精度最好的前 2 台。"""
    global _MACHINES_BY_ATTR
    if _MACHINES_BY_ATTR is not None:
        return _MACHINES_BY_ATTR
    _MACHINES_BY_ATTR = {}
    try:
        with open(os.path.join(_DATA_DIR, 'machines.csv'), encoding='utf-8-sig') as f:
            for row in _csv.DictReader(f):
                attr = (row.get('屬性') or '').strip()
                if not attr:
                    continue
                try:
                    repeat = float(row.get('重現精度(mm)') or 99)
                except ValueError:
                    repeat = 99.0
                _MACHINES_BY_ATTR.setdefault(attr, []).append({
                    '型號':     row.get('型號', '').strip(),
                    '公司':     row.get('公司', '').strip(),
                    '重現精度': repeat,
                })
        # 每屬性依重現精度升序排（越小越精），取前 2 台代表
        for attr in _MACHINES_BY_ATTR:
            _MACHINES_BY_ATTR[attr].sort(key=lambda x: x['重現精度'])
            _MACHINES_BY_ATTR[attr] = _MACHINES_BY_ATTR[attr][:2]
    except Exception:
        pass
    return _MACHINES_BY_ATTR

def _it_from_code(code: str) -> int:
    m = re.search(r'\d+', str(code))
    return int(m.group()) if m else 0

def _recommend_for_it(it: int, feature: str) -> dict:
    """
    查出能達到指定 IT 等級的製程與對應機台（沈哲民表二 + machines_process_map）。
    feature: 'H'=孔, 'S'=軸
    回傳 { processes: [...], machines: [...] }
    """
    if it <= 0:
        return {'processes': [], 'machines': []}

    proc_rows = _load_proc_cap()
    mach_map  = _load_mach_map()

    matched = []
    for r in proc_rows:
        try:
            mn, mx = int(r['it_grade_min']), int(r['it_grade_max'])
        except ValueError:
            continue
        if mn <= it <= mx and feature in r.get('feature_types', ''):
            matched.append({
                'mn':       mn,
                'proc_zh':  r['process_zh'],
                'proc_en':  r['process_en'],
                'in_house': r.get('external', 'FALSE') == 'FALSE',
            })

    # 精度由高到低（it_grade_min 越小越精），自製優先
    matched.sort(key=lambda x: (x['mn'], not x['in_house']))
    top3 = matched[:3]

    processes = [p['proc_zh'] for p in top3]

    # 機台：製程 → 屬性 → machines.csv 取實際型號
    machines_by_attr = _load_machines_by_attr()
    seen_attr, machines = set(), []
    for p in top3:
        for attr in mach_map.get(p['proc_en'], []):
            if attr in seen_attr:
                continue
            seen_attr.add(attr)
            for m in machines_by_attr.get(attr, []):
                machines.append({
                    'attr':   attr,
                    '型號':   m['型號'],
                    '公司':   m['公司'],
                    '重現精度': m['重現精度'],
                })

    return {'processes': processes, 'machines': machines[:3]}

tolerance_bp = Blueprint('tolerance', __name__)

_tol_svc = ToleranceService()
_fit_svc = FitService()


# ── IT 等級推薦 ───────────────────────────────────────────────────────────────

@tolerance_bp.post('/recommend/it')
def recommend_it():
    p = request.get_json(force=True)
    try:
        size       = float(p['size_mm'])
        target_tol = float(p['target_tol_μm'])
    except Exception:
        return jsonify({'ok': False, 'msg': '缺少或不合法的 size_mm / target_tol_μm'}), 400

    result, err = _tol_svc.recommend_it(
        size, target_tol,
        prefer_floor=p.get('prefer_it_floor'),
        prefer_ceil=p.get('prefer_it_ceil'),
    )
    if err:
        return jsonify({'ok': False, 'msg': err}), 400
    return jsonify({'ok': True, 'size_mm': size, 'target_tol_μm': target_tol, **result})


# ── ISO 公差查詢 ──────────────────────────────────────────────────────────────

@tolerance_bp.post('/api/lookup/tolerance')
@rate_limit(api_limiter)
def api_lookup_tolerance():
    p = request.get_json(force=True)
    try:
        size     = float(p['size_mm'])
        it_grade = str(p['it_grade']).upper()
    except Exception as e:
        app_logger.warning(f'參數驗證失敗: {e}')
        return jsonify({'ok': False, 'msg': '缺少或不合法的 size_mm / it_grade'}), 400

    result = _tol_svc.lookup_iso(size, it_grade)
    if not result:
        return jsonify({'ok': False, 'msg': '找不到對應的資料（請確認 Excel 已匯入，或尺寸/IT 等級是否存在）'}), 404

    return jsonify({'ok': True, 'size_mm': size, **result})


# ── 軸 / 孔公差查詢 ───────────────────────────────────────────────────────────

@tolerance_bp.post('/api/lookup/shaft')
def api_lookup_shaft():
    p = request.get_json(force=True)
    try:
        size     = float(p['size_mm'])
        code     = str(p['tolerance_code']).lower()
        it_grade = str(p['it_grade']).upper()
    except Exception:
        return jsonify({'ok': False, 'msg': '缺少或不合法的參數'}), 400

    result = _tol_svc.lookup_shaft(size, code, it_grade)
    if not result:
        return jsonify({'ok': False, 'msg': '找不到對應的軸公差資料'}), 404
    return jsonify({'ok': True, 'size_mm': size, **result})


@tolerance_bp.post('/api/lookup/hole')
def api_lookup_hole():
    p = request.get_json(force=True)
    try:
        size     = float(p['size_mm'])
        code     = str(p['tolerance_code']).upper()
        it_grade = str(p['it_grade']).upper()
    except Exception:
        return jsonify({'ok': False, 'msg': '缺少或不合法的參數'}), 400

    result = _tol_svc.lookup_hole(size, code, it_grade)
    if not result:
        return jsonify({'ok': False, 'msg': '找不到對應的孔公差資料'}), 404
    return jsonify({'ok': True, 'size_mm': size, **result})


# ── 配合分析 ──────────────────────────────────────────────────────────────────

@tolerance_bp.post('/api/analyze/fit')
def api_analyze_fit():
    p = request.get_json(force=True)
    try:
        size      = float(p['size_mm'])
        hole_str  = str(p['hole_tolerance']).upper()
        shaft_str = str(p['shaft_tolerance']).lower()
    except Exception:
        return jsonify({'ok': False, 'msg': '缺少或不合法的參數'}), 400

    result, err = _fit_svc.analyze_fit(size, hole_str, shaft_str)
    if err:
        return jsonify({'ok': False, 'msg': err}), 400
    return jsonify({'ok': True, 'size_mm': size, **result})


# ── 智能選配 ──────────────────────────────────────────────────────────────────

@tolerance_bp.post('/api/recommend/smart_fit')
def api_recommend_smart_fit():
    """配合搜尋。

    Body 接受兩種模式（dimensions 優先；二擇一）：
      A. 維度模式: {"dimensions": {"required": [...], "optional": [...]}}
      B. 關鍵字模式: {"keywords": [...]}
    """
    p          = request.get_json(force=True)
    keywords   = p.get('keywords', []) or []
    dimensions = p.get('dimensions') or {}
    has_dims   = bool((dimensions.get('required') or []) or (dimensions.get('optional') or []))

    if has_dims:
        scored = smart_fit.search_by_tags(
            required=set(dimensions.get('required') or []),
            optional=set(dimensions.get('optional') or []),
        )
        results = []
        for s in scored:
            item = dict(s['item'])
            if isinstance(item.get('tags'), set):
                item['tags'] = sorted(item['tags'])
            item['score']        = s['score']
            item['matched_tags'] = s['matched_tags']
            item['missing_tags'] = s['missing_tags']
            item['extra_tags']   = s['extra_tags']
            # ── 製程 + 機台建議（沈哲民參考表二 + machines_process_map）──
            hole_it  = _it_from_code(item.get('hole_tol', ''))
            shaft_it = _it_from_code(item.get('shaft_dev', ''))
            hole_rec  = _recommend_for_it(hole_it,  'H')
            shaft_rec = _recommend_for_it(shaft_it, 'S')
            item['processes_hole']  = hole_rec['processes']
            item['machines_hole']   = hole_rec['machines']
            item['processes_shaft'] = shaft_rec['processes']
            item['machines_shaft']  = shaft_rec['machines']
            item['hole_it']  = hole_it
            item['shaft_it'] = shaft_it
            results.append(item)
        return jsonify({'ok': True, 'results': results, 'count': len(results), 'mode': 'dimensions'})

    if not keywords:
        return jsonify({'ok': False, 'msg': '請提供 keywords 或 dimensions'}), 400

    results = smart_fit.search_fits(keywords)
    out = []
    for it in results:
        d = dict(it)
        if isinstance(d.get('tags'), set):
            d['tags'] = sorted(d['tags'])
        out.append(d)
    return jsonify({'ok': True, 'results': out, 'count': len(out), 'mode': 'keywords'})


@tolerance_bp.post('/api/recommend/machine_check')
def api_recommend_machine_check():
    p = request.get_json(force=True)
    try:
        diameter = float(p.get('diameter', 0))
        safety   = float(p.get('safety_factor', 3.0))
    except (ValueError, TypeError):
        return jsonify({'ok': False, 'msg': '無效的數值參數'}), 400

    if diameter <= 0:
        return jsonify({'ok': False, 'msg': '直徑必須大於 0'}), 400

    result = machine_check.find_capable_machines(diameter, safety)
    return jsonify({'ok': True, 'data': result})


@tolerance_bp.get('/api/keywords')
def api_get_keywords():
    try:
        tags = smart_fit.get_all_tags()
    except Exception as e:
        app_logger.error(f'Error getting tags from smart_fit: {e}')
        tags = ['定位', '高速', '滑動', '轉動', '裝拆', '重壓']

    machine_keywords = ['孔加工', '平面加工', '重切削', '多面一次加工']
    all_keywords = sorted(set(tags + machine_keywords))
    return jsonify({'ok': True, 'keywords': all_keywords})


# ── 機台資料 ──────────────────────────────────────────────────────────────────

@tolerance_bp.get('/api/machines')
def get_machines():
    base_dir  = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, '..', 'data', 'machines_data.json')
    if not os.path.exists(file_path):
        app_logger.error(f'找不到機台資料檔案: {file_path}')
        return jsonify({'ok': False, 'msg': '找不到機台資料'}), 404

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        app_logger.error(f'解析機台資料失敗: {e}')
        return jsonify({'ok': False, 'msg': f'解析資料失敗: {str(e)}'}), 500



# ── 配合建議（從分析結果生成）──────────────────────────────────────────────────

@tolerance_bp.post('/api/fit_recommendation')
def api_fit_recommendation():
    """
    Input : { pathData: [...], analysisResult: {...} }
    Output: { ok, assembly_overview, error_summary, dom_pos_axis, dom_ang_axis, recommendations }
    """
    body = request.get_json(force=True, silent=True) or {}
    path_data       = body.get('pathData', [])
    analysis_result = body.get('analysisResult', {})

    if not analysis_result or not analysis_result.get('tol_names'):
        return jsonify({'ok': False, 'msg': '缺少分析結果，請先執行公差分析。'}), 400

    try:
        result = generate_fit_recommendation(path_data, analysis_result)
        if 'error' in result:
            return jsonify({'ok': False, 'msg': result['error']}), 400
        return jsonify({'ok': True, **result})
    except Exception as e:
        app_logger.error(f'fit_recommendation error: {e}', exc_info=True)
        return jsonify({'ok': False, 'msg': f'生成建議失敗：{e}'}), 500
