"""
dsl_builder.py
--------------
確定性地從 ontology_export.csv 建構 BOM DSL 字串。
0 幻覺：所有資料 100% 來自本體庫，不依賴 AI 生成。
"""
import re
import os
import pandas as pd
from typing import Optional, Union, List, Dict, Any

# 特徵面型別對應 (ns0__X -> 縮寫)
FEATURE_TYPE_MAP = {
    '平面':    'P',
    '外圓柱面': 'S',
    '內圓柱面': 'H',
    '圓柱面':  'S',
    '錐面':    'C',
}

# ─────────────────── 私有工具函式 ───────────────────

def _get_csv_path():
    env_path = os.environ.get('RAS400_ONTOLOGY_PATH')
    if env_path and os.path.exists(env_path):
        return env_path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    server_dir  = os.path.dirname(current_dir)
    return os.path.join(server_dir, 'data', 'ras400_ontology.csv')


def _load_csv(csv_path=None):
    if csv_path is None:
        csv_path = _get_csv_path()
    df = None
    for enc in ['utf-8-sig', 'utf-8', 'big5', 'cp950']:
        try:
            df = pd.read_csv(csv_path, encoding=enc, on_bad_lines='skip')
            if {'n', 'r', 'm'}.issubset(df.columns):
                break
            df = None
        except Exception:
            pass
    if df is None:
        return None

    # 合併接觸面補丁（ras400_ontology_contacts.csv）
    current_dir = os.path.dirname(os.path.abspath(__file__))
    server_dir  = os.path.dirname(current_dir)
    contacts_path = os.path.join(server_dir, 'data', 'ras400_ontology_contacts.csv')
    if os.path.exists(contacts_path):
        for enc in ['utf-8-sig', 'utf-8', 'big5', 'cp950']:
            try:
                df_c = pd.read_csv(contacts_path, encoding=enc, on_bad_lines='skip')
                if {'n', 'r', 'm'}.issubset(df_c.columns):
                    df = pd.concat([df, df_c], ignore_index=True).drop_duplicates()
                break
            except Exception:
                pass
    return df


def _uri(node_str: str):
    """從節點字串抽取 uri 值"""
    if not isinstance(node_str, str):
        return None
    m = re.search(r'uri:\s*([^,}]+)', node_str)
    return m.group(1).strip() if m else None


def _ns0_class(node_str: str):
    """抽取第一個 ns0__<X> 的 X（特徵面型別）"""
    if not isinstance(node_str, str):
        return None
    m = re.search(r':ns0__([\u4e00-\u9fa5A-Za-z0-9_]+)', node_str)
    return m.group(1) if m else None


def _rel(rel_str: str):
    if not isinstance(rel_str, str):
        return ''
    return rel_str.strip('[]:')


# RAS400 組裝順序
_RAS400_ORDER = {
    '工作臺': 1, '軸承座': 2, '軸承': 3, '轉動軸': 4, '工作臺心軸': 5,
    '馬達': 6, '馬達水套': 7, '編碼器心軸': 8, '分流座': 9, '馬達座': 10, '編碼器': 11,
}

def _part_sort_key(name: str):
    # 優先用 RAS400 組裝順序，其次用舊格式數字前綴
    if name in _RAS400_ORDER:
        return (_RAS400_ORDER[name], name)
    m = re.match(r'^(\d+)', name)
    return (int(m.group(1)), name) if m else (999, name)


def _feat_sort_key(name: str):
    """P < S < H < C，再依數字排序"""
    m = re.search(r'-([PSHCpshc])-(\d+)', name)
    if m:
        order = {'P': 0, 'p': 0, 'S': 1, 's': 1, 'H': 2, 'h': 2, 'C': 3, 'c': 3}
        return (order.get(m.group(1), 4), int(m.group(2)))
    return (9, 0)


