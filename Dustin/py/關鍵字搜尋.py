# --- 1. 定義資料庫  ---
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

# --- 2. 搜尋功能函數 ---
def search_fits(keywords):
    """
    輸入關鍵字列表，回傳符合的配合資料。
    """
    results = []
    
    # 如果輸入只有一個字串，轉成列表
    if isinstance(keywords, str):
        keywords = [keywords]

    print(f"\n🔍 正在搜尋包含 {keywords} 的規格...\n" + "-"*40)
    
    # 遍歷資料庫中的每一筆資料
    for item in fits_database:
        # 檢查每一個關鍵字是否都在這一筆資料的某些欄位中出現
        row_text = f"{item['type']} {item['function']} {item['note']}"
        
        # 判斷邏輯：所有關鍵字都要吻合 (AND 邏輯)
        is_match = True
        for k in keywords:
            if k not in row_text:
                is_match = False
                break
        
        if is_match:
            results.append(item)
            
    return results

# --- 3. 測試與執行 ---

# 測試 A：找「高速」
found_items = search_fits(["高速"])
for item in found_items:
    print(f"[{item['ansi']}] 孔:{item['shaft']} 軸:{item['hole']} | {item['type']} - {item['function']}")

# 測試 B：找「定位」且「可裝拆」
found_items = search_fits(["定位", "可裝拆"])
for item in found_items:
    print(f"[{item['ansi']}] 孔:{item['shaft']} 軸:{item['hole']} | {item['type']} - {item['function']}")

# 測試 C：找「高應力」
found_items = search_fits(["高應力"])
for item in found_items:
    print(f"[{item['ansi']}] 孔:{item['shaft']} 軸:{item['hole']} | {item['type']} - {item['function']}")