/**
 * step_controller.js - STEP 3D 查看器控制器
 *
 * 職責：
 *   - 處理 STEP / XLSX 上傳事件
 *   - 協調 StepApi（資料）與 StepView（渲染）
 *   - 維護目前 session_id 狀態
 *   - 驅動進度顯示
 *
 * 依賴：StepApi, StepView（需先載入）
 */

const StepController = (() => {
  let _sessionId = null;

  // ── 上傳 STEP ─────────────────────────────────────────────────────────────

  async function uploadStep(file) {
    if (!file) return;
    StepView.showProgress(0, `上傳 ${file.name}...`);

    try {
      const data = await StepApi.uploadStep(file);
      if (!data.ok) throw new Error(data.msg || data.error || '上傳失敗');

      _sessionId = data.session_id;
      window._stepSessionId = _sessionId;
      StepView.showProgress(30, 'STEP 上傳成功，等待 PMI 解析...');
      return _sessionId;
    } catch (e) {
      StepView.showError(`STEP 上傳失敗: ${e.message}`);
      throw e;
    }
  }

  // ── 上傳 XLSX ─────────────────────────────────────────────────────────────

  async function uploadXlsx(file) {
    if (!file || !_sessionId) return;
    try {
      const data = await StepApi.uploadXlsx(file, _sessionId);
      if (!data.ok) throw new Error(data.msg || '上傳 XLSX 失敗');
    } catch (e) {
      StepView.showError(`XLSX 上傳失敗: ${e.message}`);
      throw e;
    }
  }

  // ── 解析 PMI ──────────────────────────────────────────────────────────────

  async function parsePmi() {
    if (!_sessionId) {
      StepView.showError('請先上傳 STEP 檔案');
      return;
    }
    StepView.showProgress(50, '解析 PMI 標註中...');

    try {
      const data = await StepApi.parsePMI(_sessionId);
      if (!data.ok) throw new Error(data.msg || data.error || 'PMI 解析失敗');

      StepView.showProgress(80, '載入 3D 幾何...');
      await loadGeometry();
      StepView.showProgress(100, '完成');
      StepView.renderPmiList(data.pmi_rows || []);
    } catch (e) {
      StepView.showError(`PMI 解析失敗: ${e.message}`);
    }
  }

  // ── 載入幾何 ──────────────────────────────────────────────────────────────

  async function loadGeometry(faceId = '*') {
    if (!_sessionId) return;
    try {
      const data = await StepApi.getGeometry(_sessionId, faceId);
      if (data.ok) StepView.render3D(data);
    } catch (e) {
      StepView.showError(`幾何載入失敗: ${e.message}`);
    }
  }

  // ── 高亮 PMI ──────────────────────────────────────────────────────────────

  async function highlightPmi(pmiId) {
    if (!_sessionId) return;
    try {
      const data = await StepApi.highlightPmi(_sessionId, pmiId);
      if (data.ok && data.geometry) StepView.highlightFaces(data.geometry);
    } catch (e) {
      console.warn(`PMI 高亮失敗: ${e.message}`);
    }
  }

  // ── 組合件分析 ────────────────────────────────────────────────────────────

  async function runAsmAnalysis() {
    if (!_sessionId) return;
    StepView.showProgress(0, '組合件接觸分析中...');

    try {
      await StepApi.runAsmContact(_sessionId);
      StepView.showProgress(50, '等待分析結果...');

      const poll = setInterval(async () => {
        const res = await StepApi.getAsmResult(_sessionId);
        if (res.status === 'done') {
          clearInterval(poll);
          StepView.showProgress(100, '分析完成');
          StepView.renderAsmResult(res.result);
        } else if (res.status === 'error') {
          clearInterval(poll);
          StepView.showError(`分析失敗: ${res.error}`);
        }
      }, 2000);
    } catch (e) {
      StepView.showError(`組合件分析失敗: ${e.message}`);
    }
  }

  // ── 匯出 CSV ──────────────────────────────────────────────────────────────

  async function exportCsv(mode = 'pmi') {
    if (!_sessionId) return;
    try {
      const data = await StepApi.exportCsv(_sessionId, mode);
      if (data.ok) StepView.triggerDownload(data.csv, `export_${mode}.csv`);
    } catch (e) {
      StepView.showError(`匯出失敗: ${e.message}`);
    }
  }

  // ── Getter ────────────────────────────────────────────────────────────────

  function getSessionId() { return _sessionId; }

  return { uploadStep, uploadXlsx, parsePmi, loadGeometry, highlightPmi, runAsmAnalysis, exportCsv, getSessionId };
})();
