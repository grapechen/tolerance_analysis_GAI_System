import sys
import os

import io
import re
import logging
import yaml
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
import ollama
from dotenv import load_dotenv

# Internal imports
try:
    from rag_engine import ask_rag_engine
except ImportError:
    ask_rag_engine = None

try:
    import graph_rag
except ImportError:
    graph_rag = None

# Set encoding for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 載入環境變數
load_dotenv()

app = Flask(__name__)
CORS(app)  # 允許來自 7010 的前端跨網域請求 (CORS)

logger = logging.getLogger(__name__)

# Frontend moved to templates/index.html and static/

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}

def get_available_models():
    config = load_config()
    cloud_model_prefixes = config.get("cloud_model_prefixes", [])
    manual_cloud_models = config.get("manual_cloud_models", [])
    if not isinstance(manual_cloud_models, list):
        manual_cloud_models = []

    try:
        client = ollama.Client(host="http://localhost:11434")
        models_info = client.list()
        model_names = []
        
        # models_info.models is expected to be a list
        raw_models = getattr(models_info, "models", [])
        if not raw_models:
            raw_models = []
            
        for m in raw_models:
            m_name = None
            if hasattr(m, "model"):
                m_name = getattr(m, "model")
            elif hasattr(m, "name"):
                m_name = getattr(m, "name")
            elif isinstance(m, dict):
                m_name = m.get("name") or m.get("model")
            
            if m_name:
                model_names.append(str(m_name))
    except Exception as e:
        print(f"[ERROR] Fetching models: {e}")
        model_names = []

    def is_cloud_model(name: str) -> bool:
        name_lower = name.lower()
        if "-cloud" in name_lower or ":cloud" in name_lower:
            return True
        for p in (cloud_model_prefixes or []):
            if name_lower.startswith(str(p)):
                return True
        return False

    def model_sort_key(name: str):
        return (0 if is_cloud_model(name) else 1, name.lower())

    final_model_dict = {}
    
    all_potential_models = list(model_names)
    for manual_ext in manual_cloud_models:
        all_potential_models.append(str(manual_ext))
    
    for m in all_potential_models:
        if not m or not isinstance(m, str):
            continue
        m_lower = str(m.lower())
        if "gemini" in m_lower:
            continue
        
        match = re.match(r"^([a-z\-]+)(?:[\d\.\-v]*)(?:[:\-].*)?$", m_lower)
        if match:
            base_family = str(match.group(1)).strip("-")
        else:
            base_family = m_lower.split(":")[0]
        
        # Family normalization
        for fam in ["deepseek", "qwen", "glm", "gpt"]:
            if str(base_family).startswith(fam):
                base_family = fam
                break

        if base_family not in final_model_dict:
            final_model_dict[str(base_family)] = m
        else:
            curr = str(final_model_dict.get(str(base_family)))
            curr_lower = curr.lower()
            m_curr_cloud = "cloud" in m_lower
            curr_is_cloud = "cloud" in curr_lower
            
            if (m_curr_cloud and not curr_is_cloud) or \
               (m_curr_cloud == curr_is_cloud and len(m) > len(curr)):
                final_model_dict[base_family] = m

    sorted_models = sorted(final_model_dict.values(), key=model_sort_key)
    return sorted_models if sorted_models else ["llama3.1:8b"]

@app.route("/")
def home():
    model_names = get_available_models()
    config = load_config()
    preferred_cloud = config.get("preferred_cloud_models", [])
    if not isinstance(preferred_cloud, list):
        preferred_cloud = []
    
    current_model = next((m for m in preferred_cloud if m in model_names), None)
    if not current_model:
        current_model = next((m for m in model_names if m.startswith(("gemma3:", "llama3"))), model_names[0])

    return render_template(
        "index.html", models=model_names, current_model=current_model
    )

