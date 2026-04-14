import os
import sys
import networkx as nx
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    pass
import faiss
import numpy as np

sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))
from triplets_extractor import get_knowledge_triplets

# 全域變數
_latest_machine_report = ""

def set_latest_report(report_text):
    global _latest_machine_report
    _latest_machine_report = report_text
    print(f"📦 GraphRAG 已儲存最新的機台媒合報表 (長度: {len(report_text)})")

# ========================================================================
# [公差圖譜 GraphRAG 測試系統 - 本地 CSV 知識庫版]
# ========================================================================

# 客製化問答 Prompt
QA_PROMPT = """你是一位嚴謹的公差與機構製造業知識助理。
你的「唯一」知識來源是下方提供的 [知識領域三元組 Context]。

[最高指導原則]：
1. 請「完全依據」下方提供的 [知識領域三元組 Context] 回答問題。絕對不要加入任何外部知識、常識或舉例。
2. **所有由資料支持的論述，都必須標註來源出處**。請依照以下格式：
   `"特徵面 1-P-1 具有個別公差 1-Par-1 [Data: Graph (1-P-1, 1-Par-1)]"`。
   每個來源標註不可超過 5 項資料識別碼。
3. 如果使用者問的問題在 Context 中找不到直接或間接的關聯，請直接回答：「在知識庫中找不到相關資料。」，絕對不要自己編造答案。
4. 【歷史分離原則】歷史對話僅供你理解「代名詞」。如果最新問題與實體產品架構無關，且無法從 Context 獲得支持，你必須強制回答：「找不到相關資料。」
5. 針對分析結果，請在心中給予一個 **Importance Score (0-100)** 評等。若某些推論的分數為 0，請直接將該部分論述刪除。
6. 回答請保持簡潔專業，並以繁體中文回覆。嚴禁補充說明 (Anti-Yapping)：當只詢問清單時，絕對禁止補充 Markdown 表格或名詞定義。

【步驟 3：修正並給出最終正確答案 (Final Output)】
根據你在 <AUDIT_REPORT> 中找出的所有錯誤，進行重整與修正。
請用以下格式輸出你最終確認過、保證 100% 正確的結果。如果需要畫架構圖，請務必將 `---BOM_START---` 和 `---BOM_END---` 放在這區塊內：
<FINAL_ANSWER>
(你更正後完美無瑕的最終解答與架構圖...)
</FINAL_ANSWER>

[輸出格式規定]：
- 如果使用者要求**產品架構圖**或**公差網路圖**，必須將結果包裹在 `---BOM_START---` 與 `---BOM_END---` 之間。
- 必須在清單第一行，以 `# [組合件名稱]` 寫出組件的名字。

[🛑 絕對防幻覺自檢機制 (Self-Correction)]：
在輸出前，無論你多麼篤定，都必須在心中執行以下查核，任何違規項目必須直接刪除：
1. **零件查核**：輸出的「零件名稱」是否真的存在於知識庫中？(不存在就刪)
2. **特徵查核**：輸出的「特徵面」是否真的隸屬於該零件？
3. **公差參照**：方括號 `[ ]` 內的交互參考公差，其目標對象是否明確標註在知識庫？絕對禁止發明知識庫裡沒有的公差名稱與目標！參考對象絕對不能是自己。

格式範例 (包含公差時)：
---BOM_START---
# 精密迴轉滑台
- 1-底座
  * 1-P-1 [1-Par-1, 1-Dis-1]
  * 1-P-2 (1-Fla-1) [1-Par-1, 1-Dis-1]
- 2-固定座
---BOM_END---

格式範例 (只有特徵面，無公差時)：
---BOM_START---
# 精密迴轉滑台
- 1-底座
  * 1-P-1
  * 1-P-2
- 2-固定座
  - 4-下軸承 (子零件範例)
    * 4-P-1
---BOM_END---
[知識領域三元組 Context]
{context}

[使用者問題 Question]
{question}

[極簡精確回答 (禁止開場白與廢話)]："""

