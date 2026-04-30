import re
try:
    from google import genai
except ImportError:
    genai = None

# 零件名稱 → 組裝編號對應（公差網路顯示用）
_PART_NUM_MAP = [
    ('工作臺心軸', '5'), ('編碼器心軸', '8'), ('馬達水套', '7'),
    ('馬達座', '10'), ('軸承座', '2'), ('工作臺', '1'),
    ('軸承', '3'), ('轉動軸', '4'), ('馬達', '6'),
    ('分流座', '9'), ('編碼器', '11'),
]

# 零件編號 → 中文名稱（反向查詢）
_PART_NAME_MAP = {num: name for name, num in _PART_NUM_MAP}

# ═══════════════════════════════════════════════════
# 結構化公差調整指令解析器
# ═══════════════════════════════════════════════════
_TOL_TYPE_MAP = {
    '直徑': 'Dia', '半徑': 'Rad', '圓柱度': 'Cyl',
    '平面度': 'Fla', '真圓度': 'Cir', '真直度': 'Str',
    '距離': 'Dis', '平行度': 'Par', '垂直度': 'Per',
    '位置度': 'Pos', '同心度': 'Co',  '對稱度': 'Sym',
    '角度': 'Ang', '圓偏轉度': 'Run', '總偏轉度': 'Tot',
}

# 公差類型 → 中文名稱（反向查詢）
_TOL_NAME_MAP = {v: k for k, v in _TOL_TYPE_MAP.items()}

