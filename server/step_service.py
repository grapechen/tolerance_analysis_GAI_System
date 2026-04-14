"""
step_service.py - STEP PMI Flask 服務層
========================================
提供 7 個 Flask 路由端點處理 STEP/PMI 解析、幾何匯出、組合件分析等。
"""

import os
import json
import uuid
import tempfile
import subprocess
import traceback
import io
from datetime import datetime
from collections import defaultdict

import pandas as pd
from flask import request, jsonify, Response, stream_with_context

from tables import PmiSession, PmiItem, AssemblyContact, PmiExportRecord, engine, Session
from step_core import (
    parse_sfa_excel, load_sfa_association, parse_tessellated_annotations,
    build_geometry_feature_tree, tessellate_face_by_step_ids,
    tessellate_shape_to_json, tao_compound_to_lines_json,
    StepXcafEngine
)
from path_extractor import Step6DofExtractor
from progress_tracker import ProgressTracker, get_progress, get_all_progress


# ═══════════════════════════════════════════════════════════
# 設定常數
# ═══════════════════════════════════════════════════════════

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'data', 'step_uploads')
ASM_WORKER_PATH = os.path.join(os.path.dirname(__file__), 'asm_worker.py')
PYTHON_EXE = r"C:\Users\User\anaconda3\envs\tol_env\python.exe"
ASM_WORKER_TIMEOUT = 600

os.makedirs(UPLOAD_DIR, exist_ok=True)

# 記憶體中的 session 存儲（用於緩存 StepXcafEngine 物件）
_step_sessions = {}


# ═══════════════════════════════════════════════════════════
# 輔助函數
# ═══════════════════════════════════════════════════════════

def _ensure_python_exe():
    """確保 Python 路徑有效"""
    if not os.path.exists(PYTHON_EXE):
        return None
    return PYTHON_EXE


def _create_session_dir(session_id):
    """為新 session 建立目錄"""
    session_dir = os.path.join(UPLOAD_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)
    return session_dir


# ═══════════════════════════════════════════════════════════
# 路由 1: POST /api/step/upload
# ═══════════════════════════════════════════════════════════

