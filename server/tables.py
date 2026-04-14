import os
os.environ['SQLALCHEMY_WARN_20'] = '0'
os.environ['SQLALCHEMY_SILENCE_UBER_WARNING'] = '0'

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, func, create_engine, text,
    UniqueConstraint, DECIMAL, Text, Enum
)
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# 讀取 .env 檔案
load_dotenv()

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


class PmiSession(BASE):
  """PMI 工作階段表（每次上傳 STEP + XLSX）"""
  __tablename__ = 'pmi_session'

  id            = Column(Integer, primary_key=True, autoincrement=True)
  session_id    = Column(String(64), nullable=False, unique=True)    # UUID
  stp_filename  = Column(String(512), nullable=False)                 # 原始檔案名
  stp_path      = Column(String(1024), nullable=False)                # 伺服器存放路徑
  xlsx_filename = Column(String(512), nullable=True)
  xlsx_path     = Column(String(1024), nullable=True)
  n_faces       = Column(Integer, default=0)
  n_pmi_rows    = Column(Integer, default=0)
  status        = Column(String(20), default='pending')               # pending, ready, error
  error_msg     = Column(Text, nullable=True)
  created_at    = Column(DateTime, server_default=func.now())
  updated_at    = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PmiItem(BASE):
  """PMI 標註條目表"""
  __tablename__ = 'pmi_item'

  id             = Column(Integer, primary_key=True, autoincrement=True)
  session_id     = Column(String(64), nullable=False)                 # FK → pmi_session.session_id
  row_index      = Column(Integer, nullable=False)                    # pmi_rows 中的索引
  label          = Column(Text, nullable=False)                       # 顯示標籤
  type_code      = Column(String(16), nullable=True)                  # dis, par, per, pos, etc.
  semantic_id    = Column(String(32), nullable=True)                  # STEP entity ID
  tao_id         = Column(String(32), nullable=True)                  # TESSELLATED_ANNOTATION_OCCURRENCE ID
  face_ids       = Column(Text, nullable=True)                        # JSON array: ["123","456"]
  is_datum       = Column(Integer, default=0)                         # TINYINT(1)
  is_interactive = Column(Integer, default=0)
  is_feature_only = Column(Integer, default=0)
  nominal_size   = Column(String(32), nullable=True)                  # 公稱尺寸 (e.g., "55.00" 或 "125.03-125.05")
  it_grade       = Column(String(10), nullable=True)                  # IT 等級 (e.g., "IT7")
  created_at     = Column(DateTime, server_default=func.now())


class AssemblyContact(BASE):
  """組合件接觸分析結果表"""
  __tablename__ = 'assembly_contact'

  id              = Column(Integer, primary_key=True, autoincrement=True)
  session_id      = Column(String(64), nullable=False)                # FK → pmi_session.session_id
  comp1_name      = Column(String(256), nullable=False)               # 零件 1 名稱
  comp2_name      = Column(String(256), nullable=False)               # 零件 2 名稱
  contact_type    = Column(String(128), nullable=False)               # 平面接合, 圓柱接合, etc.
  face_pairs_json = Column(Text, nullable=True)                       # 原始 JSON
  bbox1_json      = Column(Text, nullable=True)                       # [xmin,ymin,zmin,xmax,ymax,zmax]
  bbox2_json      = Column(Text, nullable=True)
  created_at      = Column(DateTime, server_default=func.now())


class PmiExportRecord(BASE):
  """PMI / 組合件 CSV 導出記錄表"""
  __tablename__ = 'pmi_export_record'

  id            = Column(Integer, primary_key=True, autoincrement=True)
  session_id    = Column(String(64), nullable=False)                # FK → pmi_session.session_id
  export_mode   = Column(String(8), default='pmi', nullable=False)  # 'pmi' 或 'asm'
  row_count     = Column(Integer, default=0)                        # 導出的行數
  csv_content   = Column(Text, nullable=True)                       # CSV 原始內容
  created_at    = Column(DateTime, server_default=func.now())


# ------------------------------------------------------------------


# 建立連線（優先從 .env 讀取 DATABASE_URL）
db_url = os.getenv('DATABASE_URL', "mysql+pymysql://root:Bb88710307@127.0.0.1:3306/tolerance_db?charset=utf8mb4")
engine  = create_engine(db_url, echo=False)
Session = sessionmaker(bind=engine)

if __name__ == "__main__":
    BASE.metadata.create_all(engine)
    print(f"Database tables created successfully or already exist.")
    print(f"Connection: {db_url.split('@')[-1]}") # 僅列印連線目標，隱藏密碼

    # 自動從 URL 提取資料庫名稱
    db_name = db_url.split('/')[-1].split('?')[0]

    # 統一資料庫與表的字符集
    with engine.connect() as conn:
        try:
            conn.execute(text(f"ALTER DATABASE {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"))
            conn.execute(text("ALTER TABLE iso286_tolerance CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"))
            conn.commit()
            print(f"✓ Character set for database '{db_name}' updated.")
        except Exception as e:
            print(f"! Warning during charset update: {e}")

