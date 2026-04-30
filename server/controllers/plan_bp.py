"""plan_bp.py - 方案一/方案二 驗證測試 Blueprint

路由：
  POST /api/plan1/recommend_one   方案一（單對輸入）：零件+功能+尺寸 → fit + 機台
  POST /api/plan2/analyze_path    方案二步驟①：對既有路徑做公差分析（不調整）
  POST /api/plan2/apply_command   方案二步驟②：套用使用者指令（手動 IT 變更）
  POST /api/plan1/recommend       方案一（批次版，內部測試保留）
  POST /api/plan2/adjust          方案二（自動調配版，保留）
  GET  /api/plan/mating_pairs     列出所有配對（驗證資料）
"""

from flask import Blueprint, jsonify, request

from services.plan_service import (
    PlanService,
    DEFAULT_FOCUS_PARTS,
    DEFAULT_STACK_CHAIN,
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
        'default_chain':   list(DEFAULT_STACK_CHAIN),
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


@plan_bp.post('/api/plan2/analyze_path')
def analyze_path():
    """方案二步驟①：對使用者編輯的公差累積路徑（editorPathData）做分析。

    Request JSON:
      {
        "path_data": [...]   // 來自前端 editorPathData
      }
    """
    p = request.get_json(silent=True) or {}
    path_data = p.get('path_data')
    if not isinstance(path_data, list):
        return jsonify({'ok': False, 'msg': '請提供 path_data（editorPathData）陣列'}), 400

    result = _svc.analyze_path(path_data)
    if 'error' in result:
        return jsonify({'ok': False, 'msg': result['error']}), 400
    return jsonify({'ok': True, **result})


@plan_bp.post('/api/plan2/apply_command')
def apply_command():
    """方案二步驟②：解析使用者指令並套用到路徑（其他項不動）。

    Request JSON:
      {
        "path_data": [...],            // editorPathData
        "command":   "請將編號5零件...IT7"
      }
    """
    p = request.get_json(silent=True) or {}
    command = (p.get('command') or '').strip()
    if not command:
        return jsonify({'ok': False, 'msg': '請提供 command'}), 400
    path_data = p.get('path_data')
    if not isinstance(path_data, list):
        return jsonify({'ok': False, 'msg': '請提供 path_data（editorPathData）陣列'}), 400

    result = _svc.apply_command(path_data, command)
    if 'error' in result:
        return jsonify({'ok': False, 'msg': result['error'],
                        'parsed': result.get('parsed')}), 400
    return jsonify({'ok': True, **result})


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


@plan_bp.post('/api/plan2/adjust')
def adjust_plan2():
    """方案二：對 Plan 1 結果做緊/鬆調配。

    Request JSON:
      {
        "plan1": [...],                 # 方案一輸出（必填）
        "chain": ["MP03", "MP02", ...], # 選擇要做 stack-up 的鏈，預設 DEFAULT_STACK_CHAIN
        "target_um": 50,                # 目標累積（μm），不給則用門檻法
        "high_threshold": 25,           # 高貢獻門檻 %（預設 25）
        "low_threshold":  8             # 低貢獻門檻 %（預設 8）
      }
    """
    p = request.get_json(silent=True) or {}
    plan1 = p.get('plan1')
    if not plan1:
        return jsonify({'ok': False, 'msg': '請提供 plan1（方案一輸出）'}), 400

    chain = p.get('chain') or DEFAULT_STACK_CHAIN
    try:
        target_um = float(p['target_um']) if p.get('target_um') is not None else None
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'msg': 'target_um 必須是數值'}), 400
    try:
        high_th = float(p.get('high_threshold', 25.0))
        low_th  = float(p.get('low_threshold', 8.0))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'msg': 'threshold 必須是數值'}), 400

    result = _svc.adjust_plan2(
        plan1, chain=chain, target_um=target_um,
        high_threshold=high_th, low_threshold=low_th,
    )
    if 'error' in result:
        return jsonify({'ok': False, 'msg': result['error']}), 400

    return jsonify({'ok': True, **result})
