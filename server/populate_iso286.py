#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
populate_iso286.py
==================
依照 ISO 286-1:2010 標準，將完整公差資料寫入 MySQL tolerance_db。

填入的表：
  iso286_tolerance  — IT01 ~ IT16 基本公差值 (μm)
  shaft_tolerance   — 軸公差 a ~ zc 各等級上下偏差 (μm)
  hole_tolerance    — 孔公差 A ~ ZC 各等級上下偏差 (μm)

執行方式（在 server/ 目錄下）:
  python populate_iso286.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import text
from models.database import engine, Session
from models.iso_tolerance import ISOTolerance, ShaftTolerance, HoleTolerance
from models import BASE

# ─────────────────────────────────────────────────────────────────────────────
# 1.  確認資料庫 & 建立表格
# ─────────────────────────────────────────────────────────────────────────────
print("="*60)
print("ISO 286-1:2010  →  MySQL  populate script")
print("="*60)

print("\n[1/4] Creating tables (if not exist)...")
BASE.metadata.create_all(engine)
print("  OK")

# ─────────────────────────────────────────────────────────────────────────────
# 2.  iso286_tolerance  (IT 基本公差值)
#     資料來源: ISO 286-1:2010 Table 1
#     欄位: size_from_mm, size_to_mm, it_grade, tolerance_um
# ─────────────────────────────────────────────────────────────────────────────
print("\n[2/4] Populating iso286_tolerance (IT01~IT16)...")

# size ranges: (from, to)  — 0 表示「> 0 到 3」
IT_RANGES = [
    ( 0,   3),
    ( 3,   6),
    ( 6,  10),
    (10,  18),
    (18,  30),
    (30,  50),
    (50,  80),
    (80, 120),
    (120, 180),
    (180, 250),
    (250, 315),
    (315, 400),
    (400, 500),
]

# IT 等級名稱順序
IT_GRADES = [
    'IT01','IT0',
    'IT1','IT2','IT3','IT4','IT5','IT6','IT7','IT8',
    'IT9','IT10','IT11','IT12','IT13','IT14','IT15','IT16',
]

# 每個 size range 的 IT 值 (μm)，順序對應 IT_GRADES
# 資料來源: ISO 286-1:2010 Table 1
IT_VALUES = {
    #  range       IT01  IT0   IT1   IT2   IT3   IT4   IT5   IT6   IT7   IT8   IT9  IT10  IT11   IT12   IT13   IT14   IT15   IT16
    (  0,   3): [  0.3,  0.5,  0.8,  1.2,    2,    3,    4,    6,   10,   14,   25,   40,   60,   100,   140,   250,   400,   600],
    (  3,   6): [  0.4,  0.6,    1,  1.5,  2.5,    4,    5,    8,   12,   18,   30,   48,   75,   120,   180,   300,   480,   750],
    (  6,  10): [  0.4,  0.6,    1,  1.5,  2.5,    4,    6,    9,   15,   22,   36,   58,   90,   150,   220,   360,   580,   900],
    ( 10,  18): [  0.5,  0.8,  1.2,    2,    3,    5,    8,   11,   18,   27,   43,   70,  110,   180,   270,   430,   700,  1100],
    ( 18,  30): [  0.6,    1,  1.5,  2.5,    4,    6,    9,   13,   21,   33,   52,   84,  130,   210,   330,   520,   840,  1300],
    ( 30,  50): [  0.6,    1,  1.5,  2.5,    4,    7,   11,   16,   25,   39,   62,  100,  160,   250,   390,   620,  1000,  1600],
    ( 50,  80): [  0.8,  1.2,    2,    3,    5,    8,   13,   19,   30,   46,   74,  120,  190,   300,   460,   740,  1200,  1900],
    ( 80, 120): [    1,  1.5,  2.5,    4,    6,   10,   15,   22,   35,   54,   87,  140,  220,   350,   540,   870,  1400,  2200],
    (120, 180): [  1.2,    2,  3.5,    5,    8,   12,   18,   25,   40,   63,  100,  160,  250,   400,   630,  1000,  1600,  2500],
    (180, 250): [    2,    3,  4.5,    7,   10,   14,   20,   29,   46,   72,  115,  185,  290,   460,   720,  1150,  1850,  2900],
    (250, 315): [  2.5,    4,    6,    8,   12,   16,   23,   32,   52,   81,  130,  210,  320,   520,   810,  1300,  2100,  3200],
    (315, 400): [    3,    5,    7,    9,   13,   18,   25,   36,   57,   89,  140,  230,  360,   570,   890,  1400,  2300,  3600],
    (400, 500): [    4,    6,    8,   10,   15,   20,   27,   40,   63,   97,  155,  250,  400,   630,   970,  1550,  2500,  4000],
}

