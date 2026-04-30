"""iso2768_bp.py - ISO 2768 一般公差查詢 Blueprint

C 層：只負責參數驗證 → 呼叫 ISO2768Service → 回傳 JSON。
全部業務邏輯在 services/iso2768_service.py。
"""

from flask import Blueprint, jsonify, request
from services.iso2768_service import ISO2768Service

iso2768_bp = Blueprint('iso2768', __name__)
_svc = ISO2768Service()


# ── 統一查詢入口 ──────────────────────────────────────────────────────────────

@iso2768_bp.post('/api/iso2768/lookup')
def api_lookup():
    """
    統一查表 API。

    請求 Body（JSON）：
      {
        "characteristic": "flatness",      // 必填
        "length_mm": 400,                  // 依特徵類型提供
        "geo_class": "K",                  // Part 2 用 H/K/L 或 GH/GK/GL
        "tolerance_class": "m"             // Part 1 用 f/m/c/v
      }

    回傳：
      { "ok": true, "characteristic": "...", "input": {...}, "result": {...} }
    """
    p    = request.get_json(force=True) or {}
    char = p.pop('characteristic', None)
    if not char:
        return jsonify({'ok': False, 'msg': '請提供 characteristic 欄位'}), 400

    try:
        data = _svc.lookup(char, **{k: v for k, v in p.items() if v is not None})
        return jsonify({'ok': True, **data})
    except (ValueError, KeyError, TypeError) as e:
        return jsonify({'ok': False, 'msg': str(e)}), 400


# ── 分項查詢（方便前端直接用）────────────────────────────────────────────────

@iso2768_bp.post('/api/iso2768/linear')
def api_linear():
    """查線性尺寸公差（Table 1，Part 1）。
    Body: { "size_mm": 50, "tolerance_class": "m" }
    """
    p = request.get_json(force=True) or {}
    try:
        val = _svc.lookup_linear(float(p['size_mm']), str(p['tolerance_class']))
        return jsonify({'ok': True, 'size_mm': p['size_mm'],
                        'tolerance_class': p['tolerance_class'],
                        'deviation_mm': val,
                        'notation': '±',
                        'null_means': '必須個別標示' if val is None else None})
    except (KeyError, TypeError, ValueError) as e:
        return jsonify({'ok': False, 'msg': str(e)}), 400


@iso2768_bp.post('/api/iso2768/angular')
def api_angular():
    """查角度公差（Table 3，Part 1）。
    Body: { "shorter_side_mm": 30, "tolerance_class": "m" }
    """
    p = request.get_json(force=True) or {}
    try:
        result = _svc.lookup_angular(float(p['shorter_side_mm']), str(p['tolerance_class']))
        return jsonify({'ok': True, **result, 'notation': '±'})
    except (KeyError, TypeError, ValueError) as e:
        return jsonify({'ok': False, 'msg': str(e)}), 400


@iso2768_bp.post('/api/iso2768/geometric')
def api_geometric():
    """查幾何公差（Part 2）。
    Body: {
      "characteristic": "perpendicularity",
      "geo_class": "K",
      "shorter_side_mm": 150          // 各特徵所需參數
    }
    """
    p    = request.get_json(force=True) or {}
    char = p.pop('characteristic', None)
    if not char:
        return jsonify({'ok': False, 'msg': '請提供 characteristic 欄位'}), 400

    geometric_types = {
        'straightness', 'flatness', 'circularity', 'cylindricity',
        'parallelism', 'perpendicularity', 'symmetry', 'coaxiality', 'circular_runout',
    }
    if char.lower() not in geometric_types:
        return jsonify({'ok': False, 'msg': f'{char!r} 非 Part 2 幾何公差特徵'}), 400

    try:
        data = _svc.lookup(char, **{k: v for k, v in p.items() if v is not None})
        return jsonify({'ok': True, **data})
    except (ValueError, KeyError, TypeError) as e:
        return jsonify({'ok': False, 'msg': str(e)}), 400


# ── 查詢可用等級與特徵列表（供前端下拉選單）─────────────────────────────────

@iso2768_bp.get('/api/iso2768/classes')
def api_classes():
    return jsonify({
        'ok': True,
        'part1_classes': ['f', 'm', 'c', 'v'],
        'part2_classes': ['H', 'K', 'L'],
        'part2_aliases': {'GH': 'H', 'GK': 'K', 'GL': 'L'},
        'characteristics': {
            'part1': ['linear_dimension', 'broken_edge', 'angular_dimension'],
            'part2': [
                'straightness', 'flatness', 'circularity', 'cylindricity',
                'parallelism', 'perpendicularity', 'symmetry', 'coaxiality', 'circular_runout',
            ],
        },
    })