def _detect_assembly_title(df) -> str:
    """掃描 df，回傳第一個 ns0__組合件 NamedIndividual 的 URI；無則 fallback 'RAS400'"""
    for _, row in df.iterrows():
        for col in ('n', 'm'):
            s = str(row[col])
            if 'owl__NamedIndividual' in s and ':ns0__組合件' in s:
                u = _uri(s)
                if u:
                    return u
    return 'RAS400'


# ─────────────────── 主解析函式 ───────────────────

def _parse_ontology(df):
    """
    一次掃描整個 CSV，回傳：
    - parts        : 排序後的零件名稱列表
    - feat_to_part : {feature_id -> part_id}
    - feat_type    : {feature_id -> type_abbrev}  e.g. 'Flat','Cyl','Hol'
    - feat_ind     : {feature_id -> [individual_tol_ids]}
    - feat_itr     : {feature_id -> [interactive_tol_ids]}
    - part_feats   : {part_id -> [feature_ids]}
    """
    parts_set    = set()
    feat_to_part = {}
    feat_type    = {}
    feat_ind     = {}   # {feature -> [tol]}
    feat_itr     = {}   # {feature -> [tol]}
    feat_con     = {}   # {feature -> [contact_feature]}

    assembly_uris = set()
    for _, row in df.iterrows():
        n_str = str(row['n']); m_str = str(row['m'])
        if 'owl__NamedIndividual' in n_str and ':ns0__組合件' in n_str:
            u = _uri(n_str);  assembly_uris.add(u) if u else None
        if 'owl__NamedIndividual' in m_str and ':ns0__組合件' in m_str:
            u = _uri(m_str);  assembly_uris.add(u) if u else None
    if not assembly_uris:
        assembly_uris = {'RAS400'}

    for _, row in df.iterrows():
        n_str = str(row['n'])
        r_str = str(row['r'])
        m_str = str(row['m'])
        rel   = _rel(r_str)
        n_uri = _uri(n_str)
        m_uri = _uri(m_str)

        if not n_uri or not m_uri:
            continue

        # ── 組合件 → 零件（subject 是組合件） ──
        if '有零件' in rel and n_uri in assembly_uris:
            parts_set.add(m_uri)

        # ── 零件反向：零件 → 組合件（部分資料方向相反） ──
        if '有零件' in rel and m_uri in assembly_uris:
            parts_set.add(n_uri)

        # ── 特徵面 → 所屬零件 ──
        if '有特徵面' in rel:
            # Case A: feature --[有特徵面]--> part
            ns0 = _ns0_class(n_str)
            feat_type_abbrev = FEATURE_TYPE_MAP.get(ns0, '')
            if feat_type_abbrev:
                feat_to_part[n_uri] = m_uri
                if feat_type_abbrev:
                    feat_type[n_uri] = feat_type_abbrev
            # Case B: part --[有特徵面]--> feature (方向相反)
            else:
                ns0_m = _ns0_class(m_str)
                feat_type_abbrev_m = FEATURE_TYPE_MAP.get(ns0_m, '')
                if feat_type_abbrev_m:
                    feat_to_part[m_uri] = n_uri
                    feat_type[m_uri] = feat_type_abbrev_m

        # ── 個別公差：tolerance --[有個別參考公差]--> feature ──
        if '有個別參考公差' in rel:
            # 判斷哪個是公差哪個是特徵面
            # n=公差 m=特徵 (看 ns0__ 型別)
            ns0_n = _ns0_class(n_str)
            ns0_m = _ns0_class(m_str)
            if ns0_n and ns0_n in FEATURE_TYPE_MAP:
                # n 是特徵面，m 是公差 (反方向)
                feat_ind.setdefault(n_uri, [])
                if m_uri not in feat_ind[n_uri]:
                    feat_ind[n_uri].append(m_uri)
            elif ns0_m and ns0_m in FEATURE_TYPE_MAP:
                # m 是特徵面，n 是公差
                feat_ind.setdefault(m_uri, [])
                if n_uri not in feat_ind[m_uri]:
                    feat_ind[m_uri].append(n_uri)
            else:
                # 用 URI 命名規則猜：P/S/H 是特徵面
                if m_uri and re.search(r'-[PSHCpshc]-\d', m_uri):
                    feat_ind.setdefault(m_uri, [])
                    if n_uri not in feat_ind[m_uri]:
                        feat_ind[m_uri].append(n_uri)
                elif n_uri and re.search(r'-[PSHCpshc]-\d', n_uri):
                    feat_ind.setdefault(n_uri, [])
                    if m_uri not in feat_ind[n_uri]:
                        feat_ind[n_uri].append(m_uri)

        # ── 交互參考公差：feature <--[有交互參考公差]--> tolerance ──
        if '有交互參考公差' in rel:
            ns0_n = _ns0_class(n_str)
            ns0_m = _ns0_class(m_str)
            is_n_feat = bool(ns0_n and ns0_n in FEATURE_TYPE_MAP) or \
                        bool(n_uri and re.search(r'-[PSHCpshc]-\d', n_uri))
            is_m_feat = bool(ns0_m and ns0_m in FEATURE_TYPE_MAP) or \
                        bool(m_uri and re.search(r'-[PSHCpshc]-\d', m_uri))

            if is_n_feat and not is_m_feat:
                feat_itr.setdefault(n_uri, [])
                if m_uri not in feat_itr[n_uri]:
                    feat_itr[n_uri].append(m_uri)
            elif is_m_feat and not is_n_feat:
                feat_itr.setdefault(m_uri, [])
                if n_uri not in feat_itr[m_uri]:
                    feat_itr[m_uri].append(n_uri)

        # ── 組裝接觸：feature1 --[有組裝接觸]--> feature2 ──
        if '有組裝接觸' in rel:
            ns0_n = _ns0_class(n_str)
            ns0_m = _ns0_class(m_str)
            if ns0_n and ns0_n in FEATURE_TYPE_MAP and ns0_m and ns0_m in FEATURE_TYPE_MAP:
                feat_con.setdefault(n_uri, [])
                if m_uri not in feat_con[n_uri]: feat_con[n_uri].append(m_uri)
                feat_con.setdefault(m_uri, [])
                if n_uri not in feat_con[m_uri]: feat_con[m_uri].append(n_uri)

    # 整理 part_feats
    part_feats = {}
    for f, p in feat_to_part.items():
        part_feats.setdefault(p, [])
        if f not in part_feats[p]:
            part_feats[p].append(f)

    parts = sorted(parts_set, key=_part_sort_key)
    return parts, feat_to_part, feat_type, feat_ind, feat_itr, feat_con, part_feats


