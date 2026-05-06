# -*- coding: utf-8 -*-
"""
公差統計分析：RSS (Root Sum of Squares) 與 Worst Case。
移植自 單機版/ToleranceAnalysis/StatisticsAnalysis.py 的核心數學邏輯。
已移除 Excel / Matplotlib GUI 依賴。
"""
import math
import numpy as np

RAD_TO_ARCSEC = (180.0 / math.pi) * 3600.0   # 206264.8 — 對應單機版 * (180/pi) * 3600


def compute_rss(tol_data):
    """
    計算 RSS 與 Worst Case 公差累積量。

    Returns:
        dict with keys:
          rss_X, rss_Y, rss_Z, rss_aX, rss_aY, rss_aZ  (float)
          wc_X,  wc_Y,  wc_Z,  wc_aX,  wc_aY,  wc_aZ   (float)
          contributions: list of {name, val, sX, sY, sZ, sAx, sAy, sAz,
                                   cX, cY, cZ, caX, caY, caZ}
    """
    names  = tol_data.tol_names
    values = tol_data.tol_values
    sX  = tol_data.sens_X
    sY  = tol_data.sens_Y
    sZ  = tol_data.sens_Z
    saX = tol_data.sens_aX
    saY = tol_data.sens_aY
    saZ = tol_data.sens_aZ

    n = len(names)
    contribs = []
    sum_rss_X = sum_rss_Y = sum_rss_Z = 0.0
    sum_rss_aX = sum_rss_aY = sum_rss_aZ = 0.0
    sum_wc_X = sum_wc_Y = sum_wc_Z = 0.0
    sum_wc_aX = sum_wc_aY = sum_wc_aZ = 0.0

    for i in range(n):
        t = values[i]
        cX  = sX[i]  * t
        cY  = sY[i]  * t
        cZ  = sZ[i]  * t
        caX = saX[i] * t
        caY = saY[i] * t
        caZ = saZ[i] * t

        sum_rss_X  += cX  ** 2;  sum_wc_X  += abs(cX)
        sum_rss_Y  += cY  ** 2;  sum_wc_Y  += abs(cY)
        sum_rss_Z  += cZ  ** 2;  sum_wc_Z  += abs(cZ)
        sum_rss_aX += caX ** 2;  sum_wc_aX += abs(caX)
        sum_rss_aY += caY ** 2;  sum_wc_aY += abs(caY)
        sum_rss_aZ += caZ ** 2;  sum_wc_aZ += abs(caZ)

        contribs.append({
            "name": names[i], "val": t,
            "sX": round(sX[i], 6),  "sY": round(sY[i], 6),  "sZ": round(sZ[i], 6),
            "saX": round(saX[i], 6), "saY": round(saY[i], 6), "saZ": round(saZ[i], 6),
            "cX": round(cX, 8),  "cY": round(cY, 8),  "cZ": round(cZ, 8),
            "caX": round(caX, 8), "caY": round(caY, 8), "caZ": round(caZ, 8),
        })

    def _sqrt(v): return round(math.sqrt(v), 8)

    return {
        "rss_X":  _sqrt(sum_rss_X),  "rss_Y":  _sqrt(sum_rss_Y),  "rss_Z":  _sqrt(sum_rss_Z),
        # 角度結果轉換為 arc_second（對應單機版 * (180/pi) * 3600）
        "rss_aX": round(_sqrt(sum_rss_aX) * RAD_TO_ARCSEC, 8),
        "rss_aY": round(_sqrt(sum_rss_aY) * RAD_TO_ARCSEC, 8),
        "rss_aZ": round(_sqrt(sum_rss_aZ) * RAD_TO_ARCSEC, 8),
        "wc_X":  round(sum_wc_X, 8),  "wc_Y":  round(sum_wc_Y, 8),  "wc_Z":  round(sum_wc_Z, 8),
        "wc_aX": round(sum_wc_aX * RAD_TO_ARCSEC, 8),
        "wc_aY": round(sum_wc_aY * RAD_TO_ARCSEC, 8),
        "wc_aZ": round(sum_wc_aZ * RAD_TO_ARCSEC, 8),
        "contributions": contribs,
    }


