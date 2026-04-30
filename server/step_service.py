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
import threading
from datetime import datetime
from collections import defaultdict

import pandas as pd
from flask import request, jsonify, Response, stream_with_context

from tables import PmiSession, PmiItem, AssemblyContact, PmiExportRecord, engine, Session
from step_core import (
    parse_sfa_excel, load_sfa_association, parse_tessellated_annotations,
    build_geometry_feature_tree, tessellate_face_by_step_ids,
    tessellate_shape_to_json, tao_compound_to_lines_json,
    tao_compound_to_geometry_json,
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

# 組合件分析背景任務結果存儲
# key: session_id → {"status": "running"|"done"|"error", "result": {...}, "error": "..."}
_asm_results = {}


# ═══════════════════════════════════════════════════════════
# 輔助函數
# ═══════════════════════════════════════════════════════════

def _ensure_python_exe():
    """確保 Python 路徑有效"""
    if not os.path.exists(PYTHON_EXE):
        return None
    return PYTHON_EXE


def _normalize_face_ids(face_ids) -> list:
    """
    統一 face_ids 格式為 List[str]。

    接受以下任意格式：
      - List[int]   → ["123", "456"]
      - List[str]   → ["123", "456"]  (already correct)
      - str         → 逗號分隔 "123,456" → ["123", "456"]
      - JSON str    → '["123","456"]' → ["123", "456"]
      - None / ""   → []
    """
    if not face_ids:
        return []
    if isinstance(face_ids, str):
        face_ids = face_ids.strip()
        if face_ids.startswith('['):
            try:
                face_ids = json.loads(face_ids)
            except json.JSONDecodeError:
                return []
        elif face_ids:
            face_ids = [f.strip() for f in face_ids.split(',') if f.strip()]
        else:
            return []
    if isinstance(face_ids, (list, tuple)):
        return [str(fid) for fid in face_ids if fid is not None and str(fid).strip()]
    return []


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

        # 預先佔位（表示載入中），背景執行緒完成後覆蓋
        _step_sessions[session_id] = {
            'stp_path': stp_path,
            'xlsx_path': None,
            'engine': None,
            'face_pmi_map': {},
            'pmi_rows': [],
            'tao_to_data': {},
            'semantic_to_tao': {},
            '_loading': True,
        }

        def _load_step_bg(sid, path):
            progress = ProgressTracker(sid, "step_load")
            try:
                progress.update(1, 1, "正在加載 STEP 幾何體...")
                eng = StepXcafEngine()
                eng.load(path)
                n_f = len(eng.step_id_to_face)
                n_p = len(eng.face_to_part)
                _step_sessions[sid]['engine'] = eng
                _step_sessions[sid]['_loading'] = False
                print(f"[OK] STEP 已加載：{n_f} 個面，{n_p} 個面已映射到零件")
                progress.complete(f"[OK] STEP 加載完成 ({n_f} 個面)")
            except Exception as exc:
                print(f"[ERROR] STEP 背景加載失敗：{exc}")
                _step_sessions[sid]['_loading'] = False
                _step_sessions[sid]['_load_error'] = str(exc)
                progress.error(f"[ERROR] STEP 加載失敗: {exc}")

        threading.Thread(target=_load_step_bg, args=(session_id, stp_path), daemon=True).start()

        return jsonify({
            "ok": True,
            "session_id": session_id,
            "stp_filename": stp_filename,
            "n_faces": 0,
            "message": "[OK] STEP 檔案已上傳，正在背景加載幾何體。請稍後上傳 XLSX 並解析 PMI。"
        }), 200

    except Exception as e:
        print(f"[ERROR] 上傳錯誤：{e}")
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
        print(f"[ERROR] XLSX 上傳錯誤：{e}")
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

        # ─────────────────────────────────────────────────
        # 步驟 1: 解析 XLSX（**先於 STEP 載入**，與原始代碼一致）
        # ─────────────────────────────────────────────────
        progress.update(1, 6, "[PARSING] 正在解析 Excel...")
        face_pmi_map = {}
        pmi_rows = []
        if xlsx_path and os.path.exists(xlsx_path):
            face_pmi_map, pmi_rows = parse_sfa_excel(xlsx_path)

        # ─────────────────────────────────────────────────
        # 步驟 2: XCAF 載入（face map）
        # 注：engine 應該已在上傳 STP 時預先加載到記憶體
        # ─────────────────────────────────────────────────
        progress.update(2, 6, "[LOADING] 正在準備 STEP 數據...")

        # 嘗試從記憶體讀取已加載的 engine
        if session_id in _step_sessions:
            sess_state = _step_sessions[session_id]
            # 若背景載入仍在進行，最多等待 300 秒
            if sess_state.get('_loading'):
                import time as _time
                deadline = _time.time() + 300
                progress.update(2, 6, "[LOADING] 等待背景 STEP 載入完成...")
                while sess_state.get('_loading') and _time.time() < deadline:
                    _time.sleep(0.5)
                if sess_state.get('_loading'):
                    return jsonify({"ok": False, "error": "STEP 載入超時（300 秒）"}), 504
                if sess_state.get('_load_error'):
                    return jsonify({"ok": False, "error": sess_state['_load_error']}), 500

            engine_obj = sess_state.get('engine')
            if engine_obj is None:
                return jsonify({"ok": False, "error": "STEP 引擎未初始化，請重新上傳檔案"}), 500
            print(f"[Reusing] 使用記憶體中已加載的 STEP（{len(engine_obj.step_id_to_face)} 個面）")
        else:
            # 備用：如果未在記憶體中，重新加載
            print(f"[Loading] 重新加載 STEP（未在記憶體中）")
            engine_obj = StepXcafEngine()
            engine_obj.load(stp_path)

        # ─────────────────────────────────────────────────
        # 步驟 3: CSV ASSOCIATION 鏈
        # ─────────────────────────────────────────────────
        progress.update(3, 6, "🔗 正在加載 ASSOCIATION...")
        semantic_to_tao = {}
        tao_to_data = {}
        if xlsx_path and os.path.exists(xlsx_path):
            semantic_to_tao = load_sfa_association(xlsx_path)

        # ─────────────────────────────────────────────────
        # 步驟 3b: 多層備援（只在沒有 PMI 時觸發）
        # ─────────────────────────────────────────────────
        progress.update(4, 6, "🌳 正在建構備援數據...")

        if not pmi_rows:
            # 第一層備援：視覺表單（Visual Sheets）
            if xlsx_path and os.path.exists(xlsx_path):
                from step_core import parse_sfa_visual_sheets
                extra_map, extra_rows = parse_sfa_visual_sheets(xlsx_path)
                if extra_rows:
                    face_pmi_map.update(extra_map)
                    pmi_rows.extend(extra_rows)

            # 第二層備援：ASSOCIATION 中的 annotation
            # 舊版行為：不管 Layer 1 結果，只要 semantic_to_tao 有東西就跑，去重 sid 後把遺漏的 sem 補進 pmi_rows
            if semantic_to_tao:
                existing_sids = {r.get('semantic_id') for r in pmi_rows
                                 if r.get('semantic_id') is not None}
                for i, (sem_id, tao_id) in enumerate(
                    sorted(semantic_to_tao.items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else 0), 1
                ):
                    if sem_id in existing_sids:
                        continue
                    pmi_rows.append({
                        'label': f"annotation_{i:02d} (sem#{sem_id})",
                        'semantic_id': sem_id,
                        'face_ids': [],
                        'nominal_size': None,
                        'it_grade': None,
                    })

            # 第三層備援：幾何特徵樹（最後才調用）
            if not pmi_rows:
                pmi_rows = build_geometry_feature_tree(engine_obj)

        # ─────────────────────────────────────────────────
        # 步驟 4: 全局 tessellated 標註解析
        # ─────────────────────────────────────────────────
        progress.update(5, 6, "[TESSELLATE] 正在解析 Tessellated 標註...")
        tao_to_data = {}
        if xlsx_path:
            tao_to_data, step_sem_to_tao = parse_tessellated_annotations(stp_path, scan_all=True)
            # ── Step 4a：STEP 直接鏈結（最高優先）──
            if step_sem_to_tao:
                semantic_to_tao.update(step_sem_to_tao)

        # ─────────────────────────────────────────────────
        # 步驟 4b: 智能匹配邏輯 (Smart Proximity Hook)
        # 當 CSV 斷鏈時，透過物理距離聯繫「面」與「線」
        # ─────────────────────────────────────────────────
        if pmi_rows and tao_to_data:
            from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
            from OCC.Core.TopoDS import TopoDS_Compound
            from OCC.Core.BRep import BRep_Builder

            # 找出已映射的 TAO ID
            mapped_tao_ids = {semantic_to_tao.get(r['semantic_id']) for r in pmi_rows
                            if r['semantic_id'] and r['semantic_id'] in semantic_to_tao}
            available_taos = {tid: data for tid, data in tao_to_data.items()
                            if tid not in mapped_tao_ids}

            auto_links = 0
            for row in pmi_rows:
                sid = row.get('semantic_id')
                type_code = row.get('type_code')  # None → 類型未識別，不強制預設為 'dis'
                if type_code is None:
                    print(f"  [WARN] PMI '{row.get('label','?')}' 缺少 type_code，跳過近接匹配")
                    continue

                # 如果這條公差沒有線（CSV 沒記或是沒連上）
                if not sid or sid not in semantic_to_tao or not semantic_to_tao.get(sid):
                    target_fids = row.get('face_ids', [])
                    target_faces = [engine_obj.step_id_to_face[fid] for fid in target_fids
                                  if fid in engine_obj.step_id_to_face]

                    if not target_faces or not available_taos:
                        continue

                    # 合併 target_faces 為一個 compound 以計算距離
                    face_comp = TopoDS_Compound()
                    fb = BRep_Builder()
                    fb.MakeCompound(face_comp)
                    for f in target_faces:
                        fb.Add(face_comp, f)

                    # 搜尋最近的 TAO
                    best_tid, min_dist = None, float('inf')

                    for tid, data in available_taos.items():
                        tshape = data.get('shape')
                        if not tshape:
                            continue

                        # 結構密度檢查
                        is_frame = (data.get('tri_count', 0) > 10 or data.get('edge_count', 0) > 40)
                        is_size_item = (type_code in ('dis', 'dia'))

                        if not is_size_item and not is_frame:
                            if type_code not in ('dat',):
                                continue

                        try:
                            dist_tool = BRepExtrema_DistShapeShape(face_comp, tshape)
                            if dist_tool.IsDone():
                                d = dist_tool.Value()
                                if d < min_dist:
                                    min_dist = d
                                    best_tid = tid
                        except Exception:
                            pass

                    # 若距離在極近範圍內（2.0mm）
                    if best_tid and min_dist < 2.0:
                        print(f"  [Hook] {row.get('label','?')} → TAO#{best_tid} (dist={min_dist:.3f})")
                        if sid:
                            semantic_to_tao[sid] = best_tid
                        else:
                            # 為完全無 ID 的項目建立虛擬連結
                            fake_sid = f"auto_pmi_{best_tid}"
                            row['semantic_id'] = fake_sid
                            semantic_to_tao[fake_sid] = best_tid
                        auto_links += 1
                        # 被勾走的 TAO 不再給別人用
                        del available_taos[best_tid]

            if auto_links:
                print(f"智能掛鉤：透過空間距離自動聯繫了 {auto_links} 條導引線")

        # ─────────────────────────────────────────────────
        # 步驟 4c: 後備計畫（如果仍無 PMI）
        # ─────────────────────────────────────────────────
        if not pmi_rows and tao_to_data:
            for tao_id in sorted(tao_to_data.keys(), key=lambda x: int(x) if str(x).isdigit() else 0):
                sid_key = f"unmapped_{tao_id}"
                pmi_rows.append({
                    'label': f"3D annotation #{tao_id}",
                    'semantic_id': sid_key,
                    'face_ids': [],
                    'nominal_size': None,
                    'it_grade': None,
                })
                semantic_to_tao[sid_key] = tao_id

        # 6. 寫入 pmi_item 資料表
        progress.update(6, 6, f"[WRITING] 正在寫入 {len(pmi_rows)} 個 PMI 項目...")
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
                face_ids=json.dumps(_normalize_face_ids(row.get('face_ids', []))),
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
        progress.complete(f"[OK] PMI 解析完成 ({len(engine_obj.step_id_to_face)} 個面，{len(pmi_rows)} 個 PMI 項目)")

        return jsonify({
            "ok": True,
            "session_id": session_id,
            "n_faces": len(engine_obj.step_id_to_face),
            "n_pmi_rows": len(pmi_rows),
            "pmi_rows": pmi_rows
        }), 200

    except Exception as e:
        print(f"[ERROR] 解析 PMI 錯誤：{e}")
        traceback.print_exc()
        progress = ProgressTracker(session_id, "parse_pmi")
        progress.error(f"[ERROR] 解析失敗: {str(e)}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════
# 路由 3: GET /api/step/geometry
# ═══════════════════════════════════════════════════════════

def route_get_geometry():
    """依 face_ids 回傳三角網格 JSON（支持 * 通配符加載所有面）"""
    try:
        session_id = request.args.get('session_id')
        face_ids_str = request.args.get('face_ids', '')
        deflection = float(request.args.get('deflection', 0.3))  # 默認 0.3（更快），可按需調整

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
            face_ids = _normalize_face_ids(face_ids_str)

        # 初始化進度追蹤
        progress = ProgressTracker(session_id, "tessellate")
        progress.update(1, 2, f"[TESSELLATE] 正在三角化 {len(face_ids)} 個面...")

        # 三角化
        geom = tessellate_face_by_step_ids(engine_obj, face_ids, deflection)

        if not geom:
            progress.error("[ERROR] 幾何三角化失敗")
            return jsonify({"ok": False, "error": "幾何三角化失敗"}), 500

        progress.complete("[OK] 三角化完成")

        return jsonify({
            "ok": True,
            "session_id": session_id,
            "face_ids": face_ids,
            "geometry": geom
        }), 200

    except Exception as e:
        print(f"[ERROR] 幾何查詢錯誤：{e}")
        progress = ProgressTracker(session_id, "tessellate")
        progress.error(f"[ERROR] 查詢失敗: {str(e)}")
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
        print(f"[ERROR] PMI 清單查詢錯誤：{e}")
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

        # 顏色對應（先算好，分面時需要用到）
        type_code = target_row.get('type_code', '')
        is_interactive = target_row.get('is_interactive', False)
        is_datum = target_row.get('is_datum', False)

        if is_datum or target_row.get('is_feature_only', False):
            highlight_color = "#00DA26"  # 綠色
        elif is_interactive:
            highlight_color = "#A121F0"  # 紫色
        else:
            highlight_color = "#FFA500"  # 橘色

        # 提取幾何 —— 對齊 test0402 _build_pmi_items 邏輯：
        #   交互公差：face_ids[0] = 特徵面（主色），face_ids[1:] = 基準參考面（綠色）
        #   其餘：全部 face_ids 以主色顯示
        all_face_ids = _normalize_face_ids(target_row.get('face_ids', []))

        if is_interactive and len(all_face_ids) > 1:
            feature_face_ids = all_face_ids[:1]
            datum_face_ids   = all_face_ids[1:]
        else:
            feature_face_ids = all_face_ids
            datum_face_ids   = []

        face_geometry        = tessellate_face_by_step_ids(engine_obj, feature_face_ids) if feature_face_ids else None
        datum_faces_geometry = tessellate_face_by_step_ids(engine_obj, datum_face_ids)   if datum_face_ids   else None

        # 提取 leader lines + PMI 三角形（GDT 框/符號/文字）
        leader_lines = []
        pmi_triangles = None
        tao_id = None
        if target_row.get('semantic_id'):
            tao_id = sess['semantic_to_tao'].get(target_row['semantic_id'])
        if tao_id and tao_id in tao_to_data:
            tao_compound = tao_to_data[tao_id].get('shape')
            if tao_compound:
                tao_geom = tao_compound_to_geometry_json(tao_compound)
                leader_lines = tao_geom.get('leader_lines', [])
                pmi_triangles = tao_geom.get('triangles')

        return jsonify({
            "ok": True,
            "pmi_label": target_row.get('label', ''),
            "face_geometry": face_geometry,
            "datum_faces_geometry": datum_faces_geometry,   # 基準參考面（綠色）
            "leader_lines": leader_lines,
            "pmi_triangles": pmi_triangles,
            "highlight_color": highlight_color,
            "type_code": type_code,
            "is_interactive": is_interactive
        }), 200

    except Exception as e:
        print(f"[ERROR] PMI 高亮查詢錯誤：{e}")
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════
# 路由 5b: POST /api/step/pmi_all_geometry
# 一次回傳全部 PMI 的引線 + 三角形（GDT 框/符號/文字）
# 對齊舊 Tkinter 版「載入 STEP 後全部標註直接顯示」行為
# ═══════════════════════════════════════════════════════════

def route_all_pmi_geometry():
    """一次取全部 PMI 幾何（leader_lines + triangles）給前端一次建好所有標註"""
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id')

        if not session_id:
            return jsonify({"ok": False, "error": "缺少 session_id"}), 400
        if session_id not in _step_sessions:
            return jsonify({"ok": False, "error": "Session 不存在或已過期"}), 404

        sess = _step_sessions[session_id]
        pmi_rows = sess['pmi_rows']
        tao_to_data = sess.get('tao_to_data', {})
        semantic_to_tao = sess.get('semantic_to_tao', {})

        # TAO 可能被多筆 PMI 共用 → 同一 tao_id 的幾何只算一次
        tao_geom_cache = {}
        items = []
        for idx, row in enumerate(pmi_rows):
            sem_id = row.get('semantic_id')
            tao_id = semantic_to_tao.get(sem_id) if sem_id else None
            if not tao_id or tao_id not in tao_to_data:
                continue

            if tao_id not in tao_geom_cache:
                shp = tao_to_data[tao_id].get('shape')
                tao_geom_cache[tao_id] = tao_compound_to_geometry_json(shp) if shp else None

            geom = tao_geom_cache[tao_id]
            if not geom:
                continue

            items.append({
                "row_index":    idx,
                "tao_id":       tao_id,
                "label":        row.get('label', ''),
                "type_code":    row.get('type_code', ''),
                "is_datum":     row.get('is_datum', False),
                "leader_lines": geom.get('leader_lines', []),
                "triangles":    geom.get('triangles'),
            })

        return jsonify({"ok": True, "n_items": len(items), "items": items}), 200

    except Exception as e:
        print(f"[ERROR] 全部 PMI 幾何查詢錯誤：{e}")
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════
# 路由 6: POST /api/step/asm_contact
# ═══════════════════════════════════════════════════════════

def _asm_worker_task(session_id: str, stp_path: str, out_json: str, python_exe: str):
    """組合件分析背景執行緒（不阻塞 Flask worker）"""
    import time
    progress = ProgressTracker(session_id, "asm_contact")
    try:
        progress.update(2, 3, "執行接觸分析子進程...")
        proc = subprocess.Popen(
            [python_exe, ASM_WORKER_PATH, stp_path, out_json],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding='utf-8', errors='replace'
        )

        deadline = time.time() + ASM_WORKER_TIMEOUT
        for line in iter(proc.stdout.readline, ''):
            print(line, end='', flush=True)
            if time.time() > deadline:
                proc.kill()
                try:
                    os.unlink(out_json)
                except OSError:
                    pass
                msg = f"組合件分析超過 {ASM_WORKER_TIMEOUT} 秒"
                progress.error(f"[ERROR] {msg}")
                _asm_results[session_id] = {"status": "error", "error": msg}
                return

        proc.stdout.close()
        proc.wait()

        # 讀取結果
        progress.update(3, 3, "處理分析結果...")
        result = {"status": "error", "msg": "no output", "contacts": [], "solids": [], "n_parts": 0}
        if os.path.exists(out_json):
            with open(out_json, 'r', encoding='utf-8') as f:
                result = json.load(f)
            try:
                os.unlink(out_json)
            except OSError:
                pass

        # 寫入 MySQL（已合併的接觸群組）
        if result.get('status') == 'ok':
            db_session = Session()
            try:
                for contact in result.get('contacts', []):
                    contact_obj = AssemblyContact(
                        session_id=session_id,
                        comp1_name=contact.get('comp1', ''),
                        comp2_name=contact.get('comp2', ''),
                        contact_type=contact.get('ctype', ''),
                        face_pairs_json=json.dumps(contact.get('face_pairs', [])),
                        bbox1_json=json.dumps(contact.get('group_bbox1')),
                        bbox2_json=json.dumps(contact.get('group_bbox2'))
                    )
                    db_session.add(contact_obj)
                db_session.commit()
            finally:
                db_session.close()

        # 合併 face_to_part 到 XCAF 引擎
        asm_face_to_part = result.get('face_to_part', {})
        if asm_face_to_part and session_id in _step_sessions:
            engine_obj = _step_sessions[session_id].get('engine')
            if engine_obj:
                for fid, pname in asm_face_to_part.items():
                    if fid not in engine_obj.face_to_part:
                        engine_obj.face_to_part[fid] = pname
                print(f"[OK] 合併 asm_worker face_to_part：共 {len(engine_obj.face_to_part)} 個映射")

        n_contacts = len(result.get('contacts', []))
        n_parts = result.get('n_parts', 0)
        progress.complete(f"[OK] 接觸分析完成 ({n_parts} 個部件，{n_contacts} 個接觸)")

        _asm_results[session_id] = {
            "status": "done",
            "result": {
                "ok": result.get('status') == 'ok',
                "session_id": session_id,
                "n_contacts": n_contacts,
                "n_parts": n_parts,
                "contacts": result.get('contacts', []),
                "solids": result.get('solids', []),
                "face_to_part": asm_face_to_part,
                "diagnostics": result.get('diagnostics'),
                "stype_counts": result.get('stype_counts'),
                "n_total_faces": result.get('n_total_faces', 0),
            }
        }

    except Exception as e:
        msg = str(e)
        print(f"[ERROR] 組合件分析背景錯誤：{e}")
        traceback.print_exc()
        progress.error(f"[ERROR] 分析失敗: {msg}")
        _asm_results[session_id] = {"status": "error", "error": msg}


def route_run_asm_worker():
    """啟動組合件接觸分析（非阻塞，背景執行緒）"""
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
            progress.error("[ERROR] STEP 檔案不存在")
            return jsonify({"ok": False, "error": "STEP 檔案不存在"}), 404

        python_exe = _ensure_python_exe() or "python"
        tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        tmp.close()
        out_json = tmp.name

        # 標記為執行中，清除上次結果
        _asm_results[session_id] = {"status": "running"}

        # 在背景執行緒執行，立即返回
        t = threading.Thread(
            target=_asm_worker_task,
            args=(session_id, stp_path, out_json, python_exe),
            daemon=True
        )
        t.start()

        return jsonify({
            "ok": True,
            "status": "started",
            "session_id": session_id,
            "poll_url": f"/api/step/asm_result?session_id={session_id}",
            "message": "組合件分析已在背景啟動，請輪詢 poll_url 取得結果"
        }), 202

    except Exception as e:
        print(f"[ERROR] 啟動組合件分析失敗：{e}")
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


def route_get_asm_result():
    """輪詢組合件分析結果（配合背景執行緒版 route_run_asm_worker）"""
    session_id = request.args.get('session_id')
    if not session_id:
        return jsonify({"ok": False, "error": "缺少 session_id"}), 400

    state = _asm_results.get(session_id)
    if state is None:
        return jsonify({"ok": False, "status": "not_found",
                        "error": "尚未啟動分析或 session 不存在"}), 404

    if state["status"] == "running":
        return jsonify({"ok": True, "status": "running",
                        "session_id": session_id}), 202

    if state["status"] == "error":
        return jsonify({"ok": False, "status": "error",
                        "error": state.get("error", "未知錯誤")}), 500

    # done
    res = state["result"]
    return jsonify({"ok": True, "status": "done", **res}), 200


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
        print(f"[ERROR] 6-DOF 計算錯誤：{e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ═══════════════════════════════════════════════════════════
# 路由 8: POST /api/step/export_csv
# ═══════════════════════════════════════════════════════════

def route_export_step_csv():
    """
    導出 PMI BOM CSV（欄位完全對齊舊 Tkinter 版 step_pmi_3d_viewer.py::_export_csv）。
    11 欄：公差代號/名稱-幾何類型/數量-面數/幾何參數/公差標註(PMI)/公稱尺寸/IT等級/公差數值/特徵代號/Face ID/是否勾選
    """
    try:
        data = request.get_json() or {}
        session_id = data.get('session_id')
        export_mode = data.get('mode', 'pmi')
        checked_indices = set(data.get('checked_indices') or [])

        if not session_id:
            return jsonify({"ok": False, "error": "缺少 session_id"}), 400
        if session_id not in _step_sessions:
            return jsonify({"ok": False, "error": "Session 不存在或已過期"}), 404

        sess = _step_sessions[session_id]
        pmi_rows = sess['pmi_rows']
        engine_obj = sess['engine']

        from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
        from OCC.Core.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
        from OCC.Core.TopAbs import TopAbs_REVERSED

        part_prefix = os.path.splitext(os.path.basename(sess.get('stp_path', 'X')))[0]
        if not part_prefix.strip():
            part_prefix = "1"

        # Step 1: 每個 face 的幾何型別 + 參數 + 分類符號（P/S/H/F）
        face_info = {}
        for fid, face in engine_obj.step_id_to_face.items():
            try:
                surf = BRepAdaptor_Surface(face)
                stype = surf.GetType()
                g_type, params, sym = 'OTHER', '-', 'F'
                if stype == GeomAbs_Plane:
                    g_type, params, sym = 'PLANE', 'ideal', 'P'
                elif stype == GeomAbs_Cylinder:
                    r = surf.Cylinder().Radius()
                    sym = 'H' if (face.Orientation() == TopAbs_REVERSED) else 'S'
                    g_type, params = 'CYLINDRICAL_SURFACE', f"R={r:.3f} (D={r*2:.3f})"
                face_info[str(fid)] = {'type': g_type, 'params': params, 'sym': sym}
            except Exception:
                face_info[str(fid)] = {'type': 'ERROR', 'params': '-', 'sym': 'F'}

        # Step 2: 只為 PMI 使用的 Face 分配特徵代號（P/S/H 分組，按 Face ID 連續編號）
        used_fids = set()
        for row_info in pmi_rows:
            for fid in row_info.get('face_ids', []):
                used_fids.add(str(fid))

        used_faces_by_type = {'P': [], 'S': [], 'H': [], 'F': []}
        for fid in sorted(used_fids, key=lambda x: int(x) if x.isdigit() else 0):
            sym = face_info.get(fid, {}).get('sym', 'F')
            used_faces_by_type.setdefault(sym, []).append(fid)

        fid_to_feat = {}
        for sym_type in ['P', 'S', 'H', 'F']:
            for i, fid in enumerate(used_faces_by_type[sym_type], 1):
                fid_to_feat[fid] = f"{part_prefix}-{sym_type}-{i}"

        # Step 3: 逐列輸出（不濾掉未勾選；勾選狀態反映在「是否勾選」欄）
        csv_rows = []
        type_counters = defaultdict(int)
        for idx, row_info in enumerate(pmi_rows):
            label = row_info.get('label', '')
            fids = [str(f) for f in row_info.get('face_ids', [])]

            t_code = (row_info.get('type_code') or 'tol').upper()
            type_counters[t_code] += 1
            code = f"{part_prefix}-{t_code}{type_counters[t_code]}"

            g = face_info.get(fids[0] if fids else None, {'type': '-', 'params': '-'})

            feats = [fid_to_feat.get(f, '未知特徵') for f in fids]

            csv_rows.append({
                "公差代號":      code,
                "名稱/幾何類型": g['type'],
                "數量/面數":     len(fids),
                "幾何參數":      g['params'],
                "公差標註(PMI)": label,
                "公稱尺寸":      row_info.get('nominal_size') or '',
                "IT等級":        row_info.get('it_grade') or '',
                "公差數值":      row_info.get('tolerance_value') or '',
                "特徵代號":      ", ".join(feats),
                "Face ID":       ", ".join(fids),
                "是否勾選":      "✓" if (not checked_indices or idx in checked_indices) else "",
            })

        # Step 4: 輸出 CSV，UTF-8 + BOM（Excel 正確辨識編碼）
        df = pd.DataFrame(csv_rows)
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        csv_content = '\ufeff' + csv_buffer.getvalue()   # 手動加 BOM

        # 存一份到 MySQL
        try:
            db_session = Session()
            export_record = PmiExportRecord(
                session_id=session_id,
                export_mode=export_mode,
                row_count=len(csv_rows),
                csv_content=csv_content
            )
            db_session.add(export_record)
            db_session.commit()
            db_session.close()
        except Exception as db_err:
            print(f"[WARN] CSV 寫入 MySQL 失敗（不影響下載）：{db_err}")

        # 回傳給前端下載
        return Response(
            csv_content.encode('utf-8'),
            mimetype="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="SFA_PMI_BOM_Report_{session_id[:8]}.csv"'
            }
        ), 200

    except Exception as e:
        print(f"[ERROR] CSV 導出錯誤：{e}")
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
            # 'Connection' 是 hop-by-hop header，WSGI 規範禁止應用設定（PEP 3333）
            # waitress 會直接 raise AssertionError，故移除
        }
    )


def route_get_face_to_part():
    """查詢 face_id → part_name 映射"""
    session_id = request.args.get('session_id')
    if not session_id:
        return jsonify({"ok": False, "error": "缺少 session_id"}), 400

    sess = _step_sessions.get(session_id)
    if not sess or not sess.get('engine'):
        return jsonify({"ok": False, "error": "Session 不存在或未載入 STEP"}), 404

    engine_obj = sess['engine']
    face_to_part = engine_obj.face_to_part

    # 如果指定了 face_ids 參數，只回傳指定的面
    face_ids = request.args.get('face_ids')
    if face_ids:
        ids = [fid.strip() for fid in face_ids.split(',')]
        filtered = {fid: face_to_part.get(fid) for fid in ids}
        return jsonify({
            "ok": True,
            "session_id": session_id,
            "face_to_part": filtered,
            "n_mapped": sum(1 for v in filtered.values() if v is not None),
            "n_total": len(face_to_part)
        }), 200

    return jsonify({
        "ok": True,
        "session_id": session_id,
        "face_to_part": face_to_part,
        "n_mapped": len(face_to_part),
        "n_faces": len(engine_obj.step_id_to_face)
    }), 200


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
