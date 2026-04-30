from sqlalchemy import Column, Integer, String, DateTime, DECIMAL, UniqueConstraint, func
from .database import BASE


class ISOTolerance(BASE):
    """ISO 286 基本公差表（IT 等級）"""
    __tablename__ = 'iso286_tolerance'

    id           = Column(Integer, primary_key=True, autoincrement=True)
    size_from_mm = Column(DECIMAL(10, 3), nullable=False)
    size_to_mm   = Column(DECIMAL(10, 3), nullable=False)
    it_grade     = Column(String(5),      nullable=False)   # IT01~IT18
    tolerance_um = Column(DECIMAL(12, 3), nullable=True)    # μm
    create_at    = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('size_from_mm', 'size_to_mm', 'it_grade', name='uq_range_grade'),
    )


class ShaftTolerance(BASE):
    """軸公差表（a-zc 代號）"""
    __tablename__ = 'shaft_tolerance'

    id             = Column(Integer, primary_key=True, autoincrement=True)
    size_from_mm   = Column(DECIMAL(10, 3), nullable=False)
    size_to_mm     = Column(DECIMAL(10, 3), nullable=False)
    tolerance_code = Column(String(5),      nullable=False)  # a, b, c, ..., zc
    it_grade       = Column(String(5),      nullable=False)  # IT6, IT7 …
    upper_dev_um   = Column(DECIMAL(12, 3), nullable=True)   # 上偏差 (μm)
    lower_dev_um   = Column(DECIMAL(12, 3), nullable=True)   # 下偏差 (μm)
    create_at      = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('size_from_mm', 'size_to_mm', 'tolerance_code', 'it_grade', name='uq_shaft'),
    )


class HoleTolerance(BASE):
    """孔公差表（A-ZC 代號）"""
    __tablename__ = 'hole_tolerance'

    id             = Column(Integer, primary_key=True, autoincrement=True)
    size_from_mm   = Column(DECIMAL(10, 3), nullable=False)
    size_to_mm     = Column(DECIMAL(10, 3), nullable=False)
    tolerance_code = Column(String(5),      nullable=False)  # A, B, C, ..., ZC
    it_grade       = Column(String(5),      nullable=False)
    upper_dev_um   = Column(DECIMAL(12, 3), nullable=True)
    lower_dev_um   = Column(DECIMAL(12, 3), nullable=True)
    create_at      = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('size_from_mm', 'size_to_mm', 'tolerance_code', 'it_grade', name='uq_hole'),
    )