def parse_structured_command(user_msg: str):
    """
    解析結構化公差調整指令，支援多種口語格式。

    支援範例：
      「請將編號5零件第6特徵面的第1個直徑公差由IT6放寬至IT7」
      「收緊3號零件第2個位置度公差到IT5」
      「5號零件的Dia-1放寬到IT8」
      「放寬 5-Dia-1 到 IT7」

    Returns:
        dict with keys: part_id, tol_code, tol_index, action, target_it,
                        target_name, target_grade, part_name_zh, tol_type_zh
        or None if not a structured command
    """
    # ── 模式 A：直接指定公差名稱 (e.g. "5-Dia-1" 或 "放寬 5-Dia-1 到 IT7") ──
    direct_pattern = (
        r'(\d{1,2})-([A-Z][a-z]{1,2})-(\d+)'   # group 1,2,3: 公差名稱
        r'.*?(?:放寬|收緊|調整)'                   # 動作
        r'.*?IT\s*(\d+)'                           # group 4: 目標IT
    )
    # 也支援動作在前面的格式
    direct_pattern_alt = (
        r'(放寬|收緊|調整)'                        # group 1: 動作
        r'\s*(\d{1,2})-([A-Z][a-z]{1,2})-(\d+)'  # group 2,3,4: 公差名稱
        r'.*?IT\s*(\d+)'                           # group 5: 目標IT
    )
    m = re.search(direct_pattern, user_msg)
    if m:
        part_id, tol_code, tol_idx, target_it = m.group(1), m.group(2), m.group(3), m.group(4)
        action = '放寬' if '放寬' in user_msg else ('收緊' if '收緊' in user_msg else '調整')
        return _build_command_result(part_id, tol_code, int(tol_idx), action, int(target_it))

    m = re.search(direct_pattern_alt, user_msg)
    if m:
        action, part_id, tol_code, tol_idx, target_it = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        return _build_command_result(part_id, tol_code, int(tol_idx), action, int(target_it))

    # ── 模式 B：中文口語格式 (e.g. "編號5零件第6特徵面的第1個直徑公差由IT6放寬至IT7") ──
    tol_types_re = '|'.join(_TOL_TYPE_MAP.keys())
    natural_pattern = (
        r'(?:編號\s*)?(\d{1,2})\s*號?\s*零件'     # group 1: 零件編號
        r'(?:.*?第\s*(\d+)\s*特徵面)?'              # group 2: 特徵面編號 (optional)
        r'.*?(?:第\s*(\d+)\s*個)?'                  # group 3: 公差序號 (optional)
        r'\s*(' + tol_types_re + r')'               # group 4: 公差類型
        r'\s*公差'
        r'.*?(放寬|收緊|調整)'                      # group 5: 動作
        r'.*?IT\s*(\d+)'                            # group 6: 目標IT等級
    )
    m = re.search(natural_pattern, user_msg)
    if m:
        part_id     = m.group(1)
        # feature_idx = m.group(2)  # 特徵面編號 — 僅供顯示參考
        tol_index   = int(m.group(3)) if m.group(3) else 1
        tol_type_zh = m.group(4)
        action      = m.group(5)
        target_it   = int(m.group(6))
        tol_code    = _TOL_TYPE_MAP[tol_type_zh]
        return _build_command_result(part_id, tol_code, tol_index, action, target_it)

    # ── 模式 C：簡易格式 (e.g. "收緊3號零件第2個位��度公差到IT5") ──
    simple_pattern = (
        r'(放寬|收緊|調整)'                        # group 1: 動作
        r'.*?(\d{1,2})\s*號?\s*零件'               # group 2: 零件編號
        r'.*?(?:第\s*(\d+)\s*個)?'                  # group 3: 公差序號 (optional)
        r'\s*(' + tol_types_re + r')'               # group 4: 公差類型
        r'\s*公差'
        r'.*?IT\s*(\d+)'                            # group 5: 目標IT等級
    )
    m = re.search(simple_pattern, user_msg)
    if m:
        action      = m.group(1)
        part_id     = m.group(2)
        tol_index   = int(m.group(3)) if m.group(3) else 1
        tol_type_zh = m.group(4)
        target_it   = int(m.group(5))
        tol_code    = _TOL_TYPE_MAP[tol_type_zh]
        return _build_command_result(part_id, tol_code, tol_index, action, target_it)

    # ── 模式 D：中文零件名直接格式 (e.g. "軸承座-Dia-2由IT6放寬至IT7") ──
    # 較長的零件名要排在前面，避免「軸承」吃掉「軸承座」的前綴
    _zh_names_sorted = sorted((n for n, _ in _PART_NUM_MAP), key=len, reverse=True)
    zh_names_re = '|'.join(re.escape(n) for n in _zh_names_sorted)
    _name_to_num = {n: num for n, num in _PART_NUM_MAP}

    zh_direct_pattern = (
        r'(' + zh_names_re + r')-([A-Za-z]{1,3})-?(\d+)'   # group 1,2,3: 零件-tol_code-序號（橫線可省）
        r'.*?(?:放寬|收緊|調整)'                              # 動作
        r'.*?IT\s*(\d+)'                                     # group 4: 目標 IT
    )
    m = re.search(zh_direct_pattern, user_msg)
    if m:
        zh_name, tol_code, tol_idx, target_it = m.group(1), m.group(2), m.group(3), m.group(4)
        action = '放寬' if '放寬' in user_msg else ('收緊' if '收緊' in user_msg else '調整')
        part_id = _name_to_num.get(zh_name, zh_name)
        tol_code = tol_code.capitalize()
        return _build_command_result(part_id, tol_code, int(tol_idx), action, int(target_it))

    zh_direct_pattern_alt = (
        r'(放寬|收緊|調整)'                                  # group 1: 動作
        r'\s*(' + zh_names_re + r')-([A-Za-z]{1,3})-?(\d+)' # group 2,3,4
        r'.*?IT\s*(\d+)'                                     # group 5: 目標 IT
    )
    m = re.search(zh_direct_pattern_alt, user_msg)
    if m:
        action, zh_name, tol_code, tol_idx, target_it = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        part_id = _name_to_num.get(zh_name, zh_name)
        tol_code = tol_code.capitalize()
        return _build_command_result(part_id, tol_code, int(tol_idx), action, int(target_it))

    return None


def _build_command_result(part_id: str, tol_code: str, tol_index: int, action: str, target_it: int) -> dict:
    """組裝解析結果 dict"""
    part_name_zh = _PART_NAME_MAP.get(str(part_id), f'{part_id}號零件')
    tol_type_zh  = _TOL_NAME_MAP.get(tol_code, tol_code)
    # target_name 必須與 editorPathData 的 name 欄位一致：
    # CSV 公差代號格式為「零件名稱-TYPE大寫+序號」，e.g. "工作臺心軸-DIA1"
    target_name  = f"{part_name_zh}-{tol_code.upper()}{tol_index}"
    return {
        'part_id':      str(part_id),
        'tol_code':     tol_code,
        'tol_index':    tol_index,
        'action':       action,         # 放寬 / 收緊 / 調整
        'target_it':    target_it,
        'target_name':  target_name,    # e.g. "工作臺心軸-DIA1"
        'target_grade': f"IT{target_it}",
        'part_name_zh': part_name_zh,   # e.g. "工作臺心軸"
        'tol_type_zh':  tol_type_zh,    # e.g. "直徑"
    }

