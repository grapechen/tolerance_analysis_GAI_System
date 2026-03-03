import pandas as pd

try:
    file_path = "c:/Tolerance_Project/Dustin/py/備份20260223.xlsx"
    out_path = "c:/Tolerance_Project/read_excel_out.txt"
    xl = pd.ExcelFile(file_path)
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"Sheets found: {xl.sheet_names}\n")
        
        for sheet in xl.sheet_names:
            f.write(f"\n--- Sheet: {sheet} ---\n")
            df = pd.read_excel(file_path, sheet_name=sheet)
            f.write("Columns:\n")
            f.write(str(list(df.columns)) + "\n")
            f.write("\nFirst 5 rows:\n")
            f.write(df.head(5).to_string() + "\n")
except Exception as e:
    with open("c:/Tolerance_Project/read_excel_out.txt", "w", encoding="utf-8") as f:
        f.write(f"Error: {e}\n")
