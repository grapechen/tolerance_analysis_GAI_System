/* plan_compare.js — 方案一（單對輸入）+ 方案二（路徑分析+指令調整） */
(function () {
  'use strict';

  const $ = (id) => document.getElementById(id);

  // ═══════════════════ Modal 開關 ═══════════════════
  window.openPlanCompareModal = function () {
    const m = $('plan-compare-modal'); if (m) m.classList.add('open');
  };
  window.closePlanCompareModal = function () {
    const m = $('plan-compare-modal'); if (m) m.classList.remove('open');
  };
  document.addEventListener('click', (e) => {
    const m = $('plan-compare-modal');
    if (m && e.target === m) closePlanCompareModal();
  });

  // ═══════════════════ 方案一：特徵驅動推薦 ═══════════════════

  let featuresCache = null;

  // 開 Modal 時載入特徵清單
  const _origOpen = window.openPlanCompareModal;
  window.openPlanCompareModal = function () {
    _origOpen();
    if (!featuresCache) loadFeatures();
  };

  async function loadFeatures() {
    try {
      const r = await fetch('/api/plan1/features');
      const j = await r.json();
      if (!j.ok) throw new Error(j.msg || '載入特徵失敗');
      featuresCache = j.features;
      const sel = $('pc1-feature');
      sel.innerHTML = '<option value="">— 請選擇 —</option>';
      // 依零件分組
      const byPart = {};
      featuresCache.forEach(f => {
        if (!byPart[f.part]) byPart[f.part] = [];
        byPart[f.part].push(f);
      });
      Object.keys(byPart).sort().forEach(part => {
        const og = document.createElement('optgroup');
        og.label = part;
        byPart[part].forEach(f => {
          const o = document.createElement('option');
          o.value = f.feature_id;
          o.textContent = `${f.feature_id}  (${featureTypeZh(f.feature_type)}, Φ${f.nominal_mm || '?'})${f.note ? ' — ' + f.note : ''}`;
          og.appendChild(o);
        });
        sel.appendChild(og);
      });
    } catch (e) {
      setStatus('pc1-status', '✗ 載入特徵失敗: ' + e.message, 'err');
    }
  }

  // 選了特徵後，更新 hint + 顯示 override 區
  $('pc1-feature')?.addEventListener('change', () => {
    const fid = $('pc1-feature').value;
    if (!fid || !featuresCache) {
      $('pc1-feature-info').textContent = '選擇一個特徵面後，下方會顯示已標註的公差。';
      $('pc1-overrides-row').style.display = 'none';
      return;
    }
    const f = featuresCache.find(x => x.feature_id === fid);
    if (f) {
      $('pc1-feature-info').innerHTML =
        `已選：<strong>${esc(f.feature_id)}</strong>　類型：${featureTypeZh(f.feature_type)}　公稱：Φ${f.nominal_mm || '?'}　${f.note ? `<span style="color:#94a3b8;">— ${esc(f.note)}</span>` : ''}`;
      $('pc1-overrides-row').style.display = 'block';
      // 清空 override 欄位
      ['Cir','Cyl','Per','Par','Co','Fla','it_dim'].forEach(k => { const el = $('ov-'+k); if (el) el.value = ''; });
    }
  });

  $('pc1-go')?.addEventListener('click', runPlan1);

  async function runPlan1() {
    const fid = $('pc1-feature').value;
    if (!fid) {
      setStatus('pc1-status', '請選擇特徵面', 'err');
      return;
    }
    // 收集 override
    const overrides = {};
    ['Cir','Cyl','Per','Par','Co','Fla'].forEach(k => {
      const v = $('ov-'+k)?.value.trim();
      if (v !== '') overrides[k] = Number(v);
    });
    const itOv = $('ov-it_dim')?.value.trim();
    if (itOv !== '') overrides.it_dim = Number(itOv);

    setStatus('pc1-status', '推薦中…', 'running');
    $('pc1-go').disabled = true;
    try {
      const r = await fetch('/api/plan1/feature_recommend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ feature_id: fid, overrides, safety_factor: 1.7 }),
      });
      const j = await r.json();
      if (!j.ok) throw new Error(j.msg || '推薦失敗');
      renderPlan1(j);
      const np = j.processes ? j.processes.length : 0;
      setStatus('pc1-status', `✓ ${j.geo_grades.length} 項幾何公差，${np} 個推薦製程`, 'ok');
    } catch (e) {
      setStatus('pc1-status', '✗ ' + e.message, 'err');
    } finally {
      $('pc1-go').disabled = false;
    }
  }

  function featureTypeZh(t) {
    return ({P:'平面', H:'內圓柱面', S:'外圓柱面', C:'錐面'})[t] || t;
  }

  function renderPlan1(r) {
    $('pc1-result').style.display = 'block';
    $('pc1-feature-title').textContent = `${r.feature_id} (${r.feature_zh})`;
    const summary = [
      `Φ${r.nominal_mm || '?'} mm`,
      r.it_dim ? `IT${r.it_dim}` : null,
      ...Object.entries(r.geo_tolerances || {}).map(([k,v]) => `${k}=${v}`),
    ].filter(Boolean).join('　');
    $('pc1-feature-summary').textContent = summary;

    // 幾何公差等級表
    const tbody = $('pc1-grades-tbody');
    tbody.innerHTML = '';
    if (!r.geo_grades || r.geo_grades.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" class="pc-empty">該特徵未標註幾何公差，僅按尺寸 IT 推薦製程</td></tr>';
    } else {
      r.geo_grades.forEach(g => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td><strong>${esc(g.geo_code)}</strong></td>
          <td>${g.value_um} μm</td>
          <td><span class="pc-cat-pill cat-tight">IT${g.estimated_grade}</span></td>
          <td>${esc(g.application_zh)}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    // 推薦製程清單
    const procs = $('pc1-processes');
    procs.innerHTML = '';
    if (!r.processes || r.processes.length === 0) {
      procs.innerHTML = '<div class="pc-empty">沒有匹配的製程，請檢查公差需求</div>';
      return;
    }
    r.processes.forEach((p, i) => {
      const card = document.createElement('div');
      card.className = 'pc-proc-card' + (p.external ? ' pc-proc-external' : '');
      const machinesHtml = (p.machines || []).map(m => `
        <li>
          <code>${esc(m.model)}</code>
          <span class="pc-band">[${esc(m.attr)}]</span>
          <span class="pc-band">重現精度 ${m.repeat_mm ?? '—'} mm</span>
          ${m.note ? `<span style="color:#94a3b8;font-size:11px;">${esc(m.note)}</span>` : ''}
        </li>
      `).join('') || '<li class="pc-empty">無符合精度需求的機台</li>';
      const chainHtml = (p.chain || []).map(c => esc(c.process_en)).join(' → ');
      card.innerHTML = `
        <div class="pc-proc-head">
          <span class="pc-proc-num">${i+1}.</span>
          <span class="pc-proc-name">${esc(p.process_zh)}</span>
          <span class="pc-cat-pill cat-${p.external ? 'tight' : 'loose'}">${p.external ? '外部委外' : '內部'}</span>
          <span class="pc-band">${esc(p.category)}　|　${esc(p.equipment)}　|　Ra ${p.Ra ? p.Ra[0]+'~'+p.Ra[1]+' μm' : '—'}</span>
        </div>
        <div class="pc-proc-it">
          IT 尺寸: ${itRange(p.it_dim)}　|
          形狀(圓度/圓柱度/平面度): ${itRange(p.it_circ)}　|
          平行/垂直度: ${itRange(p.it_par_perp)}　|
          同心/對稱/偏擺: ${itRange(p.it_concentric)}
        </div>
        <div class="pc-proc-chain">製程鏈: ${chainHtml || '—'}</div>
        <div class="pc-proc-machines">
          <div style="color:#94a3b8;font-size:11px;margin-bottom:4px;">可用機台 (${(p.machines || []).length}):</div>
          <ul>${machinesHtml}</ul>
        </div>
      `;
      procs.appendChild(card);
    });
  }

  function itRange(rng) {
    if (!rng || rng[0] == null) return '—';
    return rng[0] === rng[1] ? `IT${rng[0]}` : `IT${rng[0]}~IT${rng[1]}`;
  }

  // ═══════════════════ 方案二：① 路徑分析 ═══════════════════

  let analysisCache = null;

  $('pc2-analyze')?.addEventListener('click', runAnalyze);

  function getEditorPathData() {
    // 從前端全域取得使用者編輯的公差累積路徑
    return Array.isArray(window.editorPathData) ? window.editorPathData : null;
  }

  async function runAnalyze() {
    const pathData = getEditorPathData();
    if (!pathData || pathData.length === 0) {
      setStatus('pc2-analyze-status', '✗ 請先點「編輯公差路徑」建立公差累積路徑', 'err');
      return;
    }

    setStatus('pc2-analyze-status', '分析中…', 'running');
    $('pc2-analyze').disabled = true;
    try {
      const r = await fetch('/api/plan2/analyze_path', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path_data: pathData }),
      });
      const j = await r.json();
      if (!j.ok) throw new Error(j.msg || '分析失敗');
      analysisCache = j;
      renderAnalysis(j);
      $('pc2-analysis-card').style.display = 'block';
      $('pc2-command-block').style.display = 'block';
      setStatus('pc2-analyze-status',
        `✓ RSS=${j.rss_um}μm WC=${j.wc_um}μm（${j.items_count}項公差，${j.spatial_count}項位移）`, 'ok');
    } catch (e) {
      setStatus('pc2-analyze-status', '✗ ' + e.message, 'err');
    } finally {
      $('pc2-analyze').disabled = false;
    }
  }

  function renderAnalysis(j) {
    $('pc2-rss-before').textContent = j.rss_um;
    $('pc2-wc-before').textContent  = j.wc_um;
    $('pc2-chain-display').textContent = `${j.items_count} 項公差（來自 editorPathData）`;

    const tbody = $('pc2-analysis-tbody');
    tbody.innerHTML = '';
    j.items.forEach(it => {
      const tr = document.createElement('tr');
      if (it.rank === 1) tr.classList.add('pc-rank-top');
      tr.innerHTML = `
        <td class="pc-id">#${it.rank}</td>
        <td class="pc-id">${esc(it.name)}</td>
        <td>${esc(it.part || '—')}</td>
        <td>${it.nominal_size != null ? it.nominal_size : '—'}</td>
        <td>${esc(it.it_grade || '—')}</td>
        <td>${esc(it.tol_type || '—')}</td>
        <td>${it.val_um}</td>
        <td><strong>${it.contribution_pct.toFixed(1)}%</strong></td>
      `;
      tbody.appendChild(tr);
    });
  }

  // ═══════════════════ 方案二：② 指令套用 ═══════════════════

  $('pc2-apply')?.addEventListener('click', runApply);

  async function runApply() {
    const pathData = getEditorPathData();
    if (!pathData || pathData.length === 0) {
      setStatus('pc2-apply-status', '✗ 請先建立公差累積路徑並執行分析', 'err');
      return;
    }
    const command = $('pc2-command').value.trim();
    if (!command) {
      setStatus('pc2-apply-status', '請輸入指令', 'err');
      return;
    }
    setStatus('pc2-apply-status', '解析中…', 'running');
    $('pc2-apply').disabled = true;
    try {
      const r = await fetch('/api/plan2/apply_command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path_data: pathData, command }),
      });
      const j = await r.json();
      if (!j.ok) {
        let msg = j.msg || '套用失敗';
        if (j.parsed) msg += `（已解析：${j.parsed.target_name}, ${j.parsed.action} 至 IT${j.parsed.target_it}）`;
        throw new Error(msg);
      }
      renderApplyResult(j);
      $('pc2-result-card').style.display = 'block';
      setStatus('pc2-apply-status',
        `✓ 套用至 ${j.target_name}  RSS Δ=${j.rss_delta_um >= 0 ? '+' : ''}${j.rss_delta_um}μm`, 'ok');
    } catch (e) {
      setStatus('pc2-apply-status', '✗ ' + e.message, 'err');
    } finally {
      $('pc2-apply').disabled = false;
    }
  }

  function renderApplyResult(j) {
    $('pc2-rss-r-before').textContent = j.rss_before_um;
    $('pc2-rss-r-after').textContent  = j.rss_after_um;
    const dEl = $('pc2-rss-delta');
    const d = j.rss_delta_um;
    dEl.innerHTML = `<span class="${d > 0 ? 'pc-pos' : d < 0 ? 'pc-neg' : ''}">(${d >= 0 ? '+' : ''}${d}μm)</span>`;

    const p = j.parsed || {};
    const fromIt = p.target_it - (p.action === '放寬' ? 1 : (p.action === '收緊' ? -1 : 0));
    $('pc2-parsed-info').innerHTML = `
      <div><strong>解析結果：</strong>
        零件 = ${esc(p.part_name_zh)} (編號 ${esc(p.part_id)})，
        目標 = ${esc(p.target_name)}，
        動作 = <strong>${esc(p.action)}</strong>，
        IT${esc(fromIt)} → IT${esc(p.target_it)}
      </div>
      <div style="color:#94a3b8;margin-top:4px;font-size:12px;">
        命中路徑項目：<strong>${esc(j.target_name)}</strong>（index ${j.target_index}）
      </div>
    `;

    const tbody = $('pc2-result-tbody');
    tbody.innerHTML = '';
    if (!analysisCache) return;
    const c = j.change;
    analysisCache.items.forEach(it => {
      const isTarget = it.name === j.target_name;
      const tr = document.createElement('tr');
      if (isTarget) tr.classList.add('pc-target-row');
      tr.innerHTML = `
        <td class="pc-id">${esc(it.name)}</td>
        <td>${esc(it.part || '—')}</td>
        <td>${it.nominal_size != null ? it.nominal_size : '—'}</td>
        <td>${esc(isTarget ? c.before.it_grade : it.it_grade || '—')}</td>
        <td>${isTarget ? `${c.before.val_um} μm` : `${it.val_um} μm`}</td>
        <td>${isTarget ? `<code>${c.after.it_grade}</code> · ${c.after.val_um} μm` : '—'}</td>
        <td class="${isTarget && c.delta_um < 0 ? 'pc-neg' : isTarget && c.delta_um > 0 ? 'pc-pos' : ''}">${isTarget ? (c.delta_um >= 0 ? '+' : '') + c.delta_um.toFixed(1) : '—'}</td>
      `;
      tbody.appendChild(tr);
    });
  }

  // ═══════════════════ 工具 ═══════════════════

  function setStatus(id, text, cls) {
    const s = $(id);
    if (!s) return;
    s.textContent = text;
    s.className = 'pc-status ' + (cls || '');
  }
  function categoryClass(cat) {
    if (!cat) return 'transition';
    if (cat.includes('緊')) return 'tight';
    if (cat.includes('鬆')) return 'loose';
    return 'transition';
  }
  function esc(s) {
    if (s == null) return '';
    return String(s).replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }
})();
