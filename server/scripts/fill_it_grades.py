"""
fill_it_grades.py
-----------------
批次反查標準公差表，自動填入 CSV 中缺失的 IT 等級。

分類處理邏輯：
  ┌─────────────────────────────────────────────────────┐
  │ 尺寸公差 (DIA, DIS)  → ISO 286-1 反查 IT 等級       │
  │ 幾何公差 (FLA, PAR, PER, CYL, CIR, CO, SYM, RUN)   │
  │   → ISO 2768-2 比對等級 (H/K/L)                     │
  │   → 若比 H 更精密 → 標為 "特殊指定"                  │
  └─────────────────────────────────────────────────────┘

用法：
  python server/scripts/fill_it_grades.py            # 預覽模式（不修改檔案）
  python server/scripts/fill_it_grades.py --write    # 實際寫入
"""
import csv
import os
import sys
import math
import re
from copy import deepcopy

# ═══════════════════════════════════════════════
# ISO 286-1 基本公差表 (完整 IT01 ~ IT18)
# 單位：μm，尺寸範圍：mm
# ═══════════════════════════════════════════════
# 格式：(size_up_to_mm, {IT等級: 公差值μm})
ISO_286_TABLE = [
    # up_to,  IT01, IT0,  IT1,   IT2,  IT3,  IT4,  IT5,  IT6,  IT7,   IT8,   IT9,   IT10,  IT11,  IT12,  IT13,  IT14,  IT15,  IT16,  IT17,  IT18
    (3,       0.3,  0.5,  0.8,   1.2,  2,    3,    4,    6,    10,    14,    25,    40,    60,    100,   140,   250,   400,   600,   1000,  1400),
    (6,       0.4,  0.6,  1,     1.5,  2.5,  4,    5,    8,    12,    18,    30,    48,    75,    120,   180,   300,   480,   750,   1200,  1800),
    (10,      0.4,  0.6,  1,     1.5,  2.5,  4,    6,    9,    15,    22,    36,    58,    90,    150,   220,   360,   580,   900,   1500,  2200),
    (18,      0.5,  0.8,  1.2,   2,    3,    5,    8,    11,   18,    27,    43,    70,    110,   180,   270,   430,   700,   1100,  1800,  2700),
    (30,      0.6,  1,    1.5,   2.5,  4,    6,    9,    13,   21,    33,    52,    84,    130,   210,   330,   520,   840,   1300,  2100,  3300),
    (50,      0.6,  1,    1.5,   2.5,  4,    7,    11,   16,   25,    39,    62,    100,   160,   250,   390,   620,   1000,  1600,  2500,  3900),
    (80,      0.8,  1.2,  2,     3,    5,    8,    13,   19,   30,    46,    74,    120,   190,   300,   460,   740,   1200,  1900,  3000,  4600),
    (120,     1,    1.5,  2.5,   4,    6,    10,   15,   22,   35,    54,    87,    140,   220,   350,   540,   870,   1400,  2200,  3500,  5400),
    (180,     1.2,  2,    3.5,   5,    8,    12,   18,   25,   40,    63,    100,   160,   250,   400,   630,   1000,  1600,  2500,  4000,  6300),
    (250,     2,    3,    4.5,   7,    10,   14,   20,   29,   46,    72,    115,   185,   290,   460,   720,   1150,  1850,  2900,  4600,  7200),
    (315,     2.5,  4,    6,     8,    12,   16,   23,   32,   52,    81,    130,   210,   320,   520,   810,   1300,  2100,  3200,  5200,  8100),
    (400,     3,    5,    7,     9,    13,   18,   25,   36,   57,    89,    140,   230,   360,   570,   890,   1400,  2300,  3600,  5700,  8900),
    (500,     4,    6,    8,     10,   15,   20,   27,   40,   63,    97,    155,   250,   400,   630,   970,   1550,  2500,  4000,  6300,  9700),
]

IT_GRADE_NAMES = [
    'IT01', 'IT0', 'IT1', 'IT2', 'IT3', 'IT4', 'IT5', 'IT6', 'IT7',
    'IT8', 'IT9', 'IT10', 'IT11', 'IT12', 'IT13', 'IT14', 'IT15', 'IT16', 'IT17', 'IT18',
]


def get_all_tolerances(nominal_mm: float) -> dict:
    """給定公稱尺寸，回傳所有 IT 等級的公差值 (μm)"""
    for up_to, *values in ISO_286_TABLE:
        if nominal_mm <= up_to:
            return dict(zip(IT_GRADE_NAMES, values))
    # > 500mm 用最後一行
    return dict(zip(IT_GRADE_NAMES, ISO_286_TABLE[-1][1:]))


