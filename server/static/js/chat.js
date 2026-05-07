// ══════════════════════════════════════════════
// 公差分析結果渲染
// ══════════════════════════════════════════════
function renderAnalysisResult(result) {
    const isEn = window.CURRENT_LANG === 'en';
    const fmt   = (v) => (v != null ? Number(v).toFixed(4) : '0.0000');
    const fmt6  = (v) => (v != null ? Number(v).toFixed(6) : '0.000000');
    const fmtPct = (v) => (v != null ? Number(v).toFixed(2) + '%' : '—');
    // ── helper：產生數據區塊 HTML (現在改為白底黑框) ──────────────────────────────────
    function _dataBlock(title, rows, cols) {
        let tableRows = rows.map(r => `
            <tr style="border-bottom:1px solid #000000;">
                <td style="padding:4px 5px; font-weight:bold; width:30%; border-right:1px solid #000000;">${r[0]}</td>
                ${r.slice(1).map(v => `<td style="padding:4px 5px; text-align:right;">${v}</td>`).join('')}
            </tr>
        `).join('');

        return `
            <div style="background:#ffffff; color:#000000; border:1px solid #000000; padding:8px; margin-bottom:8px; font-family:'Times New Roman', serif;">
                <div style="font-weight:bold; border-bottom:2px solid #000000; margin-bottom:4px; font-size:0.9rem; text-transform:uppercase;">${title}</div>
                <table style="width:100%; border-collapse:collapse; font-size:0.8rem;">
                    ${cols ? `<thead><tr>${cols.map(c => `<th style="text-align:right; padding:0 5px; font-size:0.7rem; border-bottom:1px solid #000000;">${c}</th>`).join('')}</tr></thead>` : ''}
                    <tbody>${tableRows}</tbody>
                </table>
            </div>
        `;
    }

    // 1. Tideal Matrix
    let m = result.t_ideal_matrix || [[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]];
    const matrixHtml = _dataBlock('Tideal Matrix', [
        ['', fmt6(m[0][0]), fmt6(m[0][1]), fmt6(m[0][2]), fmt6(m[0][3])],
        ['', fmt6(m[1][0]), fmt6(m[1][1]), fmt6(m[1][2]), fmt6(m[1][3])],
        ['', fmt6(m[2][0]), fmt6(m[2][1]), fmt6(m[2][2]), fmt6(m[2][3])],
        ['', fmt6(m[3][0]), fmt6(m[3][1]), fmt6(m[3][2]), fmt6(m[3][3])]
    ]);

    // 2. Statistics Model (RSS 3sigma)
    const statsHtml = _dataBlock('Statistics Model', [
        ['Xerror', fmt(result.rss_X * -1.0), fmt(result.rss_X)],
        ['Yerror', fmt(result.rss_Y * -1.0), fmt(result.rss_Y)],
        ['Zerror', fmt(result.rss_Z * -1.0), fmt(result.rss_Z)]
    ], ['tol_range', '-3sigma', '+3sigma']);

    // 3. Worst Case Model
    const wcHtml = _dataBlock('Worst Case Model', [
        ['Xerror', fmt(result.wc_X * -1.0), fmt(result.wc_X)],
        ['Yerror', fmt(result.wc_Y * -1.0), fmt(result.wc_Y)],
        ['Zerror', fmt(result.wc_Z * -1.0), fmt(result.wc_Z)]
    ], ['tol_range', 'min', 'max']);

    // 4. Angle Statistics Model (arc_second) — backend 已輸出 arc_second
    const aStatsHtml = _dataBlock('Angle Statistics Model (arc_second)', [
        ['Xerror', fmt(result.rss_aX * -3.0), fmt(result.rss_aX * 3.0)],
        ['Yerror', fmt(result.rss_aY * -3.0), fmt(result.rss_aY * 3.0)],
        ['Zerror', fmt(result.rss_aZ * -3.0), fmt(result.rss_aZ * 3.0)]
    ], ['tol_range', '-3sigma', '+3sigma']);

    // 5. Angle Worst Case Model (arc_second) — backend 已輸出 arc_second
    const aWcHtml = _dataBlock('Angle Worst Case Model (arc_second)', [
        ['Xerror', fmt(result.wc_aX * -1.0), fmt(result.wc_aX)],
        ['Yerror', fmt(result.wc_aY * -1.0), fmt(result.wc_aY)],
        ['Zerror', fmt(result.wc_aZ * -1.0), fmt(result.wc_aZ)]
    ], ['tol_range', 'min', 'max']);

    const title = isEn ? 'Tolerance Analysis Report' : '公差分析報告';
    
    // --- 產生詳細表格 HTML (同樣改為白底黑框) ---
    const _tblHeader = (cols) => `<thead><tr style="border-bottom:2px solid #000000; background:#f1f5f9;">${cols.map(c => `<th style="text-align:left; padding:8px; font-size:0.75rem; color:#000000; border-right:1px solid #000000;">${c}</th>`).join('')}</tr></thead>`;
    
    // 敏感度表格
    const sensX = result.sensitivity || [];
    const sensHtml = `
        <div style="margin-top:10px; font-size:0.85rem; font-weight:bold; color:#000000; text-transform:uppercase;">${isEn ? 'Sensitivity Analysis' : '敏感度分析'}</div>
        <table style="width:100%; border-collapse:collapse; margin-top:5px; border:1px solid #000000; background:#ffffff;">
            ${_tblHeader([isEn?'Rank':'排名', 'tol_sym', 'X(%)', 'Y(%)', 'Z(%)'])}
            <tbody>
                ${sensX.slice(0,15).map((s,i) => `
                    <tr style="border-bottom:1px solid #000000;">
                        <td style="padding:4px 8px; border-right:1px solid #000000;">NO.${i+1}</td>
                        <td style="padding:4px 8px; font-weight:bold; border-right:1px solid #000000;">${s.name}</td>
                        <td style="padding:4px 8px; border-right:1px solid #000000;">${fmtPct(s.x)}</td>
                        <td style="padding:4px 8px; border-right:1px solid #000000;">${fmtPct(s.y)}</td>
                        <td style="padding:4px 8px;">${fmtPct(s.z)}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;

    // 貢獻度表格 (平移)
    const contX = result.contribution || [];
    const contHtml = `
        <div style="margin-top:10px; font-size:0.85rem; font-weight:bold; color:#000000; text-transform:uppercase;">${isEn ? 'Contribution Analysis' : '貢獻度分析'}</div>
        <table style="width:100%; border-collapse:collapse; margin-top:5px; border:1px solid #000000; background:#ffffff;">
            ${_tblHeader([isEn?'Rank':'排名', 'tol_sym', 'X(%)', 'Y(%)', 'Z(%)'])}
            <tbody>
                ${contX.slice(0,15).map((s,i) => `
                    <tr style="border-bottom:1px solid #000000;">
                        <td style="padding:4px 8px; border-right:1px solid #000000;">NO.${i+1}</td>
                        <td style="padding:4px 8px; font-weight:bold; border-right:1px solid #000000;">${s.name}</td>
                        <td style="padding:4px 8px; border-right:1px solid #000000;">${fmtPct(s.x)}</td>
                        <td style="padding:4px 8px; border-right:1px solid #000000;">${fmtPct(s.y)}</td>
                        <td style="padding:4px 8px;">${fmtPct(s.z)}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;

    // 角度敏感度表格
    const sensA = result.angle_sensitivity || [];
    const sensAHtml = `
        <div style="margin-top:10px; font-size:0.85rem; font-weight:bold; color:#000000; text-transform:uppercase;">${isEn ? 'Angle Sensitivity Analysis' : '角度敏感度分析'}</div>
        <table style="width:100%; border-collapse:collapse; margin-top:5px; border:1px solid #000000; background:#ffffff;">
            ${_tblHeader([isEn?'Rank':'排名', 'tol_sym', 'X(%)', 'Y(%)', 'Z(%)'])}
            <tbody>
                ${sensA.slice(0,15).map((s,i) => `
                    <tr style="border-bottom:1px solid #000000;">
                        <td style="padding:4px 8px; border-right:1px solid #000000;">NO.${i+1}</td>
                        <td style="padding:4px 8px; font-weight:bold; border-right:1px solid #000000;">${s.name}</td>
                        <td style="padding:4px 8px; border-right:1px solid #000000;">${fmtPct(s.x)}</td>
                        <td style="padding:4px 8px; border-right:1px solid #000000;">${fmtPct(s.y)}</td>
                        <td style="padding:4px 8px;">${fmtPct(s.z)}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;

    // 角度貢獻度表格
    const contA = result.angle_contribution || [];
    const contAHtml = `
        <div style="margin-top:10px; font-size:0.85rem; font-weight:bold; color:#000000; text-transform:uppercase;">${isEn ? 'Angle Contribution Analysis' : '角度貢獻度分析'}</div>
        <table style="width:100%; border-collapse:collapse; margin-top:5px; border:1px solid #000000; background:#ffffff;">
            ${_tblHeader([isEn?'Rank':'排名', 'tol_sym', 'X(%)', 'Y(%)', 'Z(%)'])}
            <tbody>
                ${contA.slice(0,15).map((s,i) => `
                    <tr style="border-bottom:1px solid #000000;">
                        <td style="padding:4px 8px; border-right:1px solid #000000;">NO.${i+1}</td>
                        <td style="padding:4px 8px; font-weight:bold; border-right:1px solid #000000;">${s.name}</td>
                        <td style="padding:4px 8px; border-right:1px solid #000000;">${fmtPct(s.x)}</td>
                        <td style="padding:4px 8px; border-right:1px solid #000000;">${fmtPct(s.y)}</td>
                        <td style="padding:4px 8px;">${fmtPct(s.z)}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;

    // 累積誤差摘要表格
    const summaryHtml = `
        <div style="margin-top:15px; font-size:0.85rem; font-weight:bold; color:#000000; text-transform:uppercase;">${isEn ? 'Accumulated Error Summary' : '累積誤差摘要'}</div>
        <div style="overflow-x:auto;">
            <table style="width:100%; border-collapse:collapse; margin-top:5px; border:1px solid #000000; background:#ffffff; font-size:0.75rem; min-width:350px;">
                <thead>
                    <tr style="background:#f1f5f9; border-bottom:2px solid #000000;">
                        <th style="padding:5px; text-align:left; border-right:1px solid #000000;">方法</th>
                        <th style="padding:5px; text-align:right; border-right:1px solid #000000;">ΔX</th>
                        <th style="padding:5px; text-align:right; border-right:1px solid #000000;">ΔY</th>
                        <th style="padding:5px; text-align:right; border-right:1px solid #000000;">ΔZ</th>
                        <th style="padding:5px; text-align:right; border-right:1px solid #000000;">ΔaX</th>
                        <th style="padding:5px; text-align:right; border-right:1px solid #000000;">ΔaY</th>
                        <th style="padding:5px; text-align:right;">ΔaZ</th>
                    </tr>
                </thead>
                <tbody>
                    <tr style="border-bottom:1px solid #000000;"><td>RSS</td><td style="text-align:right;">${fmt(result.rss_X)}</td><td style="text-align:right;">${fmt(result.rss_Y)}</td><td style="text-align:right;">${fmt(result.rss_Z)}</td><td style="text-align:right;">${fmt(result.rss_aX)}</td><td style="text-align:right;">${fmt(result.rss_aY)}</td><td style="text-align:right;">${fmt(result.rss_aZ)}</td></tr>
                    <tr style="border-bottom:1px solid #000000;"><td>Worst Case</td><td style="text-align:right;">${fmt(result.wc_X)}</td><td style="text-align:right;">${fmt(result.wc_Y)}</td><td style="text-align:right;">${fmt(result.wc_Z)}</td><td style="text-align:right;">${fmt(result.wc_aX)}</td><td style="text-align:right;">${fmt(result.wc_aY)}</td><td style="text-align:right;">${fmt(result.wc_aZ)}</td></tr>
                    <tr style="border-bottom:1px solid #000000;"><td>MC σ</td><td style="text-align:right;">${fmt(result.mc_X_std)}</td><td style="text-align:right;">${fmt(result.mc_Y_std)}</td><td style="text-align:right;">${fmt(result.mc_Z_std)}</td><td style="text-align:right;">${fmt(result.mc_aX_std)}</td><td style="text-align:right;">${fmt(result.mc_aY_std)}</td><td style="text-align:right;">${fmt(result.mc_aZ_std)}</td></tr>
                    <tr><td>MC max</td><td style="text-align:right;">${fmt(result.mc_X_max)}</td><td style="text-align:right;">${fmt(result.mc_Y_max)}</td><td style="text-align:right;">${fmt(result.mc_Z_max)}</td><td style="text-align:right;">${fmt(result.mc_aX_max)}</td><td style="text-align:right;">${fmt(result.mc_aY_max)}</td><td style="text-align:right;">${fmt(result.mc_aZ_max)}</td></tr>
                </tbody>
            </table>
        </div>
    `;

    const html = `
<div style="background:#ffffff; border:3px solid #000000; padding:15px; color:#000000; font-family:'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;">
  <div style="font-size:1.1rem; font-weight:bold; margin-bottom:15px; color:#000000; border-bottom:3px solid #000000; padding-bottom:5px;">${title}</div>

  <!-- 彩色摘要區塊 -->
  <div style="display:grid; grid-template-columns: 1fr; gap:10px;">
    ${matrixHtml}
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px;">
        ${statsHtml}
        ${wcHtml}
    </div>
    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:10px;">
        ${aStatsHtml}
        ${aWcHtml}
    </div>
  </div>

  <!-- 所有詳細數據表格 (平移與角度拆分) -->
  <div style="margin-top:20px;">
    ${sensHtml}
    ${contHtml}
    ${sensAHtml}
    ${contAHtml}
    ${summaryHtml}
  </div>

  <div style="margin-top:20px; border-top:2px solid #000000; padding-top:10px; text-align:right;">
    <button onclick="downloadAnalysisExcel()" style="background:#000000; color:#ffffff; border:none; padding:10px 20px; border-radius:4px; font-size:1rem; font-weight:bold; cursor:pointer; box-shadow:4px 4px 0px rgba(0,0,0,0.2);">
      📥 ${isEn ? 'Download Excel Report' : '下載完整 Excel 報表'}
    </button>
  </div>
</div>`;

    if (typeof addMessage === 'function') addMessage('ai', html);
    if (typeof historyDOM !== 'undefined') historyDOM.scrollTop = historyDOM.scrollHeight;
}