# 自我驗證用 Prompt
VERIFY_PROMPT = """你是一位極度嚴格的「公差與架構查核員」。
下方提供了【原始的依據 (知識庫)】以及【AI 第一次撰寫的草稿】。
你的任務是「交叉比對」草稿中的每一個項目，並進行無情的除錯與修正。

[絕對查核清單]：
1. 零件查核：草稿中的「零件名稱」是否真的存在於知識庫中？(若無，請無情刪除)
2. 特徵面查核：草稿中的「特徵面」是否正確歸屬於該零件？(若放錯層級，請修正)
3. 公差防幻覺查核：草稿中 () 與 [] 內的公差，是否在知識庫中有被該特徵面明確參照？(絕對禁止發明公差，只要知識庫沒提到的公差，請全部刪除)

請輸出「修正過後」的最終回答。
如果草稿中包含 `---BOM_START---` 與 `---BOM_END---`，請在修正後依然使用這兩個標籤包覆架構表。

【原始的依據 (知識庫)】:
{context}

【AI 第一次撰寫的草稿】:
{draft}

[嚴格修正後的最終回答]:"""

# ------------------------------------------------------------------------
# [KG-RAG 核心架構]
# ------------------------------------------------------------------------
_graph = None
_communities = {}
_embedder = None
_faiss_index = None
_edge_mapping = []
_llm_cache = {}

def init_knowledge_graph():
    """初始化 NetworkX 圖譜與 FAISS 向量索引"""
    global _graph, _communities, _embedder, _faiss_index, _edge_mapping
    
    if _graph is not None:
        return
        
    print("⏳ 正在初始化本地知識庫 (建立 NetworkX 圖譜與向量索引)...")
    _graph = nx.DiGraph()
    triplets = get_knowledge_triplets('ontology_export.csv')
    
    if not triplets:
        print("[ERROR] 無法讀取本地知識庫。")
        return
        
    # 1. 建立真實圖譜結構
    for subject, relation, obj in triplets:
        subject_part = subject.split('-')[0] if '-' in str(subject) else subject
        obj_part = obj.split('-')[0] if '-' in str(obj) else obj
        
        _graph.add_node(subject, parent_part=subject_part)
        _graph.add_node(obj, parent_part=obj_part)
        _graph.add_edge(subject, obj, relation=relation)
        
    # 2. 建立社群摘要 (Community Summaries - 離線階段)
    parts = set(nx.get_node_attributes(_graph, 'parent_part').values())
    for part in parts:
        summary_lines = [f"【中心組件】 [{part}] 的層級與關聯資訊："]
        
        # 尋找所有與該零件相關的邊 (不再受限於 subgraph 內部)
        for u, v, data in _graph.edges(data=True):
            u_part = _graph.nodes[u].get('parent_part')
            v_part = _graph.nodes[v].get('parent_part')
            rel = data['relation']
            
            if u_part == part or v_part == part:
                # 轉換為容易理解的 Context
                if rel in ['ns0__具有特徵面', 'ns0__包含特徵面', 'ns0__具有特徵']:
                    summary_lines.append(f"  └─ 零件 「{u}」 具有特徵面 -> {v}")
                elif rel in ['ns0__有零件', 'ns0__包含零件']:
                    summary_lines.append(f"  ├─ [組合件結構] 「{u}」 包含子零件 -> {v}")
                elif rel == 'ns0__交互參考公差作用於':
                    summary_lines.append(f"  └─ [跨零件公差要求] 此公差交互作用於 -> {v} 特徵面")
                elif rel == 'ns0__個別參考公差作用於':
                    summary_lines.append(f"  └─ [局部限制] 特徵面 「{v}」 具有個別公差 -> {u}")
                else:
                    summary_lines.append(f"  - ({u}) --[{rel}]--> ({v})")
        
        # 移除重複行並存入摘要
        _communities[part] = "\n".join(list(dict.fromkeys(summary_lines)))

    # 3. 向量嵌入 (Vector Embedding) - 改用 Ollama
    print("[WAIT] 嘗試透過 Ollama 載入語意模型 (nomic-embed-text) ...")
    try:
        import ollama
        # 測試 Ollama 是否有此模型
        try:
            ollama.show('nomic-embed-text')
            _embedder = 'ollama'  # 使用標記
        except Exception:
            print("[WARN] Ollama 未安裝 'nomic-embed-text'，嘗試拉取中...")
            try:
                ollama.pull('nomic-embed-text')
                _embedder = 'ollama'
            except Exception as e:
                print(f"[ERROR] 無法拉取模型: {e}")
                _embedder = None
    except Exception as e:
        print(f"[ERROR] Ollama 套件匯入錯誤或連線失敗: {e}")
        _embedder = None

    if _embedder != 'ollama':
        try:
            from sentence_transformers import SentenceTransformer
            print("[WAIT] 退回使用 sentence-transformers 本地模型...")
            _embedder = SentenceTransformer('shibing624/text2vec-base-chinese')
        except Exception as e:
            print(f"[WARN] 無法載入本地模型。錯誤: {e}")
            _embedder = None
    texts = []
    _edge_mapping = []
    for u, v, data in _graph.edges(data=True):
        text = f"{u} 的 {data['relation']} 是 {v}"
        texts.append(text)
        _edge_mapping.append((u, v))
        
    print(f"[WAIT] 正在對 {len(texts)} 筆關聯進行向量化...")
    embeddings_list = []
    if _embedder == 'ollama':
        import ollama
        for txt in texts:
            resp = ollama.embeddings(model='nomic-embed-text', prompt=txt)
            embeddings_list.append(resp['embedding'])
    elif _embedder is not None:
        embeddings_list = _embedder.encode(texts).tolist()
    else:
        print("[ERROR] 無可用的向量化工具，關聯搜尋將不可用。")
        return
        
    embeddings = np.array(embeddings_list, dtype=np.float32)
    _faiss_index = faiss.IndexFlatL2(embeddings.shape[1])
    _faiss_index.add(np.array(embeddings))
    print(f"[SUCCESS] 知識圖譜載入完成！共提取 {len(triplets)} 條關聯。")

