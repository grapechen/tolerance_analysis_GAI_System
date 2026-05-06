"""smart_fit.py — 配合公差推薦引擎

支援兩種搜尋模式：
  1. 維度搜尋 (search_by_tags)：使用者勾選 required/optional 維度，做精確布林匹配 + 排序
  2. 關鍵字搜尋 (search_fits)：對 type/function/note/ansi 字串 AND 比對（向後相容）

資料來源：
  - ansi_fits.csv          主資料庫（26 + 3 欄；29 欄）
  - ansi_fits_schema.csv   維度中英對照表（zh, en, group, group_zh）
"""

import csv
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, 'ansi_fits.csv')
SCHEMA_PATH = os.path.join(BASE_DIR, 'ansi_fits_schema.csv')

# ─────────────────────────────────────────────────────────────────────────────
# Schema 載入
# ─────────────────────────────────────────────────────────────────────────────

def _load_schema() -> list[dict]:
    """讀 ansi_fits_schema.csv → 列表（保留原順序）。"""
    schema = []
    if not os.path.exists(SCHEMA_PATH):
        return schema
    with open(SCHEMA_PATH, encoding='utf-8-sig', newline='') as f:
        for r in csv.DictReader(f):
            schema.append({
                'zh':       r['zh'].strip(),
                'en':       r['en'].strip(),
                'group':    r['group'].strip(),
                'group_zh': r['group_zh'].strip(),
            })
    return schema


_SCHEMA = _load_schema()
_DIMENSION_NAMES_ZH = [s['zh'] for s in _SCHEMA]   # 20 個維度中文名（依檔案順序）


# ─────────────────────────────────────────────────────────────────────────────
# 主資料載入
# ─────────────────────────────────────────────────────────────────────────────

def _truthy(v: str) -> bool:
    return str(v).strip().lower() in ('true', '1', '○', 'yes', 'y')


