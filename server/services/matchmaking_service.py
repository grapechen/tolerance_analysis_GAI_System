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

    def run(
        self,
        keywords: list = None,
        diameter: float = 50,
        safety_factor: float = 1.0,
        dimensions: dict = None,
    ) -> dict:
        """執行完整媒合流程，回傳結果 dict 或拋出 ValueError。

        Args:
          keywords:    舊版自由文字 keyword 列表
          dimensions:  新版維度勾選，格式 {'required': [...], 'optional': [...]}
          diameter:    公稱直徑（mm）
          safety_factor: 機台精度安全係數

        dimensions 與 keywords 二擇一；dimensions 優先。
        """
        # Step 1 — 搜尋公差配合知識庫
        if dimensions and (dimensions.get('required') or dimensions.get('optional')):
            scored = smart_fit.search_by_tags(
                required=set(dimensions.get('required') or []),
                optional=set(dimensions.get('optional') or []),
            )
            if not scored:
                raise ValueError('找不到符合維度條件的配合')
            best_fit = scored[0]['item']
            search_mode = 'dimensions'
            search_meta = {
                'top_score':    scored[0]['score'],
                'matched_tags': scored[0]['matched_tags'],
                'missing_tags': scored[0]['missing_tags'],
                'extra_tags':   scored[0]['extra_tags'],
                'total_hits':   len(scored),
            }
            # 提供給 machine_check 的 keywords，由命中標籤回推
            mc_keywords = scored[0]['matched_tags']
        else:
            keywords = keywords or []
            fits = smart_fit.search_fits(keywords)
            if not fits:
                raise ValueError('找不到對應的公差配合')
            best_fit = fits[0]
            search_mode = 'keywords'
            search_meta = {'total_hits': len(fits)}
            mc_keywords = keywords

        hole_str  = best_fit.get('hole_tol')  or best_fit.get('shaft', '')   # CSV shaft 欄 = 孔公差
        shaft_str = best_fit.get('shaft_dev') or best_fit.get('hole', '')    # CSV hole 欄 = 軸偏差

        # Step 2 — 查詢 ISO 公差詳細數值（spec_only fallback 由 FitService 內處理）
        fit_details = self._fit_svc.get_fit_details_for_matchmaking(
            diameter, hole_str, shaft_str
        )

        # Step 3 — 機台媒合
        machine_res = machine_check.find_capable_machines(
            diameter, safety_factor=safety_factor, keywords=mc_keywords
        )

        # Step 4 — 應用場景
        application_scenario = {
            'function':  best_fit.get('function', ''),
            'note':      best_fit.get('note', ''),
            'type':      best_fit.get('type', ''),
            'source':    best_fit.get('source', 'ANSI'),
            'is_approx': bool(best_fit.get('is_approx')),
        }

        # Step 5 — 製程建議（spec_only 時跳過）
        if fit_details.get('spec_only'):
            process_recommendation = {
                'skipped': True,
                'reason':  fit_details.get('note', '螺栓鎖附固定，不依賴 ISO 配合公差'),
            }
        else:
            process_recommendation = self._build_process_recommendation(
                hole_str, shaft_str, diameter
            )

        return {
            'input':              {
                'diameter':    diameter,
                'keywords':    keywords or [],
                'dimensions':  dimensions or {},
                'search_mode': search_mode,
            },
            'search_meta':        search_meta,
            'step1_selected_fit': best_fit,
            'step2_fit_details':  fit_details,
            'step3_capable_machines':     machine_res.get('machines', []),
            'step4_application_scenario': application_scenario,
            'step5_process_recommendation': process_recommendation,
            '_machines_raw': machine_res,   # 供 build_report_text 使用
        }

    # ── 製程建議 ──────────────────────────────────────────────────────────────

    # 解析 IT：只接受形如 H7/h6/g4/js5/x7 等開頭字母+數字（避免 'H7/u6' 抓錯）
    _IT_RE = re.compile(r'^[A-Za-z]+(\d+)')

    @classmethod
    def _extract_it(cls, code: str):
        m = cls._IT_RE.match((code or '').strip())
        return int(m.group(1)) if m else None

    @classmethod
    def _build_process_recommendation(cls, hole_str: str, shaft_str: str, diameter: float) -> dict:
        try:
            from recommendation.process_advisor import recommend_full

            hole_it_num  = cls._extract_it(hole_str)
            shaft_it_num = cls._extract_it(shaft_str)

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
        inp         = result['input']
        d           = inp['diameter']
        keywords    = inp.get('keywords', [])
        dims        = inp.get('dimensions') or {}
        search_mode = inp.get('search_mode', 'keywords')
        fit         = result['step2_fit_details']
        app_scene   = result['step4_application_scenario']
        proc        = result['step5_process_recommendation']
        machines    = result.get('step3_capable_machines', [])

        best        = result['step1_selected_fit']
        hole_str    = best.get('hole_tol')  or best.get('shaft', '')
        shaft_str   = best.get('shaft_dev') or best.get('hole', '')
        source      = app_scene.get('source', 'ANSI')
        is_approx   = app_scene.get('is_approx', False)

        # 搜尋條件描述
        if search_mode == 'dimensions':
            req = dims.get('required') or []
            opt = dims.get('optional') or []
            cond = f'維度: 必選=[{", ".join(req)}]'
            if opt:
                cond += f' / 可選=[{", ".join(opt)}]'
        else:
            cond = f'關鍵字(功能): {", ".join(keywords)}'

        # 配合內容（spec_only vs ISO 數值）
        if fit.get('spec_only'):
            fit_lines = [
                f'- 建議配合: {hole_str} ↔ {shaft_str} ({fit.get("fit_type", "螺栓鎖附固定")})',
                f'  * {fit.get("note", "")}',
            ]
        else:
            h = fit.get('hole', {}) or {}
            s = fit.get('shaft', {}) or {}
            fit_lines = [
                f'- 建議配合: {hole_str}/{shaft_str} ({fit.get("fit_type", "未知")})',
                f'  * 孔 {hole_str}: +{h.get("upper_um")} / +{h.get("lower_um")} um',
                f'  * 軸 {shaft_str}: {s.get("upper_um")} / {s.get("lower_um")} um',
                f'- 配合特性: 間隙 {fit.get("max_clearance_um")} ~ {fit.get("min_clearance_um")} um',
            ]

        # 來源標籤
        src_tag = {'ANSI': 'ANSI 標準', 'YRT100': 'YRT100 螺栓鎖附', 'RAS400_custom': 'RAS400 自訂'}.get(source, source)
        tag_line = f'- 配合來源: {src_tag}'
        if is_approx:
            tag_line += '  ⚠ 軸偏差為近似值，不在 ABC 協議範圍'

        # 製程
        if proc.get('skipped'):
            proc_lines = [f'- 製程建議: 跳過（{proc.get("reason", "")}）']
        else:
            hp = (proc.get('hole_process')  or {})
            sp = (proc.get('shaft_process') or {})
            proc_lines = [
                '- 製程建議:',
                f'  * 孔加工: {" → ".join(hp.get("chain", ["N/A"]))} ({hp.get("Ra_target", "N/A")})' if hp else '  * 孔加工: N/A',
                f'  * 軸加工: {" → ".join(sp.get("chain", ["N/A"]))} ({sp.get("Ra_target", "N/A")})' if sp else '  * 軸加工: N/A',
            ]

        machine_lines = []
        for i, m in enumerate(machines[:10], 1):
            reason = m.get('recommend_reason', '符合精度要求')
            machine_lines.append(f'  {i}. {m.get("model")} ({m.get("company")}): {reason}')

        lines = [
            '【最新零件媒合報表】',
            f'- 輸入直徑: {d} mm',
            f'- 搜尋條件: {cond}',
            *fit_lines,
            f'- 適合應用: {app_scene.get("function")} ({app_scene.get("type")})',
            tag_line,
            *proc_lines,
            '- 推薦機台 (Top 10):',
            *machine_lines,
        ]
        return '\n'.join(lines)

    # ── 批量媒合 ──────────────────────────────────────────────────────────────

    def run_batch(self, pairs: list) -> list:
        """批量執行媒合。每筆 pair 格式同 ras400_mating_pairs.csv，可附加 dimensions/keywords。

        回傳列表，每筆: {pair_id, pair, ok, data} 或 {pair_id, pair, ok:False, error}。
        """
        results = []
        for pair in pairs:
            pair_id      = pair.get('pair_id', '')
            diameter     = float(pair.get('nominal_dia') or 50)
            dimensions   = pair.get('dimensions') or {}
            keywords     = pair.get('keywords') or []
            function_desc = pair.get('function_desc', '')

            # 若無維度也無關鍵字，用 function_desc 做文字搜尋
            has_dims = bool(dimensions.get('required') or dimensions.get('optional'))
            if not has_dims and not keywords and function_desc:
                keywords = [function_desc]

            try:
                data = self.run(
                    keywords=keywords if not has_dims else None,
                    diameter=diameter,
                    dimensions=dimensions if has_dims else None,
                )
                results.append({'pair_id': pair_id, 'pair': pair, 'ok': True, 'data': data})
            except (ValueError, Exception) as exc:
                results.append({'pair_id': pair_id, 'pair': pair, 'ok': False, 'error': str(exc)})
        return results

    @staticmethod
    def build_batch_report_rows(batch_results: list) -> list:
        """將批量結果轉為報表列（list of dict），供前端渲染與 CSV 匯出。"""
        rows = []
        for item in batch_results:
            pair = item.get('pair', {})
            base = {
                'pair_id':       pair.get('pair_id', ''),
                'hole_part':     pair.get('hole_part', ''),
                'hole_feature':  pair.get('hole_feature', ''),
                'shaft_part':    pair.get('shaft_part', ''),
                'shaft_feature': pair.get('shaft_feature', ''),
                'nominal_dia':   pair.get('nominal_dia', ''),
                'function_desc': pair.get('function_desc', ''),
                'priority':      pair.get('priority', ''),
            }
            if not item.get('ok'):
                rows.append({**base,
                    'recommended_fit': '—', 'fit_type': '查無結果',
                    'hole_tol': '—', 'shaft_tol': '—',
                    'max_clearance_um': '', 'min_clearance_um': '',
                    'hole_it': '', 'shaft_it': '',
                    'hole_process': '', 'shaft_process': '',
                    'source': '', 'note': '',
                    'error': item.get('error', ''),
                })
                continue

            data      = item['data']
            fit       = data.get('step1_selected_fit', {})
            details   = data.get('step2_fit_details', {})
            proc      = data.get('step5_process_recommendation', {})
            app_scen  = data.get('step4_application_scenario', {})

            hole_str  = fit.get('hole_tol')  or fit.get('shaft', '')
            shaft_str = fit.get('shaft_dev') or fit.get('hole', '')

            hp = proc.get('hole_process')  or {}
            sp = proc.get('shaft_process') or {}

            rows.append({**base,
                'recommended_fit':  f"{hole_str}/{shaft_str}" if hole_str and shaft_str else (hole_str or shaft_str or '—'),
                'fit_type':         details.get('fit_type', ''),
                'hole_tol':         hole_str,
                'shaft_tol':        shaft_str,
                'max_clearance_um': details.get('max_clearance_um', ''),
                'min_clearance_um': details.get('min_clearance_um', ''),
                'hole_it':          hp.get('it_grade', ''),
                'shaft_it':         sp.get('it_grade', ''),
                'hole_process':     ' → '.join(hp.get('chain', [])),
                'shaft_process':    ' → '.join(sp.get('chain', [])),
                'source':           app_scen.get('source', ''),
                'note':             app_scen.get('note', ''),
                'error':            '',
            })
        return rows

    @staticmethod
    def build_batch_csv(report_rows: list) -> str:
        """將報表列轉為 UTF-8 CSV 字串（帶 BOM，供 Excel 開啟）。"""
        import io, csv
        cols    = ['pair_id', 'hole_part', 'hole_feature', 'shaft_part', 'shaft_feature',
                   'nominal_dia', 'function_desc', 'priority',
                   'recommended_fit', 'fit_type', 'hole_tol', 'shaft_tol',
                   'max_clearance_um', 'min_clearance_um',
                   'hole_it', 'shaft_it', 'hole_process', 'shaft_process',
                   'source', 'note', 'error']
        headers = ['配對編號', '孔件', '孔特徵', '軸件', '軸特徵',
                   '公稱直徑(mm)', '功能描述', '優先度',
                   '推薦配合', '配合類型', '孔公差', '軸公差',
                   '最大間隙(μm)', '最小間隙(μm)',
                   '孔IT等級', '軸IT等級', '孔製程', '軸製程',
                   '來源', '備註', '錯誤訊息']
        buf = io.StringIO()
        buf.write('﻿')  # BOM
        writer = csv.writer(buf)
        writer.writerow(headers)
        for row in report_rows:
            writer.writerow([str(row.get(c, '')) for c in cols])
        return buf.getvalue()