def compute_sensitivity_contribution(tol_data):
    """
    計算敏感度（%）與貢獻度（%）排序，移植自 SensitivityContributionAnalysis.py。
    角度類公差敏感度除以 tol_dis[i] 轉換為線性量綱。

    Returns:
        dict with keys:
          sensitivity        : list of {rank, name, x, y, z}  — 直移敏感度排序
          angle_sensitivity  : list of {rank, name, x, y, z}  — 角度敏感度排序
          contribution       : list of {rank, name, x, y, z}  — 直移貢獻度排序
          angle_contribution : list of {rank, name, x, y, z}  — 角度貢獻度排序
    """
    names   = tol_data.tol_names
    values  = tol_data.tol_values
    tol_dis = getattr(tol_data, 'tol_dis', [1.0] * len(names))
    n = len(names)

    # ── 敏感度（除以 tol_dis 轉換量綱，取絕對值）────────────────────────────
    def _safe_div(a, b):
        return a / b if b else 0.0

    sX  = [abs(_safe_div(tol_data.sens_X[i],  tol_dis[i])) for i in range(n)]
    sY  = [abs(_safe_div(tol_data.sens_Y[i],  tol_dis[i])) for i in range(n)]
    sZ  = [abs(_safe_div(tol_data.sens_Z[i],  tol_dis[i])) for i in range(n)]
    saX = [abs(_safe_div(tol_data.sens_aX[i], tol_dis[i])) for i in range(n)]
    saY = [abs(_safe_div(tol_data.sens_aY[i], tol_dis[i])) for i in range(n)]
    saZ = [abs(_safe_div(tol_data.sens_aZ[i], tol_dis[i])) for i in range(n)]

    def _to_pct(lst):
        total = sum(lst)
        if total == 0:
            return [0.0] * len(lst)
        return [round(v / total * 100, 4) for v in lst]

    sensXp  = _to_pct(sX);  sensYp  = _to_pct(sY);  sensZp  = _to_pct(sZ)
    sensAXp = _to_pct(saX); sensAYp = _to_pct(saY); sensAZp = _to_pct(saZ)

    total_sens  = [math.sqrt((sensXp[i]**2  + sensYp[i]**2  + sensZp[i]**2)  / 3) for i in range(n)]
    total_Asens = [math.sqrt((sensAXp[i]**2 + sensAYp[i]**2 + sensAZp[i]**2) / 3) for i in range(n)]
    sens_sequence  = sorted(range(n), key=lambda k: total_sens[k],  reverse=True)
    Asens_sequence = sorted(range(n), key=lambda k: total_Asens[k], reverse=True)

    # ── 貢獻度（raw sens × tol_value，tol_value 對角度類已預除 dist）─────────
    ctb_x  = [abs(tol_data.sens_X[i])  * values[i] for i in range(n)]
    ctb_y  = [abs(tol_data.sens_Y[i])  * values[i] for i in range(n)]
    ctb_z  = [abs(tol_data.sens_Z[i])  * values[i] for i in range(n)]
    ctb_ax = [abs(tol_data.sens_aX[i]) * values[i] for i in range(n)]
    ctb_ay = [abs(tol_data.sens_aY[i]) * values[i] for i in range(n)]
    ctb_az = [abs(tol_data.sens_aZ[i]) * values[i] for i in range(n)]

    ctb_xp  = _to_pct(ctb_x);  ctb_yp  = _to_pct(ctb_y);  ctb_zp  = _to_pct(ctb_z)
    ctb_axp = _to_pct(ctb_ax); ctb_ayp = _to_pct(ctb_ay); ctb_azp = _to_pct(ctb_az)

    total_ctb  = [math.sqrt((ctb_xp[i]**2  + ctb_yp[i]**2  + ctb_zp[i]**2)  / 3) for i in range(n)]
    total_Actb = [math.sqrt((ctb_axp[i]**2 + ctb_ayp[i]**2 + ctb_azp[i]**2) / 3) for i in range(n)]
    ctb_sequence  = sorted(range(n), key=lambda k: total_ctb[k],  reverse=True)
    Actb_sequence = sorted(range(n), key=lambda k: total_Actb[k], reverse=True)

    def _ranked(seq, xp, yp, zp):
        return [{"rank": k + 1, "name": names[i], "x": xp[i], "y": yp[i], "z": zp[i]}
                for k, i in enumerate(seq)]

    return {
        "sensitivity":        _ranked(sens_sequence,  sensXp,  sensYp,  sensZp),
        "angle_sensitivity":  _ranked(Asens_sequence, sensAXp, sensAYp, sensAZp),
        "contribution":       _ranked(ctb_sequence,   ctb_xp,  ctb_yp,  ctb_zp),
        "angle_contribution": _ranked(Actb_sequence,  ctb_axp, ctb_ayp, ctb_azp),
    }


