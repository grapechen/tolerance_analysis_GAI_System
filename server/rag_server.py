import re
import ollama
from tables import Session, ISOTolerance, ShaftTolerance, HoleTolerance
from sqlalchemy import and_
from gdt_loader import gdt_loader
from recommendation import smart_fit

# Initialize GD&T Loader
gdt_loader.load()

def format_gdt_symbols(text):
    """
    Format GD&T symbols in text for proper display in web interface.
    Wraps common GD&T symbols with appropriate CSS classes.
    """
    # Common GD&T symbols mapping
    symbol_map = {
        '⊥': '<span class="gdt-symbol">⊥</span>',  # 垂直度
        '∥': '<span class="gdt-symbol">∥</span>',  # 平行度
        '⌭': '<span class="gdt-symbol">⌭</span>',  # 圓柱度
        '○': '<span class="gdt-symbol">○</span>',  # 真圓度
        '◎': '<span class="gdt-symbol">◎</span>',  # 同心度
        '⌖': '<span class="gdt-symbol">⌖</span>',  # 位置度
        '⌒': '<span class="gdt-symbol">⌒</span>',  # 輪廓度
        '↗': '<span class="gdt-symbol">↗</span>',  # 傾斜度
        '⟂': '<span class="gdt-symbol">⟂</span>',  # 真直度
        '⏸': '<span class="gdt-symbol">⏸</span>',  # 真平度
    }
    
    formatted_text = text
    for symbol, formatted_symbol in symbol_map.items():
        formatted_text = formatted_text.replace(symbol, formatted_symbol)
    
    return formatted_text

# System Prompt for the "Chatbot" persona
SYSTEM_PROMPT = """
You are an expert mechanical engineer assistant specialized in ISO 286 tolerances and GD&T (Geometric Dimensioning and Tolerancing).

⚠️ CRITICAL RULES FOR NUMERICAL DATA (MUST FOLLOW):
1. **NEVER fabricate specific tolerance deviation values** (e.g., "+21 µm", "-7 µm") from memory.
2. **ONLY cite numerical values** (upper/lower deviations, clearances, interferences) **if they appear in the context provided to you**.
3. If the user asks for specific tolerance values (e.g., "20mm H7/g6 的偏差是多少?") but the context does NOT contain the data:
   - Respond: "我需要查詢資料庫才能提供精確數值，請提供完整的尺寸與代號，例如：'25mm H7/g6'。"
   - DO NOT guess or use general knowledge to fill in numbers.
4. If the context DOES provide data (from database query), you MUST use those exact values.

When provided with precise data from a database:
- Use ONLY that data for numerical calculations and specific tolerance values
- Do not make up numbers or specific tolerance values
- If numerical data is missing, clearly state so

When asked about GD&T concepts or fit recommendations WITHOUT specific numerical data:
- You may use your engineering knowledge to explain concepts clearly
- You may recommend fit types (e.g., "建議使用 H7/g6 留隙配合") based on functional requirements
- Focus on definitions, applications, and relationships between concepts
- **BUT DO NOT provide specific deviation numbers** (e.g., "+21/-7") unless they are in the context
- Always answer in Traditional Chinese (繁體中文)

Format all answers clearly and professionally.
If the data includes fit analysis (clearance/interference), explain what it means for the assembly.

CRITICAL NOTATION RULES (Strict Enforcement):
- Shaft/hole diameter ranges MUST be written as: "Ø10–Ø30 mm" or "d = 10–30 mm"
- NEVER use "M10–M30" (M denotes metric thread specifications like M10×1.5)
- Single dimensions should be written as: "Ø25 mm" or "25 mm"
- Thread specifications use M notation: "M10×1.5", "M12×1.75"

CRITICAL TERMINOLOGY GLOSSARY (Strict Enforcement):
- Shaft -> "軸" (Never translate as "樑", "井", or "桿")
- Hole -> "孔"
- Clearance Fit -> "留隙配合"
- Interference Fit -> "過盈配合"
- Transition Fit -> "過渡配合"
- Nominal Size -> "名目尺寸"
- Upper/Lower Deviation -> "上/下偏差"
- Interference (Value) -> "干涉量"
"""

