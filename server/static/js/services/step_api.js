/**
 * step_api.js - STEP / PMI 3D 解析 API Service
 *
 * 封裝所有 STEP 上傳、PMI 解析、幾何取得、組合件分析的後端呼叫。
 */

const StepApi = (() => {

  /** 上傳 STEP 檔案（multipart），回傳 { ok, session_id } */
  async function uploadStep(file) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch('/api/step/upload', { method: 'POST', body: formData });
    if (!response.ok) throw new Error(`上傳失敗: HTTP ${response.status}`);
    return response.json();
  }

  /** 上傳 XLSX 標註檔案 */
  async function uploadXlsx(file, session_id) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('session_id', session_id);
    const response = await fetch('/api/step/upload_xlsx', { method: 'POST', body: formData });
    if (!response.ok) throw new Error(`上傳 XLSX 失敗: HTTP ${response.status}`);
    return response.json();
  }

  /** 解析 PMI 標註 */
  function parsePMI(session_id) {
    return ApiClient.post('/api/step/parse_pmi', { session_id });
  }

  /** 取得幾何資料（face_id 可為 '*' 取全部） */
  function getGeometry(session_id, face_id = '*') {
    return ApiClient.get(`/api/step/geometry?session_id=${session_id}&face_id=${face_id}`);
  }

  /** 取得 PMI 標註列表 */
  function getPmiList(session_id) {
    return ApiClient.get(`/api/step/pmi_list?session_id=${session_id}`);
  }

  /** 高亮指定 PMI */
  function highlightPmi(session_id, pmi_id) {
    return ApiClient.post('/api/step/highlight', { session_id, pmi_id });
  }

  /** 取得所有 PMI 幾何 */
  function getAllPmiGeometry(session_id) {
    return ApiClient.post('/api/step/pmi_all_geometry', { session_id });
  }

  /** 執行組合件接觸分析 */
  function runAsmContact(session_id) {
    return ApiClient.post('/api/step/asm_contact', { session_id });
  }

  /** 取得組合件分析結果 */
  function getAsmResult(session_id) {
    return ApiClient.get(`/api/step/asm_result?session_id=${session_id}`);
  }

  /** 取得 6DOF 路徑 */
  function get6Dof(session_id) {
    return ApiClient.post('/api/step/6dof', { session_id });
  }

  /** 匯出 PMI CSV */
  function exportCsv(session_id, mode = 'pmi') {
    return ApiClient.post('/api/step/export_csv', { session_id, mode });
  }

  /** 取得進度狀態 */
  function getProgressStatus(session_id) {
    return ApiClient.get(`/api/step/progress_status?session_id=${session_id}`);
  }

  /** 建立進度 SSE 串流（回傳 EventSource） */
  function createProgressStream(session_id) {
    return new EventSource(`/api/step/progress?session_id=${session_id}`);
  }

  /** 取得面-零件對應表 */
  function getFaceToPart(session_id) {
    return ApiClient.get(`/api/step/face_to_part?session_id=${session_id}`);
  }

  return {
    uploadStep, uploadXlsx, parsePMI, getGeometry, getPmiList,
    highlightPmi, getAllPmiGeometry, runAsmContact, getAsmResult,
    get6Dof, exportCsv, getProgressStatus, createProgressStream, getFaceToPart,
  };
})();