// DOM 元素綁定
const input = document.getElementById('chat-input');
const historyDOM = document.getElementById('chat-history');
const sendBtn = document.getElementById('send-btn');
const modelSelect = document.getElementById('model-select');
const graphContainer = document.getElementById('graph-container');

let chatHistory = [];

// 處理 Enter 鍵發送
input.addEventListener('keypress', function (e) {
  if (e.key === 'Enter') sendMessage();
});

// ══════════════════════════════════════════════
// 1. 核心發送與接收邏輯
// ══════════════════════════════════════════════
async function sendMessage() {
  const msg = input.value.trim();
  if (!msg) return;

  // 攔截「進階版配合調整」指令 → 直接開啟 wizard，不送 AI
  if (/進階版|adv.?fit|advanced.?fit/i.test(msg)) {
    if (typeof openAdvFitPanel === 'function') {
      input.value = '';
      openAdvFitPanel();
      return;
    }
  }

  // 攔截「看路徑/累積路徑/公差路徑」查看指令 → 唯讀顯示 + 自動偵測當前路徑狀態
  if (/看.*路徑|路徑.*看|查看.*路徑|顯示.*路徑|看累積路徑|看公差路徑|看完整.*路徑/i.test(msg)) {
    input.value = '';
    addMessage('user', msg);
    const isEn = window.CURRENT_LANG === 'en';
    // 自動偵測最新路徑：優先 editorPathData（含所有更新），次選 _lastPathData
    const path = (typeof editorPathData !== 'undefined' && editorPathData.length)
                   ? editorPathData
                   : (window._lastPathData || []);
    if (!path.length) {
      addMessage('ai', isEn ? 'No path loaded yet.' : '尚未載入公差累積路徑，請先匯入 Excel/CSV。');
      return;
    }

    // ── 計算路徑統計 ──────────────────────────────────────────────
    const features  = path.filter(i => i.type === 'feature');
    const spatials  = path.filter(i => i.type !== 'feature');
    const maxItem   = features.reduce((m, i) =>
      !m || Math.abs(Number(i.val) || 0) > Math.abs(Number(m.val) || 0) ? i : m, null);
    const itSet     = [...new Set(features.map(i => i.it_grade).filter(Boolean))]
                        .sort((a, b) => (parseInt(a.replace('IT',''))||0) - (parseInt(b.replace('IT',''))||0));
    const updateInfo = window._pathUpdateInfo;  // 最後更新來源（由各操作設定）

    // ── 狀態列 ────────────────────────────────────────────────────
    let statusChips = `<span style="color:#374151;">共 <b>${path.length}</b> 項（${features.length} 公差特徵 / ${spatials.length} 空間轉換）</span>`;
    if (maxItem) {
      const maxVal = Math.abs(Number(maxItem.val) || 0).toFixed(4);
      statusChips += `　<span style="color:#dc2626;">最寬鬆：<b>${maxItem.name || maxItem.axis}</b> ${maxVal} mm</span>`;
    }
    if (itSet.length) {
      statusChips += `　<span style="color:#1d4ed8;">IT 等級：${itSet.join('、')}</span>`;
    }
    const updateBadge = updateInfo
      ? `<div style="padding:5px 12px; background:#f0fdf4; border-top:1px solid #bbf7d0; font-size:0.72rem; color:#15803d;">
           ◎ 最後更新：<b>${updateInfo.source}</b>（${updateInfo.time}）${updateInfo.desc ? '　' + updateInfo.desc : ''}
         </div>`
      : '';

    // ── 生成唯讀表格 ──────────────────────────────────────────────
    let rows = '';
    path.forEach(item => {
      const name  = item.name || item.axis || '—';
      const val   = item.val != null ? Number(item.val).toFixed(4) : '—';
      const bias  = item.bias != null ? item.bias : 0;
      const dist  = item.dist != null ? item.dist : 1;
      const nom   = item.nominal_size != null ? item.nominal_size : '—';
      const it    = item.it_grade || '—';
      const isSpatial = item.type === 'spatial';
      const rowBg = isSpatial ? '#f0f9ff' : '#ffffff';
      const nameColor = isSpatial ? '#6366f1' : '#000000';
      rows += `<tr style="border-bottom:1px solid #e5e7eb; background:${rowBg};">
        <td style="padding:5px 8px; color:${nameColor}; font-weight:${isSpatial?'normal':'600'};">${name}</td>
        <td style="padding:5px 8px; text-align:right;">${val}</td>
        <td style="padding:5px 8px; text-align:right; color:#6b7280;">${bias}</td>
        <td style="padding:5px 8px; text-align:right; color:#6b7280;">${dist}</td>
        <td style="padding:5px 8px; text-align:right; color:#6b7280;">${nom}</td>
        <td style="padding:5px 8px; text-align:center; font-weight:bold; color:#1d4ed8;">${it}</td>
      </tr>`;
    });
    const html = `
      <div style="background:#fff; border:1px solid #e2e8f0; border-radius:8px; overflow:hidden; font-size:0.82rem; margin:4px 0;">
        <div style="background:#f8fafc; padding:8px 12px; font-weight:700; color:#1e293b; border-bottom:1px solid #e2e8f0;">
          ${isEn ? 'Tolerance Path' : '公差累積路徑（當前版本）'}
        </div>
        <div style="padding:6px 12px; background:#fffbeb; border-bottom:1px solid #fde68a; font-size:0.75rem; line-height:1.8;">
          ${statusChips}
        </div>
        ${updateBadge}
        <div style="max-height:400px; overflow-y:auto;">
          <table style="width:100%; border-collapse:collapse;">
            <thead style="background:#f1f5f9; position:sticky; top:0;">
              <tr style="font-size:0.75rem; color:#6b7280;">
                <th style="padding:5px 8px; text-align:left;">${isEn?'Path Code':'路徑代碼'}</th>
                <th style="padding:5px 8px; text-align:right;">${isEn?'Value':'數值'}</th>
                <th style="padding:5px 8px; text-align:right;">${isEn?'Bias':'偏差'}</th>
                <th style="padding:5px 8px; text-align:right;">${isEn?'Dist':'角距'}</th>
                <th style="padding:5px 8px; text-align:right;">${isEn?'Nominal':'公稱'}</th>
                <th style="padding:5px 8px; text-align:center;">IT</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
        <div style="padding:6px 12px; font-size:0.72rem; color:#9ca3af; border-top:1px solid #e5e7eb;">
          ${isEn?'Read-only view. Click "Edit Tolerance Path" to make changes.':'唯讀查看。如需修改請點選「編輯公差路徑」按鈕。'}
        </div>
      </div>`;
    addMessage('ai', html);
    return;
  }

  input.disabled = true;
  sendBtn.disabled = true;

  addMessage('user', msg);
  chatHistory.push({ role: 'user', content: msg });
  input.value = '';

  const loadingId = addLoading();

  try {
    const selectedModel = modelSelect.value;
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: msg,
        model: selectedModel,
        history: chatHistory.slice(-6),
        lang: window.CURRENT_LANG,
        current_analysis: window._lastAnalysisResult || null,
        current_path: (typeof editorPathData !== 'undefined') ? editorPathData : null,
        current_allocation: window._lastAllocationResult || null,
        current_pmi_session_id: window._stepSessionId || null,
        wf_state: window._wf || {},
        stacking_axis: document.getElementById('stacking-axis-select')?.value || 'Y'
      })
    });
    const data = await r.json();

    const loadingEl = document.getElementById(loadingId);
    if (loadingEl) loadingEl.remove();

    if (data.reply) {
      // --- 處理 AI 回應 ---
      let finalReply = data.reply;

      // 提取 BOM DSL 區塊 ---BOM_START--- ... ---BOM_END---
      const bomRegex = /---BOM_START---[\s\S]*?---BOM_END---/g;
      const dslBlocks = [...finalReply.matchAll(bomRegex)].map(m => m[0].trim());

      // 1. 擷取 Thought (思考過程) 標籤
      let thoughtHtml = '';
      const thoughtMatch = finalReply.match(/<thought>([\s\S]*?)<\/thought>/);
      if (thoughtMatch) {
        const thoughtText = thoughtMatch[1].trim();
        thoughtHtml = `
              <div class="thought-container collapsed">
                <div class="thought-header" onclick="this.parentElement.classList.toggle('collapsed')">🧠 AI Thought Process (Click to expand)</div>
                <div class="thought-content">${thoughtText}</div>
              </div>
            `;
        finalReply = finalReply.replace(/<thought>[\s\S]*?<\/thought>/, '').trim();
      }

      // [Phase 2] Handle PMI Highlight from AI tags
      const highlightPmiRegex = /<HIGHLIGHT_PMI\s+label="([^"]+)"\s*\/>/g;
      let hMatch;
      while ((hMatch = highlightPmiRegex.exec(finalReply)) !== null) {
          const label = hMatch[1];
          if (typeof PmiPanel !== 'undefined') {
              console.log(`[AI] Highlighting PMI: ${label}`);
              PmiPanel.onAiHighlight(label);
              if (typeof openStepViewerPanel === 'function') openStepViewerPanel();
          }
      }
      // Clean tags from reply
      finalReply = finalReply.replace(highlightPmiRegex, '').trim();

      // 2.5 公差調整指令 → 後端回傳 intent.modified_path（已含新 IT 與重算後的 val），整包替換
      const modifiedPath = data.intent && data.intent.modified_path;
      if (Array.isArray(modifiedPath) && typeof editorPathData !== 'undefined') {
          editorPathData.length = 0;
          editorPathData.push(...modifiedPath);
          if (typeof renderPathFlowchart === 'function') renderPathFlowchart();
          console.log(`[CMD] editorPathData replaced (${modifiedPath.length} items) and re-rendered`);
          // 記錄更新來源（供「看路徑」顯示）
          window._pathUpdateInfo = {
              source: '公差調整指令',
              time: new Date().toLocaleTimeString('zh-TW', { hour: '2-digit', minute: '2-digit' }),
              desc: ''
          };

          // 更新 _wf 狀態
          if (window._wf) {
              if (data.intent.bearing_applied) {
                  window._wf.bearingSet    = true;
                  window._wf.readyForAlloc = window._wf.analysisRun;
              }
              // IT 調整或軸承後，如果分析已完成，標記可調配
              if (window._wf.analysisRun && window._wf.bearingSet) {
                  window._wf.readyForAlloc = true;
              }
          }
      }

      // 3. 處理診斷建議卡片 <DIAGNOSTIC_CARD>
      const cardRegex = /<DIAGNOSTIC_CARD type="(.*?)" target="(.*?)" value="(.*?)" reason="(.*?)"\s*\/>/g;
      let cardsHtml = '';
      let cardMatches = [...finalReply.matchAll(cardRegex)];
      
      if (cardMatches.length > 0) {
          cardsHtml = '<div class="suggestion-grid">';
          cardMatches.forEach(m => {
              const [_, type, target, value, reason] = m;
              const typeClass = `card-${type}`; // tighten, maintain, secondary, loosen
              const typeLabel = {
                  'tighten': (window.CURRENT_LANG === 'en' ? '🚀 Tighten' : '🚀 優先收緊'),
                  'maintain': (window.CURRENT_LANG === 'en' ? '🛡️ Maintain' : '🛡️ 嚴守原樣'),
                  'secondary': (window.CURRENT_LANG === 'en' ? '⚖️ Secondary' : '⚖️ 次要調整'),
                  'loosen': (window.CURRENT_LANG === 'en' ? '💰 Loosen' : '💰 成本優化')
              }[type] || 'Suggestion';

              cardsHtml += `
                  <div class="suggestion-card ${typeClass}">
                      <div class="card-title">${typeLabel}</div>
                      <div style="font-size:0.8rem; font-weight:bold; margin:2px 0;">${target}</div>
                      <div class="card-desc">${reason}</div>
                      ${value !== 'none' ? `<button class="apply-btn" onclick="applyAdjustment('${target}', ${value})">${window.CURRENT_LANG === 'en' ? 'Apply' : '套用'} → ${value}</button>` : ''}
                  </div>
              `;
          });
          cardsHtml += '</div>';
          finalReply = finalReply.replace(cardRegex, '');
      }

      // 4. 移除 DSL 區塊後的純文字 (用於右側聊天泡泡)
      let cleanText = finalReply.replace(bomRegex, '').trim();
      
      const textHtml = thoughtHtml + cleanText.split('\n').join('<br>') + cardsHtml;

      // 4. 渲染聊天泡泡
      if (textHtml.trim()) {
        addMessage('ai', textHtml);
      }

      // 5 & 6. 如果有圖表區塊，渲染到左側面板；如果是編輯意圖，自動開啟編輯器
      // 注意：renderResult 必須宣告在兩個條件式之外，才能讓 setTimeout 取用
      let renderResult = null;
      if (dslBlocks.length > 0 && typeof renderStructureDirectly === "function") {
        renderResult = renderStructureDirectly(dslBlocks[0], graphContainer, data.intent);

        // 公差網路、組裝接觸或特徵面意圖（非編輯）→ 自動開啟大圖彈窗
        if (data.intent && (data.intent.network || data.intent.contact || data.intent.features) && !data.intent.edit && renderResult) {
            setTimeout(() => {
                if (typeof openBomModal === "function") {
                    openBomModal(renderResult.treeHtml, renderResult.b64Topology, renderResult.snapshotPairs || []);
                }
            }, 500);
        }
      }

      // 編輯意圖 → 自動開啟公差路徑編輯器彈窗
      if (data.intent && data.intent.edit) {
        setTimeout(() => {
            if (dslBlocks.length > 0 && renderResult && renderResult.partsJson) {
                if (typeof openEditorModal === 'function') {
                    openEditorModal(decodeURIComponent(renderResult.partsJson));
                }
            } else if (typeof openEditorModal === 'function') {
                // 直接開啟編輯器（不帶 partsJson）
                const overlay = document.getElementById('editor-modal-overlay');
                if (overlay) overlay.style.display = 'flex';
            } else {
                const btn = document.querySelector('.open-editor-btn') || graphContainer?.querySelector('.open-editor-btn');
                if (btn) btn.click();
            }
        }, 300);
      }

      // 分析意圖 → 打開分析參數 Modal
      if (data.intent && data.intent.analysis) {
        setTimeout(() => {
            if (typeof openAnalysisModal === "function") openAnalysisModal();
        }, 300);
      }

      // 調配意圖 → 打開調配參數 Modal
      if (data.intent && data.intent.allocation) {
        setTimeout(() => {
            if (typeof openAllocationModal === "function") openAllocationModal();
        }, 300);
      }

      // 配合建議引導 → 開啟 Modal
      if (data.intent && data.intent.open_plan1) {
        if (typeof openPlanCompareModal === 'function') openPlanCompareModal();
      }

      chatHistory.push({ role: 'assistant', content: data.reply });
      historyDOM.scrollTop = historyDOM.scrollHeight;

    } else {
      const errMsg = (window.CURRENT_LANG === 'en') ? '[WARN] Error: Unable to get response' : '[WARN] 發生錯誤：無法取得回應';
      addMessage('ai', errMsg);
    }
  } catch (e) {
    document.getElementById(loadingId)?.remove();
    addMessage('ai', '[ERROR] 網路錯誤：' + e);
  } finally {
    input.disabled = false;
    sendBtn.disabled = false;
    input.focus();
  }
}