def reverse_lookup_it(nominal_mm, tol_mm):
    """
    反查：給定 (公稱尺寸mm, 公差值mm) → 最接近的 IT 等級

    策略：找公差值 >= tol_um 的最小 IT（即剛好能涵蓋的等級）
    若公差值比 IT01 還小，回傳 IT01；比 IT18 還大，回傳 None
    """
    if nominal_mm <= 0 or tol_mm <= 0:
        return None

    tol_um = tol_mm * 1000  # 轉為 μm
    grades = get_all_tolerances(nominal_mm)

    # 從最精密 (IT01) 往最粗 (IT18) 找
    best = None
    best_diff = float('inf')

    for name in IT_GRADE_NAMES:
        grade_um = grades[name]
        diff = abs(grade_um - tol_um)
        if diff < best_diff:
            best_diff = diff
            best = name

    # 如果最接近的 IT 等級差距超過 50%，可能是不合理的
    if best:
        grade_um = grades[best]
        ratio = tol_um / grade_um if grade_um > 0 else 999
        if ratio > 3.0:
            # 公差值比 IT18 還大很多，標記為粗放
            return None

    return best


# ═══════════════════════════════════════════════════════════════
# ISO 2768-2 (DIN ISO 2768 T2) 一般幾何公差表
# 來源：ISO 2768-2 官方標準（見 ISO-2768.pdf Page 2）
#
# ISO 2768-2 只涵蓋 4 種幾何公差：
#   1. Straightness & Flatness (真直度/平面度)
#   2. Perpendicularity (垂直度)
#   3. Symmetry (對稱度)
#   4. Run-out (圓偏轉度)
#
# ⚠ 不涵蓋：平行度(PAR)、同心度(CO)、位置度(POS)、圓柱度(CYL)
#   這些若出現在圖面上，皆為「設計者個別指定」
# ═══════════════════════════════════════════════════════════════

# 1. STRAIGHTNESS AND FLATNESS (真直度/平面度)
# 格式：(length_up_to_mm, H_mm, K_mm, L_mm)
ISO_2768_2_FLATNESS = [
    (10,   0.02,  0.05,  0.1),
    (30,   0.05,  0.1,   0.2),
    (100,  0.1,   0.2,   0.4),
    (300,  0.2,   0.4,   0.8),
    (1000, 0.3,   0.6,   1.2),
    (3000, 0.4,   0.8,   1.6),
]

# 2. PERPENDICULARITY (垂直度) — 數值來自 PDF Page 2
# 格式：(length_up_to_mm, H_mm, K_mm, L_mm)
ISO_2768_2_PERPENDICULARITY = [
    (100,  0.2,  0.4,  0.6),
    (300,  0.3,  0.6,  1.0),
    (1000, 0.4,  0.8,  1.5),
    (3000, 0.5,  0.8,  2.0),
]

# 3. SYMMETRY (對稱度)
# 格式：(length_up_to_mm, H_mm, K_mm, L_mm)
ISO_2768_2_SYMMETRY = [
    (100,  0.5,  0.6,  0.6),
    (300,  0.5,  0.6,  1.0),
    (1000, 0.5,  0.8,  1.5),
    (3000, 0.5,  1.0,  2.0),
]

# 4. RUN-OUT (圓偏轉度) — 不依尺寸，固定三級
ISO_2768_2_RUNOUT = {'H': 0.1, 'K': 0.2, 'L': 0.5}

# ── 公差類型分類 ──
# 尺寸公差：可用 ISO 286-1 反查 IT
DIMENSIONAL_TYPES = {'DIA', 'DIS', 'RAD'}

# ISO 2768-2 涵蓋的幾何公差
ISO2768_COVERED = {
    'FLA': 'FLATNESS',        # → 查 STRAIGHTNESS AND FLATNESS 表
    'STR': 'FLATNESS',        # → 查 STRAIGHTNESS AND FLATNESS 表
    'PER': 'PERPENDICULARITY',# → 查 PERPENDICULARITY 表
    'SYM': 'SYMMETRY',        # → 查 SYMMETRY 表
    'RUN': 'RUNOUT',          # → 查 RUN-OUT
    'TOT': 'RUNOUT',          # 總偏轉 → 同 RUN-OUT
}

