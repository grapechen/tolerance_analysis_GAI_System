"""ai_bp.py - AI 聊天、分析串流、資料匯入 Blueprint

包含：
  - GET  /  /en          渲染主頁面（繁中 / 英文）
  - POST /api/chat       AI 對話（Ollama / 雲端）
  - GET  /api/analyze_tolerance_stream  容差分析 SSE 串流
  - POST /api/import_excel              Excel 路徑匯入
  - POST /api/sync_report               接收 app.py 的報表同步
  - GET  /api/ras400/tolerance_lookup   RAS400 公差查找表
  - POST /api/sfa/import_csv            SFA CSV 匯入
"""

import os
import json
from flask import Blueprint, jsonify, request, render_template, Response
from scripts.triplets_extractor import get_mating_constraints
from rag_engine import ask_rag_engine
import graph_rag
from services.ai_service import AIService

ai_bp = Blueprint('ai', __name__)

_ai_svc = AIService()


# ── 頁面路由 ──────────────────────────────────────────────────────────────────

@ai_bp.get('/')
def home():
    model_names, current_model = _ai_svc.get_available_models()
    constraints = get_mating_constraints()
    return render_template(
        'index.html',
        models=model_names,
        current_model=current_model,
        lang='zh-TW',
        mating_constraints=constraints,
    )


@ai_bp.get('/en')
def home_en():
    model_names, current_model = _ai_svc.get_available_models()
    constraints = get_mating_constraints()
    return render_template(
        'index.html',
        models=model_names,
        current_model=current_model,
        lang='en',
        mating_constraints=constraints,
    )


# ── AI 對話 ───────────────────────────────────────────────────────────────────

@ai_bp.post('/api/chat')
def api_chat():
    data   = request.get_json(force=True)
    msg    = data.get('message', '')
    model  = data.get('model', 'llama3.1:8b')
    history        = data.get('history', [])
    lang           = data.get('lang', 'zh-TW')
    current_analysis    = data.get('current_analysis')
    current_path        = data.get('current_path')
    current_allocation  = data.get('current_allocation')
    current_pmi_session = data.get('current_pmi_session_id')
    wf_state            = data.get('wf_state') or {}

    if not msg:
        return jsonify({'reply': '請輸入訊息' if lang != 'en' else 'Please enter a message'}), 400

    model_lower = model.lower()
    is_cloud = (
        '-cloud' in model_lower or ':cloud' in model_lower
        or any(model_lower.startswith(p) for p in [
            'gpt-oss', 'qwen3-vl', 'qwen3-v1', 'ministral-3',
            'qwen3-coder', 'glm-4', 'deepseek', 'minimax',
        ])
    )
    base_url = 'http://localhost:11434'

    try:
        reply, bom_intent = ask_rag_engine(
            msg, model_name=model, base_url=base_url, history=history, lang=lang,
            current_analysis=current_analysis, current_path=current_path,
            current_allocation=current_allocation, current_pmi_session=current_pmi_session,
            wf_state=wf_state,
        )
    except Exception as e:
        import sys
        print(f'[WARN] RAG 執行失敗: {e}, python: {sys.executable}')
        reply     = f'[ERROR] 執行發生錯誤: {e}'
        bom_intent = {}

    return jsonify({'reply': reply, 'intent': bom_intent})


# ── 公差分析串流 (POST，避免 pathData 超過 URL 長度上限) ─────────────────────