// ══════════════════════════════════════════════
// 2. UI 輔助函式
// ══════════════════════════════════════════════
function addMessage(role, htmlContent) {
  const div = document.createElement('div');
  div.className = `message ${role}`;

  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.textContent = role === 'user' ? 'You' : 'AI';

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.innerHTML = htmlContent;

  if (role === 'user') {
    div.appendChild(bubble);
    div.appendChild(avatar);
  } else {
    div.appendChild(avatar);
    div.appendChild(bubble);
  }

  historyDOM.appendChild(div);
  historyDOM.scrollTop = historyDOM.scrollHeight;
}

function addLoading() {
  const id = 'loading-' + Date.now();
  const div = document.createElement('div');
  div.className = 'message ai';
  div.id = id;

  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.textContent = 'AI';

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.innerHTML = `
    <div class="typing-indicator">
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
    </div>
  `;

  div.appendChild(avatar);
  div.appendChild(bubble);
  historyDOM.appendChild(div);
  historyDOM.scrollTop = historyDOM.scrollHeight;
  return id;
}

// ══════════════════════════════════════════════
// 3. 分隔線拖曳 (Resizer Logic)
// ══════════════════════════════════════════════
(function initResizer() {
  const resizer = document.getElementById('panel-resizer');
  const leftPanel = document.querySelector('.left-panel');
  const appLayout = document.querySelector('.app-layout');
  if (!resizer || !leftPanel || !appLayout) return;

  let isResizing = false;

  resizer.addEventListener('mousedown', (e) => {
    isResizing = true;
    resizer.classList.add('dragging');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
  });

  document.addEventListener('mousemove', (e) => {
    if (!isResizing) return;
    const containerRect = appLayout.getBoundingClientRect();
    let newWidth = e.clientX - containerRect.left;

    // 限制最小 250px、最大為容器寬度的 70%
    const minWidth = 250;
    const maxWidth = containerRect.width * 0.7;
    newWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));

    leftPanel.style.width = newWidth + 'px';
    leftPanel.style.flex = `0 0 ${newWidth}px`;
  });

  document.addEventListener('mouseup', () => {
    if (!isResizing) return;
    isResizing = false;
    resizer.classList.remove('dragging');
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  });
})();

