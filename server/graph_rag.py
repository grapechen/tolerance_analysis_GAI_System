import os
import re
import ollama

# 從我們先前寫好的腳本引入本地知識三元組提取器
from triplets_extractor import get_knowledge_triplets, build_triplets_context

# 全域變數，暫存最新一筆的「純文字」機台媒合報表
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
2. 仔細閱讀 Context 中的句子，這是從知識圖譜中萃取出來的關聯。
3. 如果使用者問的問題在 Context 中找不到直接或間接的關聯，請直接回答：「在知識庫中找不到相關資料。」，絕對不要自己編造答案。
4. 回答請保持簡潔專業，並以繁體中文回覆。
5. **嚴禁補充說明 (Anti-Yapping)**：當使用者詢問產品結構、零件或特徵面時，請「只」輸出對應的清單。絕對禁止在清單之後補充任何 Markdown 表格、名詞定義、常識解釋或「小結」。

[✨進階結構指令✨]：
請根據使用者的問題，決定輸出的「詳細程度」：
1. **只問零件**：如果使用者問「包含哪些零件」，請只列出主要零件 (-)。絕對不要列出特徵面或公差。
2. **問特徵面**：如果使用者明確要求「特徵面」，請在零件下方列出特徵面 (*)。**絕對不要加上任何公差括號**。
3. **問公差/網路圖/細節**：如果使用者明確問「公差」或「公差網路圖」，請在特徵面後方加上公差：
   - 個別參考公差用小括號：`(公差名稱)`
   - 交互參考公差用中括號：`[公差名稱]`
[✨診斷與檢查模式✨]：
如果使用者是要「檢查」、「確認」或詢問某個零件/特徵/公差是否「缺少」、「漏掉」，請啟動【診斷模式】：
1. 仔細比對使用者提到的項目與 Context 內的實際紀錄。
2. 若使用者提到的項目在知識庫有找到，請明確回答「存在」或「正確」，並列出相關細節。
3. 若使用者提到的項目在知識庫「找不到」，請明確回答「根據目前知識庫記載，確實缺少 / 未發現該特徵面或公差」。
4. 診斷模式的回答請說明理由，此時**不需要**輸出 `---BOM_START---` 架構表，除非使用者同時要求畫出架構圖。

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

# 快取機制
_triplets_context_cache = None
_llm_cache = {}

def get_graph_rag_response(question, model_name="llama3.1:8b", base_url="http://localhost:11434"):
    """
    提供給 Web UI (ai_app.py) 呼叫的函式，支援動態切換模型與 URL
    使用本地 CSV 取代 Neo4j
    """
    global _triplets_context_cache
    
    # 1. 載入並快取知識庫 Context
    if _triplets_context_cache is None:
        print("⏳ 正在初始化本地知識庫 (讀取 0213_export.csv)...")
        # 取得當前檔案所在目錄的絕對路徑
        current_dir = os.path.dirname(os.path.abspath(__file__))
        csv_path = os.path.join(current_dir, 'data', '0213_export.csv')
        
        triplets = get_knowledge_triplets('0213_export.csv')
        if not triplets:
            return "❌ 無法讀取本地知識庫 (0213_export.csv)，請確認檔案存在且路徑正確。"
        _triplets_context_cache = build_triplets_context(triplets)
        print(f"✅ 知識庫載入完成！共提取 {len(triplets)} 條關聯。")

    cache_key = f"{model_name}_{base_url}"
    
    # 2. 初始化 LLM Client
    if cache_key not in _llm_cache:
        print(f"⏳ 正在準備連線到 Ollama (URL: {base_url}) ...")
        try:
            client = ollama.Client(host=base_url)
            _llm_cache[cache_key] = client
        except Exception as e:
            return f"❌ Ollama 連線失敗: {e}"
            
    # 3. 呼叫模型推論
    try:
        client = _llm_cache[cache_key]
        
        # --- Smart RAG 過濾器 ---
        # 建立常見的機構公差與零件字典，若題目有出現就加入關鍵字
        domain_dict = ["底座", "滑台", "螺桿", "導軌", "平台", "蝸輪", "蝸桿", "軸承", "軸", "交互參考", "平行度", "垂直度", "同心度", "圓柱度", "輪廓度", "距離", "位置", "特徵", "零件", "配合", "基準", "公差", "交互", "確認", "檢查", "缺少", "漏掉", "機台", "加工", "推薦", "精度", "定位", "重現", "製程", "車床", "銑床", "五軸", "立式", "臥式", "龍門", "搪銑", "鑽孔", "亞崴", "東台", "永進", "AWEA", "Tongtai", "YCM", "迴轉", "螺帽", "間隔", "固定座", "上板"]
        keywords = [word for word in domain_dict if word in question]
        
        # 若是英文或數字型號 (如 1-底座)
        eng_num_keywords = re.findall(r'[a-zA-Z0-9]+', question)
        keywords.extend(eng_num_keywords)
        
        # 移除太短的或重複的
        keywords = list(set([k for k in keywords if len(k) >= 2]))
        
        all_lines = _triplets_context_cache.split('\n')
        relevant_lines = []
        
        # 確保組合件本身一定會被包含
        assembly_keywords = ["精密迴轉滑台", "滑台", "組合件"]
        
        for line in all_lines:
            line_lower = line.lower()
            if not line.strip():
                continue
            # 若有命中任何關鍵字，或包含組合件關鍵字，就留下來
            if any(k.lower() in line_lower for k in keywords) or any(ak.lower() in line_lower for ak in assembly_keywords):
                relevant_lines.append(line)
        
        # 如果過濾後什麼都沒找到，就把整份知識庫丟進去 (fallback)
        filtered_context = "\n".join(relevant_lines)
        if not relevant_lines:
            # fallback: 把整份知識庫丟給 LLM，讓它自己從中找答案
            # 這比回傳空字串 (導致「找不到」) 更有用
            filtered_context = _triplets_context_cache
            
        # 💡 【核心修改】：將「動態機台報表」與 CSV 圖譜資訊完美合併
        global _latest_machine_report
        if _latest_machine_report:
            filtered_context = f"【🔥 近期使用者剛產生的機台媒合報表，請務必參考此表的規格與評分】：\n{_latest_machine_report}\n\n====================\n\n【圖譜既有公差知識】：\n{filtered_context}"
            
        print(f"🕵️ Smart RAG 過濾: 找到 {len(relevant_lines)} 條相關資料 (原 {len(all_lines)} 條) " + ("(包含機台報表注入)" if _latest_machine_report else ""))
        
        final_prompt = QA_PROMPT.format(
            context=filtered_context, 
            question=question
        )
        print(f"🤖 AI ({model_name}) 正在依據本地知識庫推論中【第一階段：生成草稿】...")
        
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
        return f"❌ GraphRAG 推論過程發生錯誤: {e}"

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
            
        print("\n🤖 查詢中... (請稍候)\n")
        response = get_graph_rag_response(question)
        print(f"\n✅ AI 最終結論: \n{response}\n")
        print("-" * 50)

if __name__ == "__main__":
    chat_with_graph_rag()
