# -*- coding: utf-8 -*-
"""
analysis_service.py — Web 服務層，銜接前端 JSON 路徑與分析引擎。
負責：
  1. 將前端 editorPathData JSON 轉換為 ToleranceData 物件。
  2. 以 Thread + Queue 執行 Jacobian 分析，透過 SSE generator 推播進度。
"""
import json
import queue
import threading
import math
import copy
import numpy as np

from analysis_engine.jacobian   import compute_jacobian
from analysis_engine.statistics import compute_rss, compute_monte_carlo, compute_sensitivity_contribution

# 軸向與引擎結果 Key 的映射關係
axis_key_map = {
    'X': 'sens_X', 'Y': 'sens_Y', 'Z': 'sens_Z',
    'aX': 'sens_aX', 'aY': 'sens_aY', 'aZ': 'sens_aZ'
}


# ─── 角度類公差判斷（需除以 dist 轉換量綱，對應 ExcelData.py 行為）──────────────
_ANGULAR_PATTERNS = ('ang', 'per', 'par', 'cra')

def _is_angular(name: str) -> bool:
    nl = name.lower()
    return any(p in nl for p in _ANGULAR_PATTERNS)


# ─── 資料模型 ──────────────────────────────────────────────────────────────────

class ToleranceData:
    """
    從前端 pathData JSON 建立供 Jacobian 引擎使用的資料容器。

    前端格式：
      [{"type": "spatial", "axis": "traX", "val": 10.0, "bias": 0, "dist": 1, "nominal_size": 25.0, "it_grade": "IT7"},
       {"type": "feature", "name": "1-disX-1", "val": 0.02, "bias": 0, "dist": 1}]
    """

    def __init__(self, path_items: list):
        self.tolnum    = len(path_items)
        self.all_sym   = []
        self.all_value = []
        self.tol_names = []
        self.tol_values = []
        self.tol_dis    = []
        # [新增] 存儲原始元數據，用於更新與回傳
        self.nominal_sizes = []
        self.it_grades = []

        # 只有純空間平移/旋轉才算 spatial
        PURE_SPATIAL_AXES = {'traX', 'traY', 'traZ', 'rotX', 'rotY', 'rotZ'}

        for j, item in enumerate(path_items):
            raw_val = float(item.get('val', 0.0))
            self.all_value.append(raw_val)
            self.nominal_sizes.append(item.get('nominal_size'))
            self.it_grades.append(item.get('it_grade'))

            axis = item.get('axis', '')
            is_pure_spatial = (item.get('type') == 'spatial') and (axis in PURE_SPATIAL_AXES)

            if is_pure_spatial:
                self.all_sym.append(axis)
            else:
                # feature 項目
                name = item.get('name') or axis or f'feat_{j}'
                self.all_sym.append(name)
                self.tol_names.append(name)

                # D 欄：角度公差轉換距離，預設 1
                dist = float(item.get('dist') or 1.0)
                if dist == 0:
                    dist = 1.0
                self.tol_dis.append(dist)

                # 角度類公差值預除 dist
                if _is_angular(name):
                    eff_val = raw_val / dist
                else:
                    eff_val = raw_val
                self.tol_values.append(eff_val)

        # 分析結果（由引擎填入）
        self.sens_X  = []
        self.sens_Y  = []
        self.sens_Z  = []
        self.sens_aX = []
        self.sens_aY = []
        self.sens_aZ = []


from openpyxl import load_workbook
import io