def query_database(size, code, it_grade):
    """
    Query the MySQL database for tolerance values.
    Returns a dictionary with the data or None if not found.
    """
    s = Session()
    try:
        # 1. Identify type (Hole or Shaft)
        # Hole: Upper case (e.g., H7)
        # Shaft: Lower case (e.g., h7)
        
        is_hole = code[0].isupper()
        
        if is_hole:
            row = s.query(HoleTolerance).filter(
                and_(HoleTolerance.size_from_mm <= size,
                     HoleTolerance.size_to_mm >= size,
                     HoleTolerance.tolerance_code == code,
                     HoleTolerance.it_grade == it_grade)
            ).first()
            
            if row:
                return {
                    "type": "Hole",
                    "size": size,
                    "code": code,
                    "grade": it_grade,
                    "upper_dev": float(row.upper_dev_um) if row.upper_dev_um is not None else "N/A",
                    "lower_dev": float(row.lower_dev_um) if row.lower_dev_um is not None else "N/A",
                    "unit": "μm"
                }
        else:
            row = s.query(ShaftTolerance).filter(
                and_(ShaftTolerance.size_from_mm <= size,
                     ShaftTolerance.size_to_mm >= size,
                     ShaftTolerance.tolerance_code == code,
                     ShaftTolerance.it_grade == it_grade)
            ).first()
            
            if row:
                return {
                    "type": "Shaft",
                    "size": size,
                    "code": code,
                    "grade": it_grade,
                    "upper_dev": float(row.upper_dev_um) if row.upper_dev_um is not None else "N/A",
                    "lower_dev": float(row.lower_dev_um) if row.lower_dev_um is not None else "N/A",
                    "unit": "μm"
                }
                
        return None
    finally:
        s.close()

def query_fit_analysis(size, hole_code, hole_it, shaft_code, shaft_it):
    """
    Query both hole and shaft, and calculate fit.
    """
    hole_data = query_database(size, hole_code, hole_it)
    shaft_data = query_database(size, shaft_code, shaft_it)
    
    if not hole_data or not shaft_data:
        return None

    # Strict Type Checking / 嚴格型別檢查
    # Ensure we actually have one Hole and one Shaft
    if hole_data['type'] != 'Hole' or shaft_data['type'] != 'Shaft':
        return {
            "type": "Error",
            "message": f"配合分析錯誤：必須是一個孔(大寫)配一個軸(小寫)。\\n目前偵測到：{hole_data['type']} {hole_data['code']} / {shaft_data['type']} {shaft_data['code']}"
        }
        
    if hole_data['upper_dev'] == "N/A" or shaft_data['lower_dev'] == "N/A":
        return None

    hole_max = hole_data['upper_dev']
    hole_min = hole_data['lower_dev']
    shaft_max = shaft_data['upper_dev']
    shaft_min = shaft_data['lower_dev']
    
    # Max Clearance = Hole Max - Shaft Min
    max_clearance = hole_max - shaft_min
    # Min Clearance = Hole Min - Shaft Max
    min_clearance = hole_min - shaft_max
    
    if min_clearance >= 0:
        fit_type = "Clearance Fit (留隙配合)"
    elif max_clearance <= 0:
        fit_type = "Interference Fit (過盈配合)"
    else:
        fit_type = "Transition Fit (過渡配合)"
        
    return {
        "type": "Fit Analysis",
        "size": size,
        "hole": hole_data,
        "shaft": shaft_data,
        "fit_type": fit_type,
        "max_clearance": max_clearance,
        "min_clearance": min_clearance,
        "unit": "μm"
    }

