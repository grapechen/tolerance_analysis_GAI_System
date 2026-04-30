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

DEFAULT_FOCUS_PARTS = ('軸承座', '轉動軸', '工作臺心軸')
DEFAULT_STACK_CHAIN = ('MP03', 'MP02', 'MP06', 'MP10', 'MP05', 'MP01')

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
        lambda d: '軸承外圈' in d and ('固定' in d or '承載' in d or '承受' in d),
        FitRule('H7', 'p6', 'LN2', '過盈配合', '軸承外圈固定承載，採過盈以防外圈滑轉'),
    ),
    (
        lambda d: '軸承內圈' in d and ('旋轉' in d or '過盈' in d),
        FitRule('H7', 'p6', 'LN2', '過盈配合', '軸承內圈隨軸旋轉，採過盈確保同步'),
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

    # ── Plan 2：步驟 ① 路徑分析（讀使用者編輯的 editorPathData） ──────────
    def analyze_path(
        self,
        path_data: list[dict],
    ) -> dict:
        """對使用者編輯的公差累積路徑（editorPathData）做分析。

        path_data 來自前端的 editorPathData，每筆是獨立公差項：
          { type: "feature", name: "軸承-Dia-1", val: 0.02 (mm),
            nominal_size: 25, it_grade: "IT7", part: "軸承", tol_type: "dis" }
        spatial 項（traX/Y/Z, rotX/Y/Z）不參與 RSS。
        """
        feats = [it for it in (path_data or []) if it.get('type') == 'feature']
        if not feats:
            return {'error': '路徑中沒有公差項，請先在「編輯公差路徑」建立路徑'}

        # mm → μm 統一在 μm 比較貢獻
        vals_um = [float(it.get('val', 0)) * 1000.0 for it in feats]
        rss_um = self._rss(vals_um)
        wc_um = sum(vals_um)
        contribs = self._contributions(vals_um)

        items = []
        for it, v_um, c in zip(feats, vals_um, contribs):
            items.append({
                'name':             it.get('name', ''),
                'part':             it.get('part', ''),
                'tol_type':         it.get('tol_type', ''),
                'val_mm':           float(it.get('val', 0)),
                'val_um':           round(v_um, 3),
                'nominal_size':     it.get('nominal_size'),
                'it_grade':         it.get('it_grade', ''),
                'contribution_pct': round(c, 2),
                'rank':             0,
            })
        order = sorted(range(len(items)), key=lambda i: items[i]['contribution_pct'], reverse=True)
        for r, idx_ in enumerate(order, start=1):
            items[idx_]['rank'] = r

        return {
            'rss_um':       round(rss_um, 3),
            'wc_um':        round(wc_um, 3),
            'items_count':  len(feats),
            'spatial_count': sum(1 for it in path_data if it.get('type') == 'spatial'),
            'items':        items,
        }

    # ── Plan 2：步驟 ② 套用使用者指令 ────────────────────────────────
    @staticmethod
    def _ras400_part_id_to_name(part_id: str) -> str:
        """編號 → 中文（與 test0402/face_namer.py COMP_NAMES 同步）。"""
        m = {
            '1': '工作臺',    '2': '馬達水套',  '3': '馬達座',
            '4': '分流座',    '5': '工作臺心軸', '6': '軸承座',
            '7': '編碼器',    '8': '轉動軸',    '9': '編碼器心軸',
            '10': '軸承',    '11': '馬達',
        }
        return m.get(str(part_id), str(part_id))

    @staticmethod
    def _normalize_name(s: str) -> str:
        """正規化公差名稱：去 hyphen、轉小寫，便於 '工作臺心軸-DIA1' vs '工作臺心軸-Dia-1' 比對。"""
        return (s or '').replace('-', '').replace('_', '').lower()

    def apply_command(
        self,
        path_data: list[dict],
        command: str,
    ) -> dict:
        """方案二步驟②：解析自然語言指令 → 對應到 editorPathData 中某筆公差項
        → 透過 ISO 286 重新查表得到新的公差值（mm）→ 重算 RSS（其他項不動）。

        指令範例:
          "請將編號5零件第6特徵面的第1個直徑公差由IT6放寬至IT7"
        指令解析結果中的 target_name 例如 "工作臺心軸-DIA1"，
        會與 editorPathData[i].name (例如 "工作臺心軸-Dia-1") 做正規化比對。
        """
        from rag_engine import parse_structured_command
        parsed = parse_structured_command(command)
        if not parsed:
            return {'error': '無法解析指令格式', 'command': command}

        target_name_norm = self._normalize_name(parsed['target_name'])
        target_part = parsed.get('part_name_zh') or self._ras400_part_id_to_name(parsed['part_id'])
        target_it = int(parsed['target_it'])
        tol_index = int(parsed.get('tol_index', 1))

        feats = [(i, it) for i, it in enumerate(path_data or []) if it.get('type') == 'feature']
        if not feats:
            return {'error': '路徑中沒有公差項', 'parsed': parsed}

        # 比對：先以 target_name 完整正規化匹配
        candidates = [(i, it) for i, it in feats
                      if self._normalize_name(it.get('name', '')) == target_name_norm]

        # 找不到精確名稱 → 退回用 (part + tol_code) 模糊匹配，配合 tol_index 取第 N 個
        if not candidates:
            tol_code_lc = parsed['tol_code'].lower()
            same_part = [(i, it) for i, it in feats
                         if it.get('part') == target_part
                         and tol_code_lc in self._normalize_name(it.get('name', ''))]
            if not same_part:
                return {
                    'error':  f"路徑中找不到 {target_part} 的 {parsed['tol_code']} 公差項",
                    'parsed': parsed,
                }
            if tol_index > len(same_part):
                return {
                    'error':  f"{parsed['tol_code']}-{tol_index} 超過該零件的公差數 ({len(same_part)})",
                    'parsed': parsed,
                    'candidates_count': len(same_part),
                }
            candidates = [same_part[tol_index - 1]]

        idx, item = candidates[0]
        nominal_size = item.get('nominal_size')
        if not nominal_size:
            return {
                'error':  f"公差項 {item.get('name')} 無 nominal_size，無法重新查 ISO 286",
                'parsed': parsed,
            }

        # 用 ISO 286 IT 等級表查新的公差值（μm → mm）
        new_tol_um = self._lookup_it_um(float(nominal_size), target_it)
        if new_tol_um is None:
            return {
                'error':  f"找不到 IT{target_it} @ Φ{nominal_size}mm 的 ISO 286 對應值",
                'parsed': parsed,
            }
        new_val_mm = round(new_tol_um / 1000.0, 6)

        # 計算 RSS（其他項維持）
        old_val_mm = float(item.get('val', 0))
        vals = [float(it.get('val', 0)) for _, it in feats]
        vals_um_before = [v * 1000.0 for v in vals]
        rss_before = self._rss(vals_um_before)
        wc_before = sum(vals_um_before)

        vals_after = list(vals)
        # 找 target item 在 feats 列表的位置
        for k, (i, it) in enumerate(feats):
            if i == idx:
                vals_after[k] = new_val_mm
                break
        vals_um_after = [v * 1000.0 for v in vals_after]
        rss_after = self._rss(vals_um_after)
        wc_after = sum(vals_um_after)

        # 回填修改後的完整 path（淺拷貝 + 替換目標 item）
        new_path = list(path_data or [])
        new_item = dict(item)
        new_item['val']      = new_val_mm
        new_item['it_grade'] = f"IT{target_it}"
        new_path[idx] = new_item

        return {
            'parsed':         parsed,
            'target_name':    item.get('name'),
            'target_part':    target_part,
            'target_index':   idx,
            'change': {
                'name':         item.get('name'),
                'before': {
                    'val_mm':    old_val_mm,
                    'val_um':    round(old_val_mm * 1000.0, 3),
                    'it_grade':  item.get('it_grade'),
                },
                'after': {
                    'val_mm':    new_val_mm,
                    'val_um':    round(new_tol_um, 3),
                    'it_grade':  f"IT{target_it}",
                },
                'delta_um':      round((new_val_mm - old_val_mm) * 1000.0, 3),
            },
            'rss_before_um':  round(rss_before, 3),
            'rss_after_um':   round(rss_after, 3),
            'wc_before_um':   round(wc_before, 3),
            'wc_after_um':    round(wc_after, 3),
            'rss_delta_um':   round(rss_after - rss_before, 3),
            'path_data':      new_path,
        }

    @staticmethod
    def _lookup_it_um(nominal_mm: float, it_grade: int) -> float | None:
        """查 ISO 286 IT 等級表，回傳該尺寸的公差（μm）。"""
        from repositories.tolerance_repo import ToleranceRepository
        repo = ToleranceRepository()
        rows = repo.find_iso_by_size(nominal_mm)
        if not rows:
            return None
        target = f"IT{it_grade}"
        for r in rows:
            if str(r.it_grade).upper() == target:
                return float(r.tolerance_um) if r.tolerance_um is not None else None
        return None

    # ── Plan 2：自動調配版（保留） ────────────────────────────────────

    def adjust_plan2(
        self,
        plan1: list[dict],
        chain: Iterable[str] = DEFAULT_STACK_CHAIN,
        target_um: float | None = None,
        high_threshold: float = 25.0,
        low_threshold: float = 8.0,
    ) -> dict:
        """跑方案二：依貢獻度分布，對 Plan 1 的 fit 做緊/鬆調配。

        Args:
            plan1: 方案一輸出（每筆需含 pair_id / nominal_dia / fit_hole / fit_shaft / tol_band_um / fit_type）
            chain: 參與 stack-up 的 pair_id 順序
            target_um: 累積目標（μm）；給定時，會嘗試調緊到目標內，再對未動的低貢獻放寬。
                       未給定時用門檻法：> high_threshold% 調緊一級、 < low_threshold% 放寬一級。
            high_threshold / low_threshold: 門檻法用百分比

        Returns:
            {
              'chain': [...],           # 鏈中各環節原始與調整後資料
              'rss_before_um': ...,
              'rss_after_um': ...,
              'wc_before_um': ...,
              'wc_after_um': ...,
              'changes': [...],         # 變動列表（含 pair_id / action / before / after / reason）
            }
        """
        chain = list(chain)
        idx = {r['pair_id']: r for r in plan1}
        chain_rows = [idx[pid] for pid in chain if pid in idx]
        if not chain_rows:
            return {'error': 'chain pairs not in plan1'}

        # 1. 原始貢獻
        bands_before = [r['tol_band_um'] for r in chain_rows]
        rss_before = self._rss(bands_before)
        wc_before = sum(bands_before)
        contribs = self._contributions(bands_before)

        # 2. 決策每環的動作
        changes: list[dict] = []
        for r, b, c in zip(chain_rows, bands_before, contribs):
            if c >= high_threshold:
                action, delta, reason = 'tighten', -1, f"貢獻度 {c:.1f}% > {high_threshold}%，調緊一級"
            elif c <= low_threshold:
                action, delta, reason = 'loosen', +1, f"貢獻度 {c:.1f}% < {low_threshold}%，放寬一級"
            else:
                action, delta, reason = 'keep', 0, f"貢獻度 {c:.1f}%，維持"

            new_hole  = _shift_grade(r['fit_hole'],  delta) if delta else r['fit_hole']
            new_shaft = _shift_grade(r['fit_shaft'], delta) if delta else r['fit_shaft']

            new_details = self._fit_details(r['nominal_dia'], new_hole, new_shaft) if delta else r['details']
            new_band = self._fit_band(new_details) if delta else r['tol_band_um']

            changes.append({
                'pair_id':           r['pair_id'],
                'action':            action,
                'contribution_pct':  round(c, 2),
                '_nominal_dia':      r['nominal_dia'],
                'before':            {
                    'hole':         r['fit_hole'],
                    'shaft':        r['fit_shaft'],
                    'fit_code':     r['fit_code'],
                    'tol_band_um':  r['tol_band_um'],
                    'fit_type':     r['fit_type'],
                },
                'after':             {
                    'hole':         new_hole,
                    'shaft':        new_shaft,
                    'fit_code':     f"{new_hole}/{new_shaft}",
                    'tol_band_um':  new_band,
                    'details':      new_details,
                },
                'delta_um':          round(new_band - r['tol_band_um'], 3),
                'reason':            reason,
            })

        bands_after = [c['after']['tol_band_um'] for c in changes]
        rss_after = self._rss(bands_after)
        wc_after = sum(bands_after)

        # 3. 若有 target，嘗試再加緊高貢獻直到達標（簡單迭代）
        if target_um is not None and rss_after > target_um:
            changes, rss_after, wc_after = self._iterate_to_target(changes, target_um)

        return {
            'chain':           [c['pair_id'] for c in changes],
            'rss_before_um':   round(rss_before, 3),
            'rss_after_um':    round(rss_after, 3),
            'wc_before_um':    round(wc_before, 3),
            'wc_after_um':     round(wc_after, 3),
            'changes':         changes,
            'meta': {
                'target_um':       target_um,
                'high_threshold':  high_threshold,
                'low_threshold':   low_threshold,
            },
        }

    @staticmethod
    def _rss(values: list[float]) -> float:
        return (sum(v * v for v in values)) ** 0.5

    @staticmethod
    def _contributions(values: list[float]) -> list[float]:
        denom = sum(v * v for v in values) or 1.0
        return [(v * v) / denom * 100 for v in values]

    def _iterate_to_target(self, changes: list[dict], target_um: float, max_iter: int = 5):
        """達標迭代：再對最高貢獻的環節調緊，最多 max_iter 輪。"""
        for _ in range(max_iter):
            bands = [c['after']['tol_band_um'] for c in changes]
            rss = self._rss(bands)
            if rss <= target_um:
                break
            # 找目前貢獻最高、且還沒到 IT_MIN 的環節再調緊一級
            order = sorted(range(len(changes)),
                           key=lambda i: bands[i] * bands[i], reverse=True)
            advanced = False
            for i in order:
                c = changes[i]
                pair_id = c['pair_id']
                cur_hole = c['after']['hole']
                cur_shaft = c['after']['shaft']
                _, hg = _split_code(cur_hole)
                _, sg = _split_code(cur_shaft)
                if hg <= IT_MIN or sg <= IT_MIN:
                    continue
                new_hole = _shift_grade(cur_hole, -1)
                new_shaft = _shift_grade(cur_shaft, -1)
                # 找回 nominal_dia
                # 從 c['before'] 拿不到，需另存。改造：在 changes 裡記下 nominal
                nominal = c.get('_nominal_dia')
                if nominal is None:
                    # bail out — 不知尺寸無法重算
                    break
                new_details = self._fit_details(nominal, new_hole, new_shaft)
                new_band = self._fit_band(new_details)
                c['after'] = {
                    'hole': new_hole, 'shaft': new_shaft,
                    'fit_code': f"{new_hole}/{new_shaft}",
                    'tol_band_um': new_band, 'details': new_details,
                }
                c['action'] = 'tighten'
                c['delta_um'] = round(new_band - c['before']['tol_band_um'], 3)
                c['reason'] += f" → 進一步收緊以達目標 {target_um}μm"
                advanced = True
                break
            if not advanced:
                break
        # 終局：依 before/after 帶寬重新判定 action 標籤，避免「先放寬後拉回」誤標
        for c in changes:
            db = c['after']['tol_band_um'] - c['before']['tol_band_um']
            c['delta_um'] = round(db, 3)
            if abs(db) < 1e-6:
                c['action'] = 'keep'
            elif db < 0:
                c['action'] = 'tighten'
            else:
                c['action'] = 'loosen'
        bands = [c['after']['tol_band_um'] for c in changes]
        return changes, self._rss(bands), sum(bands)
