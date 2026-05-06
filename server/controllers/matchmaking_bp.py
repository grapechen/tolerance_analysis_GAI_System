"""matchmaking_bp.py - 製程與機台媒合 Blueprint

薄控制層：驗證參數 → 呼叫 MatchmakingService → 依環境同步報表 → 回傳 JSON。
兩種報表同步策略：
  - HTTP 模式（app.py / 7010）：POST to http://localhost:7011/api/sync_report
  - Direct 模式（ai_app.py / 7011）：直接呼叫 graph_rag.set_latest_report()
"""

import os
import pandas as pd
from flask import Blueprint, jsonify, request
from recommendation import smart_fit
from services.matchmaking_service import MatchmakingService
from logger import app_logger

_DATA_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'data'))

matchmaking_bp = Blueprint('matchmaking', __name__)

_matchmaking_svc = MatchmakingService()


def _sanitize_fit(fit: dict) -> dict:
    """將 fit dict 內無法 JSON 序列化的欄位（如 set）轉成 list。"""
    if not isinstance(fit, dict):
        return fit
    out = dict(fit)
    if isinstance(out.get('tags'), set):
        out['tags'] = sorted(out['tags'])
    return out


@matchmaking_bp.get('/api/matchmaking/dimensions')
def api_matchmaking_dimensions():
    """回傳維度勾選 UI 所需的分組結構（中英對照）。"""
    return jsonify({
        'ok':     True,
        'groups': smart_fit.get_dimension_groups(),
    })


@matchmaking_bp.post('/api/matchmaking')
def api_matchmaking():
    """執行媒合。

    Body 接受兩種模式（dimensions 優先；二擇一）：
      A. 維度模式: {"diameter": 60, "dimensions": {"required": [...], "optional": [...]}}
      B. 關鍵字模式: {"diameter": 60, "keywords": [...]}
    """
    p             = request.get_json(force=True)
    keywords      = p.get('keywords', []) or []
    dimensions    = p.get('dimensions') or {}
    diameter      = p.get('diameter')
    safety_factor = p.get('safety_factor', 1.0)

    has_dims = bool((dimensions.get('required') or []) or (dimensions.get('optional') or []))
    if not has_dims and not keywords:
        return jsonify({
            'ok': False,
            'msg': '請提供 keywords(功能) 或 dimensions(維度勾選)，並指定 diameter(直徑)',
        }), 400
    if diameter is None:
        return jsonify({'ok': False, 'msg': '請提供 diameter(直徑)'}), 400

    try:
        diameter      = float(diameter)
        safety_factor = float(safety_factor)
    except (ValueError, TypeError):
        return jsonify({'ok': False, 'msg': 'diameter 和 safety_factor 必須是數字'}), 400

    try:
        result = _matchmaking_svc.run(
            keywords=keywords,
            diameter=diameter,
            safety_factor=safety_factor,
            dimensions=dimensions if has_dims else None,
        )
    except ValueError as e:
        return jsonify({'ok': False, 'msg': str(e)}), 404

    # 產出報表文字
    report_text = MatchmakingService.build_report_text(result)

    # 報表同步策略由 Blueprint 建立時注入的 sync_mode 決定
    sync_mode = matchmaking_bp.config.get('sync_mode', 'http')  # type: ignore[attr-defined]
    _sync_report(report_text, sync_mode)

    # 移除內部欄位、清理不可序列化的 set
    result.pop('_machines_raw', None)
    if 'step1_selected_fit' in result:
        result['step1_selected_fit'] = _sanitize_fit(result['step1_selected_fit'])
    return jsonify({'ok': True, **result})


@matchmaking_bp.get('/api/matchmaking/mating_pairs')
def api_mating_pairs():
    """回傳 ras400_mating_pairs.csv 所有配對資料。"""
    csv_path = os.path.join(_DATA_DIR, 'ras400_mating_pairs.csv')
    try:
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
        rows = df.where(df.notna(), None).to_dict(orient='records')
        return jsonify({'ok': True, 'pairs': rows})
    except Exception as e:
        return jsonify({'ok': False, 'msg': str(e)}), 500


@matchmaking_bp.post('/api/matchmaking/batch')
def api_matchmaking_batch():
    """批量執行配合推薦。

    Body: JSON 陣列，每筆格式與 ras400_mating_pairs.csv 相同，可附加：
      dimensions: {required: [...], optional: [...]}
      keywords:   [...]
    回傳：results 陣列 + report_rows 表格列 + csv 文字。
    """
    pairs = request.get_json(force=True)
    if not isinstance(pairs, list) or not pairs:
        return jsonify({'ok': False, 'msg': '請提供配對陣列'}), 400

    results = _matchmaking_svc.run_batch(pairs)
    report_rows = MatchmakingService.build_batch_report_rows(results)
    csv_text = MatchmakingService.build_batch_csv(report_rows)

    return jsonify({'ok': True, 'results': results, 'report_rows': report_rows, 'csv': csv_text})


def _sync_report(report_text: str, mode: str) -> None:
    """將報表文字同步給 AI 端。"""
    if mode == 'direct':
        try:
            import graph_rag
            graph_rag.set_latest_report(report_text)
            app_logger.info(f'報表已直接同步至 graph_rag（長度: {len(report_text)}）')
        except Exception as e:
            app_logger.warning(f'報表直接同步失敗: {e}')
    else:
        try:
            import requests
            requests.post(
                'http://localhost:7011/api/sync_report',
                json={'reportText': report_text},
                timeout=2,
            )
            app_logger.info(f'報表已 HTTP 同步至 AI 助手（長度: {len(report_text)}）')
        except Exception as e:
            app_logger.warning(f'報表 HTTP 同步失敗: {e}')