# ISO 2768-2 不涵蓋 → 設計者個別指定
ISO2768_NOT_COVERED = {
    'PAR': '平行度 — ISO 2768-2 未涵蓋，為設計者個別指定',
    'CO':  '同心度 — ISO 2768-2 未涵蓋，為設計者個別指定',
    'POS': '位置度 — ISO 2768-2 未涵蓋，為設計者個別指定',
    'CYL': '圓柱度 — ISO 2768-2 未涵蓋，為設計者個別指定',
    'ANG': '角度 — 查 ISO 2768-1 角度公差表',
}


def _lookup_table_grade(table, length_mm, tol_mm):
    """在 ISO 2768-2 表格中查詢等級 (H/K/L)"""
    length = length_mm or 100
    for up_to, h, k, l in table:
        if length <= up_to:
            ref_H = h
            if tol_mm < h:
                return '< H', ref_H
            elif tol_mm <= h * 1.05:  # 容許 5% 誤差視為 H
                return 'H', ref_H
            elif tol_mm <= k:
                return 'K', ref_H
            elif tol_mm <= l:
                return 'L', ref_H
            else:
                return '> L', ref_H
    return '> L', None


def classify_geo_tolerance(tol_type, tol_mm, ref_length_mm=None):
    """
    對幾何公差進行分級。

    ISO 2768-2 涵蓋的類型 → 查表分級 (H/K/L)
    ISO 2768-2 不涵蓋的類型 → 標記為「設計者個別指定」

    Returns:
        {
            'standard': str,           # 適用標準
            'grade': str,              # H / K / L / < H / > L / 個別指定
            'ref_H': float or None,    # H 級閾值 (mm)
            'note': str,               # 備註說明
        }
    """
    tol_type_upper = tol_type.upper()
    result = {'standard': '', 'grade': '', 'ref_H': None, 'note': ''}

    # ── 真圓度 (CIR)：特殊 — 等同直徑的 IT 等級 ──
    if tol_type_upper == 'CIR':
        result['standard'] = 'ISO 286-1'
        result['grade'] = 'see IT'
        result['note'] = '真圓度等同直徑公差，以 ISO 286 IT 等級表示'
        return result

    # ── ISO 2768-2 涵蓋的類型 ──
    if tol_type_upper in ISO2768_COVERED:
        category = ISO2768_COVERED[tol_type_upper]
        result['standard'] = 'ISO 2768-2'

        if category == 'FLATNESS':
            grade, ref_h = _lookup_table_grade(ISO_2768_2_FLATNESS, ref_length_mm, tol_mm)
        elif category == 'PERPENDICULARITY':
            grade, ref_h = _lookup_table_grade(ISO_2768_2_PERPENDICULARITY, ref_length_mm, tol_mm)
        elif category == 'SYMMETRY':
            grade, ref_h = _lookup_table_grade(ISO_2768_2_SYMMETRY, ref_length_mm, tol_mm)
        elif category == 'RUNOUT':
            ref_h = ISO_2768_2_RUNOUT['H']
            if tol_mm < ISO_2768_2_RUNOUT['H']:
                grade = '< H'
            elif tol_mm <= ISO_2768_2_RUNOUT['H'] * 1.05:
                grade = 'H'
            elif tol_mm <= ISO_2768_2_RUNOUT['K']:
                grade = 'K'
            elif tol_mm <= ISO_2768_2_RUNOUT['L']:
                grade = 'L'
            else:
                grade = '> L'
        else:
            grade, ref_h = 'N/A', None

        result['grade'] = grade
        result['ref_H'] = ref_h
        if grade == '< H':
            result['note'] = '比 ISO 2768-2 最精密的 H 級還嚴格，為設計者特殊指定'
        return result

    # ── ISO 2768-2 不涵蓋的類型 ──
    if tol_type_upper in ISO2768_NOT_COVERED:
        result['standard'] = '個別指定'
        result['grade'] = '個別指定'
        result['note'] = ISO2768_NOT_COVERED[tol_type_upper]
        return result

    # ── 未知類型 ──
    result['standard'] = 'N/A'
    result['grade'] = 'N/A'
    return result


def extract_tol_type(code: str) -> str:
    """從公差代號提取公差類型 (e.g. '工作臺心軸-FLA1' → 'FLA')"""
    m = re.match(r'^.+-([A-Za-z]+)\d+$', code.strip())
    if m:
        return m.group(1).upper()
    return ''


