"""app.py - ISO 286 基本查詢系統入口（Port 7010）

App factory 負責建立 Flask 應用並注冊所有 Blueprint。
業務邏輯、資料存取、路由定義皆已分層至各自模組。
"""

import os
import socket
from flask import Flask, send_from_directory
from flask_cors import CORS

from middleware import api_limiter
from logger import app_logger
from controllers.tolerance_bp import tolerance_bp
from controllers.matchmaking_bp import matchmaking_bp
from controllers.iso2768_bp import iso2768_bp
from controllers.plan_bp import plan_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.json.ensure_ascii = False
    CORS(app, resources={r'/*': {'origins': '*'}})
    api_limiter.init_app(app)

    # 媒合 Blueprint 使用 HTTP 同步報表到 ai_app (7011)
    matchmaking_bp.config = {'sync_mode': 'http'}   # type: ignore[attr-defined]

    app.register_blueprint(tolerance_bp)
    app.register_blueprint(matchmaking_bp)
    app.register_blueprint(iso2768_bp)
    app.register_blueprint(plan_bp)

    # ── 靜態頁面路由 ──────────────────────────────────────────────────────────
    base_dir   = os.path.dirname(os.path.abspath(__file__))
    client_dir = os.path.join(base_dir, '..', 'client')

    @app.get('/recommender')
    def recommender_page():
        return open(os.path.join(client_dir, 'recommender.html'), encoding='utf-8').read()

    @app.get('/')
    def index():
        return send_from_directory(client_dir, 'index.html')

    @app.get('/<path:filename>')
    def serve_static(filename):
        return send_from_directory(client_dir, filename)

    # 舊路徑相容
    @app.get('/lookup/tolerance')
    def lookup_tolerance_redirect():
        return index()

    return app


app = create_app()

if __name__ == '__main__':
    local_ip = socket.gethostbyname(socket.gethostname())
    app_logger.info('ISO 286 基本查詢系統啟動')
    app_logger.info(f'LAN IP: {local_ip}')
    app.run(host='0.0.0.0', port=7010, debug=True)