// ══════════════════════════════════════════════
// 4. 左側快速按鈕事件
// ══════════════════════════════════════════════
const panelBtnPrompts = {
  parts: '畫出產品架構圖，列出所有零件',
  features: '畫出所有零件的特徵面結構圖',
  network: '畫出公差網路圖',
  contact: '畫出組裝接觸關係圖',
  step_viewer: '開啟 STEP 3D 檢視器',
  edit_path: '編輯公差路徑，開啟公差編輯器',
  analysis: '進行公差分析',
  allocation: '進行公差調配'
};

document.querySelectorAll('.panel-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const action = btn.getAttribute('data-action');
    
    // 更新外觀狀態
    document.querySelectorAll('.panel-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    let prompt = panelBtnPrompts[action];
    
    // [直接開啟] 公差路徑編輯器 → 不走 AI，直接開啟
    if (action === 'edit_path') {
        const overlay = document.getElementById('editor-modal-overlay');
        if (overlay) {
            overlay.style.display = 'flex';
        } else if (typeof openEditorModal === 'function') {
            openEditorModal();
        }
        btn.classList.remove('active');
        return;
    }

    // [直接開啟] STEP 3D 檢視器按鈕 → 不走 AI，直接開啟面板
    if (action === 'step_viewer') {
        if (typeof openStepViewerPanel === 'function') {
            openStepViewerPanel();
        } else {
            // Fallback：直接操作 DOM
            const panel = document.getElementById('step-viewer-panel');
            if (panel) panel.style.display = 'flex';
        }
        return; // 攔截，不發送訊息
    }

    // [直接開啟] 進階版配合調整 → 不走 AI，直接開啟 Wizard
    if (action === 'adv_fit') {
        if (typeof openAdvFitPanel === 'function') openAdvFitPanel();
        btn.classList.remove('active');
        return;
    }

    // [直接開啟] 製程與機台媒合 → 不走 AI，直接開啟 Modal
    if (action === 'matchmaking' || !action) {
        if (typeof openMatchmakingModal === 'function') openMatchmakingModal();
        btn.classList.remove('active'); // 媒合按鈕不需要 active 狀態
        return;
    }

    // [直接開啟] 配合建議
    if (action === 'plan_compare') {
        if (typeof openPlanCompareModal === 'function') openPlanCompareModal();
        btn.classList.remove('active');
        return;
    }

    // [修正] 如果目前已有路徑數據，點擊分析或調配應直接開啟視窗，不應去問 AI (避免 AI 覆寫數據)
    if (action === 'analysis' && typeof editorPathData !== 'undefined' && editorPathData.length > 0) {
        if (typeof openAnalysisModal === 'function') {
            openAnalysisModal();
            return; // 攔截，不發送訊息
        }
    }
    if (action === 'allocation' && typeof editorPathData !== 'undefined' && editorPathData.length > 0) {
        // 狀態守衛：分析未完成時提醒
        if (window._wf && !window._wf.analysisRun) {
            if (typeof addMessage === 'function') {
                addMessage('ai',
                    '<div style="color:#f87171;">⚠️ 請先執行【公差分析】確認基線誤差，再進行公差調配。</div>'
                );
            }
            return;
        }
        if (typeof openAllocationModal === 'function') {
            openAllocationModal();
            return; // 攔截，不發送訊息
        }
    }

    // [新功能] 智能診斷分析按鈕行為 (如果沒數據才走這段問 AI 如何開始)
    if (action === 'analysis') {
        if (!window._lastAnalysisResult) {
            prompt = window.CURRENT_LANG === 'en' ? 
                'Please check my current tolerance path and tell me how to start an analysis.' : 
                '請檢查我目前的公差路徑，並告訴我如何開始執行分析報告。';
        } else {
            prompt = window.CURRENT_LANG === 'en' ? 
                'Based on the current analysis report, please provide a diagnostic diagnostic using the 4-quadrant criteria and suggest optimizations.' : 
                '依據目前最新的公差分析數據，請依照四象限準則進行診斷，並給出具體的優化建議卡片。';
        }
    }

    // [新功能] 公差調配按鈕行為
    if (action === 'allocation') {
        if (!window._lastAnalysisResult) {
            prompt = window.CURRENT_LANG === 'en' ? 
                'Please run a "Deep Analysis" first so I can perform a tolerance allocation based on the results.' : 
                '請先執行「深度分析」，我才能根據報表數據為您進行公差調配建議。';
        } else {
            prompt = window.CURRENT_LANG === 'en' ? 
                'Based on the current analysis, please perform a global "Tolerance Allocation". Recommend adjustments for all key features to balance cost and precision, and provide diagnostic cards for each suggested change.' : 
                '請根據目前的分析報表執行全局「公差調配」。針對所有關鍵特徵給出優化分配建議，目標是平衡成本與精度，並為每個建議提供可套用的診斷卡片。';
        }
    }

    // 注入 Prompt 並發送
    input.value = prompt;
    sendMessage();
  });
});

