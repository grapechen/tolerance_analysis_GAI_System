"""iso2768_service.py - ISO 2768 一般公差查表業務邏輯

M  層：server/data/iso2768.json（靜態規格資料，無需 DB）
此 S 層：封裝所有查表規則，Controller 只呼叫 public method。

支援查詢：
  Part 1  linear / broken_edge / angular
  Part 2  straightness / flatness / circularity / cylindricity
          parallelism / perpendicularity / symmetry / coaxiality / circular_runout
  unified lookup(characteristic, **kwargs)
"""

import json
import os
import re
from typing import Optional, Dict, Any


# ── 載入靜態資料（模組第一次 import 時讀取一次）─────────────────────────────

_DATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'iso2768.json')

def _load_data() -> dict:
    with open(_DATA_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

_DATA = _load_data()
_PART1 = _DATA['standards'][0]   # ISO 2768-1
_PART2 = _DATA['standards'][1]   # ISO 2768-2


# ── 私有工具 ──────────────────────────────────────────────────────────────────

def _find_range_index(ranges: list, value: float) -> Optional[int]:
    """回傳 value 落入的 range 索引（over < value <= up_to），找不到回傳 None。"""
    for i, r in enumerate(ranges):
        lo = r.get('over', 0)
        hi = r.get('up_to')        # None = 無上界
        if value > lo and (hi is None or value <= hi):
            return i
    return None


def _parse_angular_to_deg(text: str) -> float:
    """將 '1deg30min' → 1.5、'0deg20min' → 0.333... (度，浮點數)"""
    deg = 0.0
    m = re.match(r'(\d+)deg(?:(\d+)min)?', text)
    if m:
        deg = float(m.group(1))
        if m.group(2):
            deg += float(m.group(2)) / 60.0
    return deg


# ═══════════════════════════════════════════════════════════════════════════════


class ISO2768Service:
    """ISO 2768 一般公差查詢服務。

    所有 Part-1 方法的 tolerance_class 用小寫 f/m/c/v。
    所有 Part-2 方法的 geo_class 用大寫 H/K/L（或等效 GH/GK/GL）。
    """

    # ── GH/GK/GL 正規化 ────────────────────────────────────────────────────

    @staticmethod
    def _normalize_geo_class(cls: str) -> str:
        """GH→H, GK→K, GL→L, GTH→H … 其他原樣回傳。"""
        mapping = {'GH': 'H', 'GK': 'K', 'GL': 'L',
                   'GTH': 'H', 'GTK': 'K', 'GTL': 'L'}
        return mapping.get(cls.upper(), cls.upper())

    # ── Part 1：線性尺寸 ────────────────────────────────────────────────────

    def lookup_linear(self, size_mm: float, tolerance_class: str) -> Optional[float]:
        """查 Table 1：線性尺寸（非倒角）。
        回傳 ±偏差值 (mm)，null 欄位（必須個別標示）回傳 None。
        """
        tbl    = _PART1['tables']['table_1_linear_dimensions']
        cls    = tolerance_class.lower()
        idx    = _find_range_index(tbl['ranges'], size_mm)
        if idx is None:
            return None
        devs = tbl['deviations'].get(cls)
        if devs is None:
            raise ValueError(f'不支援的公差等級 {cls!r}，應為 f/m/c/v')
        return devs[idx]   # None 代表該組合不適用

    # ── Part 1：倒角/外圓角 ─────────────────────────────────────────────────

    def lookup_broken_edge(self, size_mm: float, tolerance_class: str) -> Optional[float]:
        """查 Table 2：倒角、外圓角。"""
        tbl = _PART1['tables']['table_2_broken_edges']
        cls = tolerance_class.lower()
        idx = _find_range_index(tbl['ranges'], size_mm)
        if idx is None:
            return None
        return tbl['deviations'][cls][idx]

    # ── Part 1：角度 ────────────────────────────────────────────────────────

    def lookup_angular(self, shorter_side_mm: float, tolerance_class: str) -> Optional[Dict]:
        """查 Table 3：角度公差。
        回傳 {'deg': float, 'text': '0deg30min'} 或 None。
        """
        tbl = _PART1['tables']['table_3_angular_dimensions']
        cls = tolerance_class.lower()
        idx = _find_range_index(tbl['ranges_mm'], shorter_side_mm)
        if idx is None:
            # 超過最大範圍（>400mm）取最後一項
            idx = len(tbl['ranges_mm']) - 1
        texts = tbl['deviations_deg_min'].get(cls)
        if texts is None:
            raise ValueError(f'不支援的公差等級 {cls!r}，應為 f/m/c/v')
        text = texts[idx]
        return {'deg': _parse_angular_to_deg(text), 'text': text}

    # ── Part 2：直線度 / 平面度 ─────────────────────────────────────────────

    def lookup_straightness(self, length_mm: float, geo_class: str) -> Optional[float]:
        return self._lookup_sf(length_mm, geo_class)

    def lookup_flatness(self, length_mm: float, geo_class: str) -> Optional[float]:
        return self._lookup_sf(length_mm, geo_class)

    def _lookup_sf(self, length_mm: float, geo_class: str) -> Optional[float]:
        """直線度 / 平面度共用 Table 1（Part 2）。"""
        feat = _PART2['features']['single_features']['straightness_and_flatness']
        cls  = self._normalize_geo_class(geo_class)
        idx  = _find_range_index(feat['ranges'], length_mm)
        if idx is None:
            return None
        return feat['values_mm'][cls][idx]

    # ── Part 2：圓度 ────────────────────────────────────────────────────────

    def lookup_circularity(
        self,
        diameter_tolerance_mm: float,
        geo_class: str,
    ) -> float:
        """rule: min( diameter_tolerance, circular_radial_runout )"""
        runout = self.lookup_circular_runout(geo_class)
        return min(diameter_tolerance_mm, runout)

    # ── Part 2：圓柱度（無直接公差，回傳計算公式建議）────────────────────

    def lookup_cylindricity(
        self,
        diameter_tolerance_mm: float,
        length_mm: float,
        geo_class: str,
    ) -> Dict:
        """回傳建議上限（三項之和）與各組成值，供參考。"""
        circ  = self.lookup_circularity(diameter_tolerance_mm, geo_class)
        strt  = self.lookup_straightness(length_mm, geo_class) or 0.0
        para  = max(diameter_tolerance_mm, strt)
        return {
            'no_direct_tolerance': True,
            'circularity':  circ,
            'straightness': strt,
            'parallelism':  para,
            'combined_upper_bound': round(circ + strt + para, 6),
            'note': 'cylindricity <= circularity + straightness + parallelism',
        }

    # ── Part 2：平行度 ──────────────────────────────────────────────────────

    def lookup_parallelism(
        self,
        size_tolerance_mm: float,
        length_mm: float,
        geo_class: str,
    ) -> float:
        """rule: max( size_tolerance, flatness_or_straightness_tolerance )"""
        sf = self._lookup_sf(length_mm, geo_class) or 0.0
        return max(size_tolerance_mm, sf)

    # ── Part 2：垂直度 ──────────────────────────────────────────────────────

    def lookup_perpendicularity(self, shorter_side_mm: float, geo_class: str) -> Optional[float]:
        """查 Table 2（Part 2）。"""
        feat = _PART2['features']['related_features']['perpendicularity']
        cls  = self._normalize_geo_class(geo_class)
        idx  = _find_range_index(feat['ranges'], shorter_side_mm)
        if idx is None:
            return None
        return feat['values_mm'][cls][idx]

    # ── Part 2：對稱度 ──────────────────────────────────────────────────────

    def lookup_symmetry(self, length_mm: float, geo_class: str) -> Optional[float]:
        """查 Table 3（Part 2）。"""
        feat = _PART2['features']['related_features']['symmetry']
        cls  = self._normalize_geo_class(geo_class)
        idx  = _find_range_index(feat['ranges'], length_mm)
        if idx is None:
            return None
        return feat['values_mm'][cls][idx]

    # ── Part 2：同軸度 ──────────────────────────────────────────────────────

    def lookup_coaxiality(self, geo_class: str) -> Dict:
        """無直接公差，回傳 runout 作為上界。"""
        runout = self.lookup_circular_runout(geo_class)
        return {
            'no_direct_tolerance': True,
            'fallback_circular_runout': runout,
            'note': 'coaxiality <= circular_radial_runout (Table 4)',
        }

    # ── Part 2：圓跳動 ──────────────────────────────────────────────────────

    def lookup_circular_runout(self, geo_class: str) -> float:
        """Table 4（單一值，按等級回傳）。"""
        feat = _PART2['features']['related_features']['circular_runout']
        cls  = self._normalize_geo_class(geo_class)
        val  = feat['values_mm_single_value'].get(cls)
        if val is None:
            raise ValueError(f'不支援的幾何公差等級 {cls!r}，應為 H/K/L（或 GH/GK/GL）')
        return val

    # ── Unified lookup（Controller 呼叫統一入口）────────────────────────────

    def lookup(self, characteristic: str, **kwargs) -> Dict[str, Any]:
        """
        統一查表入口。

        必要 kwargs（依 characteristic）：
          linear_dimension   : size_mm, tolerance_class
          broken_edge        : size_mm, tolerance_class
          angular_dimension  : shorter_side_mm, tolerance_class
          straightness       : length_mm, geo_class
          flatness           : length_mm, geo_class
          circularity        : diameter_tolerance_mm, geo_class
          cylindricity       : diameter_tolerance_mm, length_mm, geo_class
          parallelism        : size_tolerance_mm, length_mm, geo_class
          perpendicularity   : shorter_side_mm, geo_class
          symmetry           : length_mm, geo_class
          coaxiality         : geo_class
          circular_runout    : geo_class

        回傳 dict，包含 value_mm（或 dict），characteristic，input kwargs。
        """
        char = characteristic.lower().replace(' ', '_').replace('-', '_')

        dispatch = {
            'linear_dimension':  self._unified_linear,
            'broken_edge':       self._unified_broken_edge,
            'angular_dimension': self._unified_angular,
            'straightness':      self._unified_straightness,
            'flatness':          self._unified_flatness,
            'circularity':       self._unified_circularity,
            'cylindricity':      self._unified_cylindricity,
            'parallelism':       self._unified_parallelism,
            'perpendicularity':  self._unified_perpendicularity,
            'symmetry':          self._unified_symmetry,
            'coaxiality':        self._unified_coaxiality,
            'circular_runout':   self._unified_circular_runout,
        }

        fn = dispatch.get(char)
        if fn is None:
            raise ValueError(f'不支援的特徵類型: {characteristic!r}')

        result = fn(**kwargs)

        return {
            'characteristic': characteristic,
            'input':          kwargs,
            'result':         result,
        }

    # ── Unified 內部分派 ─────────────────────────────────────────────────────

    def _unified_linear(self, size_mm, tolerance_class, **_):
        val = self.lookup_linear(float(size_mm), str(tolerance_class))
        return {'value_mm': val, 'notation': '±', 'null_means': '必須個別標示'}

    def _unified_broken_edge(self, size_mm, tolerance_class, **_):
        return {'value_mm': self.lookup_broken_edge(float(size_mm), str(tolerance_class)), 'notation': '±'}

    def _unified_angular(self, shorter_side_mm, tolerance_class, **_):
        r = self.lookup_angular(float(shorter_side_mm), str(tolerance_class))
        return {'value_deg': r['deg'], 'text': r['text'], 'notation': '±'}

    def _unified_straightness(self, length_mm, geo_class, **_):
        return {'value_mm': self.lookup_straightness(float(length_mm), str(geo_class))}

    def _unified_flatness(self, length_mm, geo_class, **_):
        return {'value_mm': self.lookup_flatness(float(length_mm), str(geo_class))}

    def _unified_circularity(self, diameter_tolerance_mm, geo_class, **_):
        return {'value_mm': self.lookup_circularity(float(diameter_tolerance_mm), str(geo_class))}

    def _unified_cylindricity(self, diameter_tolerance_mm, length_mm, geo_class, **_):
        return self.lookup_cylindricity(float(diameter_tolerance_mm), float(length_mm), str(geo_class))

    def _unified_parallelism(self, size_tolerance_mm, length_mm, geo_class, **_):
        return {'value_mm': self.lookup_parallelism(float(size_tolerance_mm), float(length_mm), str(geo_class))}

    def _unified_perpendicularity(self, shorter_side_mm, geo_class, **_):
        return {'value_mm': self.lookup_perpendicularity(float(shorter_side_mm), str(geo_class))}

    def _unified_symmetry(self, length_mm, geo_class, **_):
        return {'value_mm': self.lookup_symmetry(float(length_mm), str(geo_class))}

    def _unified_coaxiality(self, geo_class, **_):
        return self.lookup_coaxiality(str(geo_class))

    def _unified_circular_runout(self, geo_class, **_):
        return {'value_mm': self.lookup_circular_runout(str(geo_class))}

    # ── PMI 行 fallback（供 sfa_csv_importer 使用）────────────────────────────

    # tol_type → (characteristic, 'part1'|'part2', size_param)
    _TOL_TYPE_MAP = {
        'dis': ('linear_dimension', 'part1'),
        'dia': ('linear_dimension', 'part1'),
        'fla': ('flatness',         'part2'),
        'per': ('perpendicularity', 'part2'),
        'sym': ('symmetry',         'part2'),
        'run': ('circular_runout',  'part2'),
        'tot': ('circular_runout',  'part2'),   # 全跳動→圓跳動上界
        'co':  ('coaxiality',       'part2'),
        'cir': ('circularity',      'part2'),
        'par': ('parallelism',      'part2'),
        'cyl': ('cylindricity',     'part2'),
        'ang': ('angular_dimension','part1'),
        'pos': (None, None),                    # 位置度：ISO 2768 無直接一般公差
    }

    def resolve_from_pmi_row(
        self,
        tol_type: str,
        nominal_mm: float,
        geo_class: str = 'K',
        linear_class: str = 'm',
        it_grade: str = None,
    ) -> Optional[float]:
        """
        根據 SfaRow 的公差類型與公稱尺寸，從 ISO 2768 查表取得預設值。
        當 CSV 中 tol_value 為 None 時作為 fallback。

        Args:
            tol_type     : SfaRow.tol_type ('fla','par','per','dis' …)
            nominal_mm   : 公稱尺寸（長度 / 直徑），用作查表尺寸
            geo_class    : ISO 2768-2 幾何公差等級 H/K/L（或 GH/GK/GL）
            linear_class : ISO 2768-1 尺寸公差等級 f/m/c/v
            it_grade     : ISO 286 IT 等級字串（'IT6','IT7'…），
                           parallelism / circularity / cylindricity 用來估算尺寸公差

        Returns:
            float 或 None（位置度等無法直接查表的特徵）
        """
        entry = self._TOL_TYPE_MAP.get(tol_type.lower() if tol_type else '')
        if not entry or entry[0] is None:
            return None

        char, part = entry
        nom = float(nominal_mm) if nominal_mm else 1.0   # 防止 0

        try:
            if part == 'part1':
                if char == 'linear_dimension':
                    return self.lookup_linear(nom, linear_class)
                if char == 'angular_dimension':
                    result = self.lookup_angular(nom, linear_class)
                    return result['deg'] if result else None

            # Part 2
            if char == 'flatness':
                return self.lookup_flatness(nom, geo_class)

            if char == 'perpendicularity':
                return self.lookup_perpendicularity(nom, geo_class)

            if char == 'symmetry':
                return self.lookup_symmetry(nom, geo_class)

            if char == 'circular_runout':
                return self.lookup_circular_runout(geo_class)

            if char == 'coaxiality':
                return self.lookup_circular_runout(geo_class)   # fallback = runout

            if char in ('circularity', 'parallelism', 'cylindricity'):
                # 嘗試從 IT 等級估算尺寸公差
                size_tol = self._estimate_size_tol_from_it(it_grade, nom)
                if char == 'circularity':
                    return self.lookup_circularity(size_tol or nom * 0.001, geo_class)
                if char == 'parallelism':
                    return self.lookup_parallelism(size_tol or nom * 0.001, nom, geo_class)
                if char == 'cylindricity':
                    res = self.lookup_cylindricity(size_tol or nom * 0.001, nom, geo_class)
                    return res['combined_upper_bound']

        except Exception:
            return None

        return None

    @staticmethod
    def _estimate_size_tol_from_it(it_grade: str, nominal_mm: float) -> Optional[float]:
        """從 ISO 286 IT 等級粗估尺寸公差（μm→mm）。
        僅用於 circularity/parallelism/cylindricity fallback，不需高精度。
        """
        if not it_grade:
            return None
        try:
            from repositories.tolerance_repo import ToleranceRepository
            repo = ToleranceRepository()
            row  = repo.find_iso_by_size_and_grade(nominal_mm, it_grade.upper())
            if row:
                return float(row.tolerance_um) / 1000.0   # μm → mm
        except Exception:
            pass
        return None