def parse_excel_to_path(file_stream):
    """
    從 Excel 檔案流解析公差路徑。
    格式要求：A欄為代碼(Sym), B欄為值(Val), C欄為偏差(Bias), D欄為距離(Dist)。
    """
    try:
        wb = load_workbook(io.BytesIO(file_stream), data_only=True)
    except Exception as e:
        raise ValueError(f"無法讀取 Excel 檔案，請確認格式是否正確 (.xlsx)。內容解析錯誤: {str(e)}")

    # 嘗試尋找含有公差設定的分頁
    # 邏輯：優先檢查當前分頁，若失敗則檢查所有分頁，尋找 A2 或 A1 有資料的分頁
    target_sheet = None
    PURE_SPATIAL_AXES = {'traX', 'traY', 'traZ', 'rotX', 'rotY', 'rotZ'}
    
    # 常用關鍵字分頁優先
    for name in wb.sheetnames:
        if any(k in name.lower() for k in ('tolerance', 'path', '公差', '路徑')):
            target_sheet = wb[name]
            break
            
    if not target_sheet:
        target_sheet = wb.active

    def try_parse_sheet(sheet):
        items = []
        # 從第二行開始讀取 (跳過標題) 或直接從第一行開始 (視第一格內容而定)
        start_row = 1 if sheet['A1'].value and str(sheet['A1'].value).strip() in PURE_SPATIAL_AXES else 2
        
        for row_idx in range(start_row, min(sheet.max_row, 1000) + 1): # 限制 1000 行
            try:
                sym_val = sheet.cell(row=row_idx, column=1).value
                if sym_val is None: 
                    if row_idx > start_row + 2: break # 連續空行則停止
                    continue
                
                sym_str = str(sym_val).strip()
                if not sym_str: continue

                val = float(sheet.cell(row=row_idx, column=2).value or 0.0)
                bias = float(sheet.cell(row=row_idx, column=3).value or 0.0)
                dist = float(sheet.cell(row=row_idx, column=4).value or 1.0)
                if dist == 0: dist = 1.0

                # [新增] 讀取公稱尺寸與 IT 等級
                nominal  = sheet.cell(row=row_idx, column=5).value
                it_grade = sheet.cell(row=row_idx, column=6).value
                
                is_spatial = (sym_str in PURE_SPATIAL_AXES)
                item = {
                    "type": "spatial" if is_spatial else "feature",
                    "val": val, "bias": bias, "dist": dist,
                    "nominal_size": nominal, "it_grade": it_grade
                }
                if is_spatial: item["axis"] = sym_str
                else: item["name"] = sym_str
                items.append(item)
            except (ValueError, TypeError):
                continue
        return items

    path_items = try_parse_sheet(target_sheet)
    
    # 如果選定的分頁沒掃到東西，則掃描所有分頁
    if not path_items:
        for name in wb.sheetnames:
            if wb[name] == target_sheet: continue
            path_items = try_parse_sheet(wb[name])
            if path_items: break

    if not path_items:
        raise ValueError("在 Excel 中找不到有效的公差路徑配置。請確認檔案內容是否符合格式（A欄：代碼，B欄：公差值，C欄：偏差，D欄：角度轉換距離）。")
        
    return path_items


# ─── SSE 串流分析 ──────────────────────────────────────────────────────────────

def analyze_stream(path_data: list, run_mc: bool = True, mc_samples: int = 10000, mc_sigma: float = 3.0, mc_dist: int = 0):
    """
    Generator，以 SSE 格式 yield 進度與結果。

    Usage in Flask:
        return Response(analyze_stream(path_data), mimetype='text/event-stream')

    SSE 事件格式：
        data: {"progress": 45}           — 進度百分比 (0~100)
        data: {"result": {...}}           — 最終分析結果
        data: {"error": "msg"}            — 錯誤訊息
    """
    progress_q = queue.Queue()
    result_box = [None]
    error_box  = [None]

    def _worker():
        try:
            tol_data = ToleranceData(path_data)

            if len(tol_data.tol_names) == 0:
                error_box[0] = "路徑中沒有任何公差特徵（feature），無法進行分析。"
                return

            def _cb(pct):
                progress_q.put(pct)

            t_ideal = compute_jacobian(tol_data, progress_cb=_cb)
            progress_q.put(88)

            rss = compute_rss(tol_data)
            progress_q.put(93)

            mc = compute_monte_carlo(tol_data, n_samples=mc_samples, sigma=mc_sigma, dist_type=mc_dist) if run_mc else {}
            progress_q.put(98)

            sc = compute_sensitivity_contribution(tol_data)
            progress_q.put(99)

            result_box[0] = {
                "tol_names":  tol_data.tol_names,
                "tol_values": tol_data.tol_values,
                "t_ideal_matrix": t_ideal,
                "sens_X":  tol_data.sens_X,
                "sens_Y":  tol_data.sens_Y,
                "sens_Z":  tol_data.sens_Z,
                "sens_aX": tol_data.sens_aX,
                "sens_aY": tol_data.sens_aY,
                "sens_aZ": tol_data.sens_aZ,
                **rss,
                **mc,
                **sc,   # sensitivity / angle_sensitivity / contribution / angle_contribution
            }

        except Exception as e:
            import traceback
            error_box[0] = f"{e}\n{traceback.format_exc()}"
        finally:
            progress_q.put(None)  # sentinel

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    while True:
        item = progress_q.get()
        if item is None:
            break
        yield f"data: {json.dumps({'progress': item})}\n\n"

    if error_box[0]:
        yield f"data: {json.dumps({'error': error_box[0]})}\n\n"
    elif result_box[0]:
        yield f"data: {json.dumps({'result': result_box[0]})}\n\n"
    else:
        yield f"data: {json.dumps({'error': '分析完成但無結果，請檢查後端日誌。'})}\n\n"