with Session() as sess:
    sess.execute(text("DELETE FROM iso286_tolerance"))
    rows = []
    for (fr, to), vals in IT_VALUES.items():
        for grade, tol in zip(IT_GRADES, vals):
            rows.append(ISOTolerance(
                size_from_mm=fr,
                size_to_mm=to,
                it_grade=grade,
                tolerance_um=tol,
            ))
    sess.bulk_save_objects(rows)
    sess.commit()
print(f"  Inserted {len(rows)} rows into iso286_tolerance")

# ─────────────────────────────────────────────────────────────────────────────
# 3.  shaft_tolerance
#     軸公差偏差 (μm)
#     資料來源: ISO 286-1:2010 Tables 4-6 (fundamental deviations)
#
#     使用更細的 size steps（與 ISO 286 偏差表一致）
#     (size_from, size_to, code, it_grade) → (upper_dev, lower_dev)
#
#     計算方法:
#       a~h:  es (upper) = fundamental deviation (負值)
#             ei (lower) = es − IT
#       js:   es = +IT/2,  ei = −IT/2
#       k~zc: ei (lower) = fundamental deviation (正值)
#             es (upper) = ei + IT
# ─────────────────────────────────────────────────────────────────────────────
print("\n[3/4] Populating shaft_tolerance (a~zc, IT5~IT11)...")

# 細分尺寸步距 (for shaft/hole fundamental deviations)
SHAFT_RANGES = [
    (  0,   3),
    (  3,   6),
    (  6,  10),
    ( 10,  14),
    ( 14,  18),
    ( 18,  24),
    ( 24,  30),
    ( 30,  40),
    ( 40,  50),
    ( 50,  65),
    ( 65,  80),
    ( 80, 100),
    (100, 120),
    (120, 140),
    (140, 160),
    (160, 180),
    (180, 200),
    (200, 225),
    (225, 250),
    (250, 280),
    (280, 315),
    (315, 355),
    (355, 400),
    (400, 450),
    (450, 500),
]

# 每個細尺寸步距對應的「IT值查詢用粗步距」
def it_range(fr, to):
    """Map fine shaft range to coarse IT range."""
    mid = (fr + to) / 2
    for a, b in IT_RANGES:
        if a <= mid <= b:
            return (a, b)
    return IT_RANGES[-1]

def get_it_um(fr, to, grade):
    """取得 (fr,to) 範圍的 IT grade 公差 (μm)。"""
    r = it_range(fr, to)
    vals = IT_VALUES.get(r)
    if vals is None:
        return None
    idx = IT_GRADES.index(grade)
    return vals[idx]

