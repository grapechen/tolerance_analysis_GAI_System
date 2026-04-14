import re
try:
    from google import genai
except ImportError:
    genai = None

def ask_rag_engine(user_msg, model_name="llama3.1:8b", base_url="http://localhost:11434", history=None):
    """
    統一管理 RAG 的查詢邏輯、Prompt 封裝、以及遇到無資料時的 Fallback 機制。
    
    回傳:
        reply (str): AI 的回答文本
        bom_intent (dict): 判定前端畫圖的意圖
    """
    
    bom_intent = {
        "layout": "tree",
        "contact": False,
        "edit": False,
        "target_part": None  # 指定要渲染的單一零件，None = 全部
    }
    
    # 意圖分析：圖表排版方式
    if any(k in user_msg for k in ["參考", "公差", "網路圖"]):
        bom_intent["layout"] = "grid"
        
    if any(k in user_msg for k in ["接觸", "連接", "硬接觸"]):
        bom_intent["contact"] = True
        bom_intent["layout"] = "grid"
        
    if any(k in user_msg for k in ["編輯", "路徑", "安插", "tra", "rot"]):
        bom_intent["edit"] = True

    # 意圖分析：特定零件標定
    want_all = any(k in user_msg for k in ["完整", "全部", "所有", "每個", "整體", "系統", "架構", "精密迴轉滑台"])
    if not want_all:
        part_id_match = re.search(r'(\d+)[\-－]([\u4e00-\u9fa5a-zA-Z\d]+)', user_msg)
        if part_id_match:
            pid = part_id_match.group(1)
            pname = part_id_match.group(2)
            bom_intent["target_part"] = f"{pid}-{pname}"
        else:
            part_keywords = ["底座", "固定座", "軸承", "蝸輪", "蝸桿", "上板", "下板", "間隔環", "間隔", "螺帽", "滑台"]
            for pk in part_keywords:
                if pk in user_msg:
                    bom_intent["target_part"] = pk
                    break
                    
    # 建構提供給底層模型的 Prompt
    hidden_prompt = user_msg
    is_diagnostic = any(k in user_msg for k in ["檢查", "確認", "缺少", "漏掉"])
    needs_dsl = (bom_intent["layout"] == "grid" or bom_intent["contact"] or bom_intent["edit"] or is_diagnostic)
    
    if needs_dsl:
        if not any(k in user_msg for k in ["列出", "包含", "零件", "特徵", "架構"]):
            dsl_rules = """
[系統最高行為準則]：這是一個觸發「公差網路圖表」的請求。請你「絕對務必」在回答的最後，附上符合「公差網路文字 DSL」格式的清單。
這個清單「必須」包裹在 ---BOM_START--- 與 ---BOM_END--- 之間！

[輸出格式規定]
1. 區塊第一行必須是最上層組件，例如：`# 精密迴轉滑台`
2. 零件節點使用減號：`- 零件ID-零件名稱` (若有子組件請用兩個空格縮排)
3. 每個特徵面使用星號：`* 特徵面名稱 (個別公差) [交互參考公差]`
4. 小括號 `( )` 內「只准」放個別公差（如 Dia, Rad, Cir, Cyl, Flat 等）。多個公差請用逗號隔開。
5. 方括號 `[ ]` 內「只准」放交互參考公差（如 Per, Par, Dis, Con, Pos 等）。多個公差請用逗號隔開。
6. 🚨【重要自我檢查】：方括號 `[ ]` 內的交互參考 tag，若要形成橋接，必須在至少兩個不同的特徵面出現！絕對不准參考不存在的圖面特徵，否則前端渲染會崩潰！請嚴格遵守。
"""
            hidden_prompt = user_msg + "\n\n" + dsl_rules.strip()

    model_lower = model_name.lower()

    # 雲端 Ollama 模型（:cloud 後綴）無法用於本機 GraphRAG，直接回傳提示
    is_ollama_cloud = ":cloud" in model_lower
    if is_ollama_cloud:
        return (
            "⚠️ 您選擇的是雲端模型（:cloud），需要 Ollama 帳號認證才能使用。\n"
            "請切換為本機模型（例如 `llama3.1:8b` 或 `gemma3:4b`）後再試。",
            bom_intent
        )

    # 取得 RAG Context
    from graph_rag import enhanced_graph_retrieval, QA_PROMPT
    import graph_rag

    # --- 路徑 1: 走 Gemini 原生 API ---
    if "gemini" in model_lower:
        if genai is None:
            return "[ERROR] 尚未安裝 google-genai 套件，無法使用 Gemini 模型。", bom_intent
            
        import os
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return "[ERROR] 找不到 GOOGLE_API_KEY 環境變數，請在 .env 中設定。", bom_intent

        print(f"[RUN] [Engine] 使用 Gemini 原生 API 推論: {model_name}")
        # The new SDK uses a client-based approach
        client = genai.Client(api_key=api_key)
        actual_model = "gemini-2.0-flash" # Updating to a stable high-perf model
        
        # 進行 Hybrid KG-RAG 檢索
        is_global_query = any(keyword in user_msg for keyword in ["畫", "畫出", "BOM", "清單", "產品架構圖", "所有", "網路圖"])
        context = enhanced_graph_retrieval(hidden_prompt, is_global=is_global_query)
        
        if graph_rag._latest_machine_report:
            context = f"【最新機台報表】：\n{graph_rag._latest_machine_report}\n\n{context}"

        prompt = QA_PROMPT.format(context=context, question=hidden_prompt)
        print("[SEARCH] [Engine] Gemini KG-RAG: 已擷取圖譜上下文")
        
        response = client.models.generate_content(
            model=actual_model,
            contents=prompt
        )
        reply = response.text
        return reply, bom_intent

    # --- 路徑 2: 走原本的 GraphRAG 邏輯 (Ollama) ---
    print(f"[RUN] [Engine] 使用本地模型 GraphRAG 推論: {model_name}")
    from graph_rag import get_graph_rag_response
    reply = get_graph_rag_response(hidden_prompt, model_name=model_name, base_url=base_url, history=history)

    # 判斷是否為「產品架構與零件」相關的查詢
    is_bom_request = any(k in hidden_prompt for k in ["包含", "零件", "特徵", "架構", "結構", "BOM"])
    
    # --- 退回機制 (Fallback) ---
    if "找不到相關資料" in reply:
        if is_bom_request:
            print("[WARN] [Engine] 真實 GraphRAG 無法回答結構問題，直接阻斷以防止 rag_server 產生幻覺。")
            reply = "抱歉，在本地產品架構中找不到您詢問的零件或特徵面。請確認您的拼字是否與清單相符（例如：'1-底座'）。"
        else:
            print("[WARN] [Engine] 圖譜知識庫無相關資料，轉交給工程資料庫 (rag_server) 查詢一般知識...")
            from rag_server import get_rag_response
            fallback_reply = get_rag_response(user_msg, model_name=model_name, history=history)
            if "無法識別" not in fallback_reply and fallback_reply.strip():
                reply = fallback_reply
                
    return reply, bom_intent
