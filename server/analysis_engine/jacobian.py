import numpy as np
from math import pi, cos, sin
from .models import ParameterizationModel as PM

def compute_jacobian(tol_data, progress_cb=None, stacking_axis: str = 'Y'):
    """
    優化後的 Jacobian 矩陣分析 (數值鏈式微分版)。
    將運算複雜度從 SymPy 的指數級降低為 O(N^2)。
    """
    def _report(pct):
        if progress_cb: progress_cb(int(pct))

    tol_num = tol_data.tolnum
    all_sym = tol_data.all_sym
    all_value = tol_data.all_value
    tol_names = tol_data.tol_names
    n_tols = len(tol_names)

    if n_tols == 0:
        raise ValueError("路徑中沒有任何公差特徵，無法進行分析。")

    _report(5)

    # 1. 建立名義轉換矩陣序列 (Nominal matrices at s=0)
    # 我們需要計算 zyz=0 與 zyz=90 兩種情況
    I4 = np.eye(4)
    nominals_0 = []
    nominals_90 = []
    
    # 紀錄哪些節點是公差項 (以及它在 tol_names 中的索引)
    tol_node_indices = [] # stores (path_idx, tol_idx)

    tol_idx = 0
    for j in range(tol_num):
        s_code = all_sym[j]
        sl = s_code.lower()
        v = float(all_value[j])
        is_spatial = (all_sym[j] in {'traX', 'traY', 'traZ', 'rotX', 'rotY', 'rotZ'})

        # 計算名義矩陣 (使用 numpy 提升速度)
        # 對於公差項，s=0 代入
        if   s_code == 'traX': m0 = m90 = _get_translate_m(v, 0, 0)
        elif s_code == 'traY': m0 = m90 = _get_translate_m(0, v, 0)
        elif s_code == 'traZ': m0 = m90 = _get_translate_m(0, 0, v)
        elif s_code == 'rotX': m0 = m90 = _get_rotate_x(v)
        elif s_code == 'rotY': m0 = m90 = _get_rotate_y(v)
        elif s_code == 'rotZ': m0 = m90 = _get_rotate_z(v)
        # 公差項 (Nominal = Identity)
        else:
            m0 = m90 = I4.copy()
            tol_node_indices.append((j, tol_idx))
            tol_idx += 1
        
        nominals_0.append(m0)
        nominals_90.append(m90)

    _report(15)

    # 2. 預計算左側累加矩陣與右側累加矩陣
    # Left[j] = M[0] * ... * M[j-1]
    # Right[j] = M[j+1] * ... * M[n-1]
    left_0 = [I4.copy()]
    for m in nominals_0[:-1]:
        left_0.append(left_0[-1].dot(m))
    
    right_0 = [I4.copy()]
    for m in reversed(nominals_0[1:]):
        right_0.insert(0, m.dot(right_0[0]))

    _report(35)
    
    left_90 = [I4.copy()]
    for m in nominals_90[:-1]:
        left_90.append(left_90[-1].dot(m))

    right_90 = [I4.copy()]
    for m in reversed(nominals_90[1:]):
        right_90.insert(0, m.dot(right_90[0]))

    _report(50)

    # 3. 計算敏感度
    sX, sY, sZ, saX, saY, saZ = [], [], [], [], [], []
    
    for path_j, tol_j in tol_node_indices:
        s_code = all_sym[path_j]
        sl = s_code.lower()
        
        # 獲取該類型公差在 s=0 時的導數矩陣
        dm0  = _get_derivative_m(s_code, 0,  stacking_axis)
        dm90 = _get_derivative_m(s_code, 90, stacking_axis)
        
        # dM_total = Left * dM * Right
        res0  = left_0[path_j].dot(dm0).dot(right_0[path_j])
        res90 = left_90[path_j].dot(dm90).dot(right_90[path_j])
        
        # 提取敏感度 (對應原程式碼的矩陣索引)
        # X=[0,3], Y=[1,3], Z=[2,3], aX=[2,1], aY=[0,2], aZ=[1,0]
        def _extract(m):
            return [m[0,3], m[1,3], m[2,3], m[2,1], m[0,2], m[1,0]]
        
        v0  = _extract(res0)
        v90 = _extract(res90)
        
        # 保留絕對值較大者 (同原程式邏輯)
        final_v = []
        for v_idx in range(6):
            if abs(v0[v_idx]) >= abs(v90[v_idx]):
                final_v.append(v0[v_idx])
            else:
                final_v.append(v90[v_idx])
        
        sX.append(round(final_v[0], 10))
        sY.append(round(final_v[1], 10))
        sZ.append(round(final_v[2], 10))
        saX.append(round(final_v[3], 10))
        saY.append(round(final_v[4], 10))
        saZ.append(round(final_v[5], 10))
        
        # 平滑進度報告 (50-85%)
        pct = 50 + (35 * (tol_j + 1) / n_tols)
        _report(pct)

    # 4. 計算最終累積名義矩陣 (Tideal Matrix)
    # T_total = M[0] * M[1] * ... * M[n-1]
    t_total = left_0[-1].dot(nominals_0[-1])

    tol_data.sens_X, tol_data.sens_Y, tol_data.sens_Z = sX, sY, sZ
    tol_data.sens_aX, tol_data.sens_aY, tol_data.sens_aZ = saX, saY, saZ
    _report(85)

    return t_total.tolist()

