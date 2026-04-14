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
    triplets = get_knowledge_triplets('ontology_export.csv')
    if not triplets:
        print("[ERROR] 無法從 CSV 載入三元組資料")
        return False

    _triplets = triplets
    _kg = nx.MultiDiGraph()

    # 建立圖譜
    for src, rel, tgt in triplets:
        _kg.add_edge(src, rel, relation=rel)
        _kg.add_edge(src, tgt, relation=rel)

    # 建立零件社群：找出所有「是零件類別的 NamedIndividual」
    # 策略：所有出現在「有特徵面」關係的 tgt 就是零件
    part_to_features = {}
    # 只有「數字-中文名稱」格式才是真正的零件，例如 1-底座、9-迴轉滑台上板
    # 特徵面格式為「數字-英文-數字」如 4-H-1，應排除
    PART_PATTERN = re.compile(r'^\d+-[\u4e00-\u9fa5]')

    for src, rel, tgt in triplets:
        if '有特徵面' in rel and PART_PATTERN.match(tgt):
            # src = 特徵面, tgt = 零件
            if tgt not in part_to_features:
                part_to_features[tgt] = []
            part_to_features[tgt].append(src)

    # 為每個零件生成社群摘要
    for part, features in sorted(part_to_features.items()):
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

    print(f"[INFO] 圖譜載入完成：{len(triplets)} 個三元組，{len(_communities)} 個零件社群")
    return True


def enhanced_graph_retrieval(query: str, is_global: bool = False) -> str:
    """混合檢索：全域 BOM / 局部細節"""
    if not _ensure_graph_loaded():
        return "[ERROR] 知識圖譜初始化失敗。"

    # 進階檢索：偵測公差相關意圖
    is_tolerance_query = any(k in query for k in ["公差", "網路", "路徑", "接觸", "連接", "橋接", "配合"])
    
    if is_global or is_tolerance_query:
        # 清單優先策略
        all_parts = sorted(list(_communities.keys()))
        lines = [
            f"【精密迴轉滑台 - 零件完整清單】(共 {len(all_parts)} 個)：",
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
QA_PROMPT = """你是精密機械工程師助理。請根據【知識圖譜上下文】回答問題。

【知識圖譜上下文】:
{context}

【回答規則】：
1. 使用繁體中文回答（若問題為英文則以英文回答）
2. 直接精簡地給出問題的答案，不需要廢話
3. **絕對禁止**在回答中產生 `---BOM_START---` 或 `---BOM_END---` 格式的任何內容
   （系統會自動根據本體庫產生正確的圖表）
4. 提及零件或特徵面時，使用其完整 ID 名稱（如「4-下軸承」、「3-P-1」）
5. 回答零件清單時，按編號順序列出所有零件

使用者問題: {question}
回答："""


def get_graph_rag_response(query: str, model_name: str = "llama3.1:8b", base_url: str = "http://localhost:11434", history=None, lang="zh-TW") -> str:
    """執行完整的 GraphRAG 推論"""
    try:
        is_global_query = any(k in query for k in ["畫", "畫出", "BOM", "清單", "產品架構圖", "所有", "包含哪些", "有哪些", "零件"])

        filtered_context = enhanced_graph_retrieval(query, is_global=is_global_query)

        if _latest_machine_report:
            filtered_context = f"【機台報表】：\n{_latest_machine_report}\n\n{filtered_context}"

        if is_global_query:
            filtered_context = "【系統指引：以下資料均屬於「精密迴轉滑台」的完整架構】\n\n" + filtered_context

        print(f"[SEARCH] KG-RAG {'全域' if is_global_query else '局部'} 檢索，Context 長度: {len(filtered_context)}")

        final_prompt = QA_PROMPT.format(context=filtered_context, question=query)

        client = ollama.Client(host=base_url)
        response = client.generate(
            model=model_name,
            prompt=final_prompt,
            options={"temperature": 0.0, "num_ctx": 16384}
        )

        if hasattr(response, 'response'):
            draft_result = response.response or ''
        else:
            draft_result = response.get('response', '')

        debug_text = draft_result[:100].replace('\n', ' ')
        print(f"[DEBUG] AI 回答前 100 字: {debug_text}")

        if not draft_result.strip():
            return "在知識庫中找不到相關資料。"

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