def _handle_process_query(user_msg: str, current_path: list = None):
    """
    處理製程相關查詢，確定性回答。

    支援格式：
      - 「IT6 需要什麼製程？」「IT6 怎麼加工？」
      - 「車削能達到什麼精度？」「磨削的能力？」
      - 「5-Dia-1 建議怎麼加工？」
      - 「列出所有製程」
    """
    from recommendation.process_advisor import (
        suggest_processes, estimate_capability, recommend_full,
        get_all_processes, recommend_for_path
    )

    # ── 模式 A：「IT6 需要什麼製程」「IT7 怎麼加工」 ──
    it_match = re.search(r'IT\s*(\d+)\s*.*?(?:需要|用|怎麼|如何|建議|可以|適合|製程|加工|process)', user_msg, re.IGNORECASE)
    if not it_match:
        it_match = re.search(r'(?:需要|用|怎麼|如何|建議|可以|適合|製程|加工).*?IT\s*(\d+)', user_msg, re.IGNORECASE)
    if it_match:
        it_grade = int(it_match.group(1))
        # 嘗試判斷特徵類型
        feat_type = None
        if any(k in user_msg for k in ['孔', '內孔', '內圓', 'hole', 'bore']):
            feat_type = 'H'
        elif any(k in user_msg for k in ['軸', '外圓', 'shaft', 'cylinder']):
            feat_type = 'S'
        elif any(k in user_msg for k in ['平面', '端面', 'plane', 'flat']):
            feat_type = 'P'

        rec = recommend_full(it_grade, feat_type)
        reply = f"### IT{it_grade} 製程建議\n\n{rec['summary_zh']}\n\n"

        # 詳細製程鏈
        if rec['process_chain']:
            reply += "**製程鏈明細：**\n"
            for i, step in enumerate(rec['process_chain'], 1):
                reply += f"  {i}. {step['process_zh']}（{step['process_en']}）— {step['reason']}\n"

        return reply

    # ── 模式 B：「車削能達到什麼精度」「磨削的能力」 ──
    process_names = ['車削', '銑削', '鑽孔', '鉸孔', '搪孔', '搪磨', '外圓磨削', '內圓磨削',
                     '平面磨削', '研磨拋光', '拉削', '鋸切', '鑄造', '鍛造', '磨削',
                     'turning', 'milling', 'drilling', 'reaming', 'boring', 'honing',
                     'grinding', 'lapping', 'broaching']
    for pn in process_names:
        if pn in user_msg.lower():
            desc = estimate_capability(pn)
            if '找不到' not in desc:
                return f"### 製程能力查詢\n\n{desc}"

    # ── 模式 C：「5-Dia-1 怎麼加工」「工作臺心軸-Dia-1 建議製程」 ──
    feat_match = re.search(r'(\d{1,2}-[A-Z][a-z]{1,2}-\d+)', user_msg)
    if feat_match and current_path:
        target = feat_match.group(1)
        for item in current_path:
            if item.get('name') == target:
                it_str = item.get('it_grade', '')
                nominal = item.get('nominal_size')
                try:
                    it_grade = int(str(it_str).replace('IT', '').strip())
                except (ValueError, TypeError):
                    return f"**{target}** 尚未設定 IT 等級，無法推薦製程。請先填入 IT 等級。"

                feat_type = None
                if '-H-' in target or 'Dia' in target:
                    # 判斷是孔還是軸需要看特徵面
                    feat_type = 'S'
                if '-P-' in target or 'Fla' in target or 'Dis' in target:
                    feat_type = 'P'

                rec = recommend_full(it_grade, feat_type, nominal)
                reply = f"### {target} 製程建議\n\n{rec['summary_zh']}\n\n"
                if rec['process_chain']:
                    reply += "**製程鏈：**\n"
                    for i, step in enumerate(rec['process_chain'], 1):
                        reply += f"  {i}. {step['process_zh']}（{step['process_en']}）\n"
                return reply
        return f"在目前的公差路徑中找不到 **{target}**。"

    # ── 模式 D：「列出所有製程」「製程清單」 ──
    if any(k in user_msg for k in ['所有製程', '製程清單', '列出製程', '有哪些製程', 'all process']):
        all_proc = get_all_processes()
        reply = "### 製程能力一覽表\n\n"
        reply += "| 製程 | IT範圍 | Ra (μm) | 分類 | 設備 |\n"
        reply += "|------|--------|---------|------|------|\n"
        for p in all_proc:
            reply += f"| {p['process_zh']} | IT{p['it_min']}~{p['it_max']} | {p['Ra_min']}~{p['Ra_max']} | {p['category']} | {p['equipment']} |\n"
        return reply

    # 未匹配到明確模式 → 回傳 None，走正常 LLM 流程
    return None


