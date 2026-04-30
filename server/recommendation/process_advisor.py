"""
process_advisor.py
------------------
製程建議模組：連接 IT 等級 ↔ 加工製程 ↔ 製程鏈。

提供三個核心查詢：
  1. 正向查詢：IT等級 → 可達製程
  2. 反向查詢：製程名稱 → 可達 IT 等級範圍
  3. 製程鏈規劃：目標製程 → 完整前置工序鏈

資料來源：
  - server/data/process_capability.csv
  - server/data/process_chain.csv
"""
import csv
import os

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(os.path.dirname(_THIS_DIR), 'data')

_capability_db = []
_chain_db = []
_loaded = False


def _load():
    """載入 CSV 資料（只載入一次）"""
    global _capability_db, _chain_db, _loaded
    if _loaded:
        return

    # ── 載入製程能力表 ──
    cap_path = os.path.join(_DATA_DIR, 'process_capability.csv')
    with open(cap_path, 'r', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            _capability_db.append({
                'process_en':   row['process_en'].strip(),
                'process_zh':   row['process_zh'].strip(),
                'it_min':       int(row['it_grade_min']),
                'it_max':       int(row['it_grade_max']),
                'Ra_min':       float(row['Ra_min_um']),
                'Ra_max':       float(row['Ra_max_um']),
                'category':     row['category'].strip(),
                'equipment':    row['typical_equipment'].strip(),
                'feature_types': row.get('feature_types', '').strip(),
                'note':         row.get('note', '').strip(),
            })

    # ── 載入製程鏈 ──
    chain_path = os.path.join(_DATA_DIR, 'process_chain.csv')
    with open(chain_path, 'r', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            _chain_db.append({
                'process':      row['process_en'].strip(),
                'prerequisite': row['prerequisite_en'].strip(),
                'reason':       row['reason_zh'].strip(),
            })

    _loaded = True
    print(f"[ProcessAdvisor] 載入 {len(_capability_db)} 製程, {len(_chain_db)} 製程鏈關係")


# ═══════════════════════════════════════════════
# 1. 正向查詢：IT 等級 → 可達製程
# ═══════════════════════════════════════════════
def suggest_processes(it_grade, feature_type=None):
    """
    給定 IT 等級，回傳所有能達到該精度的製程（按精密度排序）。

    Args:
        it_grade: IT 等級數字 (e.g. 6)
        feature_type: 特徵面類型 ('P'=平面, 'S'=外圓柱, 'H'=內圓柱)，可選篩選

    Returns:
        list of process dicts, 按 it_min 升序排列（最精密的在前）
    """
    _load()
    results = []
    for p in _capability_db:
        if p['it_min'] <= it_grade <= p['it_max']:
            # 特徵面類型篩選
            if feature_type and p['feature_types']:
                supported = [t.strip() for t in p['feature_types'].split(';')]
                if feature_type.upper() not in supported:
                    continue
            results.append(p)

    # 按精密度排序（it_min 越小 = 越精密 → 排前面）
    results.sort(key=lambda x: x['it_min'])
    return results


# ═══════════════════════════════════════════════
# 2. 反向查詢：製程名稱 → 可達精度
# ═══════════════════════════════════════════════
def get_process_capability(process_name):
    """
    給定製程名稱（中文或英文），回傳該製程的能力資訊。

    Args:
        process_name: 製程名稱，支援中文（車削）或英文（Turning）

    Returns:
        process dict or None
    """
    _load()
    name = process_name.strip()
    for p in _capability_db:
        if name in (p['process_en'], p['process_zh']):
            return p
    # 模糊比對
    name_lower = name.lower()
    for p in _capability_db:
        if name_lower in p['process_en'].lower() or name in p['process_zh']:
            return p
    return None


def estimate_capability(process_name: str) -> str:
    """回傳製程能力的自然語言描述"""
    p = get_process_capability(process_name)
    if not p:
        return f"找不到製程「{process_name}」的資料。"
    return (
        f"**{p['process_zh']}（{p['process_en']}）**\n"
        f"- 可達 IT 等級：IT{p['it_min']} ~ IT{p['it_max']}\n"
        f"- 表面粗糙度：Ra {p['Ra_min']} ~ {p['Ra_max']} μm\n"
        f"- 分類：{p['category']}\n"
        f"- 設備：{p['equipment']}\n"
        f"- 說明：{p['note']}"
    )


# ═══════════════════════════════════════════════
# 3. 製程鏈規劃：遞迴查前置工序
# ═══════════════════════════════════════════════
def plan_process_chain(target_process):
    """
    給定目標製程，回傳完整的製程鏈（從粗加工到精加工）。

    Args:
        target_process: 目標製程名稱（英文）

    Returns:
        list of {process_en, process_zh, reason} 從粗到精排列
    """
    _load()
    chain = []
    visited = set()

    def _find_prereq(proc_en):
        if proc_en in visited:
            return
        visited.add(proc_en)
        for c in _chain_db:
            if c['process'] == proc_en:
                _find_prereq(c['prerequisite'])
                chain.append({
                    'process_en': c['prerequisite'],
                    'process_zh': _get_zh_name(c['prerequisite']),
                    'reason': c['reason'],
                })
                return

    _find_prereq(target_process)

    # 加入目標製程本身
    chain.append({
        'process_en': target_process,
        'process_zh': _get_zh_name(target_process),
        'reason': '最終精加工',
    })

    return chain


def _get_zh_name(process_en: str) -> str:
    """英文製程名 → 中文名"""
    _load()
    for p in _capability_db:
        if p['process_en'] == process_en:
            return p['process_zh']
    return process_en


# ═══════════════════════════════════════════════
# 4. 綜合推薦：IT 等級 + 特徵類型 → 完整建議
# ═══════════════════════════════════════════════
def recommend_full(it_grade: int, feature_type: str = None,
                   nominal_size: float = None) -> dict:
    """
    綜合推薦：根據 IT 等級和特徵類型，給出完整的製程建議。

    Returns:
        {
            'it_grade': int,
            'feature_type': str,
            'recommended_process': str,    # 推薦的最終製程
            'process_chain': list,          # 完整製程鏈
            'alternatives': list,           # 替代製程
            'Ra_target': str,               # 建議表面粗糙度
            'summary_zh': str,              # 自然語言摘要
        }
    """
    processes = suggest_processes(it_grade, feature_type)

    if not processes:
        return {
            'it_grade': it_grade,
            'feature_type': feature_type,
            'recommended_process': None,
            'process_chain': [],
            'alternatives': [],
            'Ra_target': 'N/A',
            'summary_zh': f'IT{it_grade} 等級無對應的標準製程資料。',
        }

    # 選擇最經濟的（category 優先順序：machining > grinding > finishing）
    category_priority = {'machining': 0, 'grinding': 1, 'finishing': 2, 'roughing': 3, 'forming': 4}
    best = min(processes, key=lambda p: category_priority.get(p['category'], 99))

    # 完整製程鏈
    chain = plan_process_chain(best['process_en'])

    # 替代方案
    alternatives = [p for p in processes if p['process_en'] != best['process_en']]

    # 表面粗糙度目標
    ra_target = f"Ra {best['Ra_min']} ~ {best['Ra_max']} μm"

    # 製程鏈文字
    chain_str = ' → '.join(f"{s['process_zh']}" for s in chain)

    # 自然語言摘要
    ft_label = {'P': '平面', 'S': '外圓柱面', 'H': '內圓柱面'}.get(feature_type, '特徵')
    size_str = f"Ø{nominal_size}mm " if nominal_size else ""
    alt_str = '、'.join(p['process_zh'] for p in alternatives[:3])

    summary = (
        f"{size_str}{ft_label}需達 IT{it_grade} 精度，"
        f"建議製程鏈：**{chain_str}**。\n"
        f"目標表面粗糙度：{ra_target}。"
    )
    if alt_str:
        summary += f"\n替代製程：{alt_str}。"

    return {
        'it_grade': it_grade,
        'feature_type': feature_type,
        'recommended_process': best['process_zh'],
        'recommended_process_en': best['process_en'],
        'process_chain': chain,
        'alternatives': alternatives[:3],
        'Ra_target': ra_target,
        'equipment': best['equipment'],
        'summary_zh': summary,
    }


# ═══════════════════════════════════════════════
# 5. 批次查詢：為整條公差路徑推薦製程
# ═══════════════════════════════════════════════
def recommend_for_path(path_data):
    """
    為公差路徑中的每個特徵推薦製程。

    Args:
        path_data: editorPathData 格式的 list，每項含 name, val, it_grade, nominal_size 等

    Returns:
        list of recommendation dicts
    """
    results = []
    for item in path_data:
        if item.get('type') != 'feature':
            continue
        name = item.get('name', '')
        it_str = item.get('it_grade', '')
        nominal = item.get('nominal_size')

        # 判斷特徵面類型
        feature_type = None
        if '-P-' in name or '-Fla-' in name or '-Dis-' in name:
            feature_type = 'P'
        elif '-S-' in name or '-Dia-' in name and name.split('-')[0]:
            feature_type = 'S'
        elif '-H-' in name:
            feature_type = 'H'

        # 解析 IT 等級
        it_grade = None
        if it_str:
            try:
                it_grade = int(str(it_str).replace('IT', '').strip())
            except ValueError:
                pass

        if it_grade is None:
            results.append({'name': name, 'recommendation': None, 'reason': 'no IT grade'})
            continue

        rec = recommend_full(it_grade, feature_type, nominal)
        rec['name'] = name
        results.append(rec)

    return results


# ═══════════════════════════════════════════════
# 6. 全部製程一覽
# ═══════════════════════════════════════════════
def get_all_processes():
    """回傳所有製程資料"""
    _load()
    return list(_capability_db)


def get_all_tags() -> list[str]:
    """回傳所有製程名稱標籤（中文），供前端下拉選單用"""
    _load()
    return [p['process_zh'] for p in _capability_db]