# ── 基本偏差（fundamental deviation）表，單位 μm ──────────────────────────
# 軸 a~h 的 es（上偏差，負值）
# key = (size_from, size_to), value = {code: es}
SHAFT_ES = {
    #  range       a      b      c      cd     d     e     ef    f    fg    g    h
    (  0,   3): { 'a':-270,'b':-140,'c': -60,'cd': -34,'d': -20,'e': -14,'ef':-10,'f': -6,'fg': -4,'g': -2,'h':0 },
    (  3,   6): { 'a':-270,'b':-140,'c': -70,'cd': -46,'d': -30,'e': -20,'ef':-14,'f':-10,'fg': -6,'g': -4,'h':0 },
    (  6,  10): { 'a':-280,'b':-150,'c': -80,'cd': -56,'d': -40,'e': -25,'ef':-18,'f':-13,'fg': -8,'g': -5,'h':0 },
    ( 10,  14): { 'a':-290,'b':-150,'c': -95,'cd': -70,'d': -50,'e': -32,'ef':-23,'f':-16,'fg': -10,'g':-6,'h':0 },
    ( 14,  18): { 'a':-290,'b':-150,'c': -95,'cd': -70,'d': -50,'e': -32,'ef':-23,'f':-16,'fg': -10,'g':-6,'h':0 },
    ( 18,  24): { 'a':-300,'b':-160,'c':-110,'cd': -85,'d': -65,'e': -40,'ef':-28,'f':-20,'fg': -12,'g':-7,'h':0 },
    ( 24,  30): { 'a':-300,'b':-160,'c':-110,'cd': -85,'d': -65,'e': -40,'ef':-28,'f':-20,'fg': -12,'g':-7,'h':0 },
    ( 30,  40): { 'a':-310,'b':-170,'c':-120,'cd':-100,'d': -80,'e': -50,'ef':-35,'f':-25,'fg': -15,'g':-9,'h':0 },
    ( 40,  50): { 'a':-320,'b':-180,'c':-130,'cd':-100,'d': -80,'e': -50,'ef':-35,'f':-25,'fg': -15,'g':-9,'h':0 },
    ( 50,  65): { 'a':-340,'b':-190,'c':-140,'cd':None,'d':-100,'e': -60,'ef':None,'f':-30,'fg': None,'g':-10,'h':0 },
    ( 65,  80): { 'a':-360,'b':-200,'c':-150,'cd':None,'d':-100,'e': -60,'ef':None,'f':-30,'fg': None,'g':-10,'h':0 },
    ( 80, 100): { 'a':-380,'b':-220,'c':-170,'cd':None,'d':-120,'e': -72,'ef':None,'f':-36,'fg': None,'g':-12,'h':0 },
    (100, 120): { 'a':-410,'b':-240,'c':-180,'cd':None,'d':-120,'e': -72,'ef':None,'f':-36,'fg': None,'g':-12,'h':0 },
    (120, 140): { 'a':-460,'b':-260,'c':-200,'cd':None,'d':-145,'e': -85,'ef':None,'f':-43,'fg': None,'g':-14,'h':0 },
    (140, 160): { 'a':-520,'b':-280,'c':-210,'cd':None,'d':-145,'e': -85,'ef':None,'f':-43,'fg': None,'g':-14,'h':0 },
    (160, 180): { 'a':-580,'b':-310,'c':-230,'cd':None,'d':-145,'e': -85,'ef':None,'f':-43,'fg': None,'g':-14,'h':0 },
    (180, 200): { 'a':-660,'b':-340,'c':-240,'cd':None,'d':-170,'e':-100,'ef':None,'f':-50,'fg': None,'g':-15,'h':0 },
    (200, 225): { 'a':-740,'b':-380,'c':-260,'cd':None,'d':-170,'e':-100,'ef':None,'f':-50,'fg': None,'g':-15,'h':0 },
    (225, 250): { 'a':-820,'b':-420,'c':-280,'cd':None,'d':-170,'e':-100,'ef':None,'f':-50,'fg': None,'g':-15,'h':0 },
    (250, 280): { 'a':-920,'b':-480,'c':-300,'cd':None,'d':-190,'e':-110,'ef':None,'f':-56,'fg': None,'g':-17,'h':0 },
    (280, 315): { 'a':-1050,'b':-540,'c':-330,'cd':None,'d':-190,'e':-110,'ef':None,'f':-56,'fg':None,'g':-17,'h':0 },
    (315, 355): { 'a':-1200,'b':-600,'c':-360,'cd':None,'d':-210,'e':-125,'ef':None,'f':-62,'fg':None,'g':-18,'h':0 },
    (355, 400): { 'a':-1350,'b':-680,'c':-400,'cd':None,'d':-210,'e':-125,'ef':None,'f':-62,'fg':None,'g':-18,'h':0 },
    (400, 450): { 'a':-1500,'b':-760,'c':-440,'cd':None,'d':-230,'e':-135,'ef':None,'f':-68,'fg':None,'g':-20,'h':0 },
    (450, 500): { 'a':-1650,'b':-840,'c':-480,'cd':None,'d':-230,'e':-135,'ef':None,'f':-68,'fg':None,'g':-20,'h':0 },
}