def route_upload_step():
    """上傳 STEP 檔案，建立新 session（不立即解析）"""
    try:
        if 'stp_file' not in request.files:
            return jsonify({"ok": False, "error": "缺少 stp_file 欄位"}), 400

        stp_file = request.files['stp_file']

        if not stp_file or stp_file.filename == '':
            return jsonify({"ok": False, "error": "STP 檔案無效"}), 400

        # 建立 session
        session_id = str(uuid.uuid4())
        session_dir = _create_session_dir(session_id)

        # 儲存 STEP 檔案
        stp_filename = stp_file.filename
        stp_path = os.path.join(session_dir, stp_filename)
        stp_file.save(stp_path)

        # 寫入 MySQL（此時還沒有 XLSX）
        db_session = Session()
        pmi_session_obj = PmiSession(
            session_id=session_id,
            stp_filename=stp_filename,
            stp_path=stp_path,
            xlsx_filename=None,
            xlsx_path=None,
            status='pending'
        )
        db_session.add(pmi_session_obj)
        db_session.commit()
        db_session.close()

        return jsonify({
            "ok": True,
            "session_id": session_id,
            "stp_filename": stp_filename,
            "message": "✅ STEP 檔案已上傳。請上傳 XLSX 檔案，然後點擊「比對 & 解析 PMI」。"
        }), 200

    except Exception as e:
        print(f"❌ 上傳錯誤：{e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════
# 路由 1b: POST /api/step/upload_xlsx
# 將 XLSX 上傳到已存在的 session（用於兩步上傳流程）
# ═══════════════════════════════════════════════════════════

def route_upload_xlsx():
    """上傳 XLSX 檔案到已存在的 session"""
    try:
        if 'xlsx_file' not in request.files:
            return jsonify({"ok": False, "error": "缺少 xlsx_file 欄位"}), 400

        xlsx_file = request.files['xlsx_file']
        session_id = request.form.get('session_id')

        if not session_id:
            return jsonify({"ok": False, "error": "缺少 session_id"}), 400

        if not xlsx_file or xlsx_file.filename == '':
            return jsonify({"ok": False, "error": "XLSX 檔案無效"}), 400

        # 從 DB 取得 session
        db_session = Session()
        pmi_session_obj = db_session.query(PmiSession).filter_by(session_id=session_id).first()
        if not pmi_session_obj:
            db_session.close()
            return jsonify({"ok": False, "error": "Session 不存在"}), 404

        session_dir = os.path.dirname(pmi_session_obj.stp_path)

        # 儲存 XLSX 檔案
        xlsx_filename = xlsx_file.filename
        xlsx_path = os.path.join(session_dir, xlsx_filename)
        xlsx_file.save(xlsx_path)

        # 更新 session
        pmi_session_obj.xlsx_filename = xlsx_filename
        pmi_session_obj.xlsx_path = xlsx_path
        db_session.commit()
        db_session.close()

        return jsonify({
            "ok": True,
            "session_id": session_id,
            "xlsx_filename": xlsx_filename
        }), 200

    except Exception as e:
        print(f"❌ XLSX 上傳錯誤：{e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════
# 路由 2: POST /api/step/parse_pmi
# ═══════════════════════════════════════════════════════════

def route_parse_pmi():
    """解析 PMI，填充 pmi_item 資料表"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')

        if not session_id:
            return jsonify({"ok": False, "error": "缺少 session_id"}), 400

        # 初始化進度追蹤
        progress = ProgressTracker(session_id, "parse_pmi")

        # 從 DB 取得 session 資訊
        db_session = Session()
        pmi_session_obj = db_session.query(PmiSession).filter_by(session_id=session_id).first()
        if not pmi_session_obj:
            db_session.close()
            return jsonify({"ok": False, "error": "Session 不存在"}), 404

        stp_path = pmi_session_obj.stp_path
        xlsx_path = pmi_session_obj.xlsx_path

        # 1. 載入 STEP 幾何
        progress.update(1, 6, "📂 正在加載 STEP 文件...")
        engine_obj = StepXcafEngine()
        engine_obj.load(stp_path)

        # 2. 解析 XLSX（若有）
        progress.update(2, 6, "📊 正在解析 Excel...")
        face_pmi_map = {}
        pmi_rows = []
        if xlsx_path and os.path.exists(xlsx_path):
            face_pmi_map, pmi_rows = parse_sfa_excel(xlsx_path)

        # 3. 備援：幾何特徵樹
        progress.update(3, 6, "🌳 正在建構幾何特徵樹...")
        if not pmi_rows:
            pmi_rows = build_geometry_feature_tree(engine_obj)

        # 4. 載入 ASSOCIATION 鏈（semantic_id → tao_id）
        progress.update(4, 6, "🔗 正在加載 ASSOCIATION...")
        semantic_to_tao = {}
        tao_to_data = {}
        if xlsx_path and os.path.exists(xlsx_path):
            semantic_to_tao = load_sfa_association(xlsx_path)

        # 5. 解析 tessellated 標註（全局掃描）
        progress.update(5, 6, "🔺 正在解析 Tessellated 標註...")
        if xlsx_path:
            tao_to_data, step_sem_to_tao = parse_tessellated_annotations(stp_path, scan_all=True)
            semantic_to_tao.update(step_sem_to_tao)

        # 6. 寫入 pmi_item 資料表
        progress.update(6, 6, f"💾 正在寫入 {len(pmi_rows)} 個 PMI 項目...")
        for row_idx, row in enumerate(pmi_rows):
            tao_id = None
            if row.get('semantic_id'):
                tao_id = semantic_to_tao.get(row['semantic_id'])

            pmi_item_obj = PmiItem(
                session_id=session_id,
                row_index=row_idx,
                label=row.get('label', ''),
                type_code=row.get('type_code'),
                semantic_id=row.get('semantic_id'),
                tao_id=tao_id,
                face_ids=json.dumps(row.get('face_ids', [])),
                is_datum=1 if row.get('is_datum', False) else 0,
                is_interactive=1 if row.get('is_interactive', False) else 0,
                is_feature_only=1 if row.get('is_feature_only', False) else 0,
                nominal_size=row.get('nominal_size'),        # 新增：公稱尺寸
                it_grade=row.get('it_grade')                 # 新增：IT等級
            )
            db_session.add(pmi_item_obj)

        # 更新 session 狀態
        pmi_session_obj.n_faces = len(engine_obj.step_id_to_face)
        pmi_session_obj.n_pmi_rows = len(pmi_rows)
        pmi_session_obj.status = 'ready'

        db_session.commit()

        # 快取到記憶體
        _step_sessions[session_id] = {
            'stp_path': stp_path,
            'xlsx_path': xlsx_path,
            'engine': engine_obj,
            'face_pmi_map': face_pmi_map,
            'pmi_rows': pmi_rows,
            'tao_to_data': tao_to_data,
            'semantic_to_tao': semantic_to_tao,
        }

        db_session.close()

        # 完成進度追蹤
        progress.complete(f"✅ PMI 解析完成 ({len(engine_obj.step_id_to_face)} 個面，{len(pmi_rows)} 個 PMI 項目)")

        return jsonify({
            "ok": True,
            "session_id": session_id,
            "n_faces": len(engine_obj.step_id_to_face),
            "n_pmi_rows": len(pmi_rows),
            "pmi_rows": pmi_rows
        }), 200

    except Exception as e:
        print(f"❌ 解析 PMI 錯誤：{e}")
        traceback.print_exc()
        progress = ProgressTracker(session_id, "parse_pmi")
        progress.error(f"❌ 解析失敗: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════
# 路由 3: GET /api/step/geometry
# ═══════════════════════════════════════════════════════════

def route_get_geometry():
    """依 face_ids 回傳三角網格 JSON（支持 * 通配符加載所有面）"""
    try:
        session_id = request.args.get('session_id')
        face_ids_str = request.args.get('face_ids', '')
        deflection = float(request.args.get('deflection', 0.1))

        if not session_id or not face_ids_str:
            return jsonify({"ok": False, "error": "缺少參數"}), 400

        if session_id not in _step_sessions:
            return jsonify({"ok": False, "error": "Session 不存在或已過期"}), 404

        sess = _step_sessions[session_id]
        engine_obj = sess['engine']

        # 支持 * 通配符：加載所有面
        if face_ids_str == '*':
            face_ids = list(engine_obj.step_id_to_face.keys())
        else:
            face_ids = face_ids_str.split(',')

        # 初始化進度追蹤
        progress = ProgressTracker(session_id, "tessellate")
        progress.update(1, 2, f"🔺 正在三角化 {len(face_ids)} 個面...")

        # 三角化
        geom = tessellate_face_by_step_ids(engine_obj, face_ids, deflection)

        if not geom:
            progress.error("❌ 幾何三角化失敗")
            return jsonify({"ok": False, "error": "幾何三角化失敗"}), 500

        progress.complete("✅ 三角化完成")

        return jsonify({
            "ok": True,
            "session_id": session_id,
            "face_ids": face_ids,
            "geometry": geom
        }), 200

    except Exception as e:
        print(f"❌ 幾何查詢錯誤：{e}")
        progress = ProgressTracker(session_id, "tessellate")
        progress.error(f"❌ 查詢失敗: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════
# 路由 4: GET /api/step/pmi_list
# ═══════════════════════════════════════════════════════════

def route_get_pmi_list():
    """回傳 PMI 條目清單"""
    try:
        session_id = request.args.get('session_id')

        if not session_id:
            return jsonify({"ok": False, "error": "缺少 session_id"}), 400

        if session_id not in _step_sessions:
            return jsonify({"ok": False, "error": "Session 不存在或已過期"}), 404

        sess = _step_sessions[session_id]
        pmi_rows = sess['pmi_rows']

        return jsonify({
            "ok": True,
            "session_id": session_id,
            "pmi_rows": pmi_rows
        }), 200

    except Exception as e:
        print(f"❌ PMI 清單查詢錯誤：{e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════
# 路由 5: POST /api/step/highlight
# ═══════════════════════════════════════════════════════════

def route_highlight_pmi():
    """高亮指定 PMI（回傳幾何 + leader lines）"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        row_index = data.get('row_index')
        label_substring = data.get('label_substring')

        if not session_id:
            return jsonify({"ok": False, "error": "缺少 session_id"}), 400

        if session_id not in _step_sessions:
            return jsonify({"ok": False, "error": "Session 不存在或已過期"}), 404

        sess = _step_sessions[session_id]
        engine_obj = sess['engine']
        pmi_rows = sess['pmi_rows']
        tao_to_data = sess['tao_to_data']

        # 找到目標 PMI row
        target_row = None
        if row_index is not None and 0 <= row_index < len(pmi_rows):
            target_row = pmi_rows[row_index]
        elif label_substring:
            for row in pmi_rows:
                if label_substring.lower() in row.get('label', '').lower():
                    target_row = row
                    break

        if not target_row:
            return jsonify({"ok": False, "error": "找不到對應的 PMI"}), 404

        # 提取幾何
        face_ids = target_row.get('face_ids', [])
        face_geometry = tessellate_face_by_step_ids(engine_obj, face_ids) if face_ids else None

        # 提取 leader lines
        leader_lines = []
        tao_id = None
        if target_row.get('semantic_id'):
            tao_id = sess['semantic_to_tao'].get(target_row['semantic_id'])
        if tao_id and tao_id in tao_to_data:
            tao_compound = tao_to_data[tao_id].get('shape')
            if tao_compound:
                leader_lines = tao_compound_to_lines_json(tao_compound)

        # 顏色對應
        type_code = target_row.get('type_code', '')
        is_interactive = target_row.get('is_interactive', False)
        is_datum = target_row.get('is_datum', False)

        if is_datum or target_row.get('is_feature_only', False):
            highlight_color = "#00DA26"  # 綠色
        elif is_interactive:
            highlight_color = "#A121F0"  # 紫色
        else:
            highlight_color = "#FFA500"  # 橘色

        return jsonify({
            "ok": True,
            "pmi_label": target_row.get('label', ''),
            "face_geometry": face_geometry,
            "leader_lines": leader_lines,
            "highlight_color": highlight_color,
            "type_code": type_code,
            "is_interactive": is_interactive
        }), 200

    except Exception as e:
        print(f"❌ PMI 高亮查詢錯誤：{e}")
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════
# 路由 6: POST /api/step/asm_contact
# ═══════════════════════════════════════════════════════════

def route_run_asm_worker():
    """執行組合件接觸分析（subprocess）"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')

        if not session_id:
            return jsonify({"ok": False, "error": "缺少 session_id"}), 400

        # 初始化進度追蹤
        progress = ProgressTracker(session_id, "asm_contact")
        progress.update(1, 3, "準備接觸分析...")

        # 從 DB 取得 STP 路徑
        db_session = Session()
        pmi_session_obj = db_session.query(PmiSession).filter_by(session_id=session_id).first()
        if not pmi_session_obj:
            db_session.close()
            return jsonify({"ok": False, "error": "Session 不存在"}), 404

        stp_path = pmi_session_obj.stp_path
        db_session.close()

        if not os.path.exists(stp_path):
            progress.error("❌ STEP 檔案不存在")
            return jsonify({"ok": False, "error": "STEP 檔案不存在"}), 404

        # 執行子進程
        progress.update(2, 3, "🔄 執行接觸分析子進程...")
        python_exe = _ensure_python_exe()
        if not python_exe:
            python_exe = "python"

        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.close()
        out_json = tmp.name

        proc = subprocess.Popen(
            [python_exe, ASM_WORKER_PATH, stp_path, out_json],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace'
        )

        import time
        deadline = time.time() + ASM_WORKER_TIMEOUT
        for line in iter(proc.stdout.readline, ''):
            print(line, end='', flush=True)
            if time.time() > deadline:
                proc.kill()
                os.unlink(out_json)
                progress.error(f"❌ 分析超時（超過 {ASM_WORKER_TIMEOUT} 秒）")
                return jsonify({
                    "ok": False,
                    "error": f"組合件分析超過 {ASM_WORKER_TIMEOUT} 秒"
                }), 500

        proc.stdout.close()
        proc.wait()

        # 讀取結果
        progress.update(3, 3, "📊 處理分析結果...")
        result = {"status": "error", "msg": "", "contacts": [], "solids": [], "n_parts": 0}
        if os.path.exists(out_json):
            with open(out_json, 'r', encoding='utf-8') as f:
                result = json.load(f)
            os.unlink(out_json)

        # 寫入 MySQL
        if result.get('status') == 'ok':
            db_session = Session()
            for contact in result.get('contacts', []):
                contact_obj = AssemblyContact(
                    session_id=session_id,
                    comp1_name=contact.get('comp1', ''),
                    comp2_name=contact.get('comp2', ''),
                    contact_type=contact.get('ctype', ''),
                    face_pairs_json=json.dumps(contact.get('face_pairs', [])),
                    bbox1_json=json.dumps(contact['face_pairs'][0]['bbox1']) if contact.get('face_pairs') else None,
                    bbox2_json=json.dumps(contact['face_pairs'][0]['bbox2']) if contact.get('face_pairs') else None
                )
                db_session.add(contact_obj)
            db_session.commit()
            db_session.close()

        # 完成進度追蹤
        progress.complete(f"✅ 接觸分析完成 ({result.get('n_parts', 0)} 個部件，{len(result.get('contacts', []))} 個接觸)")

        return jsonify({
            "ok": result.get('status') == 'ok',
            "session_id": session_id,
            "n_contacts": len(result.get('contacts', [])),
            "n_parts": result.get('n_parts', 0),
            "contacts": result.get('contacts', []),
            "solids": result.get('solids', [])
        }), 200

    except Exception as e:
        print(f"❌ 組合件分析錯誤：{e}")
        traceback.print_exc()
        progress = ProgressTracker(session_id, "asm_contact")
        progress.error(f"❌ 分析失敗: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════
# 路由 7: POST /api/step/6dof
# ═══════════════════════════════════════════════════════════

def route_get_6dof():
    """計算兩個 AXIS2_PLACEMENT_3D 之間的 6-DOF"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        ref_entity_id = data.get('ref_entity_id')
        target_entity_id = data.get('target_entity_id')

        if not session_id:
            return jsonify({"ok": False, "error": "缺少 session_id"}), 400

        if session_id not in _step_sessions:
            return jsonify({"ok": False, "error": "Session 不存在或已過期"}), 404

        sess = _step_sessions[session_id]
        stp_path = sess['stp_path']

        # 使用 Step6DofExtractor
        extractor = Step6DofExtractor(stp_path)
        result = extractor.calculate_relative_6dof(ref_entity_id, target_entity_id)

        if not result:
            return jsonify({"ok": False, "error": "無法計算 6-DOF"}), 500

        return jsonify({
            "ok": True,
            "traX": result.get('traX'),
            "traY": result.get('traY'),
            "traZ": result.get('traZ'),
            "rotX": result.get('rotX'),
            "rotY": result.get('rotY'),
            "rotZ": result.get('rotZ'),
            "unit": "degrees"
        }), 200

    except Exception as e:
        print(f"❌ 6-DOF 計算錯誤：{e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════
# 路由 8: POST /api/step/export_csv
# ═══════════════════════════════════════════════════════════

def route_export_step_csv():
    """導出 PMI BOM 或組合件接觸報表 CSV，同時存入 MySQL"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        export_mode = data.get('mode', 'pmi')  # 'pmi' 或 'asm'
        checked_indices = data.get('checked_indices', [])  # 勾選的行索引

        if not session_id:
            return jsonify({"ok": False, "error": "缺少 session_id"}), 400

        if session_id not in _step_sessions:
            return jsonify({"ok": False, "error": "Session 不存在或已過期"}), 404

        sess = _step_sessions[session_id]
        pmi_rows = sess['pmi_rows']
        engine_obj = sess['engine']

        # 產生 CSV 內容
        csv_rows = []
        db_session = Session()

        if export_mode == 'asm':
            # ── 組合件接觸介面報表 ────────────────────────────────
            # 這裡假設檢查了組合件分析結果
            # 簡化版本：回傳 PMI BOM 表
            pass

        # ── PMI BOM 對照表（機器可讀格式）────────────────────────────
        try:
            from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
            from OCC.Core.GeomAbs import (
                GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Cone,
                GeomAbs_Torus, GeomAbs_Sphere, GeomAbs_OtherSurface
            )
            from OCC.Core.TopAbs import TopAbs_REVERSED

            part_prefix = os.path.splitext(os.path.basename(sess.get('stp_path', 'X')))[0]
            if not part_prefix.strip(): part_prefix = "1"
            
            # 第一步：給予每個 Face 獨立的拓樸特徵代號(如 P1, H1, S1)
            feat_counters = {'P': 1, 'H': 1, 'S': 1, 'F': 1}
            fid_to_feat = {}
            
            sorted_faces = sorted(engine_obj.step_id_to_face.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else x[0])
            for fid, face in sorted_faces:
                try:
                    surf = BRepAdaptor_Surface(face)
                    stype = surf.GetType()
                    sym = 'F'
                    if stype == GeomAbs_Plane:
                        sym = 'P'
                    elif stype == GeomAbs_Cylinder:
                        sym = 'H' if (face.Orientation() == TopAbs_REVERSED) else 'S'
                    
                    feat_code = f"{part_prefix}-{sym}{feat_counters[sym]}"
                    feat_counters[sym] += 1
                    fid_to_feat[str(fid)] = feat_code
                except Exception:
                    feat_code = f"{part_prefix}-F{feat_counters['F']}"
                    feat_counters['F'] += 1
                    fid_to_feat[str(fid)] = feat_code

            # 第二步：產生符合機器讀取格式的導出行
            type_counters = defaultdict(int)
            for idx, row_info in enumerate(pmi_rows):
                if checked_indices and idx not in checked_indices:
                    continue

                label = row_info.get('label', '')
                
                # 萃取與清理數據：只移除 Emoji，不要移除 [交互]/[個別] 文字
                clean_label = label
                for icon in ["🎯 ", "📐 ", "🚩 ", "🧊 ", "🎯", "📐", "🚩", "🧊"]:
                    clean_label = clean_label.replace(icon, "")
                
                # 原本形式的公差代號 (e.g. 1-POS1)
                t_code = row_info.get('type_code', 'tol').upper()
                type_counters[t_code] += 1
                old_code_format = f"{part_prefix}-{t_code}{type_counters[t_code]}"

                # 判斷參考公差類型
                ref_type = "未分類"
                if row_info.get('is_datum'):
                    ref_type = "基準"
                elif row_info.get('is_feature_only'):
                    ref_type = "特徵面"
                elif row_info.get('is_interactive'):
                    ref_type = "交互"
                else:
                    ref_type = "個別"

                fids = sorted([str(fid) for fid in row_info.get('face_ids', [])], key=lambda x: int(x) if x.isdigit() else x)
                mapped_feats = [fid_to_feat.get(fid, "未知特徵") for fid in fids]

                csv_rows.append({
                    "公差代號": old_code_format,
                    "名稱/幾何類型": row_info.get('semantic_id', ''),  # 新增
                    "公差數值": clean_label.strip(),
                    "參考公差類型": ref_type,
                    "公稱尺寸": row_info.get('nominal_size') or '',  # 新增：公稱尺寸
                    "IT等級": row_info.get('it_grade') or '',  # 新增：IT等級
                    "Face ID": ", ".join([f"#{fid}" for fid in fids]) if fids else "",
                    "特徵代號": ", ".join(mapped_feats)
                })
        except ImportError:
            # OCC 不可用時的降級方案
            type_counters = defaultdict(int)
            for idx, row_info in enumerate(pmi_rows):
                if checked_indices and idx not in checked_indices:
                    continue
                    
                label = row_info.get('label', '')
                clean_label = label
                for icon in ["🎯 ", "📐 ", "🚩 ", "🧊 ", "🎯", "📐", "🚩", "🧊"]:
                    clean_label = clean_label.replace(icon, "")
                    
                t_code = row_info.get('type_code', 'tol').upper()
                type_counters[t_code] += 1
                old_code_format = f"Fallback-{t_code}{type_counters[t_code]}"

                ref_type = "未分類"
                if row_info.get('is_datum'):
                    ref_type = "基準"
                elif row_info.get('is_interactive'):
                    ref_type = "交互"
                else:
                    ref_type = "個別"
                
                fids = sorted([str(fid) for fid in row_info.get('face_ids', [])], key=lambda x: int(x) if x.isdigit() else x)

                csv_rows.append({
                    "公差代號": old_code_format,
                    "名稱/幾何類型": row_info.get('semantic_id', ''),  # 新增
                    "公差數值": clean_label.strip(),
                    "參考公差類型": ref_type,
                    "公稱尺寸": row_info.get('nominal_size') or '',  # 新增：公稱尺寸
                    "IT等級": row_info.get('it_grade') or '',  # 新增：IT等級
                    "Face ID": ", ".join([f"#{fid}" for fid in fids]) if fids else "",
                    "特徵代號": "未知 (無法載入引擎)"
                })

        # 轉換為 CSV 字串
        df = pd.DataFrame(csv_rows)
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, encoding='utf-8-sig')
        csv_content = csv_buffer.getvalue()

        # 寫入 MySQL
        export_record = PmiExportRecord(
            session_id=session_id,
            export_mode=export_mode,
            row_count=len(csv_rows),
            csv_content=csv_content
        )
        db_session.add(export_record)
        db_session.commit()
        db_session.close()

        # 回傳 CSV 供前端下載
        return Response(
            csv_content,
            mimetype="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="PMI_Export_{session_id[:8]}.csv"'
            }
        ), 200

    except Exception as e:
        print(f"❌ CSV 導出錯誤：{e}")
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════
# 進度追蹤 SSE 端點 (新增)
# ═══════════════════════════════════════════════════════════

from progress_tracker import get_progress, ProgressTracker
from flask import stream_with_context

def route_progress_sse():
    """
    Server-Sent Events (SSE) 端點
    連接後實時推送所有 session 的進度更新
    """
    def generate_events():
        import time
        import json as json_module
        
        # 首次發送所有現有進度
        from progress_tracker import get_all_progress
        yield f"data: {json_module.dumps({'type': 'all_progress', 'data': get_all_progress()})}\n\n"
        
        # 持續推送更新
        while True:
            all_progress = get_all_progress()
            if all_progress:
                yield f"data: {json_module.dumps({'type': 'update', 'data': all_progress})}\n\n"
            time.sleep(0.5)
    
    return Response(
        stream_with_context(generate_events()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


def route_progress_status():
    """
    獲取指定 session 的進度狀態
    """
    session_id = request.args.get('session_id')
    if not session_id:
        return jsonify({"ok": False, "error": "缺少 session_id"}), 400
    
    progress = get_progress(session_id)
    return jsonify({
        "ok": True,
        "session_id": session_id,
        "progress": progress
    }), 200
