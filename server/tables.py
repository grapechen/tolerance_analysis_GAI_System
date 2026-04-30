"""tables.py - 向後相容層

此檔案已重構為 models/ 套件。
保留此模組僅供尚未更新 import 的舊程式碼使用。
新程式碼請改為：from models import ...
"""

from models import (
    BASE, engine, Session,
    ISOTolerance, ShaftTolerance, HoleTolerance,
    PmiSession, PmiItem, AssemblyContact, PmiExportRecord,
)

__all__ = [
    'BASE', 'engine', 'Session',
    'ISOTolerance', 'ShaftTolerance', 'HoleTolerance',
    'PmiSession', 'PmiItem', 'AssemblyContact', 'PmiExportRecord',
]