// ══════════════════════════════════════════════
// 5. 交互調整邏輯
// ════════════════════════════════════════──────────────────────
function applyAdjustment(targetName, newValue) {
    if (typeof editorPathData === 'undefined') {
        alert(window.CURRENT_LANG === 'en' ? "Editor data not initialized." : "編輯器資料尚未初始化。");
        return;
    }
    
    let found = false;
    editorPathData.forEach(item => {
        // 匹配特徵名稱或空間軸向
        if (item.name === targetName || item.axis === targetName) {
            item.val = newValue;
            found = true;
        }
    });

    if (found) {
        // 更新編輯器 UI (如果編輯器開啟中)
        if (typeof renderEditorList === 'function') renderEditorList();
        
        const msg = (window.CURRENT_LANG === 'en') ? 
            `✅ Applied modification: **${targetName}** set to **${newValue}**` : 
            `✅ 已套用修改：**${targetName}** 已設定為 **${newValue}**`;
        addMessage('ai', `<div>${msg}</div>`);
        
        // 提醒使用者重新執行分析
        const reAnalyzeMsg = (window.CURRENT_LANG === 'en') ? 
            'Please click "Deep Analysis" in the editor to see the updated path error.' : 
            '請點擊編輯器中的「執行公差分析」以查看更新後的路徑誤差。';
        setTimeout(() => addMessage('ai', `<div style="font-size:0.9rem; color:#000000;">${reAnalyzeMsg}</div>`), 500);
    } else {
        alert(window.CURRENT_LANG === 'en' ? "Target not found in current path." : "在目前的公差路徑中找不到該目標。");
    }
}