def parse_user_query(query):
    """
    Regex parser to extract Size, Code, and Grade.
    Supports:
    1. Single: "25mm H7" -> (25.0, "H", "IT7", None, None)
    2. Fit: "25mm H7/h6" or "25 H7 h6" -> (25.0, "H", "IT7", "h", "IT6")
    """
    # Normalize
    q = query.upper().replace(" ", "")
    
    # Regex for "25mm" or "25"
    size_match = re.search(r'(\d+\.?\d*)MM?', q)
    if not size_match:
        return None
    size = float(size_match.group(1))
    
    # Remove size from query string to avoid confusion
    q_no_size = q.replace(size_match.group(0), "")
    
    # Find all tolerance codes (e.g. H7, h6)
    # Pattern: Letter(s) + Number(s)
    matches = re.findall(r'([A-Z]+)(\d+)', q_no_size)
    
    if not matches:
        return None
        
    # First match
    code1, grade1 = matches[0]
    it1 = f"IT{grade1}"
    
    # Restore case for code1
    original_q = query.strip()
    code1_case_match = re.search(r'([a-zA-Z]+)' + grade1, original_q)
    if code1_case_match:
        code1 = code1_case_match.group(1)
        
    if len(matches) >= 2:
        # Fit Analysis detected
        code2, grade2 = matches[1]
        it2 = f"IT{grade2}"
        
        # Restore case for code2
        # We need to search after the first match to avoid finding the same one if codes are identical
        # But simple search might be enough if we assume user types in order
        # Let's try to find the second occurrence or just search in the whole string
        # A robust way is to iterate, but for now let's just search
        code2_case_match = re.search(r'([a-zA-Z]+)' + grade2, original_q[code1_case_match.end():])
        if code2_case_match:
            code2 = code2_case_match.group(1)
            
        return size, code1, it1, code2, it2
    else:
        # Single lookup
        return size, code1, it1, None, None