# ─────────────────── 公開 API ───────────────────

def build_bom_dsl() -> Optional[str]:
    """
    產生「僅零件」的 BOM DSL（不含特徵面）。
    用於回答「產品架構圖」、「包含哪些零件」類問題。
    """
    df = _load_csv()
    if df is None:
        return None

    parts, *_ = _parse_ontology(df)
    if not parts:
        return None

    title = _detect_assembly_title(df)
    lines = ['---BOM_START---', f'# {title}']
    for p in parts:
        lines.append(f'- {p}')
    lines.append('---BOM_END---')

    print(f'[DSL Builder] BOM-only DSL: {len(parts)} parts')
    return '\n'.join(lines)


def build_feature_dsl(level='network', show_contacts=False, part_filter: str = None) -> Optional[str]:
    """
    產生指定等層級的 DSL。
    level: 'feature' (零件+特徵) or 'network' (零件+特徵+公差+接觸)
    part_filter: 若指定，只輸出名稱包含此字串的零件（如 '軸承座'）
    """
    df = _load_csv()
    if df is None: return None

    parts, feat_to_part, feat_type, feat_ind, feat_itr, feat_con, part_feats = _parse_ontology(df)
    if not parts: return None

    if part_filter:
        # 去除「2-軸承座」式的數字前綴，取純零件名稱
        pf_name = re.sub(r'^\d+[-－]', '', part_filter).strip()
        # 優先精確比對，避免「工作臺」匹配到「工作臺心軸」、「馬達」匹配到「馬達座/馬達水套」
        exact = [p for p in parts if p == pf_name]
        parts = exact if exact else [p for p in parts if pf_name in p]
        if not parts: return None

    title = _detect_assembly_title(df)
    label = f'{part_filter} ({level})' if part_filter else f'{title} ({level})'
    lines = ['---BOM_START---', f'# {label}']
    for p in parts:
        lines.append(f'- {p}')
        feats = sorted(part_feats.get(p, []), key=_feat_sort_key)
        for f in feats:
            # 只有在 network 模式才提取公差與接觸
            ind_str = ''
            itr_str = ''
            
            if level == 'network':
                raw_ind = feat_ind.get(f, [])
                raw_itr = list(feat_itr.get(f, []))

                # [v3 修正] 不再把 Con-N 文字標籤塞到特徵的 itr_list 裡
                # 接觸資訊改成只透過下方 ---CONTACTS_START--- 區塊輸出，
                # 由前端用綠色連線視覺呈現，避免跟使用者標註的 PMI 公差項
                # （Cyl-1 / Dia-N / Co-1 / Per-1 等）混在同一格產生視覺干擾。

                # 重新分類 Str, Fla 等個別公差
                IND_KEYS = ['dia', 'rad', 'cyl', 'fla', 'cir', 'str', 'flat']
                ind_list = []
                itr_list = []
                for t in list(set(raw_ind + raw_itr)):
                    # 過濾掉任何殘留的 Con- 標籤（避免歷史資料汙染）
                    if t.startswith('Con-') and t[4:5].isdigit():
                        continue

                    t_low = t.lower()
                    if any(k in t_low for k in IND_KEYS) and 'ang' not in t_low:
                        ind_list.append(t)
                    else:
                        itr_list.append(t)
                
                ind_str = ' '.join(ind_list)
                itr_str = ' '.join(itr_list)

            line = f'  * {f}'
            if ind_str: line += f' ({ind_str})'
            if itr_str: line += f' [{itr_str}]'
            lines.append(line)

    # [核心修正] 為了支援跨零件的綠色連線與導出，新增全域接觸區塊
    if level == 'network' and show_contacts:
        lines.append('---CONTACTS_START---')
        contacts_found = set()
        for f1, targets in feat_con.items():
            for f2 in targets:
                pair = tuple(sorted([f1.strip(), f2.strip()]))
                if pair not in contacts_found:
                    contacts_found.add(pair)
                    lines.append(f'{pair[0]},{pair[1]}')
        lines.append('---CONTACTS_END---')

    lines.append('---BOM_END---')

    return '\n'.join(lines)

