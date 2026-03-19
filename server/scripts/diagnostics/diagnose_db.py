import pandas as pd
import re
import os

def extract_display_name(node_str):
    if not isinstance(node_str, str): return str(node_str)
    match = re.search(r'display:\s*([^,}]+)', node_str)
    if match: return match.group(1).strip().strip("'\"")
    return node_str

csv_path = 'server/data/0213_export.csv'
df = None
for enc in ['utf-8-sig', 'utf-8', 'big5', 'cp950', 'gbk']:
    try:
        df = pd.read_csv(csv_path, encoding=enc, on_bad_lines='skip')
        print(f"Loaded with {enc}")
        break
    except: pass

if df is not None:
    print("Tracing '1-底座' parent:")
    for index, row in df.iterrows():
        s = extract_display_name(str(row['n']))
        p = str(row['r']).strip('[]:')
        o = extract_display_name(str(row['m']))
        if o == '1-底座':
            print(f" - {s} | {p} | {o}")
