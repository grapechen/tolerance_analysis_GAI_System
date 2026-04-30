"""matchmaking_bp.py - 製程與機台媒合 Blueprint

薄控制層：驗證參數 → 呼叫 MatchmakingService → 依環境同步報表 → 回傳 JSON。
兩種報表同步策略：
  - HTTP 模式（app.py / 7010）：POST to http://localhost:7011/api/sync_report
  - Direct 模式（ai_app.py / 7011）：直接呼叫 graph_rag.set_latest_report()
"""

from flask import Blueprint, jsonify, request
from services.matchmaking_service import MatchmakingService
from logger import app_logger

matchmaking_bp = Blueprint('matchmaking', __name__)

_matchmaking_svc = MatchmakingService()


@matchmaking_bp.post('/api/matchmaking')
def api_matchmaking():
    p            = request.get_json(force=True)
    keywords     = p.get('keywords', [])
    diameter     = p.get('diameter')
    safety_factor = p.get('safety_factor', 1.0)

    if not keywords or not diameter:
        return jsonify({'ok': False, 'msg': '請提供 keywords(功能) 和 diameter(直徑)'}), 400

    try:
        diameter      = float(diameter)
        safety_factor = float(safety_factor)
    except ValueError:
        return jsonify({'ok': False, 'msg': 'diameter 和 safety_factor 必須是數字'}), 400

    try:
        result = _matchmaking_svc.run(keywords, diameter, safety_factor)
    except ValueError as e:
        return jsonify({'ok': False, 'msg': str(e)}), 404

    # 產出報表文字
    report_text = MatchmakingService.build_report_text(result)

    # 報表同步策略由 Blueprint 建立時注入的 sync_mode 決定
    sync_mode = matchmaking_bp.config.get('sync_mode', 'http')  # type: ignore[attr-defined]
    _sync_report(report_text, sync_mode)

    # 移除內部欄位後回傳
    result.pop('_machines_raw', None)
    return jsonify({'ok': True, **result})


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
