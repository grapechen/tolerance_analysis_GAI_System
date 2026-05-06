import os
import re
import sys
import ollama
import networkx as nx
import pandas as pd

# 確保 scripts 目錄在 import 路徑中
_server_dir = os.path.dirname(os.path.abspath(__file__))
_scripts_dir = os.path.join(_server_dir, 'scripts')
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from triplets_extractor import get_knowledge_triplets, build_triplets_context

# --- 全域變數 ---
_kg = nx.MultiDiGraph()
_communities = {}       # 儲存零件層級的摘要 (Community Summaries)
_triplets = []          # 原始三元組快取

# 可供外部讀取的快照
_latest_machine_report = None

def _ensure_graph_loaded():
    """確保圖譜已初始化，若無則自動載入"""
    global _kg, _communities, _triplets
    if _communities:
        return True

    print("[INFO] 正在初始化知識圖譜...")
    triplets = get_knowledge_triplets('ras400_ontology.csv')
    if not triplets:
        print("[ERROR] 無法從 CSV 載入三元組資料")
        return False

    # [擴充] 合併接觸面補丁檔（ras400_ontology_contacts.csv）
    contacts_triplets = get_knowledge_triplets('ras400_ontology_contacts.csv')
    if contacts_triplets:
        existing = {(s, r, t) for s, r, t in triplets}
        added = 0
        for triple in contacts_triplets:
            if triple not in existing:
                triplets.append(triple)
                added += 1
        print(f"[INFO] 合併接觸補丁：新增 {added} 條 triple")

    _triplets = triplets
    _kg = nx.MultiDiGraph()

    # 建立圖譜
    for src, rel, tgt in triplets:
        _kg.add_edge(src, rel, relation=rel)
        _kg.add_edge(src, tgt, relation=rel)

    # 建立零件社群：找出所有「是零件類別的 NamedIndividual」
    # 策略：所有出現在「有特徵面」關係的 tgt 就是零件
    part_to_features = {}
    # 零件格式：
    #   新格式：純中文名（工作臺、軸承座、馬達水套）
    #   舊格式：數字-中文名（1-底座、9-迴轉滑台上板）
    # 特徵面格式含英文字母段（工作臺-H-1、4-H-1），應排除
    PART_PATTERN = re.compile(r'^(?:\d+-)?[\u4e00-\u9fa5][\u4e00-\u9fa5]+$')

    for src, rel, tgt in triplets:
        if '有特徵面' in rel and PART_PATTERN.match(tgt):
            # src = 特徵面, tgt = 零件
            if tgt not in part_to_features:
                part_to_features[tgt] = []
            part_to_features[tgt].append(src)

    # RAS400 組裝順序
    _asm_order = {
        '工作臺': 1, '軸承座': 2, '軸承': 3, '轉動軸': 4, '工作臺心軸': 5,
        '馬達': 6, '馬達水套': 7, '編碼器心軸': 8, '分流座': 9, '馬達座': 10, '編碼器': 11,
    }

    # 為每個零件生成社群摘要（按組裝順序）
    for part, features in sorted(part_to_features.items(), key=lambda x: _asm_order.get(x[0], 999)):
        summary_lines = [f"【{part}】"]
        
        # 特徵面清單
        summary_lines.append(f"  具有 {len(features)} 個特徵面：" + "、".join(features))
        
        # 組裝接觸關係 (同一零件的特徵面)
        contacts = []
        for feat in features:
            for s, r, t in triplets:
                if s == feat and '有組裝接觸' in r:
                    contacts.append(f"「{feat}」接觸「{t}」")
        if contacts:
            summary_lines.append("  組裝接觸：" + "；".join(contacts[:5]))
            
        _communities[part] = "\n".join(summary_lines)

    # ══════════════════════════════════════════════════════════════
    # [Phase 5] 注入製程節點 — 從 process_capability.csv 動態建立
    # ══════════════════════════════════════════════════════════════
    process_triplet_count = _inject_process_nodes(_kg, _triplets, part_to_features)

    print(f"[INFO] 圖譜載入完成：{len(triplets)} 個三元組 + {process_triplet_count} 個製程三元組，{len(_communities)} 個零件社群")
    return True


