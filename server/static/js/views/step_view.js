/**
 * step_view.js - STEP 3D 查看器 View
 *
 * 職責：
 *   - 更新進度條與狀態訊息
 *   - 觸發 3D 渲染（委派給已有的 ThreeJS / OCC 繪製邏輯）
 *   - 渲染 PMI 列表到面板
 *   - 渲染組合件分析結果
 *   - 觸發檔案下載
 *
 * 不含業務邏輯或 API 呼叫。
 */

const StepView = (() => {
  let _progressBar = null;
  let _statusText  = null;
  let _pmiListEl   = null;
  let _asmResultEl = null;

  // ── 初始化 ────────────────────────────────────────────────────────────────

  function init({ progressBarEl, statusTextEl, pmiListEl, asmResultEl }) {
    _progressBar = progressBarEl;
    _statusText  = statusTextEl;
    _pmiListEl   = pmiListEl;
    _asmResultEl = asmResultEl;
  }

  // ── 進度 ──────────────────────────────────────────────────────────────────

  function showProgress(pct, message = '') {
    if (_progressBar) _progressBar.style.width = `${pct}%`;
    if (_statusText)  _statusText.textContent  = message;
  }

  function showError(message) {
    if (_statusText) {
      _statusText.textContent = `❌ ${message}`;
      _statusText.style.color = 'red';
    }
    console.error('[StepView]', message);
  }

  // ── 3D 渲染 ───────────────────────────────────────────────────────────────

  function render3D(geometryData) {
    // 委派給 step_viewer.js 中的既有渲染邏輯
    if (typeof renderStepGeometry === 'function') {
      renderStepGeometry(geometryData);
    } else {
      console.warn('[StepView] renderStepGeometry 未定義，請確認 step_viewer.js 已載入');
    }
  }

  function highlightFaces(geometryData) {
    if (typeof highlightStepFaces === 'function') {
      highlightStepFaces(geometryData);
    }
  }

  // ── PMI 列表 ──────────────────────────────────────────────────────────────

  function renderPmiList(pmiRows) {
    if (!_pmiListEl) return;
    _pmiListEl.innerHTML = '';
    pmiRows.forEach((row, idx) => {
      const li = document.createElement('li');
      li.className    = 'pmi-item';
      li.dataset.idx  = idx;
      li.textContent  = row.label || `PMI #${idx + 1}`;
      _pmiListEl.appendChild(li);
    });
  }

  // ── 組合件結果 ────────────────────────────────────────────────────────────

  function renderAsmResult(result) {
    if (!_asmResultEl) return;
    if (!result || !result.contacts) {
      _asmResultEl.innerHTML = '<p>無接觸對</p>';
      return;
    }
    const html = result.contacts.map(c =>
      `<div class="asm-contact">
        <b>${c.comp1_name}</b> ↔ <b>${c.comp2_name}</b>
        <span class="contact-type">${c.contact_type}</span>
      </div>`
    ).join('');
    _asmResultEl.innerHTML = html;
  }

  // ── 下載 ──────────────────────────────────────────────────────────────────

  function triggerDownload(content, filename) {
    const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  return { init, showProgress, showError, render3D, highlightFaces, renderPmiList, renderAsmResult, triggerDownload };
})();
