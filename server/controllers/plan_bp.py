"""plan_bp.py - 公差配合推薦 Blueprint

路由：
  POST /api/plan1/recommend_one   方案一（單對輸入）：零件+功能+尺寸 → fit + 機台
  POST /api/plan1/recommend       方案一（批次版，內部測試保留）
  GET  /api/plan/mating_pairs     列出所有配對（驗證資料）
"""

from flask import Blueprint, jsonify, request

from services.plan_service import (
    PlanService,
    DEFAULT_FOCUS_PARTS,
)

plan_bp = Blueprint('plan', __name__)
_svc = PlanService()


@plan_bp.get('/api/plan/mating_pairs')
def list_mating_pairs():
    """回傳全部 12 對 + 聚焦白名單 + 預設 stack-up 鏈。"""
    pairs = _svc.load_mating_pairs()
    focused = _svc._filter_focus(pairs, DEFAULT_FOCUS_PARTS)
    return jsonify({
        'ok':              True,
        'pairs':           pairs,
        'focused_ids':     [p['pair_id'] for p in focused],
        'default_focus':   list(DEFAULT_FOCUS_PARTS),
    })


@plan_bp.get('/api/plan1/features')
def list_features():
    """列出所有可選特徵面（給前端 dropdown）。"""
    items = _svc.list_features()
    return jsonify({'ok': True, 'count': len(items), 'features': items})


@plan_bp.post('/api/plan1/feature_recommend')
def feature_recommend():
    """方案一（特徵驅動）：選一個特徵面 → 系統根據已知公差推薦 IT/製程/機台。

    Request JSON:
      {
        "feature_id": "軸承座-H-1",
        "overrides":  {                  // 可選，覆蓋 CSV 預設
          "Cir": 0.005, "Cyl": 0.003, ...,
          "it_dim": 6
        },
        "safety_factor": 1.7
      }
    """
    p = request.get_json(silent=True) or {}
    feature_id = (p.get('feature_id') or '').strip()
    if not feature_id:
        return jsonify({'ok': False, 'msg': '請提供 feature_id'}), 400
    overrides = p.get('overrides') or {}
    try:
        safety = float(p.get('safety_factor', 1.7))
    except (TypeError, ValueError):
        safety = 1.7

    result = _svc.feature_recommend(feature_id, overrides=overrides, safety_factor=safety)
    if 'error' in result:
        return jsonify({'ok': False, 'msg': result['error']}), 404
    return jsonify({'ok': True, **result})


@plan_bp.post('/api/plan1/recommend_one')
def recommend_one():
    """方案一（單對輸入）。

    Request JSON:
      {
        "part_name": "軸承座",
        "function_desc": "軸承外圈固定，承受徑向負載",
        "nominal_dia": 47
      }
    """
    p = request.get_json(silent=True) or {}
    part_name     = (p.get('part_name') or '').strip()
    function_desc = (p.get('function_desc') or '').strip()
    try:
        nominal_dia = float(p.get('nominal_dia', 0))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'msg': 'nominal_dia 必須是數值'}), 400
    if not function_desc:
        return jsonify({'ok': False, 'msg': '請提供 function_desc'}), 400
    if nominal_dia <= 0:
        return jsonify({'ok': False, 'msg': 'nominal_dia 必須 > 0'}), 400

    result = _svc.recommend_one(part_name, function_desc, nominal_dia)
    return jsonify({'ok': True, 'result': result})





@plan_bp.get('/api/plan1/parts_list')
def parts_list():
    parts = _svc.get_parts_list()
    return jsonify({'ok': True, 'parts': parts})


@plan_bp.post('/api/plan1/advanced_recommend')
def advanced_recommend():
    p = request.get_json(silent=True) or {}
    focus_part   = (p.get('focus_part') or '').strip()
    current_path = p.get('current_path') or []
    if not focus_part:
        return jsonify({'ok': False, 'msg': '請提供 focus_part'}), 400
    result = _svc.advanced_recommend(focus_part, current_path)
    return jsonify({'ok': True, **result})


@plan_bp.post('/api/plan1/apply_fit')
def apply_fit():
    p = request.get_json(silent=True) or {}
    pair_id      = (p.get('pair_id') or '').strip()
    fit_hole     = (p.get('fit_hole') or '').strip()
    fit_shaft    = (p.get('fit_shaft') or '').strip()
    current_path = p.get('current_path') or []
    try:
        nominal_dia = float(p.get('nominal_dia', 0))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'msg': 'nominal_dia 必須是數字'}), 400
    if not pair_id or not fit_hole or not fit_shaft:
        return jsonify({'ok': False, 'msg': '缺少必要參數'}), 400
    result = _svc.apply_fit_to_path(pair_id, fit_hole, fit_shaft, nominal_dia, current_path)
    return jsonify(result)


@plan_bp.post('/api/plan1/recommend')
def recommend_plan1():
    """方案一：跑推薦。

    Request JSON (all optional):
      { "focus_parts": ["軸承座", ...] | null }   null = 不過濾，全部 12 對
    """
    p = request.get_json(silent=True) or {}
    focus_parts = p.get('focus_parts', list(DEFAULT_FOCUS_PARTS))
    if focus_parts in ([], None):
        focus_parts = None  # 不過濾

    try:
        plan1 = _svc.recommend_plan1(focus_parts=focus_parts)
    except FileNotFoundError as e:
        return jsonify({'ok': False, 'msg': f'找不到資料檔: {e}'}), 500

    return jsonify({
        'ok':      True,
        'count':   len(plan1),
        'plan1':   plan1,
        'meta':    {'focus_parts': focus_parts or 'all'},
    })