def analyze_tolerance_path(path_data: list, mc_samples: int = 10000, mc_sigma: float = 3.0, mc_dist: int = 0):
    """
    同步執行完整公差分析 (Jacobian + RSS + MC + SCA)。
    供 ai_app.py 在調配計算後進行優化結果核實。
    """
    tol_data = ToleranceData(path_data)
    if len(tol_data.tol_names) == 0:
        raise ValueError("路徑中沒有任何公差特徵，無法進行分析。")

    t_ideal = compute_jacobian(tol_data)
    rss = compute_rss(tol_data)
    mc = compute_monte_carlo(tol_data, n_samples=mc_samples, sigma=mc_sigma, dist_type=mc_dist)
    sc = compute_sensitivity_contribution(tol_data)

    return {
        "tol_names":  tol_data.tol_names,
        "tol_values": tol_data.tol_values,
        "t_ideal_matrix": t_ideal,
        "sens_X":  tol_data.sens_X,
        "sens_Y":  tol_data.sens_Y,
        "sens_Z":  tol_data.sens_Z,
        "sens_aX": tol_data.sens_aX,
        "sens_aY": tol_data.sens_aY,
        "sens_aZ": tol_data.sens_aZ,
        **rss,
        **mc,
        **sc
    }



# ─── 公差調配 ──────────────────────────────────────────────────────────────────


def get_quadrant_analysis(analysis_result: dict, tol_names: list, axis: str = 'Z'):
    """計算指定軸向的四象限分析結果 (Q1-Q4)"""
    n = len(tol_names)
    sk = axis_key_map.get(axis, 'sens_Z')
    ck = axis_key_map.get(axis, 'sens_Z').replace('sens', 'ctb')
    
    sens = np.array(analysis_result.get(sk, [0]*n))
    ctb  = np.array(analysis_result.get(ck, [0]*n))
    
    # 標準差與貢獻百分比中位數
    s_mid = np.median(np.abs(sens))
    total_ctb = np.sum(np.abs(ctb))
    c_ratio = (np.abs(ctb) / total_ctb * 100) if total_ctb > 0 else np.zeros(n)
    c_mid = np.median(c_ratio)
    
    quadrants = {}
    for i in range(n):
        si, ci_p = abs(sens[i]), c_ratio[i]
        if si > s_mid and ci_p > c_mid: q = 1
        elif si > s_mid: q = 2
        elif ci_p > c_mid: q = 3
        else: q = 4
        quadrants[tol_names[i]] = q
    return quadrants, c_ratio