def _inject_process_nodes(G: nx.MultiDiGraph, triplets: list, part_to_features: dict) -> int:
    """
    將製程節點注入知識圖譜。

    新增的節點與邊：
      IT{N}         (IT 等級節點)
      {製程名稱}     (製程節點)

    新增的關係：
      公差 → 需要IT等級 → IT{N}
      IT{N} → 可達製程  → 製程名稱
      製程A → 需前置製程 → 製程B
      製程  → 可達粗糙度 → Ra 範圍
      製程  → 使用設備   → 設備名稱
    """
    try:
        from recommendation.process_advisor import get_all_processes, plan_process_chain
    except ImportError:
        print("[WARN] process_advisor 未安裝，跳過製程節點注入")
        return 0

    count = 0
    processes = get_all_processes()

    # ── 1. 建立 IT 等級 → 製程 的關係 ──
    it_grades_seen = set()
    for proc in processes:
        proc_name = proc['process_zh']
        for it in range(proc['it_min'], proc['it_max'] + 1):
            it_node = f"IT{it}"
            G.add_edge(it_node, proc_name, relation='可達製程')
            triplets.append((it_node, '可達製程', proc_name))
            count += 1
            it_grades_seen.add(it)

        # 製程 → 粗糙度
        ra_node = f"Ra {proc['Ra_min']}~{proc['Ra_max']} μm"
        G.add_edge(proc_name, ra_node, relation='可達粗糙度')
        triplets.append((proc_name, '可達粗糙度', ra_node))
        count += 1

        # 製程 → 設備
        G.add_edge(proc_name, proc['equipment'], relation='使用設備')
        triplets.append((proc_name, '使用設備', proc['equipment']))
        count += 1

    # ── 2. 建立製程鏈（前置工序關係）──
    for proc in processes:
        chain = plan_process_chain(proc['process_en'])
        for i in range(len(chain) - 1):
            pre_zh = chain[i]['process_zh']
            cur_zh = chain[i + 1]['process_zh']
            G.add_edge(cur_zh, pre_zh, relation='需前置製程')
            triplets.append((cur_zh, '需前置製程', pre_zh))
            count += 1

    # ── 3. 從零件公差連結到 IT 等級 ──
    # 掃描所有公差三元組，找出含 IT 等級的公差節點
    import csv as _csv
    _data_dir = os.path.join(_server_dir, 'data')
    _csv_dir = r'C:\Users\User\Downloads'
    _part_files = [
        ('工作臺', '工作臺.csv'), ('軸承座', '軸承座.csv'), ('軸承', '軸承.csv'),
        ('轉動軸', '轉動軸.csv'), ('工作臺心軸', '工作臺心軸.csv'),
        ('馬達', '馬達.csv'), ('馬達水套', '馬達水套.csv'),
        ('編碼器心軸', '編碼器心軸.csv'), ('分流座', '分流座.csv'),
        ('馬達座', '馬達座.csv'), ('編碼器', '編碼器.csv'),
    ]
    _part_num = {
        '工作臺': '1', '軸承座': '2', '軸承': '3', '轉動軸': '4', '工作臺心軸': '5',
        '馬達': '6', '馬達水套': '7', '編碼器心軸': '8', '分流座': '9', '馬達座': '10', '編碼器': '11',
    }

    for part_name, csv_file in _part_files:
        csv_path = os.path.join(_csv_dir, csv_file)
        if not os.path.exists(csv_path):
            continue
        try:
            with open(csv_path, 'r', encoding='utf-8-sig') as f:
                for row in _csv.DictReader(f):
                    code = row.get('公差代號', '').strip()
                    it_str = row.get('IT等級', '').strip()
                    tol_val = row.get('公差數值', '').strip()
                    if not it_str or not tol_val or 'DAT' in code.upper():
                        continue
                    # 公差名稱轉為短格式
                    import re as _re
                    m = _re.match(r'^(.+)-([A-Za-z]+)(\d+)$', code.strip())
                    if m:
                        tol_short = f"{_part_num.get(part_name, part_name)}-{m.group(2).capitalize()}-{m.group(3)}"
                    else:
                        tol_short = code
                    it_node = f"IT{it_str}" if not it_str.startswith('IT') else it_str
                    # 跳過 H/K/L (ISO 2768-2 等級)
                    if it_str in ('H', 'K', 'L'):
                        continue
                    G.add_edge(tol_short, it_node, relation='需要IT等級')
                    triplets.append((tol_short, '需要IT等級', it_node))
                    count += 1
        except Exception as e:
            print(f"[WARN] 讀取 {csv_file} 失敗: {e}")

    return count