def enhanced_graph_retrieval(question, is_global=False, top_k=6, k_hop=1):
    """
    基於問題動態檢索圖譜上下文。
    """
    if _graph is None:
        init_knowledge_graph()
        if _graph is None:
            return "[ERROR] 知識圖譜初始化失敗。"
        
    if is_global:
        # 回答全域結構查詢
        return "\n\n".join(_communities.values())
        
    # Local Search
    if _embedder is None or _faiss_index is None:
        return "[ERROR] 語意模型初始化失敗，無法進行圖譜檢索。"

    # 1. 向量檢索 (Vector Search)
    if _embedder == 'ollama':
        import ollama
        resp = ollama.embeddings(model='nomic-embed-text', prompt=question)
        query_emb = np.array([resp['embedding']], dtype=np.float32)
    else:
        query_emb = _embedder.encode([question])  # type: ignore
        
    D, indices = _faiss_index.search(query_emb, top_k)  # type: ignore
    
    # 2. 關鍵字助推器 (Keyword Booster) - 特別針對 Windows 上的中文子字串
    # 如果使用者問 "上軸承"，我們也應該找出名為 "6-上軸承" 的節點
    potential_nodes = set()
    for node in _graph.nodes():
        if str(node) in question or question in str(node):
            potential_nodes.add(node)
            
    retrieved_subgraph = nx.DiGraph()
    
    # 加入向量檢索到的邊
    for idx_list in indices:
        for idx in idx_list:
            if idx == -1 or idx >= len(_edge_mapping):
                continue
            u, v = _edge_mapping[idx]
            potential_nodes.add(u)
            potential_nodes.add(v)

    # 3. 擴展節點 (k-hop expansion)
    for node in potential_nodes:
        if node not in _graph:
            continue
        neighbors = list(nx.single_source_shortest_path_length(_graph.to_undirected(), node, cutoff=k_hop).keys())  # type: ignore
        for neighbor in neighbors:
            if _graph.has_edge(node, neighbor):  # type: ignore
                retrieved_subgraph.add_edge(node, neighbor, relation=_graph[node][neighbor]['relation'])  # type: ignore
            if _graph.has_edge(neighbor, node):  # type: ignore
                retrieved_subgraph.add_edge(neighbor, node, relation=_graph[neighbor][node]['relation'])  # type: ignore
                    
    if not retrieved_subgraph.edges():
        return "在知識庫中找不到與「" + question + "」直接相關的圖譜資訊。"

    context_lines = ["【以下是精準檢索出的相鄰圖譜關聯結構 (Tree Structure)】："]
    for u, v, data in retrieved_subgraph.edges(data=True):
        rel = data['relation']
        if rel in ['ns0__具有特徵面', 'ns0__包含特徵面', 'ns0__具有特徵']:
             context_lines.append(f"【零件】{u}\n  └─【特徵面】{v} [Data: Graph ({u}, {v})]")
        elif rel in ['ns0__交互參考公差作用於']:
             context_lines.append(f"【公差要求】{u}\n  └─ [跨零件/特徵面指向] 作用於 -> {v} [Data: Graph ({u}, {v})]")   
        elif rel in ['ns0__個別參考公差作用於']:
             context_lines.append(f"【特徵面】{v}\n  └─ [自身限制] 具有個別公差 -> {u} [Data: Graph ({u}, {v})]") 
        else:
             context_lines.append(f"({u}) --[{rel}]--> ({v}) [Data: Graph ({u}, {v})]")
             
    # 額外安全性：如果沒有抓到任何東西，回傳空字串讓 LLM 觸發找不到資料的回答
    return "\n".join(context_lines)

