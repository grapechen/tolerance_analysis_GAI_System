"""ai_app.py - AI 公差諮詢系統入口（Port 7011）

RAS400 公差分析 AI 系統
Author    : Robert_Chen
Version   : 2.0  (2026)
Copyright : © 2026 Robert_Chen. All rights reserved.

App factory 負責建立 Flask 應用並注冊所有 Blueprint。
業務邏輯、資料存取、路由定義皆已分層至各自模組。
"""

import sys
import io
import os
import faulthandler

# ── 崩潰追蹤：segfault 時輸出 C-level traceback ─────────────────────────────
faulthandler.enable()

# ── Windows + Conda + MKL 安全設定（必須在 numpy 被 import 之前設定）──────────
# waitress 的工作執行緒裡跑 numpy 矩陣運算時，MKL 嘗試啟動多執行緒 BLAS 會
# 造成 segfault 並讓整個 Python 程式崩潰（exit code 非 0）。
# 強制覆蓋（非 setdefault）確保 conda 環境已有值時也能生效。
for _k in ('MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS',
           'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[_k] = '1'
# 允許多份 MKL/OpenMP DLL 並存（子程序繼承此設定，解決 0xC0000005 崩潰）
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
os.environ['MKL_THREADING_LAYER'] = 'sequential'
os.environ['MKL_DISABLE_FAST_MM'] = '1'

# Windows 終端機編碼修正（line_buffering 讓 print 能即時寫到 log）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

# RAS400 ontology 路徑
os.environ.setdefault(
    'RAS400_ONTOLOGY_PATH',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'ras400_ontology.csv')
)

from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

from controllers.ai_bp import ai_bp
from controllers.export_bp import export_bp
from controllers.step_bp import step_bp
from controllers.tolerance_bp import tolerance_bp
from controllers.matchmaking_bp import matchmaking_bp
from controllers.iso2768_bp import iso2768_bp
from controllers.plan_bp import plan_bp

load_dotenv()


def create_app() -> Flask:
    app = Flask(__name__)
    app.json.ensure_ascii = False
    CORS(app)

    # 媒合 Blueprint 在 ai_app 內直接呼叫 graph_rag（不走 HTTP）
    matchmaking_bp.config = {'sync_mode': 'direct'}  # type: ignore[attr-defined]

    app.register_blueprint(ai_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(step_bp)
    app.register_blueprint(tolerance_bp)
    app.register_blueprint(matchmaking_bp)
    app.register_blueprint(iso2768_bp)
    app.register_blueprint(plan_bp)

    return app


app = create_app()

if __name__ == '__main__':
    # 預設用 waitress 跑（避免 Werkzeug 在 Windows + 大 SSE 傳輸時 crash）
    # 若要除錯需求 ⇒ FLASK_DEBUG=1 改回 Werkzeug debug server
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    print('啟動 AI 聊天助手伺服器...')
    print('請訪問: http://127.0.0.1:7011')
    # 確認 MKL 安全設定已生效
    mkl_val = os.environ.get('MKL_NUM_THREADS', '未設定')
    print(f'  numpy/MKL 執行緒限制: MKL_NUM_THREADS={mkl_val}'
          + (' ✓' if mkl_val == '1' else ' ⚠ 未限制，公差分析可能崩潰！'))

    if debug_mode:
        use_reloader = os.environ.get('FLASK_RELOAD', '0') == '1'
        print(f'  模式: Werkzeug debug (reloader={"ON" if use_reloader else "OFF"})')
        print('  ⚠ 此模式下 SSE 串流可能 crash；正式使用請設 FLASK_DEBUG=0')
        app.run(host='0.0.0.0', port=7011, debug=True, use_reloader=use_reloader)
    else:
        from waitress import serve
        print('  模式: waitress（生產 WSGI，SSE 穩定）')
        serve(app, host='0.0.0.0', port=7011, threads=16, send_bytes=1)