def enhanced_graph_retrieval(query: str, is_global: bool = False) -> str:
    """混合檢索：全域 BOM / 局部細節"""
    if not _ensure_graph_loaded():
        return "[ERROR] 知識圖譜初始化失敗。"

    # 進階檢索：偵測公差相關意圖
    is_tolerance_query = any(k in query for k in ["公差", "網路", "路徑", "接觸", "連接", "橋接", "配合"])
    is_process_query = any(k in query for k in ["製程", "加工", "磨削", "車削", "銑削", "鑽孔", "鉸孔", "搪孔",
                                                  "粗糙度", "Ra", "IT", "設備", "process", "machining"])
    
    if is_global or is_tolerance_query:
        # 清單優先策略
        _asm_order = {
            '工作臺': 1, '軸承座': 2, '軸承': 3, '轉動軸': 4, '工作臺心軸': 5,
            '馬達': 6, '馬達水套': 7, '編碼器心軸': 8, '分流座': 9, '馬達座': 10, '編碼器': 11,
        }
        all_parts = sorted(list(_communities.keys()), key=lambda x: _asm_order.get(x, 999))
        lines = [
            f"【RAS400 - 零件完整清單】(共 {len(all_parts)} 個)：",
            "、".join(all_parts),
            "",
            "【各零件詳細說明與公差/接觸資訊】："
        ]
        
        # 如果是公差路徑查詢，額外撈取所有交互參考與接觸的三元組
        if is_tolerance_query:
            lines.append("\n【🚨 重要公差/接觸三元組資料 - 用於構建網路與路徑】：")
            bridge_triplets = [f"「{s}」 {r} 「{t}」" for s, r, t in _triplets
                               if any(k in r for k in ["公差", "接觸", "參考", "作用"])]
            lines.append("\n".join(bridge_triplets[:100])) # 限制數量

        if is_process_query:
            lines.append("\n【🔧 製程能力資料 - IT等級與製程對應】：")
            process_triplets = [f"「{s}」 {r} 「{t}」" for s, r, t in _triplets
                                if any(k in r for k in ["可達製程", "需要IT等級", "需前置製程", "可達粗糙度", "使用設備"])]
            lines.append("\n".join(process_triplets[:80]))
        
        char_count = sum(len(l) for l in lines)
        for part in all_parts:
            desc = _communities.get(part, "")
            if char_count + len(desc) > 4500:
                lines.append("... (後續細節已略)")
                break
            lines.append(desc)
            char_count += len(desc)
        return "\n".join(lines)

    # 局部搜尋
    found = [t for t in _triplets if query in t[0] or query in t[2]]
    if not found:
        # Fallback: 看哪個零件名稱在問題中出現
        for part in _communities:
            if part in query:
                return _communities[part]
        return "找不到相關零件。\n零件清單：" + "、".join(list(_communities.keys())[:20])

    context_lines = []
    seen = set()
    for s, r, t in found[:50]:
        line = f"「{s}」 {r} 「{t}」"
        if line not in seen:
            context_lines.append(line)
            seen.add(line)
    return "\n".join(context_lines)


# --- Prompt ---
QA_PROMPT = """你是精密機械工程師助理，負責 RAS400 精密迴轉滑台的公差分析。請根據【知識圖譜上下文】回答問題。

【知識圖譜上下文】:
{context}

【RAS400 零件組裝順序與代號（從上到下）】：
1-工作臺, 2-軸承座, 3-軸承, 4-轉動軸, 5-工作臺心軸, 6-馬達, 7-馬達水套, 8-編碼器心軸, 9-分流座, 10-馬達座, 11-編碼器

【特徵面類別架構（ontology schema）】：
特徵面
├── 平面       (代碼 P) → 面命名格式：零件名稱-P-N
├── 圓柱面
│   ├── 外圓柱面 (代碼 S) → 面命名格式：零件名稱-S-N
│   └── 內圓柱面 (代碼 H) → 面命名格式：零件名稱-H-N
└── 錐面       (代碼 C) → 面命名格式：零件名稱-C-N

【回答規則】：
1. 使用繁體中文回答（若問題為英文則以英文回答）
2. 直接精簡地給出問題的答案，不需要廢話
3. **絕對禁止**在回答中產生 `---BOM_START---` 或 `---BOM_END---` 格式的任何內容
   （系統會自動根據本體庫產生正確的圖表）
4. 提及零件時，一律使用「編號-名稱」格式（如「1-工作臺」、「5-工作臺心軸」）
5. 提及特徵面或公差代號時，省略零件名稱、只保留「編號-特徵代號」格式（如「5-P-1」、「2-Dis-3」、「7-Dia-1」）
6. 回答零件清單時，必須按組裝順序 1~11 列出

使用者問題: {question}
回答："""