def get_rag_response(user_input, model_name='llama3.1:8b'):
    """
    Main entry point for Web App or CLI.
    """
    # 1. Parse Intent
    parsed = parse_user_query(user_input)

    # --- ENHANCEMENT: Smart Fit Knowledge Injection ---
    smart_fit_results = smart_fit.search_fits(user_input)
    smart_fit_context = ""
    if smart_fit_results:
        smart_fit_context = "Found Standard Fit Recommendations based on keywords:\n"
        for item in smart_fit_results:
            smart_fit_context += f"- {item['type']} ({item['function']}): Hole {item['hole']} / Shaft {item['shaft']} (ANSI: {item['ansi']})\n"
        smart_fit_context += "\n"

    if not parsed:
        # If unable to parse measurements, try GD&T and Smart Fit search directly
        gdt_results = gdt_loader.search(user_input)
        
        if gdt_results or smart_fit_results:
             # Combined context
             context = ""
             if smart_fit_context:
                 context += smart_fit_context
             
             if gdt_results:
                 has_detailed_definition = any("定義:" in result for result in gdt_results)
                 if has_detailed_definition:
                     context += "Retrieved GD&T Definition:\n" + "\n".join(gdt_results)
                 else:
                     concept_names = [result.replace("【", "").replace("】", "") for result in gdt_results]
                     context += f"Found Related GD&T Concepts: {', '.join(concept_names)}"

             prompt = f"""
User Question: {user_input}

Context Data:
{context}

The user is asking about engineering concepts (Fits or GD&T).
If 'Found Standard Fit Recommendations' are provided, please use them to suggest specific hole/shaft combinations that match the user's needs.
If GD&T concepts are provided, explain them clearly.

Answer in Traditional Chinese (繁體中文).
"""
             
             try:
                response = ollama.chat(model=model_name, messages=[
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt},
                ])
                return format_gdt_symbols(response['message']['content'])
             except Exception as e:
                return f"Ollama Error: {e}"
        
        return "抱歉，我無法識別尺寸或公差代號 (如 25mm H7)，也找不到相關的幾何公差定義。"
        
    size, code1, it1, code2, it2 = parsed
    
    data = None
    if code2 and it2:
        # Fit Analysis
        # Determine which is hole and which is shaft based on case
        # Convention: Upper = Hole, Lower = Shaft
        # If user typed "H7 h6", code1=H, code2=h -> Hole=code1, Shaft=code2
        # If user typed "h6 H7", code1=h, code2=H -> Hole=code2, Shaft=code1
        
        if code1[0].isupper():
            hole_c, hole_it = code1, it1
            shaft_c, shaft_it = code2, it2
        else:
            hole_c, hole_it = code2, it2
            shaft_c, shaft_it = code1, it1
            
        data = query_fit_analysis(size, hole_c, hole_it, shaft_c, shaft_it)
    else:
        # Single Lookup
        data = query_database(size, code1, it1)
        
    if not data:
        # Try GD&T Search if standard database lookup failed
        # This handles questions like "什麼是圓柱度?"
        gdt_results = gdt_loader.search(user_input)
        if gdt_results:
             return "\\n".join(gdt_results)
        return "資料庫中找不到此規格的數據，且未發現相關幾何公差定義。"


    # Handle Errors from Fit Analysis
    if data.get('type') == 'Error':
        return data['message']
        
    # Check for supplemental GD&T info (e.g. if user asked "H7/g6 垂直度")
    gdt_results = gdt_loader.search(user_input)
    gdt_context = ""
    if gdt_results:
        gdt_context = "Supplemental GD&T Knowledge:\n" + "\n".join(gdt_results) + "\n"

    # 3. Augment Prompt
    if data.get('type') == 'Fit Analysis':
        context = f"""
        Retrieved Data (Fit Analysis):
        Nominal Size: {data['size']} mm
        
        Hole ({data['hole']['code']}{data['hole']['grade']}):
        - Upper Dev: {data['hole']['upper_dev']} um
        - Lower Dev: {data['hole']['lower_dev']} um
        
        Shaft ({data['shaft']['code']}{data['shaft']['grade']}):
        - Upper Dev: {data['shaft']['upper_dev']} um
        - Lower Dev: {data['shaft']['lower_dev']} um
        
    Fit Result:
        - Type: {data['fit_type']}
        - {("Max Interference" if data['max_clearance'] < 0 else "Max Clearance")}: {abs(data['max_clearance'])} um
        - {("Min Interference" if data['min_clearance'] < 0 else "Min Clearance")}: {abs(data['min_clearance'])} um
        """
    else:
        context = f"""
        Retrieved Data:
        Type: {data['type']}
        Nominal Size: {data['size']} mm
        Tolerance Code: {data['code']}
        IT Grade: {data['grade']}
        Upper Deviation: {data['upper_dev']} {data['unit']}
        Lower Deviation: {data['lower_dev']} {data['unit']}
        """
    
    prompt = f"""
    User Question: {user_input}
    
    Context Data:
    {context}
    
    Please answer the user's question using the Context Data.
    If it is a fit analysis, explain the fit type and clearance values clearly.
    Answer in Traditional Chinese (繁體中文).
    """
    
    prompt = f"""
    User Question: {user_input}
    
    Context Data:
    {context}
    
    {gdt_context}
    {smart_fit_context}
    
    Please answer the user's question using the Context Data.
    If it is a fit analysis, explain the fit type and clearance values clearly.
    If fit recommendations are present, mention them as relevant standards.
    Answer in Traditional Chinese (繁體中文).
    """

    # 4. Generate Response (using Ollama)
    try:
        # Use the provided model_name
        response = ollama.chat(model=model_name, messages=[
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user', 'content': prompt},
        ])
        return format_gdt_symbols(response['message']['content'])
        
    except Exception as e:
        return f"Ollama Error: {e}. 請確認 Ollama 已啟動且已下載 llama3.1:8b 模型。"

def chat_with_rag():
    print("=== ISO 286 公差查詢 AI (RAG 版) ===")
    print("支援單一查詢 (25mm H7) 與配合分析 (25mm H7/h6)")
    print("輸入 'exit' 離開\n")
    
    while True:
        user_input = input("User: ")
        if user_input.lower() in ['exit', 'quit']:
            break
        
        response = get_rag_response(user_input)
        print(f"AI: {response}\n")

if __name__ == "__main__":
    chat_with_rag()