def build_full_dsl(mode='network', tolerance_overrides=None, quadrants=None):
    """
    產生專業的巢狀階層公差摘要。
    支援 tolerance_overrides: {feature_name: value} 與 quadrants: {feature_name: q_index}。
    """
    df = _load_csv()
    if df is None: return "無法讀取本體庫數據。"
    
    parts, _, _, feat_ind, feat_itr, _, part_feats = _parse_ontology(df)
    
    # 建立回傳內容
    answer = []
    if mode == 'edit':
        answer = ["**[系統訊息] 已準備好公差路徑數據**\n"]
    elif mode == 'contact':
        answer = ["**組裝接觸關係摘要 (Assembly Contacts)**\n"]
    else:
        answer = ["**公差網路圖摘要 (Network Summary)**\n"]

    # 封裝為 ---BOM_START--- 格式供前端解析
    bom_lines = []
    bom_lines.append("---BOM_START---")
    
    for p in parts:
        feats = sorted(part_feats.get(p, []), key=_feat_sort_key)
        if not feats: continue
        
        bom_lines.append(f"- {p}")
        for f in feats:
            raw_ind = feat_ind.get(f, [])
            raw_itr = feat_itr.get(f, [])
            
            # 處理公差值覆寫 (如果是調配模式)
            display_val = ""
            if tolerance_overrides and f in tolerance_overrides:
                display_val = f" ({tolerance_overrides[f]})"
            
            # 處理象限標記 [Q1]...[Q4]
            q_tag = ""
            if quadrants and f in quadrants:
                q_tag = f" [Q{quadrants[f]}]"

            ind_list = []
            itr_list = []
            all_tols = list(set(raw_ind + raw_itr))
            IND_KEYS = ['dia', 'rad', 'cyl', 'fla', 'cir', 'str', 'flat'] 
            
            for t in all_tols:
                if t.startswith('Con-') and '-' in t[4:]: continue
                t_low = t.lower()
                if any(k in t_low for k in IND_KEYS) and 'ang' not in t_low:
                    ind_list.append(t)
                else:
                    itr_list.append(t)
            
            ind_s = f" ({', '.join(ind_list)})" if ind_list else ""
            itr_s = f" [{', '.join(itr_list)}]" if itr_list else ""
            
            # 組合成 DSL 行：  * 1-P-1 (0.02) [Dis-Z] [Q1]
            bom_lines.append(f"    * {f}{display_val}{itr_s}{q_tag}")
            
    bom_lines.append("---BOM_END---")
    
    # 組合最終文本
    final_output = "\n".join(bom_lines)
    return f"<AUDIT_REPORT>\n已基於最新的公差調配結果生成產品架構圖。\n</AUDIT_REPORT>\n\n<FINAL_ANSWER>\n{final_output}\n</FINAL_ANSWER>"

