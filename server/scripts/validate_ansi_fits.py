"""validate_ansi_fits.py — 一次性校驗：對 ansi_fits_updated.csv 每一列嘗試做
ISO 286 fit lookup，把所有「無法 parse」「parse 成功但查無資料」的列列出來，
產生白名單建議清單。

用法：
    python server/scripts/validate_ansi_fits.py
"""

import csv
import io
import os
import re
import sys
from collections import Counter

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.normpath(os.path.join(HERE, '..'))
PROJECT_ROOT = os.path.normpath(os.path.join(SERVER_DIR, '..'))
sys.path.insert(0, SERVER_DIR)

# 載入 .env
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(SERVER_DIR, '.env'))
except Exception:
    pass

from services.fit_service import FitService  # noqa: E402

CSV_PATH = os.path.join(PROJECT_ROOT, 'ansi_fits_updated.csv')
TEST_DIAMETERS = [10, 30, 50, 80, 120, 250]  # 多個尺寸測試（涵蓋各 ISO size band）

ISO_TOKEN_RE = re.compile(r'^[A-Za-z]+\d+$')  # 合法 ISO 代號的形式


def categorize_token(s: str) -> str:
    """對 hole/shaft 欄字串歸類。"""
    s = (s or '').strip()
    if not s:
        return 'EMPTY'
    if ISO_TOKEN_RE.match(s):
        return 'ISO'
    return 'NON_ISO'


def main():
    if not os.path.exists(CSV_PATH):
        print(f'[ERROR] 找不到 {CSV_PATH}')
        sys.exit(1)

    svc = FitService()
    rows = []
    with open(CSV_PATH, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    print(f'[INFO] 載入 {len(rows)} 筆配合資料\n')

    # 統計
    stats = Counter()
    parse_fail = []          # parse_notation 失敗（其中一邊不是 ISO 代號）
    db_miss = []             # parse 過但 DB 查無
    success = []             # 全 OK
    non_iso_tokens = Counter()  # 所有非 ISO 字樣

    for i, row in enumerate(rows, start=2):  # 從 2 起算（含 CSV 標頭）
        ansi = row.get('ansi', '').strip()
        hole_tol_str = (row.get('shaft') or '').strip()  # 欄名反直覺：shaft 欄裝 H 系列
        shaft_dev_str = (row.get('hole') or '').strip()  # 欄名反直覺：hole 欄裝小寫軸偏差

        cat_h = categorize_token(hole_tol_str)
        cat_s = categorize_token(shaft_dev_str)

        if cat_h != 'ISO':
            non_iso_tokens[hole_tol_str] += 1
        if cat_s != 'ISO':
            non_iso_tokens[shaft_dev_str] += 1

        if cat_h != 'ISO' or cat_s != 'ISO':
            parse_fail.append({
                'line': i,
                'ansi': ansi,
                'hole_tol': hole_tol_str,
                'shaft_dev': shaft_dev_str,
                'note': row.get('note', '').strip(),
                'reason': f'hole_tol={cat_h}, shaft_dev={cat_s}',
            })
            stats['parse_fail'] += 1
            continue

        # 嘗試多個尺寸；只要有一個尺寸成功就算 SUCCESS
        ok_at = []
        miss_at = []
        for d in TEST_DIAMETERS:
            r = svc.get_fit_details_for_matchmaking(d, hole_tol_str, shaft_dev_str)
            if r:
                ok_at.append(d)
            else:
                miss_at.append(d)
        if ok_at:
            success.append({
                'line': i, 'ansi': ansi,
                'hole_tol': hole_tol_str, 'shaft_dev': shaft_dev_str,
                'ok_at_mm': ok_at, 'miss_at_mm': miss_at,
            })
            stats['success'] += 1
            if miss_at:
                stats['partial_size_miss'] += 1
        else:
            db_miss.append({
                'line': i, 'ansi': ansi,
                'hole_tol': hole_tol_str, 'shaft_dev': shaft_dev_str,
                'note': row.get('note', '').strip(),
            })
            stats['db_miss'] += 1

    # ── 輸出報告 ────────────────────────────────────────────────────────────
    print('=' * 80)
    print('校驗摘要')
    print('=' * 80)
    print(f'  總列數                    : {len(rows)}')
    print(f'  ✓ ISO lookup 成功         : {stats["success"]}')
    print(f'    其中部分尺寸無資料      : {stats["partial_size_miss"]}')
    print(f'  ✗ Parse 失敗 (非 ISO 代號) : {stats["parse_fail"]}')
    print(f'  ✗ Parse OK 但 DB 查無      : {stats["db_miss"]}')
    print()

    if parse_fail:
        print('=' * 80)
        print(f'[A] 非 ISO 代號 (需加白名單) — 共 {len(parse_fail)} 筆')
        print('=' * 80)
        for p in parse_fail:
            print(f"  L{p['line']:>3}  {p['ansi']:<18} hole_tol={p['hole_tol']!r:<24} "
                  f"shaft_dev={p['shaft_dev']!r:<10} ← {p['note']}")
        print()
        print('  → 出現過的非 ISO 字樣:')
        for tok, cnt in non_iso_tokens.most_common():
            print(f'      {tok!r}  × {cnt}')
        print()

    if db_miss:
        print('=' * 80)
        print(f'[B] Parse 通過但 DB 查無 (可能 IT 等級超出表範圍) — 共 {len(db_miss)} 筆')
        print('=' * 80)
        for p in db_miss:
            print(f"  L{p['line']:>3}  {p['ansi']:<10} {p['hole_tol']}/{p['shaft_dev']:<8} ← {p['note']}")
        print()

    print('=' * 80)
    print(f'[C] 部分尺寸 lookup 失敗 (DB 在某些尺寸 band 缺資料)')
    print('=' * 80)
    partial = [s for s in success if s['miss_at_mm']]
    for s in partial:
        print(f"  L{s['line']:>3}  {s['ansi']:<18} {s['hole_tol']}/{s['shaft_dev']:<6} "
              f"ok@{s['ok_at_mm']}  miss@{s['miss_at_mm']}")
    if not partial:
        print('  (無)')
    print()

    print('=' * 80)
    print('白名單建議 (NON_ISO_FIT_TOKENS)')
    print('=' * 80)
    suggested = sorted({k for k, _ in non_iso_tokens.items()})
    print('NON_ISO_FIT_TOKENS = {')
    for tok in suggested:
        print(f'    {tok!r},')
    print('}')
    print()


if __name__ == '__main__':
    main()