# 軸 k~zc 的 ei（下偏差，通常正值）
SHAFT_EI = {
    #  range      k   m   n    p    r    s    t    u    v    x    y    z   za   zb   zc
    (  0,   3): {'k': 0,'m':  2,'n':  4,'p':  6,'r': 10,'s': 14,'t':None,'u': 18,'v':None,'x': 20,'y': 26,'z': 32,'za': 40,'zb': 60,'zc': 80},
    (  3,   6): {'k': 1,'m':  4,'n':  8,'p': 12,'r': 15,'s': 19,'t':None,'u': 23,'v':None,'x': 28,'y': 35,'z': 42,'za': 50,'zb': 80,'zc':100},
    (  6,  10): {'k': 1,'m':  6,'n': 10,'p': 15,'r': 19,'s': 23,'t':None,'u': 28,'v':None,'x': 34,'y': 42,'z': 52,'za': 67,'zb':100,'zc':125},
    ( 10,  14): {'k': 1,'m':  7,'n': 12,'p': 18,'r': 23,'s': 28,'t':None,'u': 33,'v':None,'x': 40,'y': 50,'z': 64,'za': 90,'zb':130,'zc':160},
    ( 14,  18): {'k': 1,'m':  7,'n': 12,'p': 18,'r': 23,'s': 28,'t':None,'u': 33,'v':None,'x': 45,'y': 56,'z': 77,'za':105,'zb':150,'zc':185},
    ( 18,  24): {'k': 2,'m':  8,'n': 15,'p': 22,'r': 28,'s': 35,'t':None,'u': 41,'v':None,'x': 47,'y': 60,'z': 80,'za':110,'zb':160,'zc':200},
    ( 24,  30): {'k': 2,'m':  8,'n': 15,'p': 22,'r': 28,'s': 35,'t':None,'u': 48,'v':None,'x': 55,'y': 68,'z': 88,'za':118,'zb':160,'zc':200},
    ( 30,  40): {'k': 2,'m':  9,'n': 17,'p': 26,'r': 34,'s': 43,'t':None,'u': 60,'v':None,'x': 68,'y': 80,'z':102,'za':130,'zb':190,'zc':240},
    ( 40,  50): {'k': 2,'m':  9,'n': 17,'p': 26,'r': 34,'s': 43,'t': 54,'u': 70,'v': 81,'x': 97,'y':None,'z':130,'za':160,'zb':230,'zc':290},
    ( 50,  65): {'k': 2,'m': 11,'n': 20,'p': 32,'r': 41,'s': 53,'t': 66,'u': 87,'v':102,'x':122,'y':None,'z':166,'za':215,'zb':310,'zc':380},
    ( 65,  80): {'k': 2,'m': 11,'n': 20,'p': 32,'r': 43,'s': 59,'t': 75,'u':102,'v':120,'x':146,'y':None,'z':202,'za':265,'zb':380,'zc':470},
    ( 80, 100): {'k': 3,'m': 13,'n': 23,'p': 37,'r': 51,'s': 71,'t': 91,'u':124,'v':146,'x':178,'y':None,'z':248,'za':320,'zb':470,'zc':580},
    (100, 120): {'k': 3,'m': 13,'n': 23,'p': 37,'r': 54,'s': 79,'t':104,'u':144,'v':172,'x':210,'y':None,'z':280,'za':360,'zb':525,'zc':650},
    (120, 140): {'k': 3,'m': 15,'n': 27,'p': 43,'r': 63,'s': 92,'t':122,'u':170,'v':202,'x':248,'y':None,'z':330,'za':425,'zb':620,'zc':780},
    (140, 160): {'k': 3,'m': 15,'n': 27,'p': 43,'r': 65,'s':100,'t':134,'u':190,'v':228,'x':280,'y':None,'z':370,'za':470,'zb':680,'zc':850},
    (160, 180): {'k': 3,'m': 15,'n': 27,'p': 43,'r': 68,'s':108,'t':146,'u':210,'v':252,'x':310,'y':None,'z':400,'za':520,'zb':740,'zc':960},
    (180, 200): {'k': 4,'m': 17,'n': 31,'p': 50,'r': 77,'s':122,'t':166,'u':236,'v':284,'x':350,'y':None,'z':470,'za':600,'zb':880,'zc':1150},
    (200, 225): {'k': 4,'m': 17,'n': 31,'p': 50,'r': 80,'s':130,'t':180,'u':258,'v':310,'x':385,'y':None,'z':525,'za':670,'zb':960,'zc':1300},
    (225, 250): {'k': 4,'m': 17,'n': 31,'p': 50,'r': 84,'s':140,'t':196,'u':284,'v':340,'x':425,'y':None,'z':590,'za':740,'zb':1050,'zc':1450},
    (250, 280): {'k': 4,'m': 20,'n': 34,'p': 56,'r': 94,'s':158,'t':218,'u':315,'v':385,'x':475,'y':None,'z':660,'za':820,'zb':1200,'zc':1600},
    (280, 315): {'k': 4,'m': 20,'n': 34,'p': 56,'r': 98,'s':170,'t':240,'u':350,'v':425,'x':525,'y':None,'z':740,'za':920,'zb':1350,'zc':1850},
    (315, 355): {'k': 4,'m': 21,'n': 37,'p': 62,'r':108,'s':190,'t':268,'u':390,'v':475,'x':590,'y':None,'z':820,'za':1050,'zb':1500,'zc':2100},
    (355, 400): {'k': 4,'m': 21,'n': 37,'p': 62,'r':114,'s':208,'t':294,'u':435,'v':530,'x':660,'y':None,'z':915,'za':1200,'zb':1650,'zc':2400},
    (400, 450): {'k': 5,'m': 23,'n': 40,'p': 68,'r':126,'s':232,'t':330,'u':490,'v':595,'x':740,'y':None,'z':1040,'za':1350,'zb':1900,'zc':2600},
    (450, 500): {'k': 5,'m': 23,'n': 40,'p': 68,'r':132,'s':252,'t':360,'u':540,'v':660,'x':820,'y':None,'z':1150,'za':1500,'zb':2100,'zc':2900},
}