def build_feature_summary(part_filter: str = None) -> str:
    """
    產生精簡的特徵面結構摘要（不含公差），供「特徵面結構圖」查詢使用。
    格式：零件名 (N 個特徵面): P-1~P-6, S-1~S-2, H-1~H-4, C-1~C-7
    """
    df = _load_csv()
    if df is None: return "<AUDIT_REPORT>\n無法讀取本體庫。\n</AUDIT_REPORT>\n\n<FINAL_ANSWER>\n無資料\n</FINAL_ANSWER>"

    parts, _, _, _, _, _, part_feats = _parse_ontology(df)

    if part_filter:
        pf_name = re.sub(r'^\d+[-－]', '', part_filter).strip()
        exact = [p for p in parts if p == pf_name]
        parts = exact if exact else [p for p in parts if pf_name in p]

    TYPE_LABEL = {'P': '平面', 'S': '軸面', 'H': '孔面', 'C': '接觸面'}

    lines = ["**特徵面結構摘要**\n"]
    for p in parts:
        feats = sorted(part_feats.get(p, []), key=_feat_sort_key)
        if not feats:
            lines.append(f"- {p}：無特徵面資料")
            continue
        by_type: dict = {}
        for f in feats:
            t = f.split('-')[1] if '-' in f else '?'
            by_type.setdefault(t, []).append(f.split('-', 1)[1])  # e.g. "P-1"
        type_strs = []
        for t in ['P', 'H', 'S', 'C']:
            if t in by_type:
                items = sorted(by_type[t])
                type_strs.append(f"{TYPE_LABEL.get(t, t)} {', '.join(items)}")
        lines.append(f"- **{p}**（{len(feats)} 個）：{'；'.join(type_strs)}")

    audit = f"<AUDIT_REPORT>\n共 {len(parts)} 個零件，特徵面資料來自本體庫（0 幻覺）。\n</AUDIT_REPORT>"
    return audit + "\n\n<FINAL_ANSWER>\n" + "\n".join(lines) + "\n</FINAL_ANSWER>"