function renderAllocationResult(data) {
    if (!data || !data.report) return;
    const isEn = window.CURRENT_LANG === 'en';
    const report = data.report;
    const mode = data.mode || 'auto';
    const round = window.__allocationRound || 1;
    const strategy = data.strategy || (isEn ? 'Four-Quadrant' : '四象限準則');
    
    let title, subTitle;
    if (mode === 'auto') {
        title = isEn ? `🤖 Auto Allocation Snapshot (Round #${round})` : `🤖 自動調配快照報告 (第 ${round} 次迭代)`;
        subTitle = isEn ? `Targeting ${data.axis}-axis RSS ±${data.target} | Strategy: ${strategy}` 
                          : `目標軸向: ${data.axis}，期望 RSS ±${data.target} | 策略: ${strategy}`;
    } else {
        title = isEn ? `Manual Matching Analysis (Round #${round})` : `手動匹配分析報告 (第 ${round} 次比對)`;
        subTitle = isEn ? `Comparing current manual edits against baseline | Axis: ${data.axis || 'All'}`
                          : `手動修改後與基準比對分析 | 參考軸向: ${data.axis || '全軸向'}`;
    }

    // 1. 軸向改善表 (Axis Summary - 顯示 6 自由度的前後對比)
    const axes = ['X', 'Y', 'Z', 'aX', 'aY', 'aZ'];
    let axisRows = '';
    axes.forEach(ax => {
        const item = report[ax];
        if (!item) return;
        
        const ri = item.rss_improve_pct;
        const wi = item.wc_improve_pct || 0;
        const rColor = ri > 0 ? '#16a34a' : (ri < 0 ? '#dc2626' : '#64748b');
        const wColor = wi > 0 ? '#16a34a' : (wi < 0 ? '#dc2626' : '#64748b');
        
        axisRows += `
            <tr style="border-bottom: 1px solid #f1f5f9; color: #334155; font-size: 0.8rem;">
                <td style="padding: 6px; font-weight: 800; color: #0f172a; text-align: left;">${ax}</td>
                <td style="padding: 6px; text-align: right; color: #64748b;">${item.rss_before.toFixed(5)}</td>
                <td style="padding: 6px; text-align: right; font-weight: bold;">${item.rss_after.toFixed(5)}</td>
                <td style="padding: 6px; text-align: right; color: ${rColor}; font-weight: bold;">${ri > 0 ? '+' : ''}${ri}%</td>
                <td style="padding: 6px; text-align: right; color: #64748b;">${item.wc_before.toFixed(5)}</td>
                <td style="padding: 6px; text-align: right; font-weight: bold;">${item.wc_after.toFixed(5)}</td>
                <td style="padding: 6px; text-align: right; color: ${wColor}; font-weight: bold;">${wi > 0 ? '+' : ''}${wi}%</td>
            </tr>
        `;
    });

    const axisHeader = `<thead style="color:#64748b; text-align:right; font-size:0.65rem; background:#f8fafc;">
        <tr>
            <th style="text-align:left; padding:6px;">自由度</th>
            <th style="padding:6px;">RSS (前)</th>
            <th style="padding:6px;">RSS (後)</th>
            <th style="padding:6px;">改善%</th>
            <th style="padding:6px;">WC (前)</th>
            <th style="padding:6px;">WC (後)</th>
            <th style="padding:6px;">改善%</th>
        </tr>
    </thead>`;

    // 2. 詳細變動表 (Feature Changes)
    let changeRows = '';
    if (data.newPathData) {
        const qColors = { 1: '#dc2626', 2: '#2563eb', 3: '#d97706', 4: '#16a34a' };
        const qNames = { 1: 'Q1', 2: 'Q2', 3: 'Q3', 4: 'Q4' };
        
        // [關鍵修正] 使用傳入的 prevPathData 來建立原值地圖，避免資料自相殘殺
        const oldMap = {};
        if (data.prevPathData) {
            data.prevPathData.forEach(p => { if (p.name) oldMap[p.name] = p.val; });
        } else if (window._lastPathData) {
            window._lastPathData.forEach(p => { if (p.name) oldMap[p.name] = p.val; });
        }

        data.newPathData.forEach(item => {
            if (item.type !== 'feature') return;
            const name = item.name;
            const newVal = item.val;
            const oldVal = oldMap[name] || newVal;
            const q = item.quadrant || 4;
            const diff = newVal - oldVal;
            const pct = oldVal > 0 ? (diff / oldVal * 100).toFixed(1) : 0;
            const pctColor = diff < 0 ? '#dc2626' : (diff > 0 ? '#16a34a' : '#94a3b8');

            changeRows += `
                <tr style="border-bottom: 1px solid #f8fafc; font-size: 0.85rem; color: #334155;">
                    <td style="padding: 6px; color: #1e293b;">${name}</td>
                    <td style="padding: 6px; text-align: right; color: #64748b;">${oldVal.toFixed(3)}</td>
                    <td style="padding: 6px; text-align: right; font-weight: bold; color: #0f172a;">${newVal.toFixed(3)}</td>
                    <td style="padding: 6px; text-align: right; color: ${pctColor};">${pct}%</td>
                    <td style="padding: 6px; text-align: center;"><span style="color:white; background:${qColors[q]}; padding:1px 6px; border-radius:10px; font-size:0.7rem;">${qNames[q]}</span></td>
                </tr>
            `;
        });
    }

    const html = `
        <div style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); margin: 10px 0;">
            <div style="border-bottom: 2px solid #f1f5f9; padding-bottom: 8px; margin-bottom: 12px;">
                <div style="font-weight: 800; color: #0f172a; font-size: 1.05rem;">${title}</div>
                <div style="color: #64748b; font-size: 0.8rem;">${subTitle}</div>
            </div>

            <div style="margin-bottom: 15px;">
                <div style="font-size: 0.75rem; color: #94a3b8; font-weight: bold; margin-bottom: 4px; text-transform: uppercase;">1. ${isEn ? 'Axis Summary' : '軸向匯總'}</div>
                <table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">
                    ${axisHeader}
                    <tbody>${axisRows}</tbody>
                </table>
            </div>

            <div>
                <div style="font-size: 0.75rem; color: #94a3b8; font-weight: bold; margin-bottom: 4px; text-transform: uppercase;">2. ${isEn ? 'Allocation Detail' : '公差分配明細 (Q1-Q4)'}</div>
                <div style="max-height: 200px; overflow-y: auto; border: 1px solid #f1f5f9; border-radius: 6px;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead style="background:#f8fafc; position:sticky; top:0; font-size:0.75rem; color:#64748b; text-align:right;">
                            <tr><th style="text-align:left; padding:6px;">項目</th><th style="padding:6px;">原值</th><th style="padding:6px;">現值</th><th style="padding:6px;">變動</th><th style="padding:6px; text-align:center;">診斷</th></tr>
                        </thead>
                        <tbody>${changeRows}</tbody>
                    </table>
                </div>
                <!-- 四象限圖例 -->
                <div style="margin-top:8px; display:flex; flex-wrap:wrap; gap:6px; font-size:0.72rem;">
                    <div style="display:flex; align-items:center; gap:4px;"><span style="background:#dc2626;color:#fff;padding:1px 7px;border-radius:10px;font-weight:bold;">Q1</span><span style="color:#374151;">${isEn ? 'High sens × High contrib → Tighten first' : '高敏感 × 高貢獻 → 優先收緊'}</span></div>
                    <div style="display:flex; align-items:center; gap:4px;"><span style="background:#2563eb;color:#fff;padding:1px 7px;border-radius:10px;font-weight:bold;">Q2</span><span style="color:#374151;">${isEn ? 'High sens × Low contrib → Guard, do not loosen' : '高敏感 × 低貢獻 → 規格嚴守，不可放寬'}</span></div>
                    <div style="display:flex; align-items:center; gap:4px;"><span style="background:#d97706;color:#fff;padding:1px 7px;border-radius:10px;font-weight:bold;">Q3</span><span style="color:#374151;">${isEn ? 'Low sens × High contrib → Tolerance too large, easy win' : '低敏感 × 高貢獻 → 公差過大，收緊可大幅改善'}</span></div>
                    <div style="display:flex; align-items:center; gap:4px;"><span style="background:#16a34a;color:#fff;padding:1px 7px;border-radius:10px;font-weight:bold;">Q4</span><span style="color:#374151;">${isEn ? 'Low sens × Low contrib → Can loosen to save cost' : '低敏感 × 低貢獻 → 可考慮放寬降低成本'}</span></div>
                </div>
            </div>

            <div style="margin-top: 12px; display: flex; gap: 8px;">
                <div style="flex: 1; padding: 10px; background: #f0f9ff; border-radius: 8px; font-size: 0.8rem; color: #0369a1; border-left: 4px solid #0ea5e9;">
                    💡 ${isEn ? 'The analysis panel has been updated with optimized values.' : '報表已根據最新分析結果產生，並同步四象限診斷指標。'}
                </div>
                <button onclick="exportAllocationExcel()" style="background: #0f172a; color: white; border: none; border-radius: 8px; padding: 0 15px; cursor: pointer; font-weight: bold; font-size: 0.85rem; display: flex; align-items: center; gap: 5px;">
                    📥 ${isEn ? 'Export Report' : '導出報表'}
                </button>
            </div>
        </div>
    `;
    
    if (typeof addMessage === 'function') addMessage('ai', html);

    // [核心] 自動觸發左側圖框與數據儀表板更新，展示所有自由度 (6-DOF) 的結果
    if (data.analysisResult && typeof renderAnalysisResult === 'function') {
        renderAnalysisResult(data.analysisResult);
    }
    
    if (data.dsl && typeof renderStructureDirectly === 'function') {
        const graphContainer = document.getElementById('chat-graph-container');
        if (graphContainer) {
            renderStructureDirectly(data.dsl, graphContainer, 'allocation');
        }
    }
}