# ═══════════════════════════════════════════════
# RAS400 零件 CSV 路徑
# ═══════════════════════════════════════════════
CSV_DIR = r'C:\Users\User\Downloads'
CSV_FILES = [
    '工作臺.csv', '軸承座.csv', '軸承.csv', '轉動軸.csv', '工作臺心軸.csv',
    '馬達.csv', '馬達水套.csv', '編碼器心軸.csv', '分流座.csv', '馬達座.csv', '編碼器.csv',
]


def process_csv(filepath: str, dry_run: bool = True) -> tuple[int, int, list]:
    """
    處理單個 CSV 檔案，補齊 IT 等級。

    分類邏輯：
      - 尺寸公差 (DIA/DIS/RAD) → ISO 286-1 反查 IT 等級
      - 幾何公差 (FLA/PAR/PER/CYL/CIR/CO/SYM/RUN...) → ISO 2768-2 分級 (H/K/L)
      - 真圓度 (CIR) → 特殊：等同直徑的 IT 等級，用 ISO 286 查

    Returns: (total_rows, filled_count, details_list)
    """
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    filled = 0
    details = []

    # 第一輪：收集所有特徵面的公稱尺寸
    feature_nominal = {}
    for row in rows:
        feat_codes = row.get('特徵代號', '').strip()
        nominal_str = row.get('公稱尺寸', '').strip()
        if feat_codes and nominal_str:
            try:
                nominal = float(nominal_str)
                for fc in feat_codes.split(','):
                    fc = fc.strip()
                    if fc and nominal > 0:
                        if fc not in feature_nominal or nominal > feature_nominal[fc]:
                            feature_nominal[fc] = nominal
            except ValueError:
                pass

    # 第二輪：分類處理
    for row in rows:
        code = row.get('公差代號', '').strip()
        it_grade = row.get('IT等級', '').strip()
        tol_val_str = row.get('公差數值', '').strip()
        nominal_str = row.get('公稱尺寸', '').strip()
        feat_codes = row.get('特徵代號', '').strip()

        if it_grade or not tol_val_str or 'DAT' in code.upper():
            continue

        try:
            tol_val = float(tol_val_str)
        except ValueError:
            continue
        if tol_val <= 0:
            continue

        # 判斷公差類型
        tol_type = extract_tol_type(code)

        # 取得公稱尺寸 (DIA/DIS 本身有；幾何公差從特徵面借)
        nominal = None
        if nominal_str:
            try:
                nominal = float(nominal_str)
            except ValueError:
                pass
        if not nominal or nominal <= 0:
            if feat_codes:
                for fc in feat_codes.split(','):
                    fc = fc.strip()
                    if fc in feature_nominal:
                        nominal = feature_nominal[fc]
                        break
        if not nominal or nominal <= 0:
            if feature_nominal:
                nominal = max(feature_nominal.values())

        # ═══════════════════════════════════════════
        # 路徑 A：尺寸公差 → ISO 286-1 反查 IT
        # ═══════════════════════════════════════════
        if tol_type in DIMENSIONAL_TYPES:
            if not nominal or nominal <= 0:
                details.append({
                    'code': code, 'type': tol_type,
                    'status': 'SKIP', 'reason': 'no nominal size',
                    'tol_val': tol_val, 'category': 'dimensional',
                })
                continue

            it_result = reverse_lookup_it(nominal, tol_val)
            if it_result:
                it_num = it_result.replace('IT', '')
                row['IT等級'] = it_num
                filled += 1
                details.append({
                    'code': code, 'type': tol_type,
                    'status': 'FILLED_IT', 'category': 'dimensional',
                    'nominal': nominal, 'tol_mm': tol_val,
                    'tol_um': tol_val * 1000, 'it_grade': it_result,
                })
            else:
                details.append({
                    'code': code, 'type': tol_type,
                    'status': 'NO_MATCH', 'category': 'dimensional',
                    'nominal': nominal, 'tol_mm': tol_val,
                    'tol_um': tol_val * 1000,
                    'reason': 'tolerance too large for IT18',
                })

        # ═══════════════════════════════════════════
        # 路徑 B：真圓度 → 等同直徑的 IT 等級
        # ═══════════════════════════════════════════
        elif tol_type == 'CIR':
            if not nominal or nominal <= 0:
                details.append({
                    'code': code, 'type': tol_type,
                    'status': 'SKIP', 'reason': 'no nominal size for CIR',
                    'tol_val': tol_val, 'category': 'geometric',
                })
                continue

            it_result = reverse_lookup_it(nominal, tol_val)
            if it_result:
                it_num = it_result.replace('IT', '')
                row['IT等級'] = it_num
                filled += 1
                details.append({
                    'code': code, 'type': tol_type,
                    'status': 'FILLED_IT', 'category': 'geometric (CIR=IT)',
                    'nominal': nominal, 'tol_mm': tol_val,
                    'tol_um': tol_val * 1000, 'it_grade': it_result,
                })
            else:
                details.append({
                    'code': code, 'type': tol_type,
                    'status': 'NO_MATCH', 'category': 'geometric',
                    'nominal': nominal, 'tol_mm': tol_val,
                    'tol_um': tol_val * 1000,
                })

        # ═══════════════════════════════════════════
        # 路徑 C：幾何公差 → ISO 2768-2 分級
        # ═══════════════════════════════════════════
        else:
            ref_length = nominal  # 用公稱尺寸作為參考長度
            geo_result = classify_geo_tolerance(tol_type, tol_val, ref_length)
            grade_2768 = geo_result['grade']

            # 不寫入 IT 欄位（幾何公差不屬於 IT 體系）
            # 但記錄分級結果供報告
            details.append({
                'code': code, 'type': tol_type,
                'status': 'GEO_CLASSIFIED', 'category': 'geometric',
                'tol_mm': tol_val, 'tol_um': tol_val * 1000,
                'ref_length': ref_length,
                'standard': geo_result.get('standard', ''),
                'iso2768_grade': grade_2768,
                'ref_H': geo_result.get('ref_H'),
                'note': geo_result.get('note', ''),
            })

    # 寫回
    if not dry_run and filled > 0:
        with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    return len(rows), filled, details


