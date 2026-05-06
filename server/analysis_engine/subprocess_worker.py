# -*- coding: utf-8 -*-
"""
subprocess_worker.py — 公差分析子程序

在獨立 Python 進程中執行 Jacobian + RSS + MC + SCA，
避免 PythonOCC 載入的 MKL DLL 與 numpy 的 MKL DLL 版本衝突
（Windows fatal exception: code 0xc06d007f PROCEDURE_NOT_FOUND）。

用法：從 analysis_service.py 透過 subprocess.Popen 呼叫，
      stdin 送入 JSON，stdout 逐行輸出 JSON 進度/結果。
"""

import sys
import os
import json

# 強制單執行緒，必須在任何 numpy import 之前
for _k in ('MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS',
           'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
    os.environ[_k] = '1'

# 允許多份 MKL/OpenMP DLL 並存（解決 conda 環境中 PythonOCC + numpy MKL 衝突導致 0xC0000005 崩潰）
os.environ.setdefault('KMP_DUPLICATE_LIB_OK', 'TRUE')
os.environ.setdefault('MKL_THREADING_LAYER', 'sequential')
# 禁用 MKL 動態記憶體配置，減少與其他 DLL 的衝突
os.environ.setdefault('MKL_DISABLE_FAST_MM', '1')

# 將 server/ 加入 path，使 analysis_service 可被 import
_HERE = os.path.dirname(os.path.abspath(__file__))
_SERVER_DIR = os.path.dirname(_HERE)
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)


def _emit(payload: dict):
    print(json.dumps(payload, default=str), flush=True)


def main():
    try:
        data = json.loads(sys.stdin.read())
    except Exception as e:
        _emit({'error': f'stdin JSON 解析失敗: {e}'})
        sys.exit(1)

    path_data  = data.get('path_data', [])
    mc_samples = int(data.get('mc_samples', 10000))
    mc_sigma   = float(data.get('mc_sigma', 3.0))
    mc_dist    = int(data.get('mc_dist', 0))
    run_mc     = bool(data.get('run_mc', True))
    mc_raw_cap = int(data.get('mc_raw_cap', 2000))

    try:
        from analysis_service import ToleranceData
        from analysis_engine.jacobian import compute_jacobian
        from analysis_engine.statistics import (
            compute_rss, compute_monte_carlo, compute_sensitivity_contribution
        )
    except Exception as e:
        import traceback
        _emit({'error': f'模組載入失敗: {e}\n{traceback.format_exc()}'})
        sys.exit(1)

    try:
        tol_data = ToleranceData(path_data)
    except Exception as e:
        import traceback
        _emit({'error': f'ToleranceData 建立失敗: {e}\n{traceback.format_exc()}'})
        sys.exit(1)

    if len(tol_data.tol_names) == 0:
        _emit({'error': '路徑中沒有任何公差特徵（feature），無法進行分析。'})
        sys.exit(0)

    _emit({'progress': 5})

    try:
        t_ideal = compute_jacobian(tol_data)
    except Exception as e:
        import traceback
        _emit({'error': f'compute_jacobian 失敗: {e}\n{traceback.format_exc()}'})
        sys.exit(1)
    _emit({'progress': 60})

    try:
        rss = compute_rss(tol_data)
    except Exception as e:
        import traceback
        _emit({'error': f'compute_rss 失敗: {e}\n{traceback.format_exc()}'})
        sys.exit(1)
    _emit({'progress': 75})

    mc = {}
    if run_mc:
        try:
            mc = compute_monte_carlo(tol_data, n_samples=mc_samples,
                                     sigma=mc_sigma, dist_type=mc_dist)
            if 'mc_raw' in mc and len(mc['mc_raw']) > mc_raw_cap:
                mc['mc_raw'] = mc['mc_raw'][:mc_raw_cap]
                mc['mc_raw_truncated_from'] = mc_samples
        except Exception as e:
            import traceback
            _emit({'error': f'compute_monte_carlo 失敗: {e}\n{traceback.format_exc()}'})
            sys.exit(1)
    _emit({'progress': 90})

    try:
        sc = compute_sensitivity_contribution(tol_data)
    except Exception as e:
        import traceback
        _emit({'error': f'compute_sensitivity_contribution 失敗: {e}\n{traceback.format_exc()}'})
        sys.exit(1)
    _emit({'progress': 99})

    result = {
        'tol_names':      tol_data.tol_names,
        'tol_values':     tol_data.tol_values,
        't_ideal_matrix': t_ideal,
        'sens_X':  tol_data.sens_X,
        'sens_Y':  tol_data.sens_Y,
        'sens_Z':  tol_data.sens_Z,
        'sens_aX': tol_data.sens_aX,
        'sens_aY': tol_data.sens_aY,
        'sens_aZ': tol_data.sens_aZ,
        **rss,
        **mc,
        **sc,
    }
    _emit({'result': result})


if __name__ == '__main__':
    main()