def compute_allocation(path_data: list, analysis_result: dict, target: float = 0.05, strategy: str = 'medium', axis: str = 'Z') -> dict:
    """
    自動調配核心邏輯 (原本的 Manual Allocation)
    """
    # 提取特徵名稱與原始值
    names = [item['name'] for item in path_data if item.get('type') == 'feature']
    old_values = np.array([item['val'] for item in path_data if item.get('type') == 'feature'])
    n = len(names)
    
    if n == 0:
        return {"newPathData": path_data, "report": {}}

    sk = axis_key_map.get(axis, 'sens_Z')
    sens = np.array(analysis_result.get(sk, [0]*n))
    
    # 獲取象限與貢獻比 (使用 Helper)
    q_map, cont_ratio_pct = get_quadrant_analysis(analysis_result, names, axis)
    cont_ratio = cont_ratio_pct / 100.0
    
    # 2. 策略權重分配 (w_i)
    w_i = []
    quadrants = []
    for i, name in enumerate(names):
        q = q_map[name]
        quadrants.append(q)
        if strategy == 'precision':
            # 精度優先：針對貢獻度高的項進行更激進的權重係數
            wi = 1.0 - (cont_ratio[i] * 0.8)
        else:
            # 成本優先：針對低敏感 (Q4) 的項放寬
            if q == 4: wi = 1.25
            else: wi = 1.0 - (cont_ratio[i] * 0.5)
        w_i.append(wi)

    # 3. 求解全域因子 β
    t_base = old_values * np.array(w_i)
    weighted_sum_sq = np.sum((sens * t_base)**2)
    
    if weighted_sum_sq < 1e-18:
        return {"newPathData": path_data, "report": {}}
        
    beta = target / math.sqrt(weighted_sum_sq)
    new_values = t_base * beta
    
    # 4. 更新數據與產出報告
    name_to_val = {names[i]: (round(new_values[i], 6), quadrants[i]) for i in range(n)}
    updated = copy.deepcopy(path_data)
    for item in updated:
        if item.get('type') == 'feature':
            name = item.get('name', '')
            if name in name_to_val:
                val, q = name_to_val[name]
                item['val'] = val
                item['quadrant'] = q # 存入象限資訊供前端顯示

    # 預測報告
    report = {}
    axes_list = ['X', 'Y', 'Z', 'aX', 'aY', 'aZ']
    for ax in axes_list:
        sk_ax = axis_key_map.get(ax)
        sl = analysis_result.get(sk_ax, [])
        if not sl or len(sl) != n: continue
        
        pred_rss = math.sqrt(np.sum((np.array(sl) * new_values)**2))
        curr_rss = analysis_result.get(f'rss_{ax}', 0) or 0
        
        def _pct(before, after):
            if before < 1e-12: return 0.0
            return round((before - after) / before * 100, 2)

        report[ax] = {
            'rss_before': round(curr_rss, 6),
            'rss_after':  round(pred_rss, 6),
            'rss_improve_pct': _pct(curr_rss, pred_rss)
        }
    
    report['quadrants'] = q_map
    return {"newPathData": updated, "report": report}


def compare_allocation(baseline: dict, current: dict) -> dict:
    """
    手動調配比對：計算各軸 RSS 與 Worst Case 的改善百分比。
    對應單機版 IntervalAnalysis.py 的 analysis==2 邏輯。

    Returns:
      dict of {axis: {rss_before, rss_after, rss_improve_pct,
                      wc_before, wc_after, wc_improve_pct}}
    """
    axes = ['X', 'Y', 'Z', 'aX', 'aY', 'aZ']
    result = {}
    for ax in axes:
        rss_b = baseline.get(f'rss_{ax}', 0) or 0
        rss_a = current.get(f'rss_{ax}', 0)  or 0
        wc_b  = baseline.get(f'wc_{ax}', 0)  or 0
        wc_a  = current.get(f'wc_{ax}', 0)   or 0

        def _pct(before, after):
            if before == 0:
                return 0.0
            return round((before - after) / before * 100, 2)

        result[ax] = {
            'rss_before':      round(rss_b, 6),
            'rss_after':       round(rss_a, 6),
            'rss_improve_pct': _pct(rss_b, rss_a),
            'wc_before':       round(wc_b, 6),
            'wc_after':        round(wc_a, 6),
            'wc_improve_pct':  _pct(wc_b, wc_a),
        }
    return result
