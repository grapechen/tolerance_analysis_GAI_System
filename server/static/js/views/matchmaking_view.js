/**
 * matchmaking_view.js - 製程機台媒合結果 View
 *
 * 職責：
 *   - 渲染媒合結果五步驟（配合選擇、公差數值、機台、應用場景、製程）
 *   - 顯示 / 隱藏載入狀態
 *   - 顯示錯誤訊息
 *
 * 不含業務邏輯或 API 呼叫。
 */

const MatchmakingView = (() => {
  let _resultEl  = null;
  let _loadingEl = null;
  let _errorEl   = null;

  // ── 初始化 ────────────────────────────────────────────────────────────────

  function init({ resultEl, loadingEl, errorEl }) {
    _resultEl  = resultEl;
    _loadingEl = loadingEl;
    _errorEl   = errorEl;
  }

  // ── 狀態控制 ──────────────────────────────────────────────────────────────

  function showLoading(visible) {
    if (_loadingEl) _loadingEl.style.display = visible ? '' : 'none';
    if (_resultEl && visible) _resultEl.innerHTML = '';
    if (_errorEl && visible)  _errorEl.textContent = '';
  }

  function showError(message) {
    if (_errorEl) _errorEl.textContent = message;
  }

  // ── 結果渲染 ──────────────────────────────────────────────────────────────

  function renderResult(data) {
    if (!_resultEl) return;

    const fit       = data.step2_fit_details   || {};
    const machines  = data.step3_capable_machines || [];
    const app       = data.step4_application_scenario || {};
    const proc      = data.step5_process_recommendation || {};
    const best      = data.step1_selected_fit  || {};

    const html = `
      <section class="mm-section">
        <h3>① 建議配合</h3>
        <p><b>${best.hole || '—'}/${best.shaft || '—'}</b>
           ${fit.fit_type ? `（${fit.fit_type}）` : ''}
        </p>
        <p>孔上偏差：${fit.hole?.upper_um ?? '—'} μm ／ 下偏差：${fit.hole?.lower_um ?? '—'} μm</p>
        <p>軸上偏差：${fit.shaft?.upper_um ?? '—'} μm ／ 下偏差：${fit.shaft?.lower_um ?? '—'} μm</p>
        <p>間隙範圍：${fit.min_clearance_um ?? '—'} ~ ${fit.max_clearance_um ?? '—'} μm</p>
      </section>

      <section class="mm-section">
        <h3>② 適合應用場景</h3>
        <p>${app.function || '—'}</p>
        <p class="note">${app.note || ''}</p>
      </section>

      <section class="mm-section">
        <h3>③ 製程建議</h3>
        ${_renderProcess(proc.hole_process, '孔')}
        ${_renderProcess(proc.shaft_process, '軸')}
      </section>

      <section class="mm-section">
        <h3>④ 推薦機台</h3>
        <ul class="machine-list">
          ${machines.slice(0, 10).map(m =>
            `<li><b>${m.model}</b>（${m.company}）<span>${m.recommend_reason || ''}</span></li>`
          ).join('')}
        </ul>
      </section>
    `;

    _resultEl.innerHTML = html;
  }

  function _renderProcess(proc, label) {
    if (!proc) return `<p>${label}加工：N/A</p>`;
    return `<p>${label}加工（${proc.it_grade}）：
      ${proc.chain?.join(' → ') || '—'}
      ，Ra ${proc.Ra_target || '—'}
    </p>`;
  }

  return { init, showLoading, showError, renderResult };
})();
