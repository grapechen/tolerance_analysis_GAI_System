"""fit_service.py - 配合分析業務邏輯

解析孔 / 軸公差符號，計算間隙 / 過盈，判斷配合類型。
"""

import re
from repositories.tolerance_repo import ToleranceRepository


class FitService:
    def __init__(self):
        self._repo = ToleranceRepository()

    # ── 靜態工具 ──────────────────────────────────────────────────────────────

    @staticmethod
    def parse_notation(notation: str, is_hole: bool):
        """解析公差符號，回傳 (code, it_grade) 或 (None, None)。
        例：'H7' → ('H', 'IT7')，'h6' → ('h', 'IT6')
        """
        pattern = r'([A-Za-z]+)(\d+)'
        m = re.match(pattern, notation.strip())
        if not m:
            return None, None
        code     = m.group(1).upper() if is_hole else m.group(1).lower()
        it_grade = 'IT' + m.group(2)
        return code, it_grade

    @staticmethod
    def determine_fit_type(min_clearance: float, max_clearance: float) -> str:
        """根據間隙範圍判斷配合類型。"""
        if min_clearance >= 0:
            return '留隙配合'
        if max_clearance <= 0:
            return '過盈配合'
        return '過渡配合'

    # ── 主要方法 ──────────────────────────────────────────────────────────────

    def analyze_fit(self, size_mm: float, hole_str: str, shaft_str: str):
        """執行配合分析。

        Returns:
            (result_dict, error_msg)
        """
        hole_code, hole_it = self.parse_notation(hole_str, is_hole=True)
        shaft_code, shaft_it = self.parse_notation(shaft_str, is_hole=False)

        if not hole_code or not shaft_code:
            return None, '公差格式錯誤（孔應為大寫如 H7，軸應為小寫如 h6）'

        hole  = self._repo.find_hole(size_mm, hole_code, hole_it)
        shaft = self._repo.find_shaft(size_mm, shaft_code, shaft_it)

        if not hole or not shaft:
            return None, '找不到對應的孔或軸公差資料'

        h_max = float(hole.upper_dev_um)  if hole.upper_dev_um  is not None else 0
        h_min = float(hole.lower_dev_um)  if hole.lower_dev_um  is not None else 0
        s_max = float(shaft.upper_dev_um) if shaft.upper_dev_um is not None else 0
        s_min = float(shaft.lower_dev_um) if shaft.lower_dev_um is not None else 0

        max_clearance = h_max - s_min
        min_clearance = h_min - s_max
        fit_type = self.determine_fit_type(min_clearance, max_clearance)

        return {
            'fit_type': fit_type,
            'hole':  {'公差類型': hole_code + hole_it.replace('IT', ''),  '上偏差(um)': h_max, '下偏差(um)': h_min},
            'shaft': {'公差類型': shaft_code + shaft_it.replace('IT', ''), '上偏差(um)': s_max, '下偏差(um)': s_min},
            'max_clearance_um': round(max_clearance, 3),
            'min_clearance_um': round(min_clearance, 3),
            'note': '正值為餘隙，負值為過盈',
        }, None

    def get_fit_details_for_matchmaking(
        self, size_mm: float, hole_str: str, shaft_str: str
    ) -> dict:
        """供 MatchmakingService 使用，回傳精簡的配合詳情 dict（失敗時回傳空 dict）。"""
        hole_code, hole_it   = self.parse_notation(hole_str, is_hole=True)
        shaft_code, shaft_it = self.parse_notation(shaft_str, is_hole=False)
        if not hole_code or not shaft_code:
            return {}

        hole  = self._repo.find_hole(size_mm, hole_code, hole_it)
        shaft = self._repo.find_shaft(size_mm, shaft_code, shaft_it)
        if not hole or not shaft:
            return {}

        h_max = float(hole.upper_dev_um)  if hole.upper_dev_um  is not None else 0
        h_min = float(hole.lower_dev_um)  if hole.lower_dev_um  is not None else 0
        s_max = float(shaft.upper_dev_um) if shaft.upper_dev_um is not None else 0
        s_min = float(shaft.lower_dev_um) if shaft.lower_dev_um is not None else 0

        max_c = h_max - s_min
        min_c = h_min - s_max

        return {
            'fit_type':         self.determine_fit_type(min_c, max_c),
            'hole':             {'code': hole_str,  'upper_um': h_max, 'lower_um': h_min},
            'shaft':            {'code': shaft_str, 'upper_um': s_max, 'lower_um': s_min},
            'max_clearance_um': round(max_c, 3),
            'min_clearance_um': round(min_c, 3),
        }
