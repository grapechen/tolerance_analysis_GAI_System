/**
 * tolerance_api.js - ISO 286 公差查詢 API Service
 *
 * 封裝所有與公差相關的後端呼叫。
 * View / Controller 不應直接使用 fetch，應透過此模組。
 */

const ToleranceApi = (() => {

  /** 查詢 ISO 公差 */
  function lookupISO(size_mm, it_grade) {
    return ApiClient.post('/api/lookup/tolerance', { size_mm, it_grade });
  }

  /** 查詢軸公差 */
  function lookupShaft(size_mm, tolerance_code, it_grade) {
    return ApiClient.post('/api/lookup/shaft', { size_mm, tolerance_code, it_grade });
  }

  /** 查詢孔公差 */
  function lookupHole(size_mm, tolerance_code, it_grade) {
    return ApiClient.post('/api/lookup/hole', { size_mm, tolerance_code, it_grade });
  }

  /** 配合分析（孔基制 / 軸基制） */
  function analyzeFit(size_mm, hole_tolerance, shaft_tolerance) {
    return ApiClient.post('/api/analyze/fit', { size_mm, hole_tolerance, shaft_tolerance });
  }

  /** 推薦 IT 等級 */
  function recommendIT(size_mm, target_tol_um, options = {}) {
    return ApiClient.post('/recommend/it', {
      size_mm,
      'target_tol_μm': target_tol_um,
      ...options,
    });
  }

  /** 智能選配 */
  function smartFit(keywords) {
    return ApiClient.post('/api/recommend/smart_fit', { keywords });
  }

  /** 機台能力驗證 */
  function machineCheck(diameter, safety_factor = 3.0) {
    return ApiClient.post('/api/recommend/machine_check', { diameter, safety_factor });
  }

  /** 取得所有關鍵字 */
  function getKeywords() {
    return ApiClient.get('/api/keywords');
  }

  /** 取得機台資料 */
  function getMachines() {
    return ApiClient.get('/api/machines');
  }

  return { lookupISO, lookupShaft, lookupHole, analyzeFit, recommendIT, smartFit, machineCheck, getKeywords, getMachines };
})();