def _shorten_names(text: str) -> str:
    """將 零件名稱-特徵代號 縮短為 編號-特徵代號，用於公差網路輸出。"""
    for name, num in _PART_NUM_MAP:
        text = re.sub(re.escape(name) + r'-', num + '-', text)
    return text

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
        "process_query": False,
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

    # [Phase 5] 意圖分析：製程建議
    if any(k in user_msg for k in ["製程", "加工", "磨削", "車削", "銑削", "鑽孔", "鉸孔", "搪孔", "搪磨",
                                     "研磨", "拋光", "拉削", "怎麼做", "怎麼加工", "製造", "粗糙度", "Ra",
                                     "process", "machining", "grinding", "turning", "milling"]):
        bom_intent["process_query"] = True

    # [Phase 4] 意圖分析：PMI 高亮與 3D 查看器
    if any(k in user_msg for k in ["高亮", "標註", "GD&T", "highlight", "pmi"]):
        bom_intent["pmi_highlight"] = True
        bom_intent["show_3d_viewer"] = True
        # 嘗試提取 PMI 標籤（如 dis1, par2, per3 等）
        pmi_code_match = re.search(r'(dis|par|per|pos|cyl|cir|fla|sym|pro|tot|ang|run)(\d+)', user_msg, re.IGNORECASE)
        if pmi_code_match:
            bom_intent["pmi_label"] = f"{pmi_code_match.group(1).lower()}{pmi_code_match.group(2)}"

    # 意圖分析：特定零件標定
    want_all = any(k in user_msg for k in ["完整", "全部", "所有", "每個", "整體", "系統", "架構", "零件", "特徵", "公差", "精密迴轉滑台", "RAS400", "ras400"])
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

    # ══════════════════════════════════════════════════════════════
    # [Fast Path] 結構化公差調整指令 — 跳過 LLM，確定性解析直接執行
    # ══════════════════════════════════════════════════════════════
    voice_cmd = parse_structured_command(user_msg)
    if voice_cmd:
        bom_intent["adjust_tolerance"] = True
        bom_intent["edit"] = True
        bom_intent["network"] = True
        bom_intent["features"] = True
        bom_intent["layout"] = "grid"

        action_zh   = voice_cmd['action']
        part_zh     = voice_cmd['part_name_zh']
        tol_zh      = voice_cmd['tol_type_zh']

        if not current_path:
            reply = (
                f"⚠️ 目前沒有公差累積路徑可供調整。\n\n"
                f"請先執行公差分析（輸入「畫出公差網路」），再執行調整指令。"
            )
            return reply, bom_intent

        # 委派給 PlanService 做正規化匹配 + ISO 286 查表 + 回填路徑
        from services.plan_service import PlanService
        result = PlanService().apply_command(current_path, user_msg)

        if 'error' in result:
            reply = f"⚠️ {result['error']}"
            print(f"[CMD] 結構化指令失敗 → {result.get('error')}")
            return reply, bom_intent

        change       = result['change']
        matched_name = result['target_name']
        before       = change['before']
        after        = change['after']
        arrow        = '↑' if action_zh == '放寬' else '↓'

        bom_intent["modified_path"] = result['path_data']

        reply = (
            f"✅ 已{action_zh} **{part_zh}** 的{tol_zh}公差 **{matched_name}**：\n"
            f"- IT 等級：**{before['it_grade']}** → **{after['it_grade']}** {arrow}\n"
            f"- 公差值：**{before['val_mm']:.4f} mm** → **{after['val_mm']:.4f} mm**（{after['val_um']:.1f} μm）\n\n"
            f"已自動回填修改後的公差累積路徑。"
        )
        print(f"[CMD] 結構化指令 → {action_zh} {matched_name} → {after['it_grade']} (val {before['val_mm']:.4f}→{after['val_mm']:.4f})")
        return reply, bom_intent

    # ══════════════════════════════════════════════════════════════
    # [Fast Path] 製程查詢 — 確定性回答，不需 LLM
    # ══════════════════════════════════════════════════════════════
    if bom_intent.get("process_query"):
        try:
            from recommendation.process_advisor import (
                suggest_processes, estimate_capability, recommend_full, get_all_processes
            )
            process_reply = _handle_process_query(user_msg, current_path)
            if process_reply:
                print(f"[CMD] 製程查詢 fast path 命中")
                return process_reply, bom_intent
        except Exception as e:
            print(f"[WARN] 製程查詢失敗: {e}")

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
                # contact 模式保留完整零件名稱（分流座-H-3），只有純 network 模式才縮短
                if bom_intent.get('network') and not bom_intent.get('contact'):
                    answer_content = _shorten_names(answer_content)

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
