"""tolerance_repo.py - ISO 286 公差資料存取層

只負責執行 SQL 查詢，不含任何業務邏輯。
"""

from sqlalchemy import and_
from models import Session, ISOTolerance, ShaftTolerance, HoleTolerance


class ToleranceRepository:
    # ── ISOTolerance ─────────────────────────────────────────────────────────

    def find_iso_by_size_and_grade(self, size_mm: float, it_grade: str):
        """根據尺寸與 IT 等級查詢單筆 ISOTolerance。"""
        s = Session()
        try:
            return s.query(ISOTolerance).filter(
                and_(
                    ISOTolerance.size_from_mm <= size_mm,
                    ISOTolerance.size_to_mm   >= size_mm,
                    ISOTolerance.it_grade     == it_grade,
                )
            ).first()
        finally:
            s.close()

    def find_iso_by_size(self, size_mm: float) -> list:
        """查詢指定尺寸所有 IT 等級的 ISOTolerance 列表。"""
        s = Session()
        try:
            return s.query(ISOTolerance).filter(
                and_(
                    ISOTolerance.size_from_mm <= size_mm,
                    ISOTolerance.size_to_mm   >= size_mm,
                )
            ).all()
        finally:
            s.close()

    # ── ShaftTolerance ────────────────────────────────────────────────────────

    def find_shaft(self, size_mm: float, code: str, it_grade: str):
        """根據尺寸、代號、IT 等級查詢軸公差。"""
        s = Session()
        try:
            return s.query(ShaftTolerance).filter(
                and_(
                    ShaftTolerance.size_from_mm   <= size_mm,
                    ShaftTolerance.size_to_mm     >= size_mm,
                    ShaftTolerance.tolerance_code == code.lower(),
                    ShaftTolerance.it_grade       == it_grade,
                )
            ).first()
        finally:
            s.close()

    # ── HoleTolerance ─────────────────────────────────────────────────────────

    def find_hole(self, size_mm: float, code: str, it_grade: str):
        """根據尺寸、代號、IT 等級查詢孔公差。"""
        s = Session()
        try:
            return s.query(HoleTolerance).filter(
                and_(
                    HoleTolerance.size_from_mm   <= size_mm,
                    HoleTolerance.size_to_mm     >= size_mm,
                    HoleTolerance.tolerance_code == code.upper(),
                    HoleTolerance.it_grade       == it_grade,
                )
            ).first()
        finally:
            s.close()
