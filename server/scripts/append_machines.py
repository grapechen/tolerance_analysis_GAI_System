import pandas as pd
import os

def append_machine_knowledge():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    machines_path = r'c:/Tolerance_Project/data/machines.csv'
    export_path = r'c:/Tolerance_Project/server/data/ontology_export.csv'

    print(f"Reading machines data: {machines_path}")
    try:
        df_machines = pd.read_csv(machines_path, encoding='utf-8-sig')
    except Exception as e:
        print(f"Error reading machines.csv: {e}")
        return

    new_rows = []

    for index, row in df_machines.iterrows():
        model = str(row.get('型號', '')).strip()
        if not model or pd.isna(model):
            continue

        prop = str(row.get('屬性', '')).strip()
        loc_acc = str(row.get('定位精度(mm)', ''))
        rep_acc = str(row.get('重現精度(mm)', ''))

        # 1. 屬性 -> 包含機台型號 -> 型號
        if prop and prop != 'nan':
            n_str = f"(:Resource {{display: '{prop}'}})"
            r_str = f"[:包含機台型號]"
            m_str = f"(:Resource {{display: '{model}'}})"
            new_rows.append({"n": n_str, "r": r_str, "m": m_str})

        # 2. 型號 -> 具備定位精度 -> 定位精度
        if loc_acc and loc_acc != 'nan':
            n_str = f"(:Resource {{display: '{model}'}})"
            r_str = f"[:具備定位精度]"
            m_str = f"(:Resource {{display: '{loc_acc}mm'}})"
            new_rows.append({"n": n_str, "r": r_str, "m": m_str})
            
            # 反過來，方便從精度找到機台
            n_str = f"(:Resource {{display: '定位精度 {loc_acc}mm'}})"
            r_str = f"[:適用機台]"
            m_str = f"(:Resource {{display: '{model}'}})"
            new_rows.append({"n": n_str, "r": r_str, "m": m_str})

        # 3. 型號 -> 具備重現精度 -> 重現精度
        if rep_acc and rep_acc != 'nan':
            n_str = f"(:Resource {{display: '{model}'}})"
            r_str = f"[:具備重現精度]"
            m_str = f"(:Resource {{display: '{rep_acc}mm'}})"
            new_rows.append({"n": n_str, "r": r_str, "m": m_str})
            
            # 從公差(尺寸精度)直接連結到可以做的機台
            # 例如: 若重現精度是 0.006，那大約可以對應 tolerance_um >= 6um 左右的加工
            n_str = f"(:Resource {{display: '重現精度 {rep_acc}mm'}})"
            r_str = f"[:適用機台]"
            m_str = f"(:Resource {{display: '{model}'}})"
            new_rows.append({"n": n_str, "r": r_str, "m": m_str})

    if not new_rows:
        print("Warning: No new triplets generated.")
        return

    df_new = pd.DataFrame(new_rows)
    print(f"Success: Converted {len(new_rows)} machine knowledge triplets!")

    print(f"Appending to: {export_path}")
    
    try:
        df_new.to_csv(export_path, mode='a', header=False, index=False, encoding='utf-8-sig')
        print(f"Success: Imported machine knowledge into knowledge graph!")
    except Exception as e:
        print(f"Error: Write failed: {e}")

if __name__ == "__main__":
    append_machine_knowledge()