/**

 * 導出專業調配對比報表 (Excel)
 */
async function exportAllocationExcel() {
    if (!window._lastAllocationResult) {
        alert(window.CURRENT_LANG === 'en' ? "No allocation data found." : "找不到最近的調配數據。");
        return;
    }
    
    try {
        const res = await fetch('/api/export_allocation_excel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prevPathData: window._lastAllocationResult.prevPathData,
                newPathData:  window._lastAllocationResult.newPathData,
                report:       window._lastAllocationResult.report,
                analysisResult: window._lastAllocationResult.analysisResult,
                lang:         window.CURRENT_LANG
            })
        });
        
        if (!res.ok) throw new Error("Export failed");
        
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `Tolerance_Allocation_Report_${Date.now()}.xlsx`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        
    } catch (e) {
        alert("Export Error: " + e.message);
    }
}

// ══════════════════════════════════════════════
// 6. STEP 3D 檢視器面板控制
// ══════════════════════════════════════════════

function openStepViewerPanel() {
  const panel = document.getElementById('step-viewer-panel');
  const resizer = document.getElementById('step-viewer-resizer');
  if (!panel) return;
  panel.style.display = 'flex';
  if (resizer) resizer.style.display = 'block';

  // 初始化 Three.js（只做一次）
  if (typeof StepViewer !== 'undefined' && !window._stepViewerInitialized) {
    const ok = StepViewer.init('step-viewer-container');
    if (ok) window._stepViewerInitialized = true;
  }
}

// ══════════════════════════════════════════════
// STEP 3D 檢視器面板：左右拖拉調整寬度
// ══════════════════════════════════════════════
(function initStepViewerResizer() {
  const resizer = document.getElementById('step-viewer-resizer');
  const panel   = document.getElementById('step-viewer-panel');
  const appLayout = document.querySelector('.app-layout');
  if (!resizer || !panel || !appLayout) return;

  let isResizing = false;

  resizer.addEventListener('mousedown', (e) => {
    isResizing = true;
    resizer.style.background = '#0ea5e9';
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
  });

  resizer.addEventListener('mouseenter', () => {
    if (!isResizing) resizer.style.background = '#0ea5e9';
  });
  resizer.addEventListener('mouseleave', () => {
    if (!isResizing) resizer.style.background = '#64748b';
  });

  document.addEventListener('mousemove', (e) => {
    if (!isResizing) return;
    const rect = appLayout.getBoundingClientRect();
    // 面板貼右邊，所以用「右緣 - 滑鼠 X」當寬度
    let newWidth = rect.right - e.clientX;
    const minWidth = 380;
    const maxWidth = rect.width * 0.8;
    newWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));
    panel.style.width = newWidth + 'px';

    // 通知 Three.js viewer 重繪（如果有 onWindowResize）
    if (typeof StepViewer !== 'undefined' && StepViewer.onResize) StepViewer.onResize();
    window.dispatchEvent(new Event('resize'));
  });

  document.addEventListener('mouseup', () => {
    if (!isResizing) return;
    isResizing = false;
    resizer.style.background = '#64748b';
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  });
})();


function closeStepViewerPanel() {
  const panel = document.getElementById('step-viewer-panel');
  const resizer = document.getElementById('step-viewer-resizer');
  if (panel) panel.style.display = 'none';
  if (resizer) resizer.style.display = 'none';
}

/**
 * STEP 3D Viewer 面板左右拖拉 resizer（初始化一次，全域綁定）
 */
(function initStepViewerResizer() {
  const resizer = document.getElementById('step-viewer-resizer');
  const panel = document.getElementById('step-viewer-panel');
  const appLayout = document.querySelector('.app-layout');
  if (!resizer || !panel || !appLayout) return;

  let isResizing = false;

  resizer.addEventListener('mousedown', (e) => {
    isResizing = true;
    resizer.style.background = '#0ea5e9';
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
  });

  resizer.addEventListener('mouseenter', () => {
    if (!isResizing) resizer.style.background = '#0ea5e9';
  });

  resizer.addEventListener('mouseleave', () => {
    if (!isResizing) resizer.style.background = '#64748b';
  });

  document.addEventListener('mousemove', (e) => {
    if (!isResizing) return;
    const rect = appLayout.getBoundingClientRect();
    // 從右邊界往左算新寬度
    let newWidth = rect.right - e.clientX;
    const minWidth = 380;
    const maxWidth = rect.width * 0.65;
    newWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));
    panel.style.width = newWidth + 'px';
  });

  document.addEventListener('mouseup', () => {
    if (!isResizing) return;
    isResizing = false;
    resizer.style.background = '#64748b';
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  });
})();

/**
 * 上傳 STEP 檔案：只建立 session + 顯示 3D 幾何。
 * 不自動跑 PMI 解析（由「比對 & 解析 PMI」按鈕觸發，對齊舊 Tkinter 版三步驟流程）。
 */