@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(force=True)
    user_msg = data.get("message", "")
    model_name = data.get("model", "llama3.1:8b")
    history = data.get("history", [])

    if not user_msg:
        return jsonify({"reply": "請輸入訊息"}), 400

    model_lower = model_name.lower()
    is_cloud = (
        "-cloud" in model_lower
        or ":cloud" in model_lower
        or model_lower.startswith("gpt-oss")
        or model_lower.startswith("qwen3-vl")
        or model_lower.startswith("qwen3-v1")
        or model_lower.startswith("ministral-3")
        or model_lower.startswith("qwen3-coder")
        or model_lower.startswith("glm-4")
        or model_lower.startswith("deepseek")
        or model_lower.startswith("minimax")
    )

    CLOUD_OLLAMA_URL = "http://localhost:11434"
    base_url = CLOUD_OLLAMA_URL if is_cloud else "http://localhost:11434"

    print(f"[INFO] 接收到對話請求 - 訊息: '{user_msg}', 模型: {model_name}, 網址: {base_url}")

    if ask_rag_engine is None:
        return jsonify({"reply": "[ERROR] 系統模組載入失敗 (rag_engine)，請聯絡管理員。", "intent": {}})

    try:
        reply, bom_intent = ask_rag_engine(
            user_msg, model_name=model_name, base_url=base_url, history=history
        )
    except ConnectionError as ce:
        logger.error(f"Ollama connection failed: {ce}")
        reply = "[ERROR] 無法連線至 AI 引擎 (Ollama)，請檢查服務是否啟動。"
        bom_intent = {}
    except Exception as e:
        logger.exception(f"Unexpected error in /api/chat: {e}")
        reply = f"[ERROR] 處理請求時發生未預期的錯誤: {str(e)}"
        bom_intent = {}

    return jsonify({"reply": reply, "intent": bom_intent})

@app.route("/api/machines", methods=["GET"])
def get_machines():
    import json
    file_path = os.path.join(os.path.dirname(__file__), "data", "machines_data.json")
    if not os.path.exists(file_path):
        return jsonify({"ok": False, "msg": "找不到機台資料"}), 404
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"ok": False, "msg": f"解析資料失敗: {str(e)}"}), 500

@app.route("/api/export_tolerance_excel", methods=["POST"])
def export_tolerance_excel():
    data = request.get_json()
    path_data = data.get("pathData", [])
    rows = []
    for item in path_data:
        if item.get("type") == "feature":
            rows.append({
                "路徑代碼": item.get("name"),
                "數值(平移、旋轉、公差值)": item.get("val", 0.01),
                "偏差值(公差帶偏移值)": item.get("bias", 0),
                "角度公差轉換距離": item.get("dist", "") or "",
            })
        elif item.get("type") == "spatial":
            rows.append({
                "路徑代碼": item.get("axis"),
                "數值(平移、旋轉、公差值)": item.get("val", 0.0),
                "偏差值(公差帶偏移值)": item.get("bias", 0),
                "角度公差轉換距離": item.get("dist", "") or "",
            })
    df = pd.DataFrame(rows)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="TolerancePath")
    output.seek(0)
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name="Tolerance_Path_Export.xlsx")

@app.route("/api/export_contact_lines", methods=["POST"])
def export_contact_lines():
    data = request.get_json()
    pairs = data.get("pairs", [])
    rows = []
    for pair in pairs:
        rows.append({
            "特徵面 1": pair.get("start"),
            "特徵面 2": pair.get("end"),
            "連結類型": "硬接觸",
        })
    df = pd.DataFrame(rows)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="ContactLines")
    output.seek(0)
    return send_file(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", as_attachment=True, download_name="Contact_Lines_Export.xlsx")

@app.route("/api/sync_report", methods=["POST"])
def sync_report():
    if graph_rag is None:
        return jsonify({"ok": False, "msg": "系統模組載入失敗 (graph_rag)"}), 500
    try:
        data = request.get_json()
        report_text = data.get("reportText", "")
        if not report_text:
            return jsonify({"ok": False, "msg": "沒有收到報表內容"}), 400
        graph_rag.set_latest_report(report_text)
        print(f"[SUCCESS] 成功接收並更新最新機台媒合報表 (長度: {len(report_text)})")
        return jsonify({"ok": True, "msg": "報表同步成功"})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"同步失敗: {str(e)}"}), 500

if __name__ == "__main__":
    print("啟動 AI 聊天助手伺服器...")
    print("請訪問: http://127.0.0.1:7011")
    app.run(host="0.0.0.0", port=7011, debug=True)
