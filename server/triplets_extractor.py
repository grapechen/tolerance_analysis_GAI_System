import pandas as pd
import re
import os

def extract_display_name(node_str):
    """從 Neo4j 匯出的節點字串中提取 display 屬性值"""
    if not isinstance(node_str, str):
        return str(node_str)
    
    # 找尋 display: 後面的字串，直到遇到逗號或右大括號
    match = re.search(r'display:\s*([^,}]+)', node_str)
    if match:
        return match.group(1).strip()
    return node_str

def extract_relationship(rel_str):
    """清理關係字串"""
    if not isinstance(rel_str, str):
        return str(rel_str)
    # 移除中括號與冒號，例如 [:rdfs__subClassOf] -> rdfs__subClassOf
    return rel_str.strip('[]:')

def get_knowledge_triplets(csv_filename='0213_export.csv'):
    """讀取 CSV 並回傳清理後的三元組列表"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(current_dir, 'data', csv_filename)
    
    print(f"📂 正在讀取知識圖譜檔案: {csv_path}")
    
    if not os.path.exists(csv_path):
        print("❌ 找不到 CSV 檔案")
        return []
    
    df = None
    # 嘗試多種常見編碼
    for enc in ['utf-8-sig', 'utf-8', 'big5', 'cp950', 'gbk']:
        try:
            df = pd.read_csv(csv_path, encoding=enc, on_bad_lines='skip')
            print(f"✅ 成功解碼！(編碼格式: {enc})")
            break
        except Exception:
            pass
            
    if df is None:
        print("❌ 無法讀取 CSV 檔案，請確認檔案編碼格式！")
        return []

    triplets = []
    # 確保所需欄位存在
    if not {'n', 'r', 'm'}.issubset(df.columns):
        print("❌ CSV 缺少必要的 'n', 'r', 'm' 欄位。包含的欄位為:", df.columns.tolist())
        return []

    # 用 Set 紀錄已經加入的節點屬性，避免重複
    extracted_properties = set()

    def extract_node_properties(node_str, subject_name):
        """從節點字串中提取其他重要屬性，如 rdfs:comment (定義) 與隱含的實體類別"""
        if not isinstance(node_str, str) or not subject_name:
            return
            
        # 提取 rdfs__comment
        comment_match = re.search(r'rdfs__comment:\s*([^,}]+)', node_str)
        if comment_match:
            comment = comment_match.group(1).strip().strip("'\"") # 去除頭尾可能有的引號
            if comment:
                # 建立虛擬三元組: (主體, '定義', 內容)
                prop_tuple = (subject_name, '定義', comment)
                if prop_tuple not in extracted_properties:
                    extracted_properties.add(prop_tuple)
                    triplets.append(prop_tuple)
                    
        # 特殊處理：OWL 本體論中，NamedIndividual 的類別會直接寫在節點標籤裡
        # 範例: (:Resource:ns0__垂直度公差:owl__NamedIndividual {display: '7-Per-1'})
        # 如果這個節點是一個 Individual，我們要把它的 ns0__ 抽出來當作 "是" 關係
        if 'owl__NamedIndividual' in node_str or 'NamedIndividual' in node_str:
            class_match = re.search(r'ns0__([A-Za-z0-9_\u4e00-\u9fa5]+)', node_str)
            if class_match:
                class_name = class_match.group(1)
                # 建立虛擬分類三元組: ('7-Per-1', '屬於', '垂直度公差')
                type_tuple = (subject_name, '屬於', class_name)
                if type_tuple not in extracted_properties:
                    extracted_properties.add(type_tuple)
                    triplets.append(type_tuple)

    for index, row in df.iterrows():
        n_str = str(row['n'])
        r_str = str(row['r'])
        m_str = str(row['m'])
        
        # 若為空值或 NaN 則全行跳過
        if pd.isna(row['n']) or pd.isna(row['r']) or pd.isna(row['m']):
            continue
            
        subject = extract_display_name(n_str)
        predicate = extract_relationship(r_str)
        obj = extract_display_name(m_str)
        
        # 即使欄位解析失敗，也嘗試抓取節點自帶的定義 (rdfs__comment)
        if subject:
            extract_node_properties(n_str, subject)
        if obj:
            extract_node_properties(m_str, obj)
            
        # 加入原本的關聯三元組
        if subject and obj and predicate:
            rel_tuple = (subject, predicate, obj)
            if rel_tuple not in extracted_properties:
                extracted_properties.add(rel_tuple)
                triplets.append(rel_tuple)
        
    return triplets

def build_triplets_context(triplets):
    """將三元組清單轉為供 LLM 讀取的文字 Context"""
    context_lines = []
    for s, p, o in triplets:
        # 可以依據 predicate 把它轉為更自然的中文句子，預設用簡單連接
        if p == 'rdfs__subClassOf':
            context_lines.append(f"「{s}」是「{o}」的一種。")
        elif p == 'ns0__具有零件' or p == 'ns0__包含零件':
            context_lines.append(f"「{s}」包含零件「{o}」。")
        elif p == 'ns0__個別參考公差作用於':
            context_lines.append(f"特徵面「{o}」具有個別參考公差「{s}」。")
        elif p == 'ns0__交互參考公差作用於':
            context_lines.append(f"「{s}」是作用於特徵面「{o}」的交互參考公差。")
        elif p == 'ns0__適用':
            context_lines.append(f"「{s}」適用於「{o}」。")
        else:
            # 預設組合
            context_lines.append(f"「{s}」與「{o}」的關係是：{p}。")
            
    return "\n".join(context_lines)

if __name__ == "__main__":
    triplets = get_knowledge_triplets()
    print(f"\n📊 總共提取了 {len(triplets)} 個知識三元組")
    print("\n🔍 前 10 個三元組範例：")
    for t in triplets[:10]:
        print(f" - 主體: {t[0]:<15} | 關係: {t[1]:<20} | 客體: {t[2]}")
        
    print("\n📝 轉為 LLM Context 範例 (前 5 句):")
    context_str = build_triplets_context(triplets[:5])
    print(context_str)
