"""Smoke test for PlanService + Matchmaking — runs without Flask."""

import io
import sys
import os
import json

# Force UTF-8 on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# 確保可以從 server/ 內 import
HERE = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, SERVER_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(SERVER_DIR, '.env'))
except Exception:
    pass

from services.plan_service import PlanService  # noqa: E402
from services.matchmaking_service import MatchmakingService  # noqa: E402
from recommendation import smart_fit  # noqa: E402


def section(title):
    print('\n' + '=' * 78)
    print(title)
    print('=' * 78)


def smoke_plan_service():
    svc = PlanService()
    section('Plan 1: focused (軸承座/轉動軸/工作臺心軸)')
    plan1 = svc.recommend_plan1()
    for r in plan1:
        print(f"  {r['pair_id']}  {r['hole_part']}-{r['hole_feature']} <-> "
              f"{r['shaft_part']}-{r['shaft_feature']} (Φ{r['nominal_dia']:.0f}) "
              f"-> {r['fit_code']} [{r['ansi']}]  band={r['tol_band_um']}μm  "
              f"reason: {r['reason']}")



def smoke_matchmaking_full_db():
    """跑完 42 筆配合資料，確認每筆都能完整跑完 MatchmakingService.run()。"""
    section('Matchmaking: full DB sweep (42 rows)')
    ms = MatchmakingService()
    rows = smart_fit.fits_database
    spec_only_count = 0
    for r in rows:
        # 用該列「自身」的單一 tag 觸發搜尋（若沒 tag 則跳過）
        if not r['tags']:
            continue
        first_tag = sorted(r['tags'])[0]
        try:
            res = ms.run(
                diameter=50,
                dimensions={'required': [first_tag]},
                safety_factor=1.0,
            )
            spec = res['step2_fit_details'].get('spec_only', False)
            if spec:
                spec_only_count += 1
            print(f"  {r['ansi']:<10} src={r['source']:<14} via=[{first_tag}]  "
                  f"top={res['step1_selected_fit']['ansi']}  "
                  f"spec_only={spec}")
        except ValueError as e:
            print(f"  {r['ansi']:<10} src={r['source']:<14} via=[{first_tag}]  ERROR: {e}")
    print(f"\n  spec_only fallback 觸發: {spec_only_count} 筆")


def smoke_matchmaking_dimension_cases():
    """斷言一組維度組合 → 期望的 ANSI 編號。"""
    section('Matchmaking: dimension expectations')
    ms = MatchmakingService()
    cases = [
        # (required, optional, expected_top_ansi)
        ({'中速旋轉', '中軸頸壓力'},     set(),       'RC4'),
        ({'高速旋轉', '重軸頸壓力'},     set(),       None),  # 多列同分；只驗 score
        ({'剛性對準'},                   {'精確'},   'LN2'),
        ({'強制壓入'},                   set(),       None),  # FN4/FN5/H7/u6 同分
        ({'定位', '可裝拆'},             set(),       None),  # LC1/LC2 ...
    ]
    for required, optional, expected in cases:
        scored = smart_fit.search_by_tags(required=required, optional=optional)
        if not scored:
            print(f"  required={sorted(required)} optional={sorted(optional)} -> NO MATCH")
            continue
        top = scored[0]
        ok = (expected is None) or (top['item']['ansi'] == expected)
        flag = '✓' if ok else '✗'
        print(f"  {flag} required={sorted(required)} optional={sorted(optional)}  "
              f"-> {top['item']['ansi']} (score={top['score']}, src={top['item']['source']})")


def smoke_keyword_backward_compat():
    section('Matchmaking: keyword backward-compat')
    ms = MatchmakingService()
    for kws in [['壓入'], ['滑動'], ['定位']]:
        try:
            res = ms.run(keywords=kws, diameter=50)
            print(f"  keywords={kws}  -> {res['step1_selected_fit']['ansi']}  "
                  f"src={res['step1_selected_fit']['source']}  "
                  f"mode={res['input']['search_mode']}")
        except ValueError as e:
            print(f"  keywords={kws}  -> ERROR: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# 黃金對應清單 — 來源：server/data/docs/功能描述查詢指南.md §四
# ─────────────────────────────────────────────────────────────────────────────
# (label, required_tags, expected_ansi)
# 文件描述的零件配對 → 應該選擇的功能 → 推薦配合
GOLDEN_PART_PAIRS = [
    ('工作臺(1) ↔ 工作臺心軸(5)',     {'定位', '精確', '過渡', '可裝拆'}, 'H7/k6'),
    ('軸承座(2) ↔ 軸承(3) 外圈',       {'定位', '固定'},                    'H6'),
    ('軸承座(2) ↔ 馬達座(10)',         {'定位', '固定', '可裝拆'},          'H7/h6'),
    ('軸承YRT(3) ↔ 軸承座(2) 外圈',    {'定位', '固定'},                    'H6'),
    ('軸承YRT(3) ↔ 工作臺心軸(5) 內圈', {'定位', '過渡'},                   'js5'),
    ('轉動軸(4) ↔ 工作臺心軸(5)',      {'壓入', '強制壓入'},                'H7/u6'),
    ('馬達(6) ↔ 馬達水套(7)',          {'壓入', '中壓入'},                  'H7/s6'),
    ('馬達水套(7) ↔ 馬達座(10)',       {'定位', '固定', '可裝拆'},          'H7/h6'),
    ('編碼器心軸(8) ↔ 工作臺心軸(5)',  {'定位', '精確', '可裝拆'},          'H7/h6'),
    ('分流座(9) ↔ 馬達座(10)',         {'定位', '固定', '可裝拆'},          'H7/h6'),
    ('編碼器(11) ↔ 馬達座(10)',        {'定位', '固定', '可裝拆'},          'H7/h6'),
]


def smoke_golden_part_pairs():
    """文件 §四 RAS-400 各零件功能對應 → 驗證搜尋引擎是否符合預期。

    報告格式：
      ✓ #1   完全符合 (預期 ansi 排第一)
      ◯ #N   命中於前 N 名（同分多筆 fallback 排序）
      ✗      預期 ansi 完全不在結果中
    """
    section('Golden: RAS-400 §四 零件配對對應 (11 筆)')
    rank1 = rank_topN = miss = 0
    for label, required, expected in GOLDEN_PART_PAIRS:
        scored = smart_fit.search_by_tags(required=required)
        ansis = [s['item']['ansi'] for s in scored]
        if not ansis:
            mark = '✗'; rank = '-'
            miss += 1
        elif ansis[0] == expected:
            mark = '✓ #1'; rank = 1
            rank1 += 1
        elif expected in ansis:
            rank = ansis.index(expected) + 1
            mark = f'◯ #{rank}'
            rank_topN += 1
        else:
            mark = '✗ NOT FOUND'; rank = '-'
            miss += 1

        top3 = ', '.join(ansis[:3]) if ansis else '(empty)'
        print(f"  {mark:<10} {label:<35}  required={sorted(required)!s:<40}")
        print(f"           expected={expected:<8}  top-3=[{top3}]")

    print()
    print(f"  Summary: {rank1} 筆 #1 完美命中 / {rank_topN} 筆排在前 N "
          f"/ {miss} 筆未命中  (共 {len(GOLDEN_PART_PAIRS)} 筆)")


def main():
    smoke_plan_service()
    smoke_matchmaking_full_db()
    smoke_matchmaking_dimension_cases()
    smoke_keyword_backward_compat()
    smoke_golden_part_pairs()


if __name__ == '__main__':
    main()
