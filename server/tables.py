import os
os.environ['SQLALCHEMY_WARN_20'] = '0'
os.environ['SQLALCHEMY_SILENCE_UBER_WARNING'] = '0'

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, func, create_engine, text,
    UniqueConstraint, DECIMAL
)
from sqlalchemy.orm import sessionmaker, declarative_base

BASE = declarative_base()   # 宣告一個映射, 建立一個基礎類別


# ------------------------------------------------------------------


class ISOTolerance(BASE):
  """ISO 286 基本公差表（IT 等級）"""
  __tablename__ = 'iso286_tolerance'

  id = Column(Integer, primary_key=True, autoincrement=True)
  size_from_mm = Column(DECIMAL(10,3), nullable=False)
  size_to_mm   = Column(DECIMAL(10,3), nullable=False)
  it_grade     = Column(String(5),     nullable=False)   # IT01~IT18
  tolerance_um = Column(DECIMAL(12,3), nullable=True)    # 統一存 μm
  create_at = Column(DateTime, server_default=func.now())

  __table_args__ = (
      UniqueConstraint('size_from_mm','size_to_mm','it_grade', name='uq_range_grade'),
  )


class ShaftTolerance(BASE):
  """軸公差表（a-zc 等代號）"""
  __tablename__ = 'shaft_tolerance'

  id = Column(Integer, primary_key=True, autoincrement=True)
  size_from_mm = Column(DECIMAL(10,3), nullable=False)
  size_to_mm   = Column(DECIMAL(10,3), nullable=False)
  tolerance_code = Column(String(5), nullable=False)  # a, b, c, ..., zc
  it_grade     = Column(String(5), nullable=False)    # IT6, IT7, etc.
  upper_dev_um = Column(DECIMAL(12,3), nullable=True) # 上偏差 (μm)
  lower_dev_um = Column(DECIMAL(12,3), nullable=True) # 下偏差 (μm)
  create_at = Column(DateTime, server_default=func.now())

  __table_args__ = (
      UniqueConstraint('size_from_mm','size_to_mm','tolerance_code','it_grade', name='uq_shaft'),
  )


class HoleTolerance(BASE):
  """孔公差表（A-ZC 等代號）"""
  __tablename__ = 'hole_tolerance'

  id = Column(Integer, primary_key=True, autoincrement=True)
  size_from_mm = Column(DECIMAL(10,3), nullable=False)
  size_to_mm   = Column(DECIMAL(10,3), nullable=False)
  tolerance_code = Column(String(5), nullable=False)  # A, B, C, ..., ZC
  it_grade     = Column(String(5), nullable=False)    # IT6, IT7, etc.
  upper_dev_um = Column(DECIMAL(12,3), nullable=True) # 上偏差 (μm)
  lower_dev_um = Column(DECIMAL(12,3), nullable=True) # 下偏差 (μm)
  create_at = Column(DateTime, server_default=func.now())

  __table_args__ = (
      UniqueConstraint('size_from_mm','size_to_mm','tolerance_code','it_grade', name='uq_hole'),
  )

  


# ------------------------------------------------------------------


# 建立連線（設定 charset=utf8mb4）
engine  = create_engine("mysql+pymysql://root:Bb88710307@127.0.0.1:3307/tol?charset=utf8mb4", echo=False)
Session = sessionmaker(bind=engine)

if __name__ == "__main__":
    BASE.metadata.create_all(engine)
    print("ISO 286 Tolerance Table created successfully...")

    # 統一資料庫與表的字符集
    with engine.connect() as conn:
        conn.execute(text("ALTER DATABASE tol CHARACTER SET utf8mb4 COLLATE  utf8mb4_unicode_ci;"))
        conn.execute(text("ALTER TABLE iso286_tolerance CONVERT TO CHARACTER SET utf8mb4 COLLATE  utf8mb4_unicode_ci;"))
        conn.execute(text("SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci"))

