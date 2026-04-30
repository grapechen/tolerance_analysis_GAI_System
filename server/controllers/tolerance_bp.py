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
import json
import os

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
    p        = request.get_json(force=True)
    keywords = p.get('keywords', [])
    if not keywords:
        return jsonify({'ok': False, 'msg': '請提供 keywords 列表'}), 400

    results = smart_fit.search_fits(keywords)
    return jsonify({'ok': True, 'results': results, 'count': len(results)})


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
