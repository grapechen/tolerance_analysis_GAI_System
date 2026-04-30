from sqlalchemy import Column, Integer, String, DateTime, Text, Index, func
from .database import BASE


class PmiSession(BASE):
    """PMI 工作階段表（每次上傳 STEP + XLSX）"""
    __tablename__ = 'pmi_session'

    id            = Column(Integer, primary_key=True, autoincrement=True)
    session_id    = Column(String(64),   nullable=False, unique=True)
    stp_filename  = Column(String(512),  nullable=False)
    stp_path      = Column(String(1024), nullable=False)
    xlsx_filename = Column(String(512),  nullable=True)
    xlsx_path     = Column(String(1024), nullable=True)
    n_faces       = Column(Integer, default=0)
    n_pmi_rows    = Column(Integer, default=0)
    status        = Column(String(20), default='pending')   # pending | ready | error
    error_msg     = Column(Text, nullable=True)
    created_at    = Column(DateTime, server_default=func.now())
    updated_at    = Column(DateTime, server_default=func.now(), onupdate=func.now())


class PmiItem(BASE):
    """PMI 標註條目表"""
    __tablename__ = 'pmi_item'

    id              = Column(Integer, primary_key=True, autoincrement=True)
    session_id      = Column(String(64),  nullable=False)
    row_index       = Column(Integer,     nullable=False)
    label           = Column(Text,        nullable=False)
    type_code       = Column(String(16),  nullable=True)   # dis, par, per, pos …
    semantic_id     = Column(String(32),  nullable=True)
    tao_id          = Column(String(32),  nullable=True)
    face_ids        = Column(Text,        nullable=True)   # JSON array
    is_datum        = Column(Integer, default=0)
    is_interactive  = Column(Integer, default=0)
    is_feature_only = Column(Integer, default=0)
    nominal_size    = Column(String(32),  nullable=True)
    it_grade        = Column(String(10),  nullable=True)
    created_at      = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index('ix_pmi_item_session_id',   'session_id'),
        Index('ix_pmi_item_semantic_id',  'semantic_id'),
    )


class AssemblyContact(BASE):
    """組合件接觸分析結果表"""
    __tablename__ = 'assembly_contact'

    id              = Column(Integer, primary_key=True, autoincrement=True)
    session_id      = Column(String(64),  nullable=False)
    comp1_name      = Column(String(256), nullable=False)
    comp2_name      = Column(String(256), nullable=False)
    contact_type    = Column(String(128), nullable=False)
    face_pairs_json = Column(Text, nullable=True)
    bbox1_json      = Column(Text, nullable=True)
    bbox2_json      = Column(Text, nullable=True)
    created_at      = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index('ix_asm_contact_session_id', 'session_id'),
    )


class PmiExportRecord(BASE):
    """PMI / 組合件 CSV 導出記錄表"""
    __tablename__ = 'pmi_export_record'

    id          = Column(Integer, primary_key=True, autoincrement=True)
    session_id  = Column(String(64), nullable=False)
    export_mode = Column(String(8),  default='pmi', nullable=False)  # 'pmi' | 'asm'
    row_count   = Column(Integer, default=0)
    csv_content = Column(Text, nullable=True)
    created_at  = Column(DateTime, server_default=func.now())