def build_text_summary(mode='network') -> str:
    """
    產生專業的巢狀階層公差摘要。
    格式符合使用者提供的 Javascript 解析需求，包含 AUDIT_REPORT 與 FINAL_ANSWER。
    """
    df = _load_csv()
    if df is None: return "無法讀取本體庫數據。"
    
    parts, _, _, feat_ind, feat_itr, _, part_feats = _parse_ontology(df)
    
    # [統計分類] 為求透明，統計本次識別出的公差類型
    all_ind_types = set()
    all_itr_types = set()
    IND_KEYS = ['dia', 'rad', 'cyl', 'fla', 'cir', 'str', 'flat']
    
    for f_tols in list(feat_ind.values()) + list(feat_itr.values()):
        for t in f_tols:
            t_low = t.lower()
            if any(k in t_low for k in IND_KEYS) and 'ang' not in t_low:
                all_ind_types.add(t.split('-')[1]) # 提取如 Fla, Str
            elif not t.startswith('Con-'):
                all_itr_types.add(t.split('-')[1]) # 提取如 Dis, Par, Per
    
    # [自省報告] 列出識別到的所有公差類別
    audit = [
        "<AUDIT_REPORT>",
        f"1. 個別公差 (Individual): {', '.join(sorted(all_ind_types)) if all_ind_types else '無'}",
        f"2. 交互公差 (Interactive): {', '.join(sorted(all_itr_types)) if all_itr_types else '無'}",
        f"3. {'已開啟組裝接觸 (Con-) 關聯性分析。' if mode == 'contact' else '已自動隱藏組裝接觸 (Con-)，僅顯示公差網路。'}",
        "</AUDIT_REPORT>"
    ]
    
    if mode == 'edit':
        answer = [
            "**[系統訊息] 已準備好公差路徑數據**\n",
            "正在為您開啟「公差路徑編輯器」... 您可以手動調整平移 (tra)、旋轉 (rot) 與特徵公差值 (tol)，調整後點擊「匯出 CSV」即可下載。"
        ]
    elif mode == 'contact':
        answer = ["**組裝接觸關係摘要 (Assembly Contacts)**\n"]
        contacts_found = set()
        parts, _, _, _, _, feat_con, _ = _parse_ontology(df)
        for f1, targets in feat_con.items():
            for f2 in targets:
                # 嚴格去重：排序字串並移除前後空白
                pair = tuple(sorted([f1.strip(), f2.strip()]))
                if pair not in contacts_found:
                    contacts_found.add(pair)
                    # 呈現格式：1-P-1 ↔ 2-P-1
                    answer.append(f"- {pair[0]} ↔ {pair[1]} (組裝接觸)")
        if not contacts_found:
            answer.append("未偵測到任何明確的組裝接觸面關係。")
    else:
        answer = ["**公差網路圖摘要 (Network Summary)**\n"]
        # ... 原有的 network summary 邏輯 (下方的循環) ...
    
    if mode != 'contact':
        for p in parts:
            feats = sorted(part_feats.get(p, []), key=_feat_sort_key)
            if not feats: continue
            
            answer.append(f"- {p}")
            for f in feats:
                raw_ind = feat_ind.get(f, [])
                raw_itr = feat_itr.get(f, [])
                
                ind_list = []
                itr_list = []
                all_tols = list(set(raw_ind + raw_itr))
                IND_KEYS = ['dia', 'rad', 'cyl', 'fla', 'cir', 'str', 'flat'] 
                
                for t in all_tols:
                    if t.startswith('Con-') and '-' in t[4:]: continue # 輔助標籤不顯示
                    t_low = t.lower()
                    if any(k in t_low for k in IND_KEYS) and 'ang' not in t_low:
                        ind_list.append(t)
                    else:
                        itr_list.append(t)
                
                # 完全符合 JS 代碼中的 join(', ') 與空格邏輯
                ind_s = f" ({', '.join(ind_list)})" if ind_list else ""
                itr_s = f" [{', '.join(itr_list)}]" if itr_list else ""
                
                # 使用 4 格空格與 *，移除任何額外的中文字標籤
                answer.append(f"    * {f}{ind_s}{itr_s}")
            
    return '\n'.join(audit) + "\n\n<FINAL_ANSWER>\n" + '\n'.join(answer) + "\n</FINAL_ANSWER>"