# ──────────────────────────────────────────────────────────────────────────────
# Helper Functions (數值運算版)
# ──────────────────────────────────────────────────────────────────────────────

def _get_translate_m(x, y, z):
    return np.array([
        [1, 0, 0, x],
        [0, 1, 0, y],
        [0, 0, 1, z],
        [0, 0, 0, 1]
    ], dtype=float)

def _get_rotate_x(deg):
    rad = deg * pi / 180
    c, s = cos(rad), sin(rad)
    return np.array([[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]], dtype=float)

def _get_rotate_y(deg):
    rad = deg * pi / 180
    c, s = cos(rad), sin(rad)
    return np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]], dtype=float)

def _get_rotate_z(deg):
    rad = deg * pi / 180
    c, s = cos(rad), sin(rad)
    return np.array([[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]], dtype=float)

def _get_derivative_m(s_code, zyz, stacking_axis: str = 'Y'):
    """取得特定公差類型的導數矩陣 dM/ds (於 s=0 處)。
    stacking_axis: 'X'/'Y'/'Z' — dis/fla/sym 無軸後綴時的堆疊方向。
    """
    sl = s_code.lower()
    z_rad = zyz * pi / 180
    cz, sz = cos(z_rad), sin(z_rad)

    # 堆疊軸 → 矩陣列索引
    _stack_row = {'X': 0, 'Y': 1, 'Z': 2}.get(stacking_axis.upper(), 1)

    # 預設為零矩陣
    d = np.zeros((4, 4))

    # ── 直移類公差 (dM/dx = [0,0,0,1]) ──
    if   any(p in sl for p in ('disx', 'flax', 'symx')): d[0, 3] = 1.0
    elif any(p in sl for p in ('disy', 'flay', 'symy')): d[1, 3] = 1.0
    elif any(p in sl for p in ('disz', 'flaz', 'symz')): d[2, 3] = 1.0
    elif any(p in sl for p in ('dis',  'fla',  'sym' )): d[_stack_row, 3] = 1.0  # 使用者指定軸向
    
    # ── 角度類公差 (旋轉型) ──
    elif 'angx' in sl or 'perx' in sl or 'parx' in sl or 'crax' in sl:
        # Rx'(0) = [[0,0,0,0],[0,0,-1,0],[0,1,0,0],[0,0,0,0]]
        d[1, 2], d[2, 1] = -1.0, 1.0
    elif 'angy' in sl or 'pery' in sl or 'pary' in sl or 'cray' in sl:
        # Ry'(0) = [[0,0,1,0],[0,0,0,0],[-1,0,0,0],[0,0,0,0]]
        d[0, 2], d[2, 0] = 1.0, -1.0
    elif 'angz' in sl or 'perz' in sl or 'parz' in sl or 'craz' in sl:
        # Rz'(0) = [[0,-1,0,0],[1,0,0,0],[0,0,0,0],[0,0,0,0]]
        d[0, 1], d[1, 0] = -1.0, 1.0
    elif any(p in sl for p in ('ang', 'per', 'par', 'cra')):
        # 這些是 ZYZ 結構：M = Rz(c) * Ry(s) * Rz(-c)
        # dM/ds at s=0 is Rz(c) * Ry'(0) * Rz(-c)
        # Ry'(0) = [[0,0,1,0],[0,0,0,0],[-1,0,0,0],[0,0,0,0]]
        dm_y = np.array([[0,0,1,0],[0,0,0,0],[-1,0,0,0],[0,0,0,0]])
        mz = _get_rotate_z(zyz)
        mzi = _get_rotate_z(-zyz)
        d = mz.dot(dm_y).dot(mzi)
        
    # ── 特微類公差 (位置度/同心度等) ──
    # M = [[1, 0, 0, (s/2)*cos(c)], [0, 1, 0, (s/2)*sin(c)], [0, 0, 1, 0], [0, 0, 0, 1]]
    # dM/ds = [[0, 0, 0, 0.5*cos(c)], [0, 0, 0, 0.5*sin(c)], [0, 0, 0, 0], [0, 0, 0, 0]]
    elif any(p in sl for p in ('con', 'cir', 'cy', 'pos', 'str')):
        d[0, 3] = 0.5 * cz
        d[1, 3] = 0.5 * sz
        
    # ── 直徑/半徑公差 (dM/ds = [cos(c), sin(c), 0, 0]) ──
    elif any(p in sl for p in ('dia', 'rad', 'crd')):
        d[0, 3] = cz
        d[1, 3] = sz
        
    return d