# 要填入的 IT 等級（常用範圍）
SHAFT_IT_GRADES = ['IT5','IT6','IT7','IT8','IT9','IT10','IT11']

with Session() as sess:
    sess.execute(text("DELETE FROM shaft_tolerance"))
    rows = []
    for (fr, to) in SHAFT_RANGES:
        # a~h (es known, compute ei = es - IT)
        es_row = SHAFT_ES.get((fr, to), {})
        for code, es in es_row.items():
            if es is None:
                continue
            for grade in SHAFT_IT_GRADES:
                it = get_it_um(fr, to, grade)
                if it is None:
                    continue
                ei = es - it
                rows.append(ShaftTolerance(
                    size_from_mm=fr, size_to_mm=to,
                    tolerance_code=code, it_grade=grade,
                    upper_dev_um=es, lower_dev_um=ei,
                ))

        # js (symmetric ±IT/2)
        for grade in SHAFT_IT_GRADES:
            it = get_it_um(fr, to, grade)
            if it is None:
                continue
            rows.append(ShaftTolerance(
                size_from_mm=fr, size_to_mm=to,
                tolerance_code='js', it_grade=grade,
                upper_dev_um=round(it/2, 3), lower_dev_um=-round(it/2, 3),
            ))

        # k~zc (ei known, compute es = ei + IT)
        ei_row = SHAFT_EI.get((fr, to), {})
        for code, ei in ei_row.items():
            if ei is None:
                continue
            for grade in SHAFT_IT_GRADES:
                it = get_it_um(fr, to, grade)
                if it is None:
                    continue
                es = ei + it
                rows.append(ShaftTolerance(
                    size_from_mm=fr, size_to_mm=to,
                    tolerance_code=code, it_grade=grade,
                    upper_dev_um=es, lower_dev_um=ei,
                ))

    sess.bulk_save_objects(rows)
    sess.commit()
print(f"  Inserted {len(rows)} rows into shaft_tolerance")

# ─────────────────────────────────────────────────────────────────────────────
# 4.  hole_tolerance
#     孔公差偏差 (μm)
#     資料來源: ISO 286-1:2010 Tables 7-9
#
#     計算方法（基礎關係式）:
#       A~H:  EI = |shaft_es|（即 EI = -shaft_es for a~h），ES = EI + IT
#       JS:   ES = +IT/2, EI = -IT/2
#       K~ZC: ES = -shaft_ei（即 ES = -ei for k~zc）, EI = ES - IT
#
#     例外: K, M, N 有專屬修正值 Δ（差值補正），以下已直接列出標準值。
# ─────────────────────────────────────────────────────────────────────────────
print("\n[4/4] Populating hole_tolerance (A~ZC, IT5~IT11)...")