def _shorten_part_names(text: str) -> str:
    """將 AI 回覆中的零件名稱前綴替換為組裝編號。
    例：工作臺-P-1 → 1-P-1、馬達水套-Dia-1 → 7-Dia-1
    注意：較長名稱必須先替換，避免前綴被誤匹配（如先替換工作臺心軸再替換工作臺）。
    """
    import re
    # 按名稱長度由長到短排列，避免前綴誤匹配
    _PART_NUM = [
        ('工作臺心軸', '5'),
        ('編碼器心軸', '8'),
        ('馬達水套',   '7'),
        ('馬達座',     '10'),
        ('軸承座',     '2'),
        ('工作臺',     '1'),
        ('軸承',       '3'),
        ('轉動軸',     '4'),
        ('馬達',       '6'),
        ('分流座',     '9'),
        ('編碼器',     '11'),
    ]
    for name, num in _PART_NUM:
        # 匹配「零件名稱-特徵代號」模式，替換為「編號-特徵代號」
        text = re.sub(re.escape(name) + r'-', num + '-', text)
    return text


def get_graph_rag_response(query: str, model_name: str = "llama3.1:8b", base_url: str = "http://localhost:11434", history=None, lang="zh-TW") -> str:
    """執行完整的 GraphRAG 推論"""
    try:
        is_global_query = any(k in query for k in ["畫", "畫出", "BOM", "清單", "產品架構圖", "所有", "包含哪些", "有哪些", "零件", "RAS400", "ras400"])

        filtered_context = enhanced_graph_retrieval(query, is_global=is_global_query)

        if _latest_machine_report:
            filtered_context = f"【機台報表】：\n{_latest_machine_report}\n\n{filtered_context}"

        if is_global_query:
            filtered_context = "【系統指引：以下資料均屬於「RAS400」的完整架構】\n\n" + filtered_context

        print(f"[SEARCH] KG-RAG {'全域' if is_global_query else '局部'} 檢索，Context 長度: {len(filtered_context)}")

        final_prompt = QA_PROMPT.format(context=filtered_context, question=query)

        client = ollama.Client(host=base_url)
        try:
            response = client.generate(
                model=model_name,
                prompt=final_prompt,
                options={"temperature": 0.0, "num_ctx": 16384}
            )
        except Exception as _ollama_err:
            err_str = str(_ollama_err)
            if '403' in err_str or 'subscription' in err_str.lower():
                print(f"[ERROR] Ollama 模型 '{model_name}' 需要訂閱（403），請改用免費模型（如 llama3.1:8b）。")
                return f"[模型錯誤] 目前選用的模型 **{model_name}** 需要 Ollama 訂閱。請在右上角切換模型為 **llama3.1:8b**。"
            raise

        if hasattr(response, 'response'):
            draft_result = response.response or ''
        else:
            draft_result = response.get('response', '')

        debug_text = draft_result[:100].replace('\n', ' ')
        print(f"[DEBUG] AI 回答前 100 字: {debug_text}")

        if not draft_result.strip():
            return "在知識庫中找不到相關資料。"

        is_network_query = any(k in query for k in ["公差網路", "網路", "路徑", "橋接"])
        if is_network_query:
            draft_result = _shorten_part_names(draft_result)

        cot_label = '全域結構' if is_global_query else '局部檢索'
        thought = f"""<thought>
[模式] {cot_label}
[社群] 共 {len(_communities)} 個零件群組
[Context] 長度 {len(filtered_context)} 字符
[參數] num_ctx: 16384
</thought>"""
        return thought + "\n" + draft_result

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"[ERROR] GraphRAG 推論過程發生錯誤: {e}"


def set_latest_report(report_text: str):
    global _latest_machine_report
    _latest_machine_report = report_text
    print("[INFO] 已同步最新機台報表快照至 RAG。")