def _run_mc_core(n_samples, values, sX, sY, sZ, saX, saY, saZ,
                 biases=None, dist_type=0, sigma=3.0):
    """
    向量化蒙地卡羅核心 (已移除 Numba 依賴)。
    使用 NumPy 矩陣運算替代 JIT 迴圈，效能與 JIT 相當且更具移植性。

    biases: C 欄偏差值陣列（與 values 等長）。
            距離公差不對稱帶時非零；幾何公差應為 0。
            對應原始 ToleranceModel.py StatisticsModel 的 `d` 參數。
    """
    n_features = len(values)
    b = np.zeros(n_features) if biases is None else np.asarray(biases, dtype=np.float64)

    # 產生隨機變量矩陣 (n_samples, n_features)
    # 分布中心 = bias (b)，半寬 = val/2
    if dist_type == 0:
        # 均勻分布：[bias - val/2, bias + val/2]
        rand = np.random.random((n_samples, n_features)) - 0.5   # [-0.5, 0.5)
        deltas = rand * values + b                                 # 以 bias 為中心
    else:
        # 常態分布：mean=bias, std=(val/2)/sigma
        std_devs = (values / 2.0) / sigma
        deltas = np.random.normal(b, std_devs, size=(n_samples, n_features))

    # 建立敏感度矩陣 (n_features, 6)
    sens_matrix = np.column_stack((sX, sY, sZ, saX, saY, saZ))
    
    # 使用矩陣乘法一次算出所有結果 (n_samples, n_features) @ (n_features, 6) -> (n_samples, 6)
    results = deltas @ sens_matrix
    
    return results

def compute_monte_carlo(tol_data, n_samples=10000, sigma=3.0, dist_type=0):
    """
    Monte Carlo 模擬 (Numba JIT 加速版本)。
    - sigma: 2, 3, 4 (預設 3)
    - dist_type: 0 (均勻), 1 (常態)
    """
    # 1. 數據準備
    values  = np.array(tol_data.tol_values, dtype=np.float64)
    biases  = np.array(getattr(tol_data, 'tol_biases', [0.0]*len(tol_data.tol_values)), dtype=np.float64)
    sX  = np.array(tol_data.sens_X,  dtype=np.float64)
    sY  = np.array(tol_data.sens_Y,  dtype=np.float64)
    sZ  = np.array(tol_data.sens_Z,  dtype=np.float64)
    saX = np.array(tol_data.sens_aX, dtype=np.float64)
    saY = np.array(tol_data.sens_aY, dtype=np.float64)
    saZ = np.array(tol_data.sens_aZ, dtype=np.float64)

    # 2. 執行核心運算（傳入 biases）
    res_matrix = _run_mc_core(n_samples, values, sX, sY, sZ, saX, saY, saZ,
                              biases=biases, dist_type=dist_type, sigma=float(sigma))

    # 3. 角度欄位（cols 3,4,5）轉換為 arc_second（對應單機版 * (180/pi) * 3600）
    res_matrix[:, 3] *= RAD_TO_ARCSEC
    res_matrix[:, 4] *= RAD_TO_ARCSEC
    res_matrix[:, 5] *= RAD_TO_ARCSEC

    # 4. 統計計算
    def _get_stats(arr):
        std  = np.std(arr)
        max_abs = np.max(np.abs(arr))
        return round(std, 8), round(max_abs, 8)

    # 從結果矩陣中提取各維度數據
    xstd, xmax   = _get_stats(res_matrix[:, 0])
    ystd, ymax   = _get_stats(res_matrix[:, 1])
    zstd, zmax   = _get_stats(res_matrix[:, 2])
    axstd, axmax = _get_stats(res_matrix[:, 3])   # 已為 arc_second
    aystd, aymax = _get_stats(res_matrix[:, 4])
    azstd, azmax = _get_stats(res_matrix[:, 5])

    return {
        "mc_X_std": xstd,   "mc_Y_std": ystd,   "mc_Z_std": zstd,
        "mc_aX_std": axstd, "mc_aY_std": aystd, "mc_aZ_std": azstd,
        "mc_X_max": xmax,   "mc_Y_max": ymax,   "mc_Z_max": zmax,
        "mc_aX_max": axmax, "mc_aY_max": aymax, "mc_aZ_max": azmax,
        "mc_raw": res_matrix.tolist()  # cols 0-2 mm, cols 3-5 arc_second
    }
