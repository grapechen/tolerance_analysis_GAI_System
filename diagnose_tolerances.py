import pandas as pd
import re
import os

def extract_display_name(node_str):
    if not isinstance(node_str, str): return str(node_str)
    match = re.search(r"display:\s*'([^']+)'", node_str)
    if not match: match = re.search(r"display:\s*([^,}]+)", node_str)
    return match.group(1).strip() if match else node_str

def check_db():
    csv_path = 'server/data/0213_export.csv'
    
    df = None
    for enc in ['utf-8-sig', 'big5', 'cp950', 'utf-8']:
        try:
            df = pd.read_csv(csv_path, encoding=enc)
            print(f"✅ Loaded with encoding: {enc}")
            break
        except Exception:
            continue
            
    if df is None:
        print("❌ Failed to load CSV")
        return
    
    feature_to_tols = {}
    
    for _, row in df.iterrows():
        n = str(row['n'])
        r = str(row['r'])
        m = str(row['m'])
        
        subject = extract_display_name(n)
        relation = r.strip('[]:')
        obj = extract_display_name(m)
        
        # Check if either subject or object is a feature code (e.g., 1-P-1)
        # Features are usually in the format [0-9]-[A-Z]-[0-9]
        feature_pattern = r'^\d+-[A-Z]-\d+$'
        
        if re.match(feature_pattern, subject):
            if subject not in feature_to_tols: feature_to_tols[subject] = []
            feature_to_tols[subject].append((relation, obj))
            
        if re.match(feature_pattern, obj):
            if obj not in feature_to_tols: feature_to_tols[obj] = []
            feature_to_tols[obj].append((relation, subject))

    print("\n✅ Feature to Tolerance Mapping:")
    for feat in sorted(feature_to_tols.keys()):
        print(f"\nFeature: {feat}")
        for rel, target in sorted(list(set(feature_to_tols[feat]))):
            # Only print relations that look like tolerances
            if any(k in target for k in ['Fla', 'Dia', 'Cir', 'Cyl', 'Pos', 'Sym', 'Par', 'Per', 'Ang', 'Con', 'Dis']):
                print(f"  -> {rel}: {target}")

if __name__ == "__main__":
    check_db()
