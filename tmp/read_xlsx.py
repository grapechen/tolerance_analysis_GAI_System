import pandas as pd
import sys

input_file = r"c:\Tolerance_Project\新增資料夾\軸承座\軸承座-3-sfa.xlsx"
output_file = r"c:\Tolerance_Project\tmp\xlsx_full_report.txt"

try:
    xl = pd.ExcelFile(input_file)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"所有分頁: {xl.sheet_names}\n")
        for sheet in xl.sheet_names:
            df = pd.read_excel(input_file, sheet_name=sheet)
            f.write(f"\n===== 分頁: {sheet} (共 {len(df)} 筆) =====\n")
            f.write(df.to_string())
            f.write("\n" + "="*50 + "\n")
    print(f"完整報告已成功輸出至: {output_file}")
except Exception as e:
    print(f"錯誤: {e}")
