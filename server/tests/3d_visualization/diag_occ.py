# -*- coding: utf-8 -*-
"""pythonocc-core 環境診斷腳本 — 逐步測試，找出 crash 位置"""
import sys

def p(msg):
    print(msg, flush=True)

p("=== pythonocc-core 環境診斷 ===\n")

# [1] 版本
try:
    import OCC
    p(f"[1] OCC 版本：{OCC.VERSION}")
except Exception as e:
    p(f"[1] 無法取得版本：{e}")

# [2] BinXCAFDrivers plugin（載入後可解決 XCAFApp segfault）
p("\n[2] 載入 BinXCAFDrivers plugin...")
try:
    import OCC.Core.BinXCAFDrivers
    p("    ✅ 可用")
except Exception as e:
    p(f"    ⚠  不可用：{e}")

# [3] XCAFApp import（僅 import，還不呼叫）
p("\n[3] import XCAFApp_Application...")
try:
    from OCC.Core.XCAFApp import XCAFApp_Application
    p("    ✅ import 成功")
except Exception as e:
    p(f"    ❌ {e}")
    sys.exit(1)

# [4] GetApplication()  ← 最常 segfault 的地方
p("\n[4] XCAFApp_Application.GetApplication()  ← 若此後無輸出 = segfault")
try:
    app = XCAFApp_Application.GetApplication()
    p(f"    ✅ 成功，app = {type(app)}")
except Exception as e:
    p(f"    ❌ 例外：{e}")

# [5] TDocStd_Document
p("\n[5] 建立 TDocStd_Document...")
try:
    from OCC.Core.TDocStd import TDocStd_Document
    from OCC.Core.TCollection import TCollection_ExtendedString
    doc = TDocStd_Document(TCollection_ExtendedString("MDTV-CAF"))
    p(f"    ✅ 成功")
except Exception as e:
    p(f"    ❌ {e}")

p("\n=== 診斷完畢 ===")
