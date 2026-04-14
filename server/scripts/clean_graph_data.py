import csv
import re

# 定義輸入與輸出檔案
INPUT_FILE = 'server/data/ontology_export.csv'
OUTPUT_FILE = 'server/data/ontology_export_cleaned.csv'

# 要刪除的 Meta-nodes 關鍵字 (對應建議 1)
# 這些是 OWL/RDF 本體的架構節點，對 RAG 實質問答無幫助
meta_node_keywords = [
    'owl__DatatypeProperty', 
    'owl__ObjectProperty', 
    'owl__Ontology',
    'owl__NamedIndividual',
    'owl__Restriction',
    'owl__Axiom',
    'owl__Class' # 我們保留實質的 Class 屬性，但如果是純定義 meta 的則看情況，這裡先不全擋，用正則過濾內容
]

def clean_uri(text):
    """
    清理冗長無用的 URI 前綴 (Namespace) (對應建議 2)
    將類似 http://www.semanticweb.org/...#尺寸 轉換為 '尺寸'
    """
    if not text:
        return text
    # 找尋 '#' 後面的字串，直到遇到單引號、雙引號、大括號或分隔符號
    # 這是針對 Neo4j cypher dump 格式的清理
    cleaned = re.sub(r"http://[^\s'\"#,]+#([^'\",}]+)", r"\1", text)
    
    # 也順便清理 Neo4j 匯出格式裡的 ns0__ 之類的前綴
    cleaned = re.sub(r"ns\d+__", "", cleaned)
    return cleaned

def is_meta_node(row_str):
    """判斷整行是否包含要過濾的 meta node 標籤"""
    for keyword in meta_node_keywords:
        if keyword in row_str:
            # 特例：如果是 owl__Class 但裡面有包 rdfs__label 或 rdfs__comment，代表這是實質知識概念，必須保留！
            if keyword == 'owl__Class' and ('rdfs__label' in row_str or 'rdfs__comment' in row_str):
                return False
            return True
    return False

def process_csv():
    print(f"⏳ 開始清理知識圖譜匯出檔：{INPUT_FILE}")
    
    try:
        # 為了處理可能的編碼問題，直接用讀取字串的方式處理
        with open(INPUT_FILE, 'r', encoding='utf-8', errors='ignore') as infile, \
             open(OUTPUT_FILE, 'w', encoding='utf-8', newline='') as outfile:
            
            # 使用 CSV 模組處理
            reader = csv.reader(infile)
            writer = csv.writer(outfile)
            
            headers = next(reader, None)
            if headers:
                writer.writerow(headers)
            
            count_total = 0
            count_kept = 0
            count_removed = 0
            
            for row in reader:
                if not row:
                    continue
                count_total += 1
                row_str = ",".join(row)
                
                # 執行 1：判斷是否為 Meta-node 並過濾
                # (注意：使用者說保留 3、4，所以我們不過濾 owl:disjointWith 和無 comment 的節點)
                if is_meta_node(row_str):
                    count_removed += 1
                    continue
                
                # 執行 2：清理 URI 前綴
                cleaned_row = [clean_uri(cell) for cell in row]
                
                writer.writerow(cleaned_row)
                count_kept += 1
                
        print("\n✅ 清理完成！")
        print(f"📊 總處理筆數: {count_total}")
        print(f"🗑️ 已刪除 Meta-nodes (要求 1): {count_removed} 筆")
        print(f"💾 剩餘保留並清理 URI 後的筆數 (要求 2): {count_kept} 筆")
        print(f"\n📂 已儲存為全新乾淨檔案: {OUTPUT_FILE}")
        print("💡 您可以將這個 _cleaned.csv 重新匯入 Neo4j，GraphRAG 的負擔將大幅減輕！")

    except Exception as e:
        print(f"❌ 發生錯誤: {e}")

if __name__ == "__main__":
    process_csv()
