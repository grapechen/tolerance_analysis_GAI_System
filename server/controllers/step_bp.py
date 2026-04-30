"""step_bp.py - STEP / PMI 3D 解析 Blueprint

將 step_service.py 的路由函式包裝為 Blueprint，
保持 step_service.py 的實作不變。
"""

from flask import Blueprint
from step_service import (
    route_upload_step,
    route_upload_xlsx,
    route_parse_pmi,
    route_get_geometry,
    route_get_pmi_list,
    route_highlight_pmi,
    route_all_pmi_geometry,
    route_run_asm_worker,
    route_get_asm_result,
    route_get_6dof,
    route_export_step_csv,
    route_progress_sse,
    route_progress_status,
    route_get_face_to_part,
)

step_bp = Blueprint('step', __name__)

# ── 上傳 ──────────────────────────────────────────────────────────────────────
step_bp.add_url_rule('/api/step/upload',      'step_upload',      route_upload_step,     methods=['POST'])
step_bp.add_url_rule('/api/step/upload_xlsx', 'step_upload_xlsx', route_upload_xlsx,     methods=['POST'])

# ── 解析 ──────────────────────────────────────────────────────────────────────
step_bp.add_url_rule('/api/step/parse_pmi',   'step_parse_pmi',   route_parse_pmi,       methods=['POST'])

# ── 幾何 ──────────────────────────────────────────────────────────────────────
step_bp.add_url_rule('/api/step/geometry',         'step_geometry',        route_get_geometry,      methods=['GET'])
step_bp.add_url_rule('/api/step/pmi_list',          'step_pmi_list',        route_get_pmi_list,      methods=['GET'])
step_bp.add_url_rule('/api/step/highlight',         'step_highlight',       route_highlight_pmi,     methods=['POST'])
step_bp.add_url_rule('/api/step/pmi_all_geometry',  'step_pmi_all_geom',    route_all_pmi_geometry,  methods=['POST'])

# ── 組合件 ────────────────────────────────────────────────────────────────────
step_bp.add_url_rule('/api/step/asm_contact', 'step_asm_contact', route_run_asm_worker,  methods=['POST'])
step_bp.add_url_rule('/api/step/asm_result',  'step_asm_result',  route_get_asm_result,  methods=['GET'])

# ── 6DOF 路徑 ─────────────────────────────────────────────────────────────────
step_bp.add_url_rule('/api/step/6dof',        'step_6dof',        route_get_6dof,        methods=['POST'])

# ── 匯出 ──────────────────────────────────────────────────────────────────────
step_bp.add_url_rule('/api/step/export_csv',  'step_export_csv',  route_export_step_csv, methods=['POST'])

# ── 進度追蹤 ──────────────────────────────────────────────────────────────────
step_bp.add_url_rule('/api/step/progress',         'step_progress',         route_progress_sse,     methods=['GET'])
step_bp.add_url_rule('/api/step/progress_status',  'step_progress_status',  route_progress_status,  methods=['GET'])
step_bp.add_url_rule('/api/step/face_to_part',      'step_face_to_part',     route_get_face_to_part, methods=['GET'])