@ai_bp.post('/api/analyze_tolerance_stream')
def analyze_tolerance_stream():
    body = request.get_json(silent=True) or {}
    path_data = body.get('pathData', [])
    if not isinstance(path_data, list):
        return jsonify({'error': 'pathData 必須為陣列'}), 400

    try:
        mc_samples = int(body.get('n_samples', 10000))
        mc_sigma   = float(body.get('sigma', 3.0))
        mc_dist    = int(body.get('dist_type', 0))
    except (ValueError, TypeError):
        mc_samples, mc_sigma, mc_dist = 10000, 3.0, 0

    try:
        from analysis_service import analyze_stream
    except ImportError as e:
        return jsonify({'error': f'analysis_service 載入失敗: {e}'}), 500

    return Response(
        analyze_stream(path_data, mc_samples=mc_samples, mc_sigma=mc_sigma, mc_dist=mc_dist),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


# ── Excel 匯入 ────────────────────────────────────────────────────────────────

@ai_bp.post('/api/import_excel')
def import_excel():
    if 'file' not in request.files:
        return jsonify({'error': '未提供檔案'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': '未選擇檔案'}), 400

    try:
        from analysis_service import parse_excel_to_path
        path_data = parse_excel_to_path(file.read(), filename=file.filename)
        return jsonify({'pathData': path_data})
    except Exception as e:
        return jsonify({'error': f'解析失敗: {str(e)}'}), 500


# ── 報表同步接收端（供 app.py/7010 呼叫）─────────────────────────────────────

@ai_bp.post('/api/sync_report')
def sync_report():
    try:
        data        = request.get_json()
        report_text = data.get('reportText', '')
        if not report_text:
            return jsonify({'ok': False, 'msg': '沒有收到報表內容'}), 400
        graph_rag.set_latest_report(report_text)
        return jsonify({'ok': True, 'msg': '報表同步成功'})
    except Exception as e:
        return jsonify({'ok': False, 'msg': f'同步失敗: {str(e)}'}), 500


# ── RAS400 公差查找 ───────────────────────────────────────────────────────────

@ai_bp.get('/api/ras400/tolerance_lookup')
def ras400_tolerance_lookup():
    try:
        import math
        from sfa_csv_importer import SfaCsvImporter, ANGULAR_TYPES
        from scripts.ras400_ontology_builder import RAS400_PARTS, tol_code_to_uri

        def _clean(v):
            if v is None: return None
            if isinstance(v, float) and math.isnan(v): return None
            if isinstance(v, str) and v.strip().lower() == 'nan': return None
            return v

        lookup = {}
        for part_name, csv_path in RAS400_PARTS:
            if not os.path.exists(csv_path):
                continue
            imp  = SfaCsvImporter()
            rows = imp.load_csv(csv_path)
            for row in rows:
                if row.is_datum() or row.is_feature_only:
                    continue
                uri = tol_code_to_uri(row.code)
                nominal = _clean(row.nominal)
                lookup[uri] = {
                    'val':          row.tol_value or 0,
                    'bias':         row.bias or 0,
                    'nominal_size': nominal,
                    'it_grade':     _clean(row.it_grade),
                    'dist':         nominal if row.tol_type in ANGULAR_TYPES and nominal else '',
                    'type_code':    row.tol_type,
                    'part':         part_name,
                }
        return jsonify({'ok': True, 'lookup': lookup, 'count': len(lookup)})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── SFA CSV 匯入 ──────────────────────────────────────────────────────────────

@ai_bp.post('/api/sfa/import_csv')
def sfa_import_csv():
    try:
        import tempfile
        from sfa_csv_importer import SfaCsvImporter

        ontology_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'ras400_ontology.csv')

        # ISO 2768 等級（可由前端傳入，預設 mK）
        geo_class    = request.form.get('iso2768_geo',    None) or (request.get_json(silent=True) or {}).get('iso2768_geo',    'K')
        linear_class = request.form.get('iso2768_linear', None) or (request.get_json(silent=True) or {}).get('iso2768_linear', 'm')

        importer = SfaCsvImporter(
            ontology_csv_path    = ontology_path,
            iso2768_geo_class    = geo_class,
            iso2768_linear_class = linear_class,
        )

        axis = 'Z'
        include_types = None

        if 'csv_file' in request.files:
            f    = request.files['csv_file']
            axis = request.form.get('axis', 'Z')
            ts   = request.form.get('include_types', '')
            if ts:
                include_types = set(ts.split(','))
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
            f.save(tmp.name)
            csv_path = tmp.name
        else:
            body     = request.get_json() or {}
            csv_path = body.get('csv_path')
            axis     = body.get('axis', 'Z')
            tl       = body.get('include_types')
            if tl:
                include_types = set(tl)
            if not csv_path or not os.path.exists(csv_path):
                return jsonify({'ok': False, 'error': '找不到 CSV 檔案'}), 400

        rows      = importer.load_csv(csv_path)
        path_data = importer.build_path_from_csv(csv_path, axis=axis, include_types=include_types)

        by_type = {}
        for r in rows:
            by_type[r.tol_type] = by_type.get(r.tol_type, 0) + 1

        return jsonify({
            'ok':          True,
            'n_pmi_rows':  len(rows),
            'n_path_items': len(path_data),
            'by_type':     by_type,
            'path_data':   path_data,
            'axis':        axis,
        })
    except Exception as e:
        import traceback
        return jsonify({'ok': False, 'error': str(e), 'trace': traceback.format_exc()}), 500