def get_graph_rag_response(question, model_name="llama3.1:8b", base_url="http://localhost:11434", history=None):
    """
    提供給 Web UI (ai_app.py) 呼叫的函式，支援動態切換模型與 URL
    使用本地 CSV + NetworkX + FAISS 建立 Hybrid Topology RAG
    """
    
    # 1. 載入並快取知識庫 Context
    init_knowledge_graph()
    if _graph is None:
        return "[ERROR] 無法初始化知識圖譜。請檢查資料。"

    cache_key = f"{model_name}_{base_url}"
    import ollama
    
    # 2. 初始化 LLM Client
    if cache_key not in _llm_cache:
        print(f"⏳ 正在準備連線到 Ollama (URL: {base_url}) ...")
        try:
            client = ollama.Client(host=base_url)
            _llm_cache[cache_key] = client
        except Exception as e:
            return f"[ERROR] Ollama 連線失敗: {e}"
            
    # 3. 呼叫模型推論
    try:
        client = _llm_cache[cache_key]
        
        # 判斷是否為「全域結構查詢」
        global_intent_keywords = ["架構", "結構", "bom", "清單", "所有零件"]
        is_global_query = any(kw.lower() in question.lower() for kw in global_intent_keywords)
        
        # 執行加強版的混合式圖譜搜尋 (Hybrid Topology RAG)
        filtered_context = enhanced_graph_retrieval(question, is_global=is_global_query, top_k=6, k_hop=1)
        
        # 💡 【擴增】：將「動態機台報表」與圖譜資訊合併
        global _latest_machine_report
        if _latest_machine_report:
            filtered_context = f"【🔥 近期使用者剛產生的機台媒合報表，請務必參考此表的規格與評分】：\n{_latest_machine_report}\n\n====================\n\n{filtered_context}"
            
        # 加上對話歷史紀錄 (History)
        if history:
            history_text = "\n".join([f"{'User' if msg.get('role') == 'user' else 'Assistant'}: {msg.get('content')}" for msg in history])
            filtered_context = f"【近期對話上下文 History】(使用者剛才與你的對話，可能包含他現在用代名詞指稱的對象)：\n{history_text}\n\n====================\n\n{filtered_context}"
            
        print(f"[SEARCH] KG-RAG 過濾: 使用 {'Global Community 摘要' if is_global_query else 'Vector Search + k-hop 圖譜相鄰擴展'}")
        
        final_prompt = QA_PROMPT.format(
            context=filtered_context, 
            question=question
        )
        print(f"[AI] AI ({model_name}) 正在依據本地知識庫推論中【第一階段：生成草稿】...")
        
        response = client.generate(
            model=model_name,
            prompt=final_prompt,
            options={
                "temperature": 0.0,
                "num_ctx": 8192
            }
        )
        draft_result = response.get('response', '')
        
        # 避免模型只回傳空白導致前端報錯
        if not draft_result or not draft_result.strip():
            return "在知識庫中找不到相關資料。"
            
        # -------------------------------------------------------------------
        # 優化：單次推論 (Single-pass generated)
        # 由於已將驗證邏輯與嚴格防幻覺指令合併至 QA_PROMPT 中，此處直接回傳，以大幅減少等待時間 (延遲減半)。
        # -------------------------------------------------------------------
        return draft_result
            
        return draft_result
    except Exception as e:
        return f"[ERROR] GraphRAG 推論過程發生錯誤: {e}"

def chat_with_graph_rag():
    print("\n==================================")
    print("=== 公差 GraphRAG (本地CSV版) 啟動 ===")
    print("==================================")
    print("您可以問例如：『精密迴轉滑台包含哪些零件？』")
    print("輸入 'exit' 離開\n")
    
    while True:
        question = input("User 提問: ")
        if question.lower() in ['exit', 'quit']:
            break
            
        print("\n[AI] 查詢中... (請稍候)\n")
        response = get_graph_rag_response(question)
        print(f"\n[SUCCESS] AI 最終結論: \n{response}\n")
        print("-" * 50)

if __name__ == "__main__":
    chat_with_graph_rag()