def load_fits_from_csv() -> list[dict]:
    """讀 ansi_fits.csv，每筆封裝為：
      - type, function, note, ansi, source, is_approx, lookup_skip
      - hole_tol (CSV 'shaft' 欄)、shaft_dev (CSV 'hole' 欄) ← 修正反直覺欄名
      - tags: set[str]   該筆 ○ 過的維度（中文）
    """
    database = []
    if not os.path.exists(CSV_PATH):
        print(f'Warning: CSV file not found at {CSV_PATH}')
        return database

    with open(CSV_PATH, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            tags = {dim for dim in _DIMENSION_NAMES_ZH if (row.get(dim, '') or '').strip() == '○'}
            database.append({
                'type':        (row.get('type') or '').strip(),
                'function':    (row.get('function') or '').strip(),
                'note':        (row.get('note') or '').strip(),
                'ansi':        (row.get('ansi') or '').strip(),
                # 對下游語意正確的欄名：
                #   CSV 'shaft' 欄裝孔公差 (H 系列) → hole_tol
                #   CSV 'hole'  欄裝軸偏差 (h6/g4 等) → shaft_dev
                # 同時保留 'shaft' / 'hole' alias 給既有呼叫者
                'hole_tol':    (row.get('shaft') or '').strip(),
                'shaft_dev':   (row.get('hole') or '').strip(),
                'shaft':       (row.get('shaft') or '').strip(),  # alias，向後相容
                'hole':        (row.get('hole') or '').strip(),   # alias，向後相容
                'source':      (row.get('source') or 'ANSI').strip() or 'ANSI',
                'is_approx':   _truthy(row.get('is_approx', '')),
                'lookup_skip': _truthy(row.get('lookup_skip', '')),
                'tags':        tags,
            })
    return database


# 模組載入時讀一次（保留舊行為）
fits_database = load_fits_from_csv()


# ─────────────────────────────────────────────────────────────────────────────
# 維度分組（給前端 UI）
# ─────────────────────────────────────────────────────────────────────────────

def get_dimension_groups() -> list[dict]:
    """組成前端可直接 render 的群組結構。
    回傳：
      [{group: 'speed', group_zh: '速度',
        items: [{zh: '慢速旋轉', en: 'slow_rotation'}, ...]}, ...]
    """
    groups = {}
    order = []
    for item in _SCHEMA:
        g = item['group']
        if g not in groups:
            groups[g] = {
                'group':    g,
                'group_zh': item['group_zh'],
                'items':    [],
            }
            order.append(g)
        groups[g]['items'].append({'zh': item['zh'], 'en': item['en']})
    return [groups[g] for g in order]


def list_all_dimensions() -> list[str]:
    """全部 20 個維度中文名（依 schema 順序）。"""
    return list(_DIMENSION_NAMES_ZH)


# ─────────────────────────────────────────────────────────────────────────────
# 維度搜尋（核心新功能）
# ─────────────────────────────────────────────────────────────────────────────

def search_by_tags(required, optional=None) -> list[dict]:
    """依維度勾選做精確匹配 + 評分排序。

    Args:
      required: iterable[str]  必選維度（中文名），全部要 ○ 的列才會入選
      optional: iterable[str]  可選維度，命中越多排越前

    Returns:
      list of ScoredFit dict，依 score 由高到低排列：
        {
          'item':         原始 fit dict,
          'score':        int  (基礎 100 + 每個 optional 命中 +10),
          'matched_tags': list[str],
          'missing_tags': list[str],   使用者勾了該列卻沒勾的
          'extra_tags':   list[str],   該列勾了但使用者沒選的
        }
    """
    required = set(required or [])
    optional = set(optional or [])

    # 排除無效維度名（不在 schema 內）
    valid = set(_DIMENSION_NAMES_ZH)
    required &= valid
    optional &= valid

    if not required and not optional:
        return []

    results = []
    for item in fits_database:
        tags = item['tags']

        # 必選全中
        if required and not required.issubset(tags):
            continue

        matched_optional = optional & tags
        score = 100 + 10 * len(matched_optional)

        results.append({
            'item':         item,
            'score':        score,
            'matched_tags': sorted((required | matched_optional)),
            'missing_tags': sorted(optional - tags),
            'extra_tags':   sorted(tags - required - matched_optional),
        })

    # 排序：score 高 → extra_tags 少（更專一）→ ANSI > RAS400_custom > YRT100
    # specificity tie-break：同分時偏好 extra_tags 較少（命中得乾淨、無多餘屬性）
    src_order = {'ANSI': 0, 'RAS400_custom': 1, 'YRT100': 2}
    results.sort(key=lambda r: (
        -r['score'],
        len(r['extra_tags']),
        src_order.get(r['item']['source'], 9),
    ))
    return results


# ─────────────────────────────────────────────────────────────────────────────
# 關鍵字搜尋（向後相容；先嘗試映射到維度）
# ─────────────────────────────────────────────────────────────────────────────

def _map_keywords_to_dimensions(keywords: list[str]) -> set[str]:
    """嘗試把使用者關鍵字對映到 schema 中的維度中文名。
    完全相同 → 中文名比對 / 英文名比對都接受。
    """
    matched = set()
    for kw in keywords:
        kw = kw.strip()
        if not kw:
            continue
        for dim in _SCHEMA:
            if kw == dim['zh'] or kw.lower() == dim['en'].lower():
                matched.add(dim['zh'])
                break
    return matched


def search_fits(keywords) -> list[dict]:
    """向後相容介面：先嘗試把 keywords 對映到維度做維度搜尋；
    若任一 keyword 對映不到，則 fallback 到原本的字串 AND 比對。
    """
    if isinstance(keywords, str):
        keywords = keywords.split()
    keywords = [str(k).strip() for k in keywords if str(k).strip()]
    if not keywords:
        return []

    # 嘗試走維度路徑
    mapped = _map_keywords_to_dimensions(keywords)
    if mapped and len(mapped) == len(keywords):
        # 全部 keyword 都成功映射 → 走維度搜尋（全列為 required）
        scored = search_by_tags(required=mapped)
        return [s['item'] for s in scored]

    # Fallback：原本的字串 AND 比對
    results = []
    for item in fits_database:
        row_text = f"{item['type']} {item['function']} {item['note']} {item['ansi']}"
        if all(k in row_text for k in keywords):
            results.append(item)
    return results


# ─────────────────────────────────────────────────────────────────────────────
# 既有 helper（保留）
# ─────────────────────────────────────────────────────────────────────────────

def get_all_tags() -> list[str]:
    """回傳所有可用的維度中文名（取代舊版自製 keyword 清單）。"""
    return list_all_dimensions()
