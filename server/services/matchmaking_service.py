"""matchmaking_service.py - 製程與機台媒合業務邏輯

整合 smart_fit → ISO 公差查詢 → 機台篩選 → 製程建議，並產出報表文字。
Controllers 依需求決定如何同步報表（HTTP 或直接 graph_rag）。
"""

import re
from recommendation import smart_fit, machine_check
from services.fit_service import FitService


class MatchmakingService:
    def __init__(self):
        self._fit_svc = FitService()

    def run(self, keywords: list, diameter: float, safety_factor: float = 1.0) -> dict:
        """執行完整媒合流程，回傳結果 dict 或拋出 ValueError。"""
        # Step 1 — 搜尋公差配合知識庫
        fits = smart_fit.search_fits(keywords)
        if not fits:
            raise ValueError('找不到對應的公差配合')

        best_fit  = fits[0]
        hole_str  = best_fit.get('hole', '')
        shaft_str = best_fit.get('shaft', '')

        # Step 2 — 查詢 ISO 公差詳細數值
        fit_details = self._fit_svc.get_fit_details_for_matchmaking(
            diameter, hole_str, shaft_str
        )

        # Step 3 — 機台媒合
        machine_res = machine_check.find_capable_machines(
            diameter, safety_factor=safety_factor, keywords=keywords
        )

        # Step 4 — 應用場景
        application_scenario = {
            'function': best_fit.get('function', ''),
            'note':     best_fit.get('note', ''),
            'type':     best_fit.get('type', ''),
        }

        # Step 5 — 製程建議
        process_recommendation = self._build_process_recommendation(
            hole_str, shaft_str, diameter
        )

        return {
            'input':              {'diameter': diameter, 'keywords': keywords},
            'step1_selected_fit': best_fit,
            'step2_fit_details':  fit_details,
            'step3_capable_machines':     machine_res.get('machines', []),
            'step4_application_scenario': application_scenario,
            'step5_process_recommendation': process_recommendation,
            '_machines_raw': machine_res,   # 供 build_report_text 使用
        }

    # ── 製程建議 ──────────────────────────────────────────────────────────────

    @staticmethod
    def _build_process_recommendation(hole_str: str, shaft_str: str, diameter: float) -> dict:
        try:
            from recommendation.process_advisor import recommend_full

            hole_it_num  = int(re.search(r'\d+', hole_str).group())  if re.search(r'\d+', hole_str)  else None
            shaft_it_num = int(re.search(r'\d+', shaft_str).group()) if re.search(r'\d+', shaft_str) else None

            hole_rec  = recommend_full(hole_it_num,  'H', diameter) if hole_it_num  else None
            shaft_rec = recommend_full(shaft_it_num, 'S', diameter) if shaft_it_num else None

            return {
                'hole_process': {
                    'it_grade':    f'IT{hole_it_num}',
                    'recommended': hole_rec['recommended_process'],
                    'chain':       [s['process_zh'] for s in hole_rec['process_chain']],
                    'Ra_target':   hole_rec['Ra_target'],
                    'equipment':   hole_rec.get('equipment'),
                } if hole_rec else None,
                'shaft_process': {
                    'it_grade':    f'IT{shaft_it_num}',
                    'recommended': shaft_rec['recommended_process'],
                    'chain':       [s['process_zh'] for s in shaft_rec['process_chain']],
                    'Ra_target':   shaft_rec['Ra_target'],
                    'equipment':   shaft_rec.get('equipment'),
                } if shaft_rec else None,
            }
        except Exception as e:
            print(f'[WARN] 製程建議產生失敗: {e}')
            return {}

    # ── 報表文字產生 ───────────────────────────────────────────────────────────

    @staticmethod
    def build_report_text(result: dict) -> str:
        """根據媒合結果產生純文字報表，供 AI 同步使用。"""
        d           = result['input']['diameter']
        keywords    = result['input']['keywords']
        fit         = result['step2_fit_details']
        app_scene   = result['step4_application_scenario']
        proc        = result['step5_process_recommendation']
        machines    = result.get('step3_capable_machines', [])

        best        = result['step1_selected_fit']
        hole_str    = best.get('hole', '')
        shaft_str   = best.get('shaft', '')

        hp = (proc.get('hole_process')  or {})
        sp = (proc.get('shaft_process') or {})

        machine_lines = []
        for i, m in enumerate(machines[:10], 1):
            reason = m.get('recommend_reason', '符合精度要求')
            machine_lines.append(f'  {i}. {m.get("model")} ({m.get("company")}): {reason}')

        lines = [
            '【最新零件媒合報表】',
            f'- 輸入直徑: {d} mm',
            f'- 關鍵字(功能): {", ".join(keywords)}',
            f'- 建議配合: {hole_str}/{shaft_str} ({fit.get("fit_type", "未知")})',
            f'  * 孔 {hole_str}: +{fit.get("hole", {}).get("upper_um")} / +{fit.get("hole", {}).get("lower_um")} um',
            f'  * 軸 {shaft_str}: {fit.get("shaft", {}).get("upper_um")} / {fit.get("shaft", {}).get("lower_um")} um',
            f'- 配合特性: 間隙 {fit.get("max_clearance_um")} ~ {fit.get("min_clearance_um")} um',
            f'- 適合應用: {app_scene.get("function")} ({app_scene.get("type")})',
            '- 製程建議:',
            f'  * 孔加工: {" → ".join(hp.get("chain", ["N/A"]))} ({hp.get("Ra_target", "N/A")})' if hp else '  * 孔加工: N/A',
            f'  * 軸加工: {" → ".join(sp.get("chain", ["N/A"]))} ({sp.get("Ra_target", "N/A")})' if sp else '  * 軸加工: N/A',
            '- 推薦機台 (Top 10):',
            *machine_lines,
        ]
        return '\n'.join(lines)
