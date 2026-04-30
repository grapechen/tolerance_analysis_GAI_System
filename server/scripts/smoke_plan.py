"""Smoke test for PlanService — runs Plan 1 and Plan 2 without Flask."""

import sys
import os
import json

# 確保可以從 server/ 內 import
HERE = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, SERVER_DIR)

from services.plan_service import PlanService, DEFAULT_STACK_CHAIN  # noqa: E402


def main() -> None:
    svc = PlanService()
    print('=== Plan 1: focused (軸承座/轉動軸/工作臺心軸) ===')
    plan1 = svc.recommend_plan1()
    for r in plan1:
        print(f"  {r['pair_id']}  {r['hole_part']}-{r['hole_feature']} <-> "
              f"{r['shaft_part']}-{r['shaft_feature']} (Φ{r['nominal_dia']:.0f}) "
              f"-> {r['fit_code']} [{r['ansi']}]  band={r['tol_band_um']}μm  "
              f"reason: {r['reason']}")

    print('\n=== Plan 2: stack-up adjust on default chain ===')
    print(f"  chain = {DEFAULT_STACK_CHAIN}")
    # 把全部 12 對都拿來，因為鏈裡有 MP01/MP10 可能不在 focus 內
    plan1_all = svc.recommend_plan1(focus_parts=None)
    plan2 = svc.adjust_plan2(plan1_all)
    print(f"  rss_before = {plan2['rss_before_um']}μm   rss_after = {plan2['rss_after_um']}μm")
    print(f"  wc_before  = {plan2['wc_before_um']}μm   wc_after  = {plan2['wc_after_um']}μm")
    for c in plan2['changes']:
        print(f"  {c['pair_id']:<4} {c['action']:<7} contrib={c['contribution_pct']:>5.1f}%  "
              f"{c['before']['fit_code']} -> {c['after']['fit_code']}  Δ={c['delta_um']:+.1f}μm  ({c['reason']})")


if __name__ == '__main__':
    main()
