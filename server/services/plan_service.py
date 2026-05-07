"""plan_service.py - 方案一(推薦)/方案二(調配) 業務邏輯

Plan 1: 由零件功能描述推薦公差配合（rule-based + ansi_fits 對照）
Plan 2: 對 Plan 1 結果做敏感度分析，高貢獻調緊、低貢獻放寬
"""

from __future__ import annotations

import csv
import os
import re
from dataclasses import dataclass
from typing import Iterable

from recommendation import smart_fit, process_advisor
from recommendation import feature_recommender
from services.fit_service import FitService

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data')
MATING_PAIRS_CSV = os.path.normpath(os.path.join(DATA_DIR, 'ras400_mating_pairs.csv'))
FEATURE_TOL_CSV  = os.path.normpath(os.path.join(DATA_DIR, 'ras400_feature_tolerances.csv'))

DEFAULT_FOCUS_PARTS = ('軸承座', '軸承', '轉動軸', '工作臺心軸')

# IT 範圍：方案二可調區間
IT_MIN = 5
IT_MAX = 11


@dataclass
class FitRule:
    """從 function_desc 規則匹配到一條配合建議。"""
    hole: str       # 'H7'
    shaft: str      # 'p6'
    ansi: str       # 'LN2'
    fit_type: str   # '過盈配合'
    reason: str


# ── 規則庫（依 RAS400 工程慣例與 ansi_fits.csv 對齊）────────────────────────
# 上方規則優先；第一個命中即停止。
FIT_RULES: list[tuple[callable, FitRule]] = [
    (
        lambda d: '軸承外環' in d and ('固定' in d or '承載' in d or '承受' in d),
        FitRule('H7', 'p6', 'LN2', '過盈配合', '軸承外環固定承載，採過盈以防外環滑轉'),
    ),
    (
        lambda d: '軸承內環' in d and ('旋轉' in d or '過盈' in d),
        FitRule('H7', 'p6', 'LN2', '過盈配合', '軸承內環隨軸旋轉，採過盈確保同步'),
    ),
    (
        lambda d: ('傳遞' in d and '扭矩' in d) or '對接' in d,
        FitRule('H7', 'k6', 'LT3', '過渡配合', '扭矩傳遞需準確定位（輕打入）'),
    ),
    (
        lambda d: '可組裝' in d or '可裝拆' in d or '可拆裝' in d,
        FitRule('H7', 'h6', 'LC2', '留隙配合', '須可組裝拆卸，採滑動定位'),
    ),
    (
        lambda d: '高旋轉精度' in d or '同軸度' in d or '讀取' in d,
        FitRule('H7', 'h6', 'LC2', '留隙配合', '需高旋轉精度，採精密定位（LC2）'),
    ),
    (
        lambda d: '密封' in d or '冷卻' in d,
        FitRule('H7', 'h6', 'LC2', '留隙配合', '密封/冷卻接合採定位裝拆'),
    ),
    (
        lambda d: '定位' in d,
        FitRule('H7', 'h6', 'LC2', '留隙配合', '一般定位連接，採滑動配合'),
    ),
]

DEFAULT_RULE = FitRule('H7', 'h6', 'LC2', '留隙配合', '預設定位配合')


# ── IT 解析輔助 ────────────────────────────────────────────────────────────

_IT_RE = re.compile(r'([A-Za-z]+)(\d+)')
_SFA_CODE_RE = re.compile(r'^(.+)-([A-Za-z]+)(\d+)$')


def _split_code(notation: str) -> tuple[str, int]:
    """'H7' -> ('H', 7); 'p6' -> ('p', 6)."""
    m = _IT_RE.match(notation.strip())
    if not m:
        raise ValueError(f"bad notation {notation!r}")
    return m.group(1), int(m.group(2))


def _shift_grade(notation: str, delta: int) -> str:
    """調整 IT 等級。delta<0 變嚴(數字小)，delta>0 變鬆(數字大)。"""
    code, grade = _split_code(notation)
    new = max(IT_MIN, min(IT_MAX, grade + delta))
    return f"{code}{new}"


# ── 配合類別簡化標籤（緊/鬆/過渡）─────────────────────────────────────────
_CATEGORY_MAP = {
    '過盈配合': '緊配合',
    '留隙配合': '鬆配合',
    '過渡配合': '過渡配合',
}