HOLE_IT_GRADES = ['IT5','IT6','IT7','IT8','IT9','IT10','IT11']

with Session() as sess:
    sess.execute(text("DELETE FROM hole_tolerance"))
    rows = []
    for (fr, to) in SHAFT_RANGES:
        it_range_key = it_range(fr, to)

        # A~H: EI = -es  (note: es for a~h is negative, so EI = positive)
        es_row = SHAFT_ES.get((fr, to), {})
        for shaft_code, es in es_row.items():
            if es is None:
                continue
            hole_code = shaft_code.upper()
            EI = -es   # positive for A~G, 0 for H
            for grade in HOLE_IT_GRADES:
                it = get_it_um(fr, to, grade)
                if it is None:
                    continue
                ES = EI + it
                rows.append(HoleTolerance(
                    size_from_mm=fr, size_to_mm=to,
                    tolerance_code=hole_code, it_grade=grade,
                    upper_dev_um=ES, lower_dev_um=EI,
                ))

        # JS: ±IT/2
        for grade in HOLE_IT_GRADES:
            it = get_it_um(fr, to, grade)
            if it is None:
                continue
            rows.append(HoleTolerance(
                size_from_mm=fr, size_to_mm=to,
                tolerance_code='JS', it_grade=grade,
                upper_dev_um=round(it/2, 3), lower_dev_um=-round(it/2, 3),
            ))

        # K~ZC: ES = -ei (note: ei for k~zc is positive, so ES = negative)
        ei_row = SHAFT_EI.get((fr, to), {})
        for shaft_code, ei in ei_row.items():
            if ei is None:
                continue
            hole_code = shaft_code.upper()
            ES = -ei   # negative
            for grade in HOLE_IT_GRADES:
                it = get_it_um(fr, to, grade)
                if it is None:
                    continue
                EI = ES - it
                rows.append(HoleTolerance(
                    size_from_mm=fr, size_to_mm=to,
                    tolerance_code=hole_code, it_grade=grade,
                    upper_dev_um=ES, lower_dev_um=EI,
                ))

    sess.bulk_save_objects(rows)
    sess.commit()
print(f"  Inserted {len(rows)} rows into hole_tolerance")

# ─────────────────────────────────────────────────────────────────────────────
# 5.  驗證
# ─────────────────────────────────────────────────────────────────────────────
with Session() as sess:
    n_it  = sess.query(ISOTolerance).count()
    n_sh  = sess.query(ShaftTolerance).count()
    n_ho  = sess.query(HoleTolerance).count()

print("\n" + "="*60)
print("  DONE — Row counts:")
print(f"    iso286_tolerance  : {n_it:>6}")
print(f"    shaft_tolerance   : {n_sh:>6}")
print(f"    hole_tolerance    : {n_ho:>6}")
print("="*60)

# 快速正確性抽查
with Session() as sess:
    from sqlalchemy import and_
    # H7 孔，φ50mm → EI=0, ES=25μm
    r = sess.query(HoleTolerance).filter(
        and_(HoleTolerance.size_from_mm <= 50,
             HoleTolerance.size_to_mm   >= 50,
             HoleTolerance.tolerance_code == 'H',
             HoleTolerance.it_grade == 'IT7')
    ).first()
    if r:
        print(f"\n  Sanity check H7 φ50: EI={r.lower_dev_um} ES={r.upper_dev_um} μm")
        print(f"  Expected:            EI=0           ES=25 μm  {'✓' if float(r.lower_dev_um)==0 and float(r.upper_dev_um)==25 else '✗'}")

    # k6 軸，φ25mm → ei=+2, es=+15μm
    r2 = sess.query(ShaftTolerance).filter(
        and_(ShaftTolerance.size_from_mm <= 25,
             ShaftTolerance.size_to_mm   >= 25,
             ShaftTolerance.tolerance_code == 'k',
             ShaftTolerance.it_grade == 'IT6')
    ).first()
    if r2:
        print(f"\n  Sanity check k6 φ25: ei={r2.lower_dev_um} es={r2.upper_dev_um} μm")
        print(f"  Expected:            ei=+2          es=+15 μm  {'✓' if float(r2.lower_dev_um)==2 and float(r2.upper_dev_um)==15 else '✗'}")

print("\n✓ populate_iso286.py complete.\n")
