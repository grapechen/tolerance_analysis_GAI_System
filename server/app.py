import os

import socket
import json
import re
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from sqlalchemy import and_
from tables import Session, ISOTolerance, ShaftTolerance, HoleTolerance
from middleware import rate_limit, api_limiter
from logger import app_logger
from recommendation import smart_fit, machine_check
import rag_server

app = Flask(__name__)
app.json.ensure_ascii = False
CORS(app, resources={r'/*': {'origins': '*'}})

local_ip = socket.gethostbyname(socket.gethostname())
app_logger.info('ISO 286 基本查詢系統啟動')
app_logger.info(f'LAN IP: {local_ip}')
app_logger.info('Build: 2025-08-30')

@app.get("/recommender")
def recommender_page():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, '../client/recommender.html')
    return open(file_path, encoding='utf-8').read()

@app.route("/")
def index():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    client_dir = os.path.join(base_dir, '../client')
    return send_from_directory(client_dir, 'index.html')

@app.route("/<path:filename>")
def serve_static(filename):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    client_dir = os.path.join(base_dir, '../client')
    return send_from_directory(client_dir, filename)

@app.route('/api/machines', methods=['GET'])
def get_machines():
    """回傳機台與能力資料給前端"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, 'data', 'machines_data.json')
    if not os.path.exists(file_path):
        app_logger.error(f"找不到機台資料檔案: {file_path}")
        return jsonify({"ok": False, "msg": "找不到機台資料"}), 404
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        app_logger.error(f"解析機台資料失敗: {e}")
        return jsonify({"ok": False, "msg": f"解析資料失敗: {str(e)}"}), 500

# Keep old endpoint for compatibility if needed, but redirect or reuse
@app.get("/lookup/tolerance")
def lookup_tolerance_redirect():
    return index()

@app.post("/recommend/it")
def recommend_it():
    """
    請求：
      {
        "size_mm": 25.0,               # 名目尺寸
        "target_tol_μm": 16,           # 期望公差(μm)
        "prefer_it_floor": "IT5",      # (選) 下限
        "prefer_it_ceil":  "IT10"      # (選) 上限
      }
    回應：建議 IT 等級 + 公差值
    """
    p = request.get_json(force=True)
    try:
        size = float(p["size_mm"])
        target_tol = float(p["target_tol_μm"])
    except Exception:
        return jsonify({"ok": False, "msg": "缺少或不合法的 size_mm / target_tol_μm"}), 400

    prefer_floor = p.get("prefer_it_floor")
    prefer_ceil  = p.get("prefer_it_ceil")

    s = Session()
    try:
        rows = s.query(ISOTolerance).filter(
            and_(ISOTolerance.size_from_mm <= size,
                 ISOTolerance.size_to_mm   >= size)
        ).all()
        if not rows:
            return jsonify({"ok": False, "msg": "指定尺寸無對應 ISO286 區間"}), 404

        def it_key(it_txt: str) -> int:
            k = it_txt.upper().replace("IT","")
            try:
                return int(k)
            except ValueError:
                return int(float(k))

        if prefer_floor:
            floor_n = it_key(prefer_floor)
            rows = [r for r in rows if it_key(r.it_grade) >= floor_n]
        if prefer_ceil:
            ceil_n = it_key(prefer_ceil)
            rows = [r for r in rows if it_key(r.it_grade) <= ceil_n]

        if not rows:
            return jsonify({"ok": False, "msg": "條件過嚴，沒有可用的 IT 等級"}), 400

        best = min(rows, key=lambda r: abs(float(r.tolerance_um) - target_tol))
        return jsonify({
            "ok": True,
            "size_mm": size,
            "target_tol_μm": target_tol,
            "recommended_it": best.it_grade,
            "tolerance_μm": float(best.tolerance_um),
            "range_mm": [float(best.size_from_mm), float(best.size_to_mm)]
        })
    finally:
        s.close()

@app.post("/api/lookup/tolerance")
@rate_limit(api_limiter)
def api_lookup_tolerance():
    """
    請求：
      { "size_mm": 25.0, "it_grade": "IT7" }
    回應：
      { ok, size_mm, it_grade, tolerance_μm, range_mm }
    """
    p = request.get_json(force=True)
    # 參數驗證
    try:
        size = float(p["size_mm"])
        it_grade = str(p["it_grade"]).upper()
    except Exception as e:
        app_logger.warning(f"參數驗證失敗: {e}")
        return jsonify({"ok": False, "msg": "缺少或不合法的 size_mm / it_grade"}), 400

    s = Session()
    try:
        row = s.query(ISOTolerance).filter(
            and_(ISOTolerance.size_from_mm <= size,
                 ISOTolerance.size_to_mm   >= size,
                 ISOTolerance.it_grade     == it_grade)
        ).first()

        if not row:
            return jsonify({"ok": False, "msg": "找不到對應的資料（請確認 Excel 已匯入，或尺寸/IT 等級是否存在）"}), 404

        return jsonify({
            "ok": True,
            "size_mm": size,
            "it_grade": row.it_grade,
            "tolerance_μm": float(row.tolerance_um),
            "range_mm": [float(row.size_from_mm), float(row.size_to_mm)]
        })
    finally:
        s.close()

@app.post("/api/lookup/shaft")
def api_lookup_shaft():
    """
    請求：{ "size_mm": 25.0, "tolerance_code": "h", "it_grade": "IT7" }
    回應：{ ok, size_mm, tolerance_code, it_grade, upper_dev_um, lower_dev_um, range_mm }
    """
    p = request.get_json(force=True)
    try:
        size = float(p["size_mm"])
        code = str(p["tolerance_code"]).lower()
        it_grade = str(p["it_grade"]).upper()
    except Exception:
        return jsonify({"ok": False, "msg": "缺少或不合法的參數"}), 400

    s = Session()
    try:
        row = s.query(ShaftTolerance).filter(
            and_(ShaftTolerance.size_from_mm <= size,
                 ShaftTolerance.size_to_mm >= size,
                 ShaftTolerance.tolerance_code == code,
                 ShaftTolerance.it_grade == it_grade)
        ).first()

        if not row:
            return jsonify({"ok": False, "msg": "找不到對應的軸公差資料"}), 404

        return jsonify({
            "ok": True,
            "size_mm": size,
            "tolerance_code": row.tolerance_code,
            "it_grade": row.it_grade,
            "upper_dev_um": float(row.upper_dev_um) if row.upper_dev_um is not None else None,
            "lower_dev_um": float(row.lower_dev_um) if row.lower_dev_um is not None else None,
            "range_mm": [float(row.size_from_mm), float(row.size_to_mm)]
        })
    finally:
        s.close()


@app.post("/api/lookup/hole")
def api_lookup_hole():
    """
    請求：{ "size_mm": 25.0, "tolerance_code": "H", "it_grade": "IT7" }
    回應：{ ok, size_mm, tolerance_code, it_grade, upper_dev_um, lower_dev_um, range_mm }
    """
    p = request.get_json(force=True)
    try:
        size = float(p["size_mm"])
        code = str(p["tolerance_code"]).upper()
        it_grade = str(p["it_grade"]).upper()
    except Exception:
        return jsonify({"ok": False, "msg": "缺少或不合法的參數"}), 400

    s = Session()
    try:
        row = s.query(HoleTolerance).filter(
            and_(HoleTolerance.size_from_mm <= size,
                 HoleTolerance.size_to_mm >= size,
                 HoleTolerance.tolerance_code == code,
                 HoleTolerance.it_grade == it_grade)
        ).first()

        if not row:
            return jsonify({"ok": False, "msg": "找不到對應的孔公差資料"}), 404

        return jsonify({
            "ok": True,
            "size_mm": size,
            "tolerance_code": row.tolerance_code,
            "it_grade": row.it_grade,
            "upper_dev_um": float(row.upper_dev_um) if row.upper_dev_um is not None else None,
            "lower_dev_um": float(row.lower_dev_um) if row.lower_dev_um is not None else None,
            "range_mm": [float(row.size_from_mm), float(row.size_to_mm)]
        })
    finally:
        s.close()


@app.post("/api/analyze/fit")
def api_analyze_fit():
    """
    配合分析
    請求：{ "size_mm": 25.0, "hole_tolerance": "H7", "shaft_tolerance": "h6" }
    回應：配合類型、餘隙/過盈範圍等
    """
    p = request.get_json(force=True)
    try:
        size = float(p["size_mm"])
        hole_str = str(p["hole_tolerance"]).upper()
        shaft_str = str(p["shaft_tolerance"]).lower()
    except Exception:
        return jsonify({"ok": False, "msg": "缺少或不合法的參數"}), 400

    # 解析孔和軸的代號與 IT 等級
    hole_match = re.match(r'([A-Z]+)(\d+)', hole_str)
    shaft_match = re.match(r'([a-z]+)(\d+)', shaft_str)
    
    if not hole_match or not shaft_match:
        return jsonify({"ok": False, "msg": "公差格式錯誤（孔應為大寫如 H7，軸應為小寫如 h6）"}), 400

    if hole_match and shaft_match:
        hole_code = hole_match.group(1)
        hole_it = "IT" + hole_match.group(2)
        shaft_code = shaft_match.group(1)
        shaft_it = "IT" + shaft_match.group(2)
    else:
        return jsonify({"ok": False, "msg": "無法解析公差等級"}), 400

    s = Session()
    try:
        # 查詢孔公差
        hole = s.query(HoleTolerance).filter(
            and_(HoleTolerance.size_from_mm <= size,
                 HoleTolerance.size_to_mm >= size,
                 HoleTolerance.tolerance_code == hole_code,
                 HoleTolerance.it_grade == hole_it)
        ).first()

        # 查詢軸公差
        shaft = s.query(ShaftTolerance).filter(
            and_(ShaftTolerance.size_from_mm <= size,
                 ShaftTolerance.size_to_mm >= size,
                 ShaftTolerance.tolerance_code == shaft_code,
                 ShaftTolerance.it_grade == shaft_it)
        ).first()

        if not hole or not shaft:
            return jsonify({"ok": False, "msg": "找不到對應的孔或軸公差資料"}), 404

        # 計算配合
        hole_max = float(hole.upper_dev_um) if hole.upper_dev_um is not None else 0
        hole_min = float(hole.lower_dev_um) if hole.lower_dev_um is not None else 0
        shaft_max = float(shaft.upper_dev_um) if shaft.upper_dev_um is not None else 0
        shaft_min = float(shaft.lower_dev_um) if shaft.lower_dev_um is not None else 0

        # 最大間隙 = 孔最大 - 軸最小
        max_clearance = hole_max - shaft_min
        # 最小間隙 = 孔最小 - 軸最大
        min_clearance = hole_min - shaft_max

        # 判斷配合類型
        if min_clearance >= 0:
            fit_type = "留隙配合"
        elif max_clearance <= 0:
            fit_type = "過盈配合"
        else:
            fit_type = "過渡配合"

        return jsonify({
            "ok": True,
            "size_mm": size,
            "hole": {"公差類型": hole_code + hole_it.replace("IT", ""), "上偏差(um)": hole_max, "下偏差(um)": hole_min},
            "shaft": {"公差類型": shaft_code + shaft_it.replace("IT", ""), "上偏差(um)": shaft_max, "下偏差(um)": shaft_min},
            "fit_type": fit_type,
            "max_clearance_um": float(f"{max_clearance:.3f}"),
            "min_clearance_um": float(f"{min_clearance:.3f}"),
            "note": "正值為餘隙，負值為過盈"
        })
    finally:
        s.close()





@app.post("/api/recommend/smart_fit")
def api_recommend_smart_fit():
    """
    智能選配 API
    請求：{ "keywords": ["定位", "高速"] }
    回應：[ ... matching fits ... ]
    """
    p = request.get_json(force=True)
    keywords = p.get("keywords", [])
    
    if not keywords:
        return jsonify({"ok": False, "msg": "請提供 keywords 列表"}), 400

    results = smart_fit.search_fits(keywords)
    return jsonify({
        "ok": True,
        "results": results,
        "count": len(results)
    })

@app.get("/api/keywords")
def api_get_keywords():
    """
    取得所有預設的關鍵字供前端產生下拉選單
    包含 smart_fit 與 machine_check 中出現的常見應用場景
    """
    # 從 smart_fit 中取得已知的 tags
    try:
        tags = smart_fit.get_all_tags()
    except Exception as e:
        app_logger.error(f"Error getting tags from smart_fit: {e}")
        tags = ["定位", "高速", "滑動", "轉動", "裝拆", "重壓"]
        
    # 我們也額外加上 machine_check.csv 中常出現的加工關鍵字
    machine_keywords = ["孔加工", "平面加工", "重切削", "多面一次加工"]
    
    # 聯集並排序
    all_keywords = sorted(list(set(tags + machine_keywords)))
    
    return jsonify({
        "ok": True,
        "keywords": all_keywords
    })

@app.post("/api/recommend/machine_check")
def api_recommend_machine_check():
    """
    機台能力驗證 API
    請求：{ "diameter": 50.0, "safety_factor": 3.0 }
    回應：{ ok, target_repeat_mm, machines: [...] }
    """
    p = request.get_json(force=True)
    try:
        diameter = float(p.get("diameter", 0))
        safety = float(p.get("safety_factor", 3.0))
    except (ValueError, TypeError):
        return jsonify({"ok": False, "msg": "無效的數值參數"}), 400

    if diameter <= 0:
        return jsonify({"ok": False, "msg": "直徑必須大於 0"}), 400

    result = machine_check.find_capable_machines(diameter, safety)
    
    return jsonify({
        "ok": True,
        "data": result
    })

@app.post("/api/chat")
def api_chat():
    """
    AI 諮詢 API (RAG)
    請求：{ "message": "25mm H7/g6 的配合情形?" }
    回應：{ "ok": true, "reply": "..." }
    """
    p = request.get_json(force=True)
    user_input = p.get("message", "")
    
    if not user_input:
        return jsonify({"ok": False, "msg": "請輸入訊息"}), 400

    # 使用 rag_server 處理
    try:
        reply = rag_server.get_rag_response(user_input)
        return jsonify({"ok": True, "reply": reply})
    except Exception as e:
        app_logger.error(f"Chat Error: {e}")
        return jsonify({"ok": False, "msg": str(e)}), 500

@app.post("/api/matchmaking")
def api_matchmaking():
    """
    製程與機台媒合總流程 API
    對應架構圖：
    1. 輸入功能 & 加工直徑
    2. 搜尋知識庫並選擇適合之公差配合
    3. 公差配合詳細數值
    4. 對應加工能力符合機台
    5. 適合應用場景
    """
    p = request.get_json(force=True)
    keywords = p.get("keywords", [])
    diameter = p.get("diameter")
    safety_factor = p.get("safety_factor", 1.0)

    if not keywords or not diameter:
        return jsonify({"ok": False, "msg": "請提供 keywords(功能) 和 diameter(直徑)"}), 400

    try:
        diameter = float(diameter)
        safety_factor = float(safety_factor)
    except ValueError:
        return jsonify({"ok": False, "msg": "diameter 和 safety_factor 必須是數字"}), 400

    # 1. 搜尋知識庫並選擇適合之公差配合 (從 ANSI Fits CSV)
    fits = smart_fit.search_fits(keywords)
    if not fits:
        return jsonify({"ok": False, "msg": "找不到對應的公差配合"}), 404
        
    best_fit = fits[0]  # 取最符合的第一筆
    hole_str = best_fit.get("hole", "")
    shaft_str = best_fit.get("shaft", "")

    # 2. 公差配合詳細數值 (查 ISO SQL Table)
    s = Session()
    fit_details = {}
    try:
        hole_match = re.match(r'([A-Z]+)(\d+)', hole_str)
        shaft_match = re.match(r'([a-z]+)(\d+)', shaft_str)
        
        if hole_match and shaft_match:
            hole_code, hole_it = hole_match.group(1), "IT" + hole_match.group(2)
            shaft_code, shaft_it = shaft_match.group(1), "IT" + shaft_match.group(2)

            hole = s.query(HoleTolerance).filter(
                and_(HoleTolerance.size_from_mm <= diameter, HoleTolerance.size_to_mm >= diameter,
                     HoleTolerance.tolerance_code == hole_code, HoleTolerance.it_grade == hole_it)
            ).first()

            shaft = s.query(ShaftTolerance).filter(
                and_(ShaftTolerance.size_from_mm <= diameter, ShaftTolerance.size_to_mm >= diameter,
                     ShaftTolerance.tolerance_code == shaft_code, ShaftTolerance.it_grade == shaft_it)
            ).first()

            if hole and shaft:
                h_max = float(hole.upper_dev_um) if hole.upper_dev_um is not None else 0
                h_min = float(hole.lower_dev_um) if hole.lower_dev_um is not None else 0
                s_max = float(shaft.upper_dev_um) if shaft.upper_dev_um is not None else 0
                s_min = float(shaft.lower_dev_um) if shaft.lower_dev_um is not None else 0

                max_clearance = h_max - s_min
                min_clearance = h_min - s_max

                fit_type = "過渡配合"
                if min_clearance >= 0:
                    fit_type = "留隙配合"
                elif max_clearance <= 0:
                    fit_type = "過盈配合"

                fit_details = {
                    "fit_type": fit_type,
                    "hole": {"code": hole_str, "upper_um": h_max, "lower_um": h_min},
                    "shaft": {"code": shaft_str, "upper_um": s_max, "lower_um": s_min},
                    "max_clearance_um": float(f"{max_clearance:.3f}"),
                    "min_clearance_um": float(f"{min_clearance:.3f}")
                }
    finally:
        s.close()

    # 3. 對應加工能力符合機台 (Machine CSV)
    machine_res = machine_check.find_capable_machines(diameter, safety_factor=safety_factor, keywords=keywords)
    
    # 4. 適合應用場景
    application_scenario = {
        "function": best_fit.get("function", ""),
        "note": best_fit.get("note", ""),
        "type": best_fit.get("type", "")
    }

    return jsonify({
        "ok": True,
        "input": {"diameter": diameter, "keywords": keywords},
        "step1_selected_fit": best_fit,
        "step2_fit_details": fit_details,
        "step3_capable_machines": machine_res.get("machines", []),
        "step4_application_scenario": application_scenario
    })

if __name__ == '__main__':
    # 與你原本一樣在 7010 埠啟動
    app.run(host='0.0.0.0', port=7010, debug=True)