def _simplified_category(fit_type: str) -> str:
    return _CATEGORY_MAP.get(fit_type, fit_type)


# 圓柱配合的工程慣例偏好（process_advisor 預設會選拉削，此處改為更貼近實務）
_FEATURE_PROC_PREF = {
    'H': ['Reaming', 'Boring', 'Internal Grinding', 'Honing', 'Broaching'],
    'S': ['Cylindrical Grinding', 'Turning', 'Broaching', 'Milling'],
    'P': ['Surface Grinding', 'Milling', 'Lapping'],
}


def _process_pick(it_grade: int, feature_type: str, nominal: float) -> dict:
    """為單一特徵（H/S）挑製程與設備，回傳精簡 dict。

    取得 process_advisor.suggest_processes() 的所有可達製程後，依照
    _FEATURE_PROC_PREF 的工程慣例偏好排序，再呼叫 recommend_full 取得
    完整製程鏈與設備資訊。
    """
    candidates = process_advisor.suggest_processes(it_grade, feature_type)
    if not candidates:
        return {
            'process_zh':    'N/A', 'process_en': None,
            'equipment':     'N/A', 'Ra_target': 'N/A',
            'process_chain': '',    'alternatives': [],
        }

    pref = _FEATURE_PROC_PREF.get(feature_type, [])
    rank = {name: i for i, name in enumerate(pref)}
    candidates.sort(key=lambda p: rank.get(p['process_en'], 99))
    best = candidates[0]

    # 用 best 拿完整資訊（製程鏈、Ra）
    rec = process_advisor.recommend_full(it_grade, feature_type, nominal)
    # process_advisor 的 best 可能不同；強制用我們的 best
    chain = process_advisor.plan_process_chain(best['process_en'])
    chain_zh = ' → '.join(s['process_zh'] for s in chain)
    alt_zh = [c['process_zh'] for c in candidates[1:4]]

    return {
        'process_zh':    best['process_zh'],
        'process_en':    best['process_en'],
        'equipment':     best.get('equipment', ''),
        'Ra_target':     f"Ra {best['Ra_min']} ~ {best['Ra_max']} μm",
        'process_chain': chain_zh,
        'alternatives':  alt_zh,
    }


# ── Plan 1 ─────────────────────────────────────────────────────────────────

