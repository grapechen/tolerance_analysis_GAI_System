import time

# --- 1. 定義資料庫 (資料寫死在程式裡，不用讀檔) ---
fits_database = [
    {'type': '留隙配合', 'function': '精確定位', 'shaft': 'H5', 'hole': 'g4', 'ansi': 'RC1', 'note': '運轉和滑動'},
    {'type': '留隙配合', 'function': '定溫', 'shaft': 'H6', 'hole': 'g5', 'ansi': 'RC2', 'note': '運轉和滑動'},
    {'type': '留隙配合', 'function': '低轉速 低軸頸壓力', 'shaft': 'H7', 'hole': 'f6', 'ansi': 'RC3', 'note': '運轉和滑動'},
    {'type': '留隙配合', 'function': '中轉速 中軸頸壓力', 'shaft': 'H8', 'hole': 'f7', 'ansi': 'RC4', 'note': '運轉和滑動'},
    {'type': '留隙配合', 'function': '溫差大 高轉速 高軸頸壓力', 'shaft': 'H8', 'hole': 'e7', 'ansi': 'RC5', 'note': '運轉和滑動'},
    {'type': '留隙配合', 'function': '溫差大 高轉速 高軸頸壓力', 'shaft': 'H9', 'hole': 'e8', 'ansi': 'RC6', 'note': '運轉和滑動'},
    {'type': '留隙配合', 'function': '溫差大 精度不高', 'shaft': 'H9', 'hole': 'd8', 'ansi': 'RC7', 'note': '運轉和滑動'},
    {'type': '留隙配合', 'function': '大公差', 'shaft': 'H10', 'hole': 'c9', 'ansi': 'RC8', 'note': '運轉和滑動'},
    {'type': '留隙配合', 'function': '大公差', 'shaft': 'H11', 'hole': 'c11', 'ansi': 'RC9', 'note': '運轉和滑動'},
    {'type': '留隙配合', 'function': '定位 可裝拆', 'shaft': 'H6', 'hole': 'h5', 'ansi': 'LC1', 'note': '滑動'},
    {'type': '留隙配合', 'function': '定位 可裝拆', 'shaft': 'H7', 'hole': 'h6', 'ansi': 'LC2', 'note': '滑動'},
    {'type': '過渡配合', 'function': '定位 可裝拆', 'shaft': 'H7', 'hole': 'j6', 'ansi': 'LT1', 'note': '輕推'},
    {'type': '過渡配合', 'function': '定位', 'shaft': 'H8', 'hole': 'j7', 'ansi': 'LT2', 'note': '輕推'},
    {'type': '過渡配合', 'function': '準確定位', 'shaft': 'H7', 'hole': 'k6', 'ansi': 'LT3', 'note': '輕打'},
    {'type': '過渡配合', 'function': '準確定位', 'shaft': 'H8', 'hole': 'k7', 'ansi': 'LT4', 'note': '壓入'},
    {'type': '過渡配合', 'function': '準確定位', 'shaft': 'H7', 'hole': 'n6', 'ansi': 'LT5', 'note': '中壓'},
    {'type': '過盈配合', 'function': '剛性 對準', 'shaft': 'H7', 'hole': 'p6', 'ansi': 'LN2', 'note': '重壓'},
    {'type': '過盈配合', 'function': '壓力小 堅固', 'shaft': 'H6', 'hole': 'n5', 'ansi': 'FN1', 'note': '重壓'},
    {'type': '過盈配合', 'function': '壓力小 堅固', 'shaft': 'H6', 'hole': 'p5', 'ansi': 'FN1', 'note': '重壓'},
    {'type': '過盈配合', 'function': '鑄鐵配合使用', 'shaft': 'H7', 'hole': 's6', 'ansi': 'FN2', 'note': '重壓'},
    {'type': '過盈配合', 'function': '壓力大', 'shaft': 'H7', 'hole': 't6', 'ansi': 'FN3', 'note': '重壓'},
    {'type': '過盈配合', 'function': '高應力', 'shaft': 'H7', 'hole': 'u6', 'ansi': 'FN4', 'note': '重壓'},
    {'type': '過盈配合', 'function': '高應力', 'shaft': 'H8', 'hole': 'x7', 'ansi': 'FN5', 'note': '重壓'}
]

# --- 2. 搜尋核心功能 ---
def search_fits(keywords):
    results = []
    # 遍歷資料庫
    for item in fits_database:
        # 將該行的所有資訊拼成一個字串方便檢查
        row_text = f"{item['type']} {item['function']} {item['note']}"
        
        # 檢查是否所有關鍵字都吻合
        is_match = True
        for k in keywords:
            if k not in row_text:
                is_match = False
                break
        
        if is_match:
            results.append(item)
    return results

# --- 3. 主程式：互動輸入欄 ---
def main():
    print("="*50)
    print("🛠️  工程公差配合查詢系統 (輸入 'q' 離開) 🛠️")
    print("="*50)
    
    while True:
        # 這裡就是製作「輸入欄」的關鍵指令 input()
        user_input = input("\n請輸入查詢關鍵字 (多個關鍵字請用空白隔開) > ")
        
        # 檢查是否要離開
        if user_input.lower() in ['q', 'exit', 'quit']:
            print("程式結束，掰掰！")
            break
            
        if not user_input.strip():
            continue # 如果沒輸入東西就按 Enter，重來
            
        # 切割輸入字串 (例如 "定位 過渡" -> ["定位", "過渡"])
        keywords = user_input.strip().split()
        
        print(f"正在尋找同時包含 {keywords} 的規格...")
        found_items = search_fits(keywords)
        
        if found_items:
            print(f"--> 找到 {len(found_items)} 筆結果：")
            print("-" * 60)
            print(f"{'ANSI':<6} | {'孔':<4} / {'軸':<4} | {'類型':<8} | {'功能需求'}")
            print("-" * 60)
            for item in found_items:
                # 格式化輸出
                print(f"{item['ansi']:<6} | {item['shaft']:<4} / {item['hole']:<4} | {item['type']:<8} | {item['function']} ({item['note']})")
        else:
            print("❌ 找不到符合條件的資料，請換個關鍵字試試。")

if __name__ == "__main__":
    main()