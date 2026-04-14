import os
import re

def merge_html_template():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ref_path = os.path.join(base_dir, "參考.txt")
    target_path = os.path.join(base_dir, "ai_app.py")
    
    # 讀取參考檔 (提取完整的 2400行 HTML_TEMPLATE)
    with open(ref_path, "r", encoding="utf-8") as f:
        ref_text = f.read()
        
    # regex 擷取包含前後 """ 的 HTML_TEMPLATE 變數
    # .*? 會比對非貪婪的內容，要求到最尾端的 </html>\n""" 為止
    ref_match = re.search(r'HTML_TEMPLATE\s*=\s*(?:""")[\s\S]*?(?:""")', ref_text)
    
    if not ref_match:
        print("❌ 無法在 參考.txt 中找到 HTML_TEMPLATE 區塊！")
        return
    full_html_block = ref_match.group(0)
    
    # 讀取目前的 ai_app.py (被截斷的版本)
    with open(target_path, "r", encoding="utf-8") as f:
        target_text = f.read()
        
    target_match = re.search(r'HTML_TEMPLATE\s*=\s*(?:""")[\s\S]*?(?:""")', target_text)
    if not target_match:
        print("❌ 無法在 ai_app.py 中找到被截斷的 HTML_TEMPLATE 區塊！")
        return
        
    # 執行無縫整合：抽換字串
    print("🔄 正在整合 D槽(參考.txt) 完整的前端渲染邏輯，保留 C槽(ai_app.py) 最新的後端 API...")
    merged_text = target_text[:target_match.start()] + full_html_block + target_text[target_match.end():]
    
    # 備份原本的 ai_app.py
    backup_path = os.path.join(base_dir, "ai_app_backup.py")
    with open(backup_path, "w", encoding="utf-8") as f:
        f.write(target_text)
    print(f"📦 已備份目前的 ai_app.py 為 ai_app_backup.py")
    
    # 寫入整合後的新版本
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(merged_text)
        
    print("✅ 整合完成！產品架構圖、網格、綠線接觸與公差網路邏輯已滿血回歸！")

if __name__ == "__main__":
    merge_html_template()