class PlanService:
    def __init__(self):
        self._fit_svc = FitService()

    @staticmethod
    def load_mating_pairs(csv_path: str = MATING_PAIRS_CSV) -> list[dict]:
        rows: list[dict] = []
        with open(csv_path, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                rows.append({
                    'pair_id':       r['pair_id'],
                    'hole_part':     r['hole_part'],
                    'hole_feature':  r['hole_feature'],
                    'shaft_part':    r['shaft_part'],
                    'shaft_feature': r['shaft_feature'],
                    'nominal_dia':   float(r['nominal_dia']) if r['nominal_dia'] else 0.0,
                    'function_desc': r['function_desc'],
                    'priority':      r.get('priority', ''),
                })
        return rows

    @staticmethod
    def _filter_focus(pairs: list[dict], focus_parts: Iterable[str] | None) -> list[dict]:
        if not focus_parts:
            return pairs
        focus = set(focus_parts)
        return [p for p in pairs if p['hole_part'] in focus or p['shaft_part'] in focus]

    @staticmethod
    def recommend_fit(function_desc: str) -> FitRule:
        """根據功能描述比對規則庫，回傳第一條命中的 FitRule。"""
        for predicate, rule in FIT_RULES:
            if predicate(function_desc):
                return rule
        return DEFAULT_RULE

    @staticmethod
    def _ansi_source(rule: FitRule) -> dict | None:
        """從 ansi_fits.csv 找回對應這條 fit 的原始一列，作為來源引用。"""
        for row in smart_fit.fits_database:
            if row.get('hole') == rule.hole and row.get('shaft') == rule.shaft:
                return row
        return None

    def _fit_details(self, size_mm: float, hole: str, shaft: str) -> dict:
        """呼叫 FitService 拿到此 fit 在指定尺寸下的偏差與間隙。"""
        return self._fit_svc.get_fit_details_for_matchmaking(size_mm, hole, shaft)

    # ── Plan 1：特徵驅動版（最新版本） ────────────────────────────────
    @staticmethod
    def load_feature_tolerances(csv_path: str = FEATURE_TOL_CSV) -> list[dict]:
        """讀 ras400_feature_tolerances.csv，每筆 = 一個特徵面的預設公差。"""
        rows = []
        with open(csv_path, encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                def _f(k):
                    v = (r.get(k) or '').strip()
                    if v == '':
                        return None
                    try:
                        return float(v)
                    except ValueError:
                        return v
                rows.append({
                    'part':           r['part'].strip(),
                    'feature':        r['feature'].strip(),
                    'feature_type':   r['feature_type'].strip(),
                    'feature_id':     f"{r['part'].strip()}-{r['feature'].strip()}",
                    'nominal_mm':     _f('nominal_mm'),
                    'Cir': _f('Cir'),  'Cyl': _f('Cyl'),
                    'Per': _f('Per'),  'Par': _f('Par'),
                    'Co':  _f('Co'),   'Run': _f('Run'),
                    'Fla': _f('Fla'),
                    'it_dim':         _f('it_dim'),
                    'note':           (r.get('note') or '').strip(),
                })
        return rows

    def list_features(self) -> list[dict]:
        """列出所有可選特徵面（給 UI dropdown）。"""
        return [{'feature_id': f['feature_id'], 'part': f['part'],
                 'feature': f['feature'], 'feature_type': f['feature_type'],
                 'nominal_mm': f['nominal_mm'], 'note': f['note']}
                for f in self.load_feature_tolerances()]

    def feature_recommend(
        self,
        feature_id: str,
        overrides: dict | None = None,
        safety_factor: float = 1.7,
    ) -> dict:
        """主 API：給特徵 ID（如 '軸承座-H-1'）→ 推薦 IT/製程/機台。

        Args:
            feature_id: '{part}-{feature}' e.g. '軸承座-H-1'
            overrides:  dict 形式覆蓋 {Cir/Cyl/Per/Par/Co/Run/Fla/it_dim}（mm 或 IT數）
        """
        rows = self.load_feature_tolerances()
        match = next((r for r in rows if r['feature_id'] == feature_id), None)
        if not match:
            return {'error': f'找不到特徵: {feature_id}'}

        # 收集幾何公差（從 CSV + overrides）
        geo_keys = ['Cir', 'Cyl', 'Per', 'Par', 'Co', 'Run', 'Fla']
        geo_tols = {k: match[k] for k in geo_keys if match[k] is not None}
        if overrides:
            for k in geo_keys:
                if k in overrides and overrides[k] is not None:
                    geo_tols[k] = float(overrides[k])
            if 'it_dim' in overrides and overrides['it_dim'] is not None:
                match['it_dim'] = int(overrides['it_dim'])

        nominal = match.get('nominal_mm') or 50.0
        it_dim_val = int(match['it_dim']) if match.get('it_dim') is not None else None

        # 呼叫 feature_recommender 主邏輯
        rec = feature_recommender.recommend_for_feature(
            feature_type=match['feature_type'],
            nominal_mm=nominal,
            geo_tolerances=geo_tols,
            it_dim=it_dim_val,
            safety_factor=safety_factor,
        )

        return {
            'feature_id':       feature_id,
            'part':             match['part'],
            'feature':          match['feature'],
            'feature_type':     match['feature_type'],
            'feature_zh':       rec.get('feature_zh'),
            'nominal_mm':       nominal,
            'it_dim':           it_dim_val,
            'geo_tolerances':   geo_tols,
            'note':             match.get('note', ''),
            'geo_grades':       rec.get('geo_grades', []),
            'processes':        rec.get('processes', []),
            'safety_factor':    safety_factor,
        }

    # ── Plan 1：單對輸入版（保留） ─────────────────────────────────────
    def recommend_one(
        self,
        part_name: str,
        function_desc: str,
        nominal_dia: float,
    ) -> dict:
        """方案一（單對輸入）：依功能描述推薦 fit + 機台。

        不需要參考 mating_pairs.csv，直接用使用者輸入。
        """
        rule = self.recommend_fit(function_desc)
        details = self._fit_details(nominal_dia, rule.hole, rule.shaft)
        ansi_src = self._ansi_source(rule)
        it_hole  = _split_code(rule.hole)[1]
        it_shaft = _split_code(rule.shaft)[1]
        proc_hole  = _process_pick(it_hole,  'H', nominal_dia)
        proc_shaft = _process_pick(it_shaft, 'S', nominal_dia)

        return {
            'part_name':     part_name,
            'function_desc': function_desc,
            'nominal_dia':   nominal_dia,
            'fit_hole':      rule.hole,
            'fit_shaft':     rule.shaft,
            'fit_code':      f"{rule.hole}/{rule.shaft}",
            'ansi':          rule.ansi,
            'fit_type':      rule.fit_type,
            'category':      _simplified_category(rule.fit_type),
            'reason':        rule.reason,
            'source':        ansi_src or {'note': 'ansi_fits.csv 無精確對應'},
            'details':       details,
            'tol_band_um':   self._fit_band(details),
            'process_hole':  proc_hole,
            'process_shaft': proc_shaft,
        }

    # ── Plan 1：批次版 ────────────────────────────────────────────────
    def recommend_plan1(
        self,
        focus_parts: Iterable[str] | None = DEFAULT_FOCUS_PARTS,
        csv_path: str = MATING_PAIRS_CSV,
    ) -> list[dict]:
        """跑方案一：對每個配對推薦 fit，並補上 ISO 偏差數值。"""
        pairs = self.load_mating_pairs(csv_path)
        pairs = self._filter_focus(pairs, focus_parts)

        results: list[dict] = []
        for p in pairs:
            rule = self.recommend_fit(p['function_desc'])
            details = self._fit_details(p['nominal_dia'], rule.hole, rule.shaft)
            ansi_src = self._ansi_source(rule)

            # 初步製程規劃：為孔/軸各選一個製程＋設備
            it_hole  = _split_code(rule.hole)[1]
            it_shaft = _split_code(rule.shaft)[1]
            proc_hole  = _process_pick(it_hole,  'H', p['nominal_dia'])
            proc_shaft = _process_pick(it_shaft, 'S', p['nominal_dia'])

            results.append({
                **p,
                'fit_hole':       rule.hole,
                'fit_shaft':      rule.shaft,
                'fit_code':       f"{rule.hole}/{rule.shaft}",
                'ansi':           rule.ansi,
                'fit_type':       rule.fit_type,
                'category':       _simplified_category(rule.fit_type),  # 緊/鬆/過渡
                'reason':         rule.reason,
                'source':         ansi_src or {'note': 'ansi_fits.csv 無精確對應'},
                'details':        details,
                'tol_band_um':    self._fit_band(details),
                'process_hole':   proc_hole,
                'process_shaft':  proc_shaft,
            })
        return results

    @staticmethod
    def _fit_band(details: dict) -> float:
        """配合的總公差帶寬（μm）= 孔公差帶 + 軸公差帶。

        這是該配合對徑向累積誤差的「上限貢獻量」。
        """
        if not details:
            return 0.0
        h = details.get('hole', {})
        s = details.get('shaft', {})
        h_band = abs(h.get('upper_um', 0) - h.get('lower_um', 0))
        s_band = abs(s.get('upper_um', 0) - s.get('lower_um', 0))
        return round(h_band + s_band, 3)

    # ── 進階版配合調整 ─────────────────────────────────────────────────────────

    def get_parts_list(self, csv_path: str = MATING_PAIRS_CSV) -> list[str]:
        """回傳所有唯一零件名稱（hole_part + shaft_part 合併去重，依字母排序）。"""
        pairs = self.load_mating_pairs(csv_path)
        parts = set()
        for p in pairs:
            parts.add(p['hole_part'])
            parts.add(p['shaft_part'])
        return sorted(parts)

    @staticmethod
    def _match_part_items(part_name: str, path: list[dict]) -> list[dict]:
        """從 current_path 找屬於某零件的路徑項目。

        Priority 1: item.get('part') == part_name（精確）
        Priority 2: SFA 新格式前綴完全一致（regex group == part_name，非 substring）
        Priority 3: fallback，回傳空串列
        spatial 型 item 一律跳過。
        """
        matched = []
        seen_names = set()

        for item in path:
            if item.get('type') == 'spatial':
                continue

            item_name = item.get('name', '')

            # Priority 1: 明確 part 欄位
            item_part = (item.get('part') or '').strip()
            if item_part and item_part == part_name:
                if item_name not in seen_names:
                    matched.append(item)
                    seen_names.add(item_name)
                continue

            # Priority 2: SFA 新格式前綴（精確，非 substring）
            m = _SFA_CODE_RE.match(item_name)
            if m and m.group(1) == part_name:
                if item_name not in seen_names:
                    matched.append(item)
                    seen_names.add(item_name)

        return matched

    # 幾何公差型別清單（不能被 DIA 配合更新）
    _GEO_TYPES = frozenset({
        'fla', 'par', 'per', 'co', 'cyl', 'cir', 'run', 'tot',
        'pos', 'ang', 'sym', 'pro', 'dis',
    })

    @classmethod
    def _select_dia_items(cls, items: list[dict]) -> list[dict]:
        """篩選應被更新的路徑項目（三層 fallback）。

        1st: tol_type == 'dia'（明確直徑公差）
        2nd: tol_type 為空（未標記，視為尺寸公差）
        3rd: tol_type 不在幾何公差清單（自訂類型如 'size'/'linear'）
        幾何公差（fla/par/per/co … 及 dis）一律排除。
        """
        def tt(i):
            return (i.get('tol_type') or '').lower().strip()

        dia   = [i for i in items if tt(i) == 'dia']
        if dia:
            return dia
        empty = [i for i in items if not tt(i)]
        if empty:
            return empty
        # 第三層：非幾何自訂類型（如 'size', 'linear' 等）
        return [i for i in items if tt(i) not in cls._GEO_TYPES]

    def advanced_recommend(
        self,
        focus_part: str,
        current_path: list[dict],
        csv_path: str = MATING_PAIRS_CSV,
    ) -> dict:
        """以 focus_part 為基準，找相關配對並推薦配合，同時預覽路徑比對結果。"""
        pairs = self.load_mating_pairs(csv_path)

        focus_pairs = [
            p for p in pairs
            if p['hole_part'] == focus_part or p['shaft_part'] == focus_part
        ]

        related_part_names = {focus_part}
        for p in focus_pairs:
            related_part_names.add(p['hole_part'])
            related_part_names.add(p['shaft_part'])
        focus_ids = {p['pair_id'] for p in focus_pairs}
        related_pairs = [
            p for p in pairs
            if p['pair_id'] not in focus_ids
            and (p['hole_part'] in related_part_names or p['shaft_part'] in related_part_names)
        ]

        def enrich(p: dict, is_focus: bool) -> dict:
            rule    = self.recommend_fit(p['function_desc'])
            details = self._fit_details(p['nominal_dia'], rule.hole, rule.shaft)
            return {
                **p,
                'fit_hole':    rule.hole,
                'fit_shaft':   rule.shaft,
                'fit_code':    f"{rule.hole}/{rule.shaft}",
                'fit_type':    rule.fit_type,
                'reason':      rule.reason,
                'tol_band_um': self._fit_band(details),
                'is_focus':    is_focus,
            }

        enriched_focus   = [enrich(p, True)  for p in focus_pairs]
        enriched_related = [enrich(p, False) for p in related_pairs]

        path_matches: dict[str, list[str]] = {}
        for p in focus_pairs + related_pairs:
            hole_items  = self._match_part_items(p['hole_part'],  current_path or [])
            shaft_items = self._match_part_items(p['shaft_part'], current_path or [])
            all_matched = hole_items + shaft_items
            path_matches[p['pair_id']] = list(
                dict.fromkeys(i.get('name') for i in all_matched if i.get('name'))
            )

        return {
            'focus_pairs':   enriched_focus,
            'related_pairs': enriched_related,
            'path_matches':  path_matches,
        }

    def apply_fit_to_path(
        self,
        pair_id: str,
        fit_hole: str,
        fit_shaft: str,
        nominal_dia: float,
        current_path: list[dict],
        csv_path: str = MATING_PAIRS_CSV,
    ) -> dict:
        """套用選定配合至公差累積路徑，只更新 DIA 型公差項目。"""
        pairs = self.load_mating_pairs(csv_path)
        pair  = next((p for p in pairs if p['pair_id'] == pair_id), None)
        if not pair:
            return {
                'ok': False, 'msg': f'找不到配對: {pair_id}',
                'updated_path': current_path, 'changes': [],
            }

        details    = self._fit_details(nominal_dia, fit_hole, fit_shaft)
        hole_info  = details.get('hole', {})
        shaft_info = details.get('shaft', {})

        if details.get('spec_only'):
            return {
                'ok': True,
                'updated_path': current_path,
                'changes': [],
                'message': f'{pair_id} 為螺栓鎖附固定規格，不適用 ISO 配合公差自動更新。',
            }

        hole_tol_mm  = round(abs(hole_info.get('upper_um', 0)  - hole_info.get('lower_um', 0))  / 1000, 6)
        shaft_tol_mm = round(abs(shaft_info.get('upper_um', 0) - shaft_info.get('lower_um', 0)) / 1000, 6)

        updated_path = [dict(item) for item in (current_path or [])]
        changes: list[dict] = []

        hole_candidates = self._match_part_items(pair['hole_part'], updated_path)
        for item in self._select_dia_items(hole_candidates):
            if hole_tol_mm <= 0:
                continue
            old_val   = item.get('val', 0)
            item['val'] = hole_tol_mm
            changes.append({
                'name':     item.get('name'),
                'part':     pair['hole_part'],
                'role':     'hole',
                'old_val':  old_val,
                'new_val':  hole_tol_mm,
                'source':   f'{fit_hole}@{nominal_dia}mm',
                'tol_type': item.get('tol_type', '(未標記)'),
            })

        shaft_candidates = self._match_part_items(pair['shaft_part'], updated_path)
        for item in self._select_dia_items(shaft_candidates):
            if shaft_tol_mm <= 0:
                continue
            old_val   = item.get('val', 0)
            item['val'] = shaft_tol_mm
            changes.append({
                'name':     item.get('name'),
                'part':     pair['shaft_part'],
                'role':     'shaft',
                'old_val':  old_val,
                'new_val':  shaft_tol_mm,
                'source':   f'{fit_shaft}@{nominal_dia}mm',
                'tol_type': item.get('tol_type', '(未標記)'),
            })

        if not changes:
            if not hole_candidates and not shaft_candidates:
                msg = (
                    f'未能找到「{pair["hole_part"]}」或「{pair["shaft_part"]}」的對應路徑項目。\n'
                    f'可能原因：路徑代碼為抽象格式（disZ1, co1 等），不含零件資訊。\n'
                    f'解決方式：在 Excel G 欄填入「所屬零件」名稱後重新匯入，或使用 SFA CSV 格式（代碼如「工作臺心軸-DIA1」）。'
                )
            else:
                matched_parts = []
                geo_names: list[str] = []
                for cands, pname in ((hole_candidates, pair['hole_part']),
                                     (shaft_candidates, pair['shaft_part'])):
                    if cands:
                        matched_parts.append(pname)
                        geo_names += [i.get('name', '') for i in cands if i.get('name')]
                geo_sample = '、'.join(geo_names[:3]) + ('…' if len(geo_names) > 3 else '')
                msg = (
                    f'找到「{"、".join(matched_parts)}」的路徑項目（{geo_sample}），'
                    f'但均為幾何公差（fla/par/per/co 等），無直徑尺寸公差可更新。\n\n'
                    f'解決方式：在 Excel 路徑中為「{"、".join(matched_parts)}」補上一列 tol_type=dia 的'
                    f'孔/軸直徑公差（例如：軸承座孔徑 H7 → 加一列 name=軸承座-DIA1，tol_type=dia）後重新匯入。'
                )
            return {'ok': True, 'updated_path': current_path, 'changes': [], 'message': msg}

        msg = (
            f'已套用 {pair_id}（{pair["hole_part"]} ↔ {pair["shaft_part"]}）'
            f'{fit_hole}/{fit_shaft} 配合，更新了 {len(changes)} 個路徑項目。'
        )
        return {
            'ok':           True,
            'updated_path': updated_path,
            'changes':      changes,
            'message':      msg,
        }

