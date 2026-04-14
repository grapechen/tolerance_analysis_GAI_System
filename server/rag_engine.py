import re
try:
    from google import genai
except ImportError:
    genai = None

def ask_rag_engine(user_msg, model_name="llama3.1:8b", base_url="http://localhost:11434", history=None, lang="zh-TW", current_analysis=None, current_path=None, current_allocation=None, current_pmi_session=None):
    """
    統一管理 RAG 的查詢邏輯、Prompt 封裝、以及遇到無資料時的 Fallback 機制。

    回傳:
        reply (str): AI 的回答文本
        bom_intent (dict): 判定前端畫圖的意圖
    """

    bom_intent = {
        "layout": "tree", # 'tree' (BOM/Structure) or 'grid' (Features/Network)
        "features": False,
        "network": False,
        "contact": False,
        "edit": False,
        "analysis": False,
        "allocation": False,
        "adjust_tolerance": False,
        "target_part": None,
        "pmi_highlight": False,
        "pmi_label": None,
        "pmi_row_index": None,
        "show_3d_viewer": False,
        "run_asm_contact": False
    }
    
    # 意圖分析：特徵面與公差層次
    if any(k in user_msg for k in ["網路", "接觸", "連接", "網格", "線"]):
        bom_intent["layout"] = "grid"
    
    if any(k in user_msg for k in ["特徵", "面", "P", "S", "H"]):
        bom_intent["features"] = True
        
    if any(k in user_msg for k in ["參考", "公差", "網路圖", "Dis", "Par", "Per", "Con-", "連線"]):
        bom_intent["network"] = True
        bom_intent["features"] = True
        bom_intent["layout"] = "grid"
        
    if any(k in user_msg for k in ["接觸", "連接", "硬接觸", "Con"]):
        bom_intent["contact"] = True
        bom_intent["network"] = True
        bom_intent["features"] = True
        bom_intent["layout"] = "grid"
        
    if any(k in user_msg for k in ["編輯", "路徑", "安插", "tra", "rot"]):
        bom_intent["edit"] = True
        
    if any(k in user_msg for k in ["分析", "計算", "報表", "analysis"]):
        bom_intent["analysis"] = True

    if any(k in user_msg for k in ["調配", "分配", "最佳化", "allocation"]):
        bom_intent["allocation"] = True

    if any(k in user_msg for k in ["放寬", "收緊", "調整", "IT等級"]):
        bom_intent["adjust_tolerance"] = True
        bom_intent["edit"] = True

    # [Phase 4] 意圖分析：PMI 高亮與 3D 查看器
    if any(k in user_msg for k in ["高亮", "標註", "GD&T", "highlight", "pmi"]):
        bom_intent["pmi_highlight"] = True
        bom_intent["show_3d_viewer"] = True
        # 嘗試提取 PMI 標籤（如 dis1, par2, per3 等）
        pmi_code_match = re.search(r'(dis|par|per|pos|cyl|cir|fla|sym|pro|tot|ang|run)(\d+)', user_msg, re.IGNORECASE)
        if pmi_code_match:
            bom_intent["pmi_label"] = f"{pmi_code_match.group(1).lower()}{pmi_code_match.group(2)}"

    # 意圖分析：特定零件標定
    want_all = any(k in user_msg for k in ["完整", "全部", "所有", "每個", "整體", "系統", "架構", "零件", "特徵", "公差", "精密迴轉滑台"])
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
    
    # ── 處理深度分析 context ──────────────────────────────────────────────
    analysis_context = ""
    if current_analysis:
        a = current_analysis
        analysis_context = "\n【當前公差分析報表數據】：\n"

        # RSS（6軸）
        analysis_context += (
            f"- RSS (mm):    X={a.get('rss_X',0):.6f}, Y={a.get('rss_Y',0):.6f}, Z={a.get('rss_Z',0):.6f}\n"
            f"- RSS (arc_s): aX={a.get('rss_aX',0):.6f}, aY={a.get('rss_aY',0):.6f}, aZ={a.get('rss_aZ',0):.6f}\n"
        )

        # Worst Case（6軸）
        analysis_context += (
            f"- WC (mm):    X={a.get('wc_X',0):.6f}, Y={a.get('wc_Y',0):.6f}, Z={a.get('wc_Z',0):.6f}\n"
            f"- WC (arc_s): aX={a.get('wc_aX',0):.6f}, aY={a.get('wc_aY',0):.6f}, aZ={a.get('wc_aZ',0):.6f}\n"
        )

        # Monte Carlo std（6軸）
        analysis_context += (
            f"- MC Std (mm):    X={a.get('mc_X_std',0):.6f}, Y={a.get('mc_Y_std',0):.6f}, Z={a.get('mc_Z_std',0):.6f}\n"
            f"- MC Std (arc_s): aX={a.get('mc_aX_std',0):.6f}, aY={a.get('mc_aY_std',0):.6f}, aZ={a.get('mc_aZ_std',0):.6f}\n"
        )

        # Monte Carlo max（6軸）
        analysis_context += (
            f"- MC Max (mm):    X={a.get('mc_X_max',0):.6f}, Y={a.get('mc_Y_max',0):.6f}, Z={a.get('mc_Z_max',0):.6f}\n"
            f"- MC Max (arc_s): aX={a.get('mc_aX_max',0):.6f}, aY={a.get('mc_aY_max',0):.6f}, aZ={a.get('mc_aZ_max',0):.6f}\n"
        )

        # 公差路徑明細（每個特徵名稱與數值）
        tol_names  = a.get('tol_names', [])
        tol_values = a.get('tol_values', [])
        if tol_names:
            analysis_context += "- 公差特徵明細：\n"
            for nm, vl in zip(tol_names, tol_values):
                analysis_context += f"  * {nm}: {vl:.6f}\n"

        # 貢獻度排名（直移 + 角度，前5名）
        contributions = a.get('contribution', [])
        if contributions:
            analysis_context += "- 直移貢獻度排名 (Contribution %):\n"
            for c in contributions[:5]:
                analysis_context += f"  * {c.get('name')}: X={c.get('x',0):.1f}%, Y={c.get('y',0):.1f}%, Z={c.get('z',0):.1f}%\n"

        angle_contributions = a.get('angle_contribution', [])
        if angle_contributions:
            analysis_context += "- 角度貢獻度排名 (Angle Contribution %):\n"
            for c in angle_contributions[:5]:
                analysis_context += f"  * {c.get('name')}: aX={c.get('x',0):.1f}%, aY={c.get('y',0):.1f}%, aZ={c.get('z',0):.1f}%\n"

        # 敏感度排名（直移 + 角度，前5名）
        sensitivities = a.get('sensitivity', [])
        if sensitivities:
            analysis_context += "- 直移敏感度排名 (Sensitivity %):\n"
            for s in sensitivities[:5]:
                analysis_context += f"  * {s.get('name')}: X={s.get('x',0):.1f}%, Y={s.get('y',0):.1f}%, Z={s.get('z',0):.1f}%\n"

        angle_sensitivities = a.get('angle_sensitivity', [])
        if angle_sensitivities:
            analysis_context += "- 角度敏感度排名 (Angle Sensitivity %):\n"
            for s in angle_sensitivities[:5]:
                analysis_context += f"  * {s.get('name')}: aX={s.get('x',0):.1f}%, aY={s.get('y',0):.1f}%, aZ={s.get('z',0):.1f}%\n"

        # 四象限診斷準則
        analysis_context += """
【公差優化建議準則 (四象限法)】：
1. 高靈敏度、高貢獻度：[關鍵優化項] 優先收緊此公差。
2. 高靈敏度、低貢獻度：[嚴守項] 維持現狀，不可放寬。
3. 高靈敏度、低貢獻度：[次要優化項] 若 Case 1 已優化仍不足，再考慮此項。
4. 低靈敏度、低貢獻度：[成本優化項] 可考慮放大公差以降低成本。
5. 全局公差調配 (Allocation)：綜合評估所有特徵，建議「放寬」非關鍵特徵以降低成本，並「精確收緊」關鍵特徵以確保總 RSS 符合規格。

【自然語言公差調整指令處理】：
如果使用者要求「放寬」或「收緊」特定公差，請檢查 context 中的數據。
若目標特徵缺乏「公稱尺寸 (Nominal Size)」，請禮貌地詢問使用者該特徵的公稱尺寸（例如：請提供 5-P-6 的公稱尺寸）。
若已有數據，請輸出以下格式的標籤以便系統自動套用：
<ADJUST_TOLERANCE target="[特徵名稱或索引]" grade="[目標 IT 等級，如 IT7 或 h7]" />
<DIAGNOSTIC_CARD type="[tighten|loosen]" target="[特徵名稱]" value="[新數值]" reason="[理由]" />
"""

    # ── 處理調配 context ──────────────────────────────────────────────────
    allocation_context = ""
    if current_allocation:
        alloc_mode = current_allocation.get('mode', '')
        if alloc_mode == 'auto':
            axis   = current_allocation.get('axis', 'Z')
            target = current_allocation.get('target', '')
            weight = current_allocation.get('weight', '')
            weight_label = {'high': '高成本優先（放寬低敏感度）', 'medium': '等貢獻度分配', 'low': '偏向精度（均勻收緊）'}.get(weight, weight)
            prev_path = {item['name']: item['val'] for item in current_allocation.get('prevPathData', []) if item.get('type') == 'feature'}
            new_path  = {item['name']: item['val'] for item in current_allocation.get('newPathData', [])  if item.get('type') == 'feature'}
            allocation_context = f"\n【公差自動調配結果】（目標軸：{axis}，目標 RSS：±{target}，策略：{weight_label}）：\n"
            for name in new_path:
                old_v = prev_path.get(name, new_path[name])
                new_v = new_path[name]
                direction = '↓收緊' if new_v < old_v else ('↑放寬' if new_v > old_v else '不變')
                allocation_context += f"  * {name}: {old_v:.6f} → {new_v:.6f}  {direction}\n"

        elif alloc_mode == 'compare':
            report = current_allocation.get('report', {})
            allocation_context = "\n【手動調配前後比對結果】：\n"
            allocation_context += f"{'軸向':<6} {'RSS改善%':>10} {'WC改善%':>10}\n"
            for ax in ['X', 'Y', 'Z', 'aX', 'aY', 'aZ']:
                r = report.get(ax, {})
                rss_pct = r.get('rss_improve_pct', 0)
                wc_pct  = r.get('wc_improve_pct', 0)
                allocation_context += f"  {ax:<6} {rss_pct:>+9.2f}%  {wc_pct:>+9.2f}%\n"
            allocation_context += "（正值表示改善，負值表示惡化）\n"

    # [Phase 4] 處理 PMI Context ────────────────────────────────────────────────────
    pmi_context = ""
    if current_pmi_session and bom_intent.get("pmi_highlight"):
        # 從 _step_sessions 中取得 PMI rows（由 step_service.py 維護）
        try:
            from step_service import _step_sessions
            session_data = _step_sessions.get(current_pmi_session)
            if session_data and 'pmi_rows' in session_data:
                pmi_rows = session_data['pmi_rows']
                pmi_context = "\n【當前上傳的 STEP 模型 PMI 清單 (最多30項)】：\n"
                for i, row in enumerate(pmi_rows[:30]):
                    label = row.get('label', '(未命名)')
                    type_code = row.get('type_code', 'N/A')
                    pmi_context += f"  [{i}] {type_code}: {label}\n"
                pmi_context += "\n【PMI 高亮指令說明】：\n"
                pmi_context += "如果使用者要求高亮特定 PMI 標籤（如「高亮 dis1」或「標註 per3」），請在回覆中包含以下格式的標籤：\n"
                pmi_context += "  <HIGHLIGHT_PMI label=\"[PMI標籤，如dis1/par2/per3]\" />\n"
                pmi_context += "標籤將被前端自動攔截並驅動 3D 查看器高亮相應的幾何面。\n"
        except ImportError:
            pass

    # 建構提供給底層模型的 Prompt
    extra_context = analysis_context + allocation_context + pmi_context
    hidden_prompt = extra_context + "\n" + user_msg if extra_context else user_msg
    is_diagnostic = any(k in user_msg for k in ["檢查", "確認", "缺少", "漏掉"])
    
    # 意圖分類：BOM(純零件) vs 特徵/公差網路 vs 接觸圖
    is_bom_only     = not (bom_intent['layout'] == 'grid' or bom_intent['contact'] or bom_intent['edit'])
    needs_features  = bom_intent['layout'] == 'grid' or bom_intent['contact'] or bom_intent['edit'] or is_diagnostic
    needs_dsl = True  # 永遠由後端自動生成 DSL，不依賴 AI

    model_lower = model_name.lower()

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
        client = genai.Client(api_key=api_key)
        actual_model = "gemini-2.0-flash"
        
        # 進行 Hybrid KG-RAG 檢索
        is_global_query = any(keyword in user_msg for keyword in ["畫", "畫出", "BOM", "清單", "產品架構圖", "所有", "網路圖", "包含哪些", "有哪些"])
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
        # [修正] 不在此 return，讓 reply 繼續走後面的確定性 DSL 注入邏輯

    # --- 路徑 2: 全面由 Ollama 處理 (含 gpt-oss 本地模型，Gemini 路徑跳過此區塊) ---
    else:
        print(f"[RUN] [Engine] 使用本地 Ollama 推論: {model_name}")
        from graph_rag import get_graph_rag_response
        reply = get_graph_rag_response(hidden_prompt, model_name=model_name, base_url=base_url, history=history, lang=lang)

    # 判斷是否為「產品架構與零件」以及「公差網路相關」的查詢
    is_bom_request = any(k in user_msg for k in ["包含", "零件", "特徵", "架構", "結構", "BOM", "哪些", "公差", "網路", "接觸", "連線", "畫出"])
    
    # --- 退回機制 (Fallback) ---
    has_no_data_phrase = "找不到相關資料" in reply
    is_long_reply = len(reply) > 200
    has_bom_block = "---BOM_START---" in reply or "零件" in reply or "清單" in reply

    # 針對結構查詢 (is_bom_request)，只要有任何內容或是長度中等以上，就不執行阻斷
    if has_no_data_phrase and not (is_long_reply or has_bom_block or (is_bom_request and len(reply) > 50)):
        # 提取 thought process 以便保留
        thought_match = re.search(r'<thought>[\s\S]*?<\/thought>', reply)
        thought_process = thought_match.group(0) if thought_match else ""

        if is_bom_request:
            print("[WARN] [Engine] 真實 GraphRAG 回報找不到資料，執行友善阻斷。")
            reply = thought_process + "\n抱歉，在本地產品架構中找不到您詢問的零件或特徵面。請確認您的拼字是否正確。"
        else:
            print("[WARN] [Engine] 圖譜知識庫無相關資料，轉交給工程資料庫 (rag_server) 查詢一般知識...")
            from rag_server import get_rag_response
            fallback_reply = get_rag_response(user_msg, model_name=model_name, history=history, lang=lang)
            if "無法識別" not in fallback_reply and fallback_reply.strip():
                reply = thought_process + "\n" + fallback_reply
                
    # --- 確定性 DSL 注入（後端直接從本體庫生成，不依賴 AI）---
    try:
        import sys as _sys
        import os as _os
        _scripts = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'scripts')
        if _scripts not in _sys.path:
            _sys.path.insert(0, _scripts)
        from dsl_builder import build_bom_dsl, build_feature_dsl, build_text_summary
        
        # 先移除 AI 可能自行生成的任何 DSL（避免重複/幻覺）
        reply = re.sub(r'---BOM_START---[\s\S]*?---BOM_END---', '', reply).strip()
        
        # 根據 intent 選擇正確的 DSL 型態
        is_bom_query = any(k in user_msg for k in ["零件", "包含", "架構", "BOM", "哪些", "列出", "結構"])
        is_feature_query = any(k in user_msg for k in ["特徵", "公差", "網路", "接觸", "連接"])
        
        if bom_intent.get('contact') or bom_intent.get('network') or bom_intent.get('layout') == 'grid' or bom_intent.get('edit'):
            dsl = build_feature_dsl(level='network', show_contacts=bom_intent.get('contact', False))
        elif bom_intent.get('features'):
            dsl = build_feature_dsl(level='feature')
        elif is_bom_query:
            dsl = build_bom_dsl()
        else:
            dsl = None

        if dsl:
            # [核心修正] 回報結構重組，區分「公差網路」、「組裝接觸」與「路徑編輯」
            if bom_intent.get('network') or bom_intent.get('edit') or bom_intent.get('contact'):
                # 檢測是否為「接觸」或「編輯/路徑」相關查詢
                msg_lower = user_msg.lower()
                is_contact_query = any(k in msg_lower for k in ['接觸', '組裝', 'contact', 'assembly'])
                is_edit_query    = any(k in msg_lower for k in ['編輯', '路徑', 'editor', 'path'])

                # 決定摘要模式
                summary_mode = 'network'
                if is_edit_query:
                    summary_mode = 'edit'
                elif is_contact_query:
                    summary_mode = 'contact'

                summary = build_text_summary(mode=summary_mode)

                answer_match = re.search(r'<FINAL_ANSWER>([\s\S]*?)<\/FINAL_ANSWER>', summary)
                answer_content = answer_match.group(1).strip() if answer_match else ""

                # 編輯模式：只顯示固定系統提示，省略 AI 生成內容
                if summary_mode == 'edit':
                    reply = f"[系統訊息] 已準備好公差路徑數據\n\n正在為您開啟「公差路徑編輯器」... 您可以手動調整平移 (tra)、旋轉 (rot) 與特徵公差值 (tol)，調整後點擊「匯出 CSV」即可下載。\n\n{dsl}"
                else:
                    audit_match = re.search(r'<AUDIT_REPORT>([\s\S]*?)<\/AUDIT_REPORT>', summary)
                    audit_content = audit_match.group(1).strip() if audit_match else "數據處理完成。"
                    reply = (
                        f"<AUDIT_REPORT>\n{audit_content}\n</AUDIT_REPORT>\n\n"
                        f"{answer_content}\n\n"
                        f"{dsl}"
                    )
            else:
                reply = reply + ('\n\n' if reply else '') + dsl
            print(f'[DSL Builder] 確定性 DSL 已注入 ({"Edit/Network" if (bom_intent.get("network") or bom_intent.get("edit")) else "BOM"})')
    except Exception as _e:
        print(f'[WARN] DSL Builder 注入失敗: {_e}')
    
    return reply, bom_intent