def main():
    dry_run = '--write' not in sys.argv
    mode_str = 'DRY RUN (preview)' if dry_run else 'WRITE MODE'
    print(f'=== fill_it_grades.py — {mode_str} ===\n')

    total_all = 0
    filled_it = 0
    geo_count = 0

    for fname in CSV_FILES:
        fpath = os.path.join(CSV_DIR, fname)
        if not os.path.exists(fpath):
            print(f'[SKIP] {fname} not found')
            continue

        total, filled, details = process_csv(fpath, dry_run=dry_run)
        total_all += total
        filled_it += filled

        if details:
            part_name = fname.replace('.csv', '')
            # Count geo items
            geo_items = [d for d in details if d['status'] == 'GEO_CLASSIFIED']
            geo_count += len(geo_items)
            it_items = [d for d in details if d['status'] == 'FILLED_IT']

            print(f'\n--- {part_name} (IT:{len(it_items)}, GEO:{len(geo_items)}) ---')
            for d in details:
                if d['status'] == 'FILLED_IT':
                    ref_grades = get_all_tolerances(d['nominal'])
                    grade_val = ref_grades.get(d['it_grade'], '?')
                    print(f"  [ISO 286] {d['code']:<25} "
                          f"{d['type']:<4} nom={d['nominal']:>6}mm  "
                          f"tol={d['tol_um']:>7.1f}um  => {d['it_grade']} "
                          f"(table={grade_val}um)")

                elif d['status'] == 'GEO_CLASSIFIED':
                    ref_h = d.get('ref_H')
                    std = d.get('standard', 'ISO 2768-2')
                    grade = d.get('iso2768_grade', '')
                    ref_str = f"(H={ref_h}mm)" if ref_h else ''
                    tag = '[2768-2]' if '2768' in std else '[SPEC]  '
                    print(f"  {tag}  {d['code']:<25} "
                          f"{d['type']:<4} tol={d['tol_um']:>7.1f}um  "
                          f"=> {std}: {grade} {ref_str}")

                elif d['status'] == 'SKIP':
                    print(f"  [SKIP]    {d['code']:<25} "
                          f"tol={d['tol_val']}mm  {d['reason']}")

                elif d['status'] == 'NO_MATCH':
                    print(f"  [WARN]    {d['code']:<25} "
                          f"nom={d.get('nominal',0):>6}mm  "
                          f"tol={d['tol_um']:>7.1f}um  => no match")

    print(f'\n=== Summary ===')
    print(f'  IT grades filled (ISO 286-1):     {filled_it}')
    print(f'  Geometric classified (ISO 2768-2): {geo_count}')
    if dry_run:
        print('>>> DRY RUN. Use --write to save.')


if __name__ == '__main__':
    main()