function uploadStepFile(file) {
  if (!file) return;
  console.log(`📤 上傳 STEP: ${file.name}`);

  const formData = new FormData();
  formData.append('stp_file', file);

  fetch('/api/step/upload', { method: 'POST', body: formData })
    .then(r => r.json())
    .then(data => {
      if (!data.ok) { alert(`❌ 上傳失敗: ${data.error}`); return; }
      window._stepSessionId = data.session_id;
      console.log(`✅ Session 建立: ${data.session_id}`);

      // 清空舊的 PMI 清單與高亮（新 session 開始）
      if (typeof PmiPanel !== 'undefined') PmiPanel.clear();
      if (typeof StepViewer !== 'undefined') StepViewer.clearGeometry();

      // 立即載入 3D 幾何（淺灰半透明底模），但不跑 PMI 解析
      if (typeof StepViewer !== 'undefined') {
        StepViewer.loadAllGeometry(window._stepSessionId, 0.3);
      }

      alert('✅ STEP 已上傳，3D 模型已載入。\n接著請載入 XLSX，然後點擊「比對 & 解析 PMI」。');
    })
    .catch(err => { console.error('❌ 錯誤:', err); alert('發生錯誤: ' + err.message); });
}

/**
 * 上傳 XLSX 檔案到已有的 session（對齊舊版獨立上傳）。
 * 不跑解析，只把 XLSX 附到 session，等按鈕觸發。
 */
function uploadXlsxFile(file) {
  if (!file) return;
  if (!window._stepSessionId) {
    alert('❌ 請先上傳 STEP 檔案');
    return;
  }
  console.log(`📊 上傳 XLSX: ${file.name} (Session: ${window._stepSessionId})`);

  const formData = new FormData();
  formData.append('xlsx_file', file);
  formData.append('session_id', window._stepSessionId);

  fetch('/api/step/upload_xlsx', { method: 'POST', body: formData })
    .then(r => r.json())
    .then(data => {
      if (!data.ok) { alert(`❌ XLSX 上傳失敗: ${data.error}`); return; }
      console.log(`✅ XLSX 已附加到 session`);
      alert('✅ XLSX 已載入，請點擊「比對 & 解析 PMI」開始解析。');
    })
    .catch(err => { console.error('❌ 錯誤:', err); alert('發生錯誤: ' + err.message); });
}

/**
 * 手動觸發 PMI 解析（「比對 & 解析 PMI」按鈕）
 */
function parsePMI() {
  if (!window._stepSessionId) { alert('❌ 請先上傳 STEP 檔案'); return; }
  console.log(`🔍 手動觸發 PMI 解析 (Session: ${window._stepSessionId})`);
  fetch('/api/step/parse_pmi', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: window._stepSessionId })
  })
    .then(r => r.json())
    .then(data => {
      if (!data.ok) { alert(`❌ 解析失敗: ${data.error}`); return; }
      console.log(`✅ PMI 解析完成: ${data.n_pmi_rows} 項`);
      // 注意：STEP 上傳時已經做過三角化，不要重跑 loadAllGeometry（會再三角化一遍）。
      // 這裡只載入 PMI 引線+標註到既有場景，並把 PMI 清單渲染出來。
      if (typeof StepViewer !== 'undefined' && StepViewer.loadAllPmiAnnotations) {
        StepViewer.loadAllPmiAnnotations(window._stepSessionId);
      }
      if (typeof PmiPanel !== 'undefined') PmiPanel.render(data.pmi_rows, window._stepSessionId);
    })
    .catch(err => { console.error('❌ 錯誤:', err); alert('發生錯誤: ' + err.message); });
}

/**
 * 導出 PMI BOM CSV（同時保存到 MySQL）
 */
function exportStepCSV() {
  if (!window._stepSessionId) { alert('❌ 請先上傳 STEP 檔案'); return; }

  const checkedIndices = typeof PmiPanel !== 'undefined' ? PmiPanel.getAllChecked() : [];
  console.log(`📤 導出 CSV: session=${window._stepSessionId}, checked=${checkedIndices.length} 項`);

  fetch('/api/step/export_csv', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: window._stepSessionId,
      mode: 'pmi',
      checked_indices: checkedIndices
    })
  })
    .then(response => {
      if (!response.ok) {
        return response.json().then(data => { throw new Error(data.error || '導出失敗'); });
      }
      return response.blob().then(blob => ({ blob, response }));
    })
    .then(({ blob, response }) => {
      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = 'PMI_Export.csv';
      if (contentDisposition) {
        const match = contentDisposition.match(/filename="(.+?)"/);
        if (match) filename = match[1];
      }
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      console.log(`✅ CSV 已導出: ${filename}`);
      alert(`✅ CSV 已導出並保存到資料庫\n檔案: ${filename}\n勾選項: ${checkedIndices.length}`);
    })
    .catch(err => {
      console.error('❌ 導出錯誤:', err);
      alert(`❌ 導出失敗: ${err.message}`);
    });
}

/**
 * 執行組合件接觸分析（非阻塞版，配合後端背景執行緒）
 */
function runAssemblyContactAnalysis() {
  if (!window._stepSessionId) { alert('❌ 請先上傳 STEP 檔案'); return; }

  const btnLabel = '🔗 分析接觸';
  const btn = event && event.target ? event.target : null;
  if (btn) { btn.disabled = true; btn.textContent = '⏳ 分析中...'; }

  fetch('/api/step/asm_contact', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: window._stepSessionId })
  })
    .then(r => r.json())
    .then(data => {
      if (!data.ok) {
        alert(`❌ 啟動失敗: ${data.error}`);
        if (btn) { btn.disabled = false; btn.textContent = btnLabel; }
        return;
      }
      // 後端回 202 + poll_url，開始輪詢
      console.log('🔄 分析已啟動，輪詢結果中...');
      _pollAsmResultChat(data.poll_url, btn, btnLabel);
    })
    .catch(err => {
      console.error('❌ 錯誤:', err);
      alert('❌ 分析發生錯誤: ' + err.message);
      if (btn) { btn.disabled = false; btn.textContent = btnLabel; }
    });
}

/**
 * 輪詢 /api/step/asm_result（chat.js 專用，避免與 app.js 的同名函數衝突）
 */
function _pollAsmResultChat(pollUrl, btn, btnLabel) {
  const INTERVAL_MS = 2000;
  let elapsed = 0;
  const MAX_WAIT_MS = 620000;

  const iv = setInterval(async () => {
    elapsed += INTERVAL_MS;
    try {
      const r = await fetch(pollUrl);
      const d = await r.json();

      if (d.status === 'done') {
        clearInterval(iv);
        console.log(`✅ 組合件分析完成: ${d.contacts ? d.contacts.length : 0} 個接觸對`);
        if (typeof renderAsmContactsFromStep !== 'undefined' && d.contacts) {
          renderAsmContactsFromStep(d.contacts);
          addMessage('ai', '🔗 組合件接觸分析完成，接觸圖已更新。');
        }
        if (btn) { btn.disabled = false; btn.textContent = btnLabel; }

      } else if (d.status === 'error') {
        clearInterval(iv);
        alert(`❌ 分析失敗: ${d.error}`);
        if (btn) { btn.disabled = false; btn.textContent = btnLabel; }

      } else if (elapsed >= MAX_WAIT_MS) {
        clearInterval(iv);
        alert('❌ 分析等待超時，請重試');
        if (btn) { btn.disabled = false; btn.textContent = btnLabel; }
      }
    } catch (err) {
      clearInterval(iv);
      console.error('❌ 輪詢錯誤:', err);
      alert('❌ 分析發生錯誤: ' + err.message);
      if (btn) { btn.disabled = false; btn.textContent = btnLabel; }
    }
  }, INTERVAL_MS);
}
