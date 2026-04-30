"""tolerance_service.py - ISO 286 公差業務邏輯

負責 IT 等級推薦與公差查詢，呼叫 ToleranceRepository 取得資料。
"""

from repositories.tolerance_repo import ToleranceRepository


class ToleranceService:
    def __init__(self):
        self._repo = ToleranceRepository()

    # ── IT 等級轉數字 ─────────────────────────────────────────────────────────

    @staticmethod
    def _it_key(it_txt: str) -> int:
        k = it_txt.upper().replace('IT', '')
        try:
            return int(k)
        except ValueError:
            return int(float(k))

    # ── IT 等級推薦 ───────────────────────────────────────────────────────────

    def recommend_it(
        self,
        size_mm: float,
        target_tol_um: float,
        prefer_floor: str = None,
        prefer_ceil: str = None,
    ):
        """回傳最接近目標公差的 IT 等級。

        Returns:
            (result_dict, error_msg) — 成功時 error_msg 為 None。
        """
        rows = self._repo.find_iso_by_size(size_mm)
        if not rows:
            return None, '指定尺寸無對應 ISO286 區間'

        if prefer_floor:
            floor_n = self._it_key(prefer_floor)
            rows = [r for r in rows if self._it_key(r.it_grade) >= floor_n]
        if prefer_ceil:
            ceil_n = self._it_key(prefer_ceil)
            rows = [r for r in rows if self._it_key(r.it_grade) <= ceil_n]

        if not rows:
            return None, '條件過嚴，沒有可用的 IT 等級'

        best = min(rows, key=lambda r: abs(float(r.tolerance_um) - target_tol_um))
        return {
            'recommended_it': best.it_grade,
            'tolerance_μm':   float(best.tolerance_um),
            'range_mm':        [float(best.size_from_mm), float(best.size_to_mm)],
        }, None

    # ── 查詢 ISO / 軸 / 孔 ────────────────────────────────────────────────────

    def lookup_iso(self, size_mm: float, it_grade: str):
        """查詢 ISOTolerance。回傳 dict 或 None。"""
        row = self._repo.find_iso_by_size_and_grade(size_mm, it_grade.upper())
        if not row:
            return None
        return {
            'it_grade':      row.it_grade,
            'tolerance_μm':  float(row.tolerance_um),
            'range_mm':       [float(row.size_from_mm), float(row.size_to_mm)],
        }

    def lookup_shaft(self, size_mm: float, code: str, it_grade: str):
        """查詢 ShaftTolerance。回傳 dict 或 None。"""
        row = self._repo.find_shaft(size_mm, code.lower(), it_grade.upper())
        if not row:
            return None
        return {
            'tolerance_code': row.tolerance_code,
            'it_grade':       row.it_grade,
            'upper_dev_um':   float(row.upper_dev_um) if row.upper_dev_um is not None else None,
            'lower_dev_um':   float(row.lower_dev_um) if row.lower_dev_um is not None else None,
            'range_mm':        [float(row.size_from_mm), float(row.size_to_mm)],
        }

    def lookup_hole(self, size_mm: float, code: str, it_grade: str):
        """查詢 HoleTolerance。回傳 dict 或 None。"""
        row = self._repo.find_hole(size_mm, code.upper(), it_grade.upper())
        if not row:
            return None
        return {
            'tolerance_code': row.tolerance_code,
            'it_grade':       row.it_grade,
            'upper_dev_um':   float(row.upper_dev_um) if row.upper_dev_um is not None else None,
            'lower_dev_um':   float(row.lower_dev_um) if row.lower_dev_um is not None else None,
            'range_mm':        [float(row.size_from_mm), float(row.size_to_mm)],
        }
