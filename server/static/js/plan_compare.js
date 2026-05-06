/* plan_compare.js — 公差配合推薦 */
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

  // ═══════════════════ 初版：公差配合推薦 ═══════════════════

  let featuresCache = null;

  // 開 Modal 時載入特徵清單 + 維度面板 + preset 按鈕
  const _origOpen = window.openPlanCompareModal;
  window.openPlanCompareModal = function () {
    _origOpen();
    if (!featuresCache) loadFeatures();
    pc1InitDimensions();
    pc1RenderPresets();
  };

  // ═══════════════════ 初版：功能描述/維度勾選 ═══════════════════

  // 全域維度狀態：{ '中速旋轉': 'required', '精確': 'optional', ... }
  window._pc1DimState = window._pc1DimState || {};

  // 零件配對對應（依「功能描述查詢指南」§四）
  // 每筆 { partA, partB, partB_label, required, expected_ansi, fit_text }
  // partB_label 是顯示給使用者看的「配合對象 — 功能描述」字樣
  const PC1_PART_PAIRS = [
    { partA: '工作臺(1)',     partB: '工作臺心軸(5)',     partB_label: '工作臺心軸(5)（螺栓+定位銷）',  required: ['定位','精確','過渡','可裝拆'], expected_ansi: 'H7/k6', fit_text: 'H7/k6' },
    { partA: '軸承座(2)',     partB: '軸承(3) 外圈',        partB_label: '軸承(3) 外圈（YRT 螺栓鎖附）', required: ['定位','固定'],                  expected_ansi: 'H6',    fit_text: 'H6' },
    { partA: '軸承座(2)',     partB: '馬達水套(7)',           partB_label: '馬達水套(7)',                   required: ['定位','固定','可裝拆'],         expected_ansi: 'H7/h6', fit_text: 'H7/h6' },
    { partA: '軸承YRT(3)',   partB: '工作臺心軸(5) 內圈',   partB_label: '工作臺心軸(5) 內圈（YRT 螺栓鎖附）', required: ['定位','過渡'],            expected_ansi: 'js5',   fit_text: 'js5' },
    { partA: '轉動軸(4)',     partB: '工作臺心軸(5)',         partB_label: '工作臺心軸(5)（永久固定）',     required: ['壓入','強制壓入'],            expected_ansi: 'H7/u6', fit_text: 'H7/u6' },
    { partA: '馬達(6)',         partB: '馬達水套(7)',           partB_label: '馬達水套(7)（永久固定）',         required: ['壓入','中壓入'],              expected_ansi: 'H7/s6', fit_text: 'H7/s6' },
    { partA: '馬達水套(7)',   partB: '馬達座(10)',           partB_label: '馬達座(10)',                   required: ['定位','固定','可裝拆'],         expected_ansi: 'H7/h6', fit_text: 'H7/h6' },
    { partA: '編碼器心軸(8)', partB: '工作臺心軸(5)',         partB_label: '工作臺心軸(5)（同軸用）',         required: ['定位','精確','可裝拆'],         expected_ansi: 'H7/h6', fit_text: 'H7/h6' },
    { partA: '分流座(9)',     partB: '馬達座(10)',           partB_label: '馬達座(10)',                   required: ['定位','固定','可裝拆'],         expected_ansi: 'H7/h6', fit_text: 'H7/h6' },
    { partA: '編碼器(11)',     partB: '編碼器心軸(8)',         partB_label: '編碼器心軸(8)',                 required: ['定位','固定','可裝拆'],         expected_ansi: 'H7/h6', fit_text: 'H7/h6' },
  ];

  // 11 個零件（含被動角色 工作臺心軸(5) / 馬達座(10)）
  // 各零件適用的維度群組（不在清單內的群組會隱藏）
  const _PART_DIM_GROUPS = {
    '工作臺(1)':     ['用途', '裝配', '環境'],
    '軸承座(2)':     ['用途', '裝配', '軸頸壓力', '環境'],
    '轉動軸(4)':     ['用途', '裝配', '壓入強度'],
    '工作臺心軸(5)': ['用途', '裝配', '速度', '動作型態', '環境'],
    '馬達(6)':       ['用途', '裝配', '壓入強度', '速度'],
    '馬達水套(7)':   ['用途', '裝配', '環境'],
    '編碼器心軸(8)': ['用途', '裝配', '壓入強度'],
    '分流座(9)':     ['用途', '裝配'],
    '馬達座(10)':    ['用途', '裝配'],
    '編碼器(11)':    ['用途', '裝配'],
  };

  function _filterDimGroups(part) {
    const allowed = _PART_DIM_GROUPS[part];
    document.querySelectorAll('#pc1-dim-groups .smart-dim-group').forEach(grp => {
      const label = grp.querySelector('.smart-dim-group-label')?.textContent?.trim();
      grp.style.display = (!allowed || allowed.includes(label)) ? '' : 'none';
    });
  }

  const PC1_PARTS = [
    '工作臺(1)', '軸承座(2)', '軸承YRT(3)', '轉動軸(4)', '工作臺心軸(5)',
    '馬達(6)', '馬達水套(7)', '編碼器心軸(8)', '分流座(9)', '馬達座(10)', '編碼器(11)',
  ];

  // 由零件查它在 §四 中所有的配對（含被動角色：partA 或 partB 都算）
  function pc1PairsForPart(part) {
    return PC1_PART_PAIRS.filter(p => p.partA === part || p.partB === part || p.partB.startsWith(part));
  }

  // 當前選中的配對
  let _pc1ActivePreset = null;  // 被選中的 PC1_PART_PAIRS 元素
  let _pc1CurrentPart  = null;  // 目前選中的零件名稱
  // 每個零件的已儲存狀態 { [partName]: { dimState, results, dims, activePreset } }
  const _pc1PartStates = {};

  function pc1RenderParts() {
    const wrap = $('pc1-part-buttons');
    if (!wrap || wrap.dataset.loaded === 'true') return;
    let html = '';
    PC1_PARTS.forEach((part) => {
      html += `<button type="button" class="pc1-preset-btn"
                 data-part="${part}" onclick="pc1SelectPart('${part}')">
                 ${part}
               </button>`;
    });
    wrap.innerHTML = html;
    wrap.dataset.loaded = 'true';
  }

  // 保留舊名稱以相容於 openPlanCompareModal
  function pc1RenderPresets() { pc1RenderParts(); }

  // 步驟 ①：點零件 → 直接顯示推薦配合卡片
  window.pc1SelectPart = function (part) {
    _pc1CurrentPart = part;
    _filterDimGroups(part);

    // 高亮零件按鈕 + ✓ 標記
    document.querySelectorAll('#pc1-part-buttons .pc1-preset-btn').forEach(b => {
      const isActive = b.dataset.part === part;
      const hasSaved = !!_pc1PartStates[b.dataset.part];
      b.classList.toggle('pc1-preset-active', isActive);
      b.querySelector('.pc1-saved-badge')?.remove();
      if (hasSaved && !isActive) {
        const badge = document.createElement('span');
        badge.className = 'pc1-saved-badge';
        badge.textContent = ' ✓';
        b.appendChild(badge);
      }
    });

    // 渲染直接推薦卡片
    const pairs   = pc1PairsForPart(part);
    const section = $('pc1-pair-section');
    const wrap    = $('pc1-pair-buttons');
    const label   = $('pc1-pair-label');
    if (!section || !wrap) return;

    if (!pairs.length) {
      wrap.innerHTML = `<div class="pc-empty">該零件未在配對清單中</div>`;
      section.style.display = 'block';
      return;
    }

    if (label) label.textContent = `${part} 的建議配合：`;

    const saved = _pc1PartStates[part];
    wrap.innerHTML = pairs.map(pair => {
      const idx      = PC1_PART_PAIRS.indexOf(pair);
      const added    = saved?.activePreset === pair;
      const reqTxt   = pair.required.join(' ＋ ');
      return `
        <div class="pc1-rec-card${added ? ' pc1-rec-card--added' : ''}" data-idx="${idx}">
          <div class="pc1-rec-counterpart">→ ${esc(pair.partB_label || pair.partB)}</div>
          <div class="pc1-rec-needs">${esc(reqTxt)}</div>
          <div class="pc1-rec-fit">推薦配合：<strong>${esc(pair.fit_text)}</strong></div>
          <div class="pc1-rec-actions">
            ${added
              ? `<span class="pc1-rec-added-label">✓ 已加入報表</span>
                 <button class="pc1-rec-btn-cancel" onclick="pc1RemoveFromReport(${idx}, this)">✕ 取消</button>
                 <button class="pc1-rec-btn-alt" onclick="pc1ApplyTemplate(${idx})">🔍 搜尋替代配合</button>`
              : `<button class="pc1-rec-btn-add" onclick="pc1AddToReport(${idx}, this)">＋ 加入報表</button>
                 <button class="pc1-rec-btn-alt" onclick="pc1ApplyTemplate(${idx})">🔍 搜尋替代配合</button>`
            }
          </div>
        </div>`;
    }).join('');

    section.style.display = 'block';

    // 還原已存的維度狀態（供「搜尋替代配合」用）
    if (saved) {
      _pc1ActivePreset = saved.activePreset;
      window._pc1DimState = Object.assign({}, saved.dimState);
      document.querySelectorAll('#pc1-dim-groups .dim-chip').forEach(chip => {
        const zh = chip.dataset.zh;
        chip.classList.remove('dim-state-required', 'dim-state-optional');
        if (saved.dimState[zh] === 'required')  chip.classList.add('dim-state-required');
        if (saved.dimState[zh] === 'optional') chip.classList.add('dim-state-optional');
      });
    } else {
      _pc1ActivePreset = null;
      window._pc1DimState = {};
      document.querySelectorAll('#pc1-dim-groups .dim-chip')
        .forEach(c => c.classList.remove('dim-state-required', 'dim-state-optional'));
    }
    // 預設隱藏維度搜尋面板（只在「搜尋替代配合」時展開）
    const dimResult = $('pc1-dim-result');
    if (dimResult && !saved?.resultVisible) dimResult.style.display = 'none';
  };

  // 加入報表：自動用預設維度搜尋 → 取 top 結果 → 存入 PartStates → 更新批量清單
  window.pc1AddToReport = async function (idx, btnEl) {
    const pair = PC1_PART_PAIRS[idx];
    if (!pair || !_pc1CurrentPart) return;

    if (btnEl) { btnEl.disabled = true; btnEl.textContent = '搜尋中…'; }

    try {
      const dims = { required: pair.required, optional: [] };
      const r    = await fetch('/api/recommend/smart_fit', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dimensions: dims }),
      });
      const j = await r.json();
      if (!j.ok) throw new Error(j.msg);

      const results = j.results || [];
      // 優先選與 fit_text 相符的結果
      const top = results.find(rr => rr.ansi === pair.fit_text || rr.ansi === pair.expected_ansi)
                  || results[0];

      // 存入 PartStates
      _pc1PartStates[_pc1CurrentPart] = {
        dimState:     Object.fromEntries(pair.required.map(k => [k, 'required'])),
        activePreset: pair,
        rawResults:   results,
        dims,
        resultsHtml:  '',
        summaryText:  pair.required.join(' ＋ '),
        resultVisible: false,
      };

      // 更新卡片 UI
      const card = btnEl?.closest('.pc1-rec-card');
      if (card) {
        card.classList.add('pc1-rec-card--added');
        const actions = card.querySelector('.pc1-rec-actions');
        if (actions) actions.innerHTML =
          `<span class="pc1-rec-added-label">✓ 已加入報表${top ? '（' + top.ansi + '）' : ''}</span>
           <button class="pc1-rec-btn-cancel" onclick="pc1RemoveFromReport(${idx}, this)">✕ 取消</button>
           <button class="pc1-rec-btn-alt" onclick="pc1ApplyTemplate(${idx})">🔍 搜尋替代配合</button>`;
      }

      // 更新零件按鈕 ✓ 標記
      const partBtn = document.querySelector(`#pc1-part-buttons .pc1-preset-btn[data-part="${_pc1CurrentPart}"]`);
      if (partBtn && !partBtn.querySelector('.pc1-saved-badge')) {
        const badge = document.createElement('span');
        badge.className = 'pc1-saved-badge'; badge.textContent = ' ✓';
        partBtn.appendChild(badge);
      }
    } catch (e) {
      if (btnEl) { btnEl.disabled = false; btnEl.textContent = '＋ 加入報表'; }
      alert('加入失敗：' + e.message);
    }
  };

  // 取消加入報表
  window.pc1RemoveFromReport = function (idx, btnEl) {
    const pair = PC1_PART_PAIRS[idx];
    if (!pair || !_pc1CurrentPart) return;

    // 清除存檔（若存的就是這個 pair）
    const s = _pc1PartStates[_pc1CurrentPart];
    if (s && s.activePreset === pair) {
      delete _pc1PartStates[_pc1CurrentPart];
    }

    // 更新卡片 UI → 回到「加入報表」狀態
    const card = btnEl?.closest('.pc1-rec-card');
    if (card) {
      card.classList.remove('pc1-rec-card--added');
      const actions = card.querySelector('.pc1-rec-actions');
      if (actions) actions.innerHTML =
        `<button class="pc1-rec-btn-add" onclick="pc1AddToReport(${idx}, this)">＋ 加入報表</button>
         <button class="pc1-rec-btn-alt" onclick="pc1ApplyTemplate(${idx})">🔍 搜尋替代配合</button>`;
    }

    // 若該零件沒有其他已加入的配對，移除 ✓ 標記
    const hasOther = Object.values(_pc1PartStates).some(
      v => v && v.activePreset && pc1PairsForPart(_pc1CurrentPart).includes(v.activePreset)
    );
    if (!hasOther) {
      const partBtn = document.querySelector(
        `#pc1-part-buttons .pc1-preset-btn[data-part="${_pc1CurrentPart}"]`
      );
      partBtn?.querySelector('.pc1-saved-badge')?.remove();
    }
  };

  // 搜尋結果選用替代配合 → 存入 PartStates + 更新推薦卡片 + 顯示輸出按鈕
  window.pc1SelectAlternativeFit = function (btnEl, encodedAnsi, encodedItem) {
    if (!_pc1CurrentPart) return;
    const ansi = decodeURIComponent(encodedAnsi);
    let itemData = {};
    try { itemData = JSON.parse(decodeURIComponent(encodedItem)); } catch {}

    // 取得目前的維度狀態
    const dims = { required: [], optional: [] };
    Object.entries(window._pc1DimState || {}).forEach(([k, v]) => {
      if (v === 'required') dims.required.push(k);
      else if (v === 'optional') dims.optional.push(k);
    });

    // 存入 PartStates（覆蓋原本的推薦）
    _pc1PartStates[_pc1CurrentPart] = {
      dimState:     Object.assign({}, window._pc1DimState),
      activePreset: _pc1ActivePreset,
      rawResults:   [itemData],
      dims,
      resultsHtml:  '',
      summaryText:  dims.required.join(' ＋ '),
      resultVisible: true,
    };

    // 標記按鈕為已選
    btnEl.textContent = `✓ 已選用 ${ansi}`;
    btnEl.disabled = true;
    btnEl.style.background = '#166534';

    // 更新推薦卡片的狀態（若對應卡片存在）
    if (_pc1ActivePreset) {
      const pairIdx = PC1_PART_PAIRS.indexOf(_pc1ActivePreset);
      const card = document.querySelector(`#pc1-pair-buttons .pc1-rec-card[data-idx="${pairIdx}"]`);
      if (card) {
        card.classList.add('pc1-rec-card--added');
        const actions = card.querySelector('.pc1-rec-actions');
        if (actions) actions.innerHTML =
          `<span class="pc1-rec-added-label">✓ 已選用替代配合 ${esc(ansi)}</span>
           <button class="pc1-rec-btn-cancel" onclick="pc1RemoveFromReport(${pairIdx}, this)">✕ 取消</button>`;
      }
    }

    // 更新零件按鈕 ✓ 標記
    const partBtn = document.querySelector(
      `#pc1-part-buttons .pc1-preset-btn[data-part="${_pc1CurrentPart}"]`
    );
    if (partBtn && !partBtn.querySelector('.pc1-saved-badge')) {
      const badge = document.createElement('span');
      badge.className = 'pc1-saved-badge'; badge.textContent = ' ✓';
      partBtn.appendChild(badge);
    }

    // 顯示輸出按鈕
    _show('pc1-export-txt');
  };

  // 點配對範本 → 套入維度 + 展開搜尋面板
  window.pc1ApplyTemplate = function (idx) {
    const preset = PC1_PART_PAIRS[idx];
    if (!preset) return;

    // 1. 清空現有 chip 勾選
    window._pc1DimState = {};
    document.querySelectorAll('#pc1-dim-groups .dim-chip').forEach(c => {
      c.classList.remove('dim-state-required', 'dim-state-optional');
    });

    // 2. 標記必選 chip
    preset.required.forEach(zh => {
      window._pc1DimState[zh] = 'required';
      const sel = `#pc1-dim-groups .dim-chip[data-zh="${zh}"]`;
      const btn = document.querySelector(sel);
      if (btn) btn.classList.add('dim-state-required');
    });

    _pc1ActivePreset = preset;
    pc1UpdateDimSummary();

    // 展開維度搜尋面板（搜尋替代配合模式）
    const dimForm = $('pc1-dim-form');
    if (dimForm) dimForm.style.display = '';
    const dimResult = $('pc1-dim-result');
    if (dimResult) dimResult.style.display = 'none';

    const status = $('pc1-dim-status');
    if (status) {
      status.textContent = '已載入 ' + preset.fit_text + ' 的維度，可調整後搜尋替代配合';
      status.className = 'pc-status ok';
    }
  };

  async function pc1InitDimensions() {
    const container = $('pc1-dim-groups');
    if (!container || container.dataset.loaded === 'true') return;
    try {
      const r = await fetch('/api/matchmaking/dimensions');
      const j = await r.json();
      if (!j.ok) return;
      let html = '';
      j.groups.forEach(g => {
        html += `<div class="smart-dim-group">
          <span class="smart-dim-group-label">${g.group_zh}</span>
          <div class="smart-dim-chips">`;
        g.items.forEach(it => {
          const safeZh = it.zh.replace(/"/g, '&quot;');
          html += `<button type="button" class="dim-chip"
                     data-zh="${safeZh}" data-en="${it.en}"
                     onclick="pc1CycleDim(this)" title="${it.en}">${it.zh}</button>`;
        });
        html += `</div></div>`;
      });
      container.innerHTML = html;
      container.dataset.loaded = 'true';
    } catch (e) {
      console.error('[plan_compare] 載入維度失敗:', e);
    }
  }

  window.pc1CycleDim = function (btn) {
    const zh = btn.dataset.zh;
    const cur = window._pc1DimState[zh] || '';
    const next = cur === '' ? 'required' : (cur === 'required' ? 'optional' : '');
    if (next === '') delete window._pc1DimState[zh];
    else window._pc1DimState[zh] = next;
    btn.classList.remove('dim-state-required', 'dim-state-optional');
    if (next) btn.classList.add('dim-state-' + next);
    pc1UpdateDimSummary();
  };

  function pc1UpdateDimSummary() {
    const required = Object.keys(window._pc1DimState).filter(k => window._pc1DimState[k] === 'required');
    const optional = Object.keys(window._pc1DimState).filter(k => window._pc1DimState[k] === 'optional');
    const summary  = $('pc1-dim-summary');
    const clearBtn = $('pc1-dim-clear');
    if (!required.length && !optional.length) {
      if (summary) summary.textContent = '未選擇維度';
      if (clearBtn) clearBtn.style.display = 'none';
    } else {
      const parts = [];
      if (required.length) parts.push(`必選 ${required.length}`);
      if (optional.length) parts.push(`可選 ${optional.length}`);
      if (summary) summary.textContent = '已選 ' + parts.join(' / ');
      if (clearBtn) clearBtn.style.display = 'inline-block';
    }
  }

  window.pc1ClearDims = function () {
    window._pc1DimState = {};
    document.querySelectorAll('#pc1-dim-groups .dim-chip').forEach(c => {
      c.classList.remove('dim-state-required', 'dim-state-optional');
    });
    pc1UpdateDimSummary();
  };

  function pc1GetDimensions() {
    const required = Object.keys(window._pc1DimState).filter(k => window._pc1DimState[k] === 'required');
    const optional = Object.keys(window._pc1DimState).filter(k => window._pc1DimState[k] === 'optional');
    return { required, optional };
  }

  window.pc1RunDimSearch = async function () {
    const dims = pc1GetDimensions();
    if (!dims.required.length && !dims.optional.length) {
      const status = $('pc1-dim-status');
      if (status) { status.textContent = '✗ 請至少勾選一個維度'; status.className = 'pc-status err'; }
      return;
    }
    const status = $('pc1-dim-status');
    const btn    = $('pc1-dim-go');
    if (status) { status.textContent = '搜尋中…'; status.className = 'pc-status running'; }
    if (btn) btn.disabled = true;
    try {
      const r = await fetch('/api/recommend/smart_fit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dimensions: dims }),
      });
      const j = await r.json();
      if (!j.ok) throw new Error(j.msg || '搜尋失敗');
      pc1RenderDimResults(j.results || [], dims);
      if (status) {
        status.textContent = `✓ 找到 ${j.results.length} 筆配合`;
        status.className = 'pc-status ok';
      }
      // 搜尋完成後立即存檔（含原始結果，供載入配對清單使用）
      if (_pc1CurrentPart) {
        _pc1PartStates[_pc1CurrentPart] = {
          dimState:      Object.assign({}, window._pc1DimState),
          activePreset:  _pc1ActivePreset,
          resultsHtml:   $('pc1-dim-list')        ? $('pc1-dim-list').innerHTML          : '',
          summaryText:   $('pc1-dim-summary-line') ? $('pc1-dim-summary-line').textContent : '',
          resultVisible: true,
          rawResults:    j.results || [],   // 原始推薦結果（含IT等級、製程、機台）
          dims,                              // 使用的維度
        };
        // 更新零件按鈕 ✓ 標記
        const btn2 = document.querySelector(`#pc1-part-buttons .pc1-preset-btn[data-part="${_pc1CurrentPart}"]`);
        if (btn2 && !btn2.querySelector('.pc1-saved-badge')) {
          const badge = document.createElement('span');
          badge.className = 'pc1-saved-badge';
          badge.textContent = ' ✓';
          btn2.appendChild(badge);
        }
      }
    } catch (e) {
      if (status) { status.textContent = '✗ ' + e.message; status.className = 'pc-status err'; }
    } finally {
      if (btn) btn.disabled = false;
    }
  };

  function esc(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]); }

  function pc1RenderDimResults(results, dims) {
    const card = $('pc1-dim-result');
    const summaryLine = $('pc1-dim-summary-line');
    const list = $('pc1-dim-list');
    const docBanner = $('pc1-doc-expected');
    if (!card || !list) return;
    card.style.display = 'block';
    const parts = [];
    if (dims.required.length) parts.push(`必選 [${dims.required.join(', ')}]`);
    if (dims.optional.length) parts.push(`可選 [${dims.optional.join(', ')}]`);
    if (summaryLine) summaryLine.textContent = parts.join(' / ');

    // 文件 §四 預期推薦橫幅（僅 preset 觸發時顯示）
    if (docBanner) {
      if (_pc1ActivePreset) {
        const p = _pc1ActivePreset;
        const expectedRow = (results || []).find(r => r.ansi === p.expected_ansi);
        const rank = expectedRow ? (results.indexOf(expectedRow) + 1) : null;
        const rankText = rank ? `（在搜尋結果中排第 ${rank} 名）` : '（未在搜尋結果中）';
        const pairTxt = p.partA && p.partB ? `${esc(p.partA)} ↔ ${esc(p.partB)}` : '';
        docBanner.innerHTML = `
          📖 <div class="pc1-doc-pair">${pairTxt}</div>
          <b>文件 §四 推薦：${esc(p.fit_text)}</b>
          <span class="doc-expected-rank">${rankText}</span>
        `;
        docBanner.style.display = 'block';
      } else {
        docBanner.style.display = 'none';
      }
    }

    if (!results.length) {
      list.innerHTML = '<div class="pc-empty">找不到符合條件的配合</div>';
      return;
    }
    let html = '';
    results.slice(0, 12).forEach(item => {
      const hole  = item.hole_tol  || item.shaft || '';
      const shaft = item.shaft_dev || item.hole  || '';
      const src = item.source || 'ANSI';
      const srcBadge = ({
        'ANSI':         '<span class="src-badge src-ansi">ANSI</span>',
        'YRT100':       '<span class="src-badge src-yrt">YRT100</span>',
        'RAS400_custom':'<span class="src-badge src-ras">RAS400</span>',
      })[src] || '';
      const approxWarn = item.is_approx
        ? ' <span class="approx-warn" title="軸偏差為近似值，不在 ABC 協議範圍">⚠ 近似值</span>' : '';
      const scoreBadge = (item.score != null)
        ? `<span class="score-badge" title="必選+可選命中加權">${item.score}</span>` : '';
      const matchedBadges = (item.matched_tags || []).map(t => `<span class="match-tag">${esc(t)}</span>`).join('');
      // preset 啟用時，把預期 ansi 那筆做高亮邊框
      const isExpected = _pc1ActivePreset && item.ansi === _pc1ActivePreset.expected_ansi;
      // 製程 + 機台建議（沈哲民 → process_capability → machines_process_map → machines.csv）
      const hProc = (item.processes_hole  || []).join(' → ');
      const sProc = (item.processes_shaft || []).join(' → ');
      const _machStr = (machs) => (machs || [])
        .map(m => {
          const isMock = m['型號'].startsWith('MOCK-');
          return isMock
            ? `${m.attr}（重現±${m['重現精度']}mm）`
            : `${m.attr}｜${m['型號']} (${m['公司']}, ±${m['重現精度']}mm)`;
        })
        .join('、');
      const hMach = _machStr(item.machines_hole);
      const sMach = _machStr(item.machines_shaft);
      const procHtml = (hProc || sProc) ? `
        <div class="pc-fit-process">
          ${hProc ? `<div><span class="proc-label">孔製程</span><b>${esc(hProc)}</b>${hMach ? `<div class="mach-tag">🏭 ${esc(hMach)}</div>` : ''}</div>` : ''}
          ${sProc ? `<div><span class="proc-label">軸製程</span><b>${esc(sProc)}</b>${sMach ? `<div class="mach-tag">🏭 ${esc(sMach)}</div>` : ''}</div>` : ''}
        </div>` : '';
      const itemJson = encodeURIComponent(JSON.stringify({
        ansi: item.ansi, type: item.type, function: item.function,
        hole_tol: item.hole_tol, shaft_dev: item.shaft_dev,
        processes_hole: item.processes_hole, processes_shaft: item.processes_shaft,
        machines_hole: item.machines_hole, machines_shaft: item.machines_shaft,
      }));
      html += `
        <div class="pc-fit-card${isExpected ? ' pc-fit-card-expected' : ''}">
          <div class="pc-fit-head">${srcBadge} ${esc(item.type)} · ${esc(item.function)} ${scoreBadge}${approxWarn}${isExpected ? ' <span class="doc-pick-badge">📖 文件推薦</span>' : ''}</div>
          <div class="pc-fit-meta">
            <span>孔: <b>${esc(hole) || '-'}</b></span>
            <span>軸: <b>${esc(shaft) || '-'}</b></span>
            <span>編碼: ${esc(item.ansi)}</span>
          </div>
          ${item.note ? `<div class="pc-fit-note">${esc(item.note)}</div>` : ''}
          ${procHtml}
          ${matchedBadges ? `<div class="match-tags">${matchedBadges}</div>` : ''}
          <div style="margin-top:6px;">
            <button class="pc1-rec-btn-add" onclick="pc1SelectAlternativeFit(this, '${encodeURIComponent(item.ansi)}', decodeURIComponent('${itemJson}'))">
              ＋ 選用此配合 → 加入報表
            </button>
          </div>
        </div>`;
    });
    list.innerHTML = html;
  }

  // 使用者手動切換 chip 時，清掉 active 配對按鈕標記（保留零件選擇）
  const _origCycleDim = window.pc1CycleDim;
  window.pc1CycleDim = function (btn) {
    _pc1ActivePreset = null;
    document.querySelectorAll('#pc1-pair-buttons .pc1-pair-btn')
      .forEach(b => b.classList.remove('pc1-preset-active'));
    _origCycleDim(btn);
  };

  // 清除按鈕：清 chip + 清配對選擇 + 清零件選擇 + 清當前零件存檔
  const _origClearDims = window.pc1ClearDims;
  window.pc1ClearDims = function () {
    _pc1ActivePreset = null;
    // 清除當前零件的存檔
    if (_pc1CurrentPart) {
      delete _pc1PartStates[_pc1CurrentPart];
      const btn = document.querySelector(`#pc1-part-buttons .pc1-preset-btn[data-part="${_pc1CurrentPart}"]`);
      btn?.querySelector('.pc1-saved-badge')?.remove();
    }
    document.querySelectorAll('#pc1-pair-buttons .pc1-pair-btn')
      .forEach(b => b.classList.remove('pc1-preset-active'));
    document.querySelectorAll('#pc1-part-buttons .pc1-preset-btn')
      .forEach(b => b.classList.remove('pc1-preset-active'));
    const section = $('pc1-pair-section');
    if (section) section.style.display = 'none';
    _origClearDims();
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

  // ═══════════════════ 初版 · 批量配合報表 ═══════════════════

  let _batchPairs      = [];   // 從 API 載入的配對清單
  let _batchCsv        = '';   // 最後一次批量結果的 CSV 字串
  let _batchReportRows = [];   // 批量推薦結果（供輸出報告用）

  window.pc1BatchLoad = async function () {
    const status = $('pc1-batch-status');

    // ── 優先：使用者已推薦的零件存檔 ──────────────────────────────────────
    const savedEntries = Object.entries(_pc1PartStates)
      .filter(([, s]) => s.rawResults && s.rawResults.length);

    if (savedEntries.length > 0) {
      _batchPairs = savedEntries.map(([partLabel, s], idx) => {
        const preset  = s.activePreset;
        const top     = s.rawResults[0];
        const dimDesc = Object.entries(s.dimState)
          .filter(([, v]) => v === 'required').map(([k]) => k).join(' ＋ ');

        // ★ 優先使用使用者實際選用的配合（preset.fit_text），而非 smart_fit 第一名
        const fitCode = preset?.fit_text || top?.ansi || '';

        // 解析孔/軸偏差：'H7/k6' → H7 + k6；'js5' → 只有軸；'H6' → 只有孔
        let holeFeature = '', shaftFeature = '';
        if (fitCode.includes('/')) {
          [holeFeature, shaftFeature] = fitCode.split('/', 2);
        } else if (fitCode && fitCode[0] === fitCode[0].toUpperCase()
                   && fitCode[0].toLowerCase() !== fitCode[0]) {
          holeFeature = fitCode;   // 大寫開頭 = 孔公差（H6, H7…）
        } else {
          shaftFeature = fitCode;  // 小寫開頭 = 軸公差（js5, k6, u6…）
        }

        return {
          pair_id:       `REC-${String(idx + 1).padStart(2, '0')}`,
          hole_part:     (preset?.partA || partLabel).replace(/\(\d+\)/, ''),
          hole_feature:  holeFeature,
          shaft_part:    preset ? preset.partB_label || preset.partB : '（見推薦）',
          shaft_feature: shaftFeature,
          nominal_dia:   preset?.nominal_dia || '',
          function_desc: dimDesc || top?.function || '',
          priority:      'high',
          _ansi:         fitCode,
          _fromRec:      true,
        };
      });
      _batchRenderTable(_batchPairs);
      if (status) status.textContent = `已載入 ${_batchPairs.length} 筆推薦配對（來自初版選擇）`;
      _show('pc1-batch-pairs');
      _show('pc1-batch-selall');
      _show('pc1-batch-clrall');
      _show('pc1-export-txt');
      return;
    }

    // ── 備援：從資料庫載入預設配對 ────────────────────────────────────────
    if (status) status.textContent = '（尚未選擇零件，載入預設配對）載入中…';
    try {
      const res  = await fetch('/api/matchmaking/mating_pairs');
      const data = await res.json();
      if (!data.ok) throw new Error(data.msg);
      _batchPairs = data.pairs;
      _batchRenderTable(data.pairs);
      if (status) status.textContent = `已載入 ${data.pairs.length} 個預設配對`;
      _show('pc1-batch-pairs');
      _show('pc1-batch-selall');
      _show('pc1-batch-clrall');
      _show('pc1-export-txt');
    } catch (e) {
      if (status) status.textContent = '載入失敗：' + e.message;
    }
  };

  function _show(id, display) {
    const el = $(id);
    if (el) el.style.display = display || '';
  }

  function _batchRenderTable(pairs) {
    const tbody = $('pc1-batch-tbody');
    if (!tbody) return;
    const priorityLabel = { high: '🔴 高', medium: '🟡 中', low: '⚪ 低' };
    tbody.innerHTML = pairs.map((p, i) => {
      const recBadge = p._fromRec
        ? `<span style="color:#4ade80;font-size:10px;margin-left:4px;">● 已推薦${p._ansi ? ' ' + p._ansi : ''}</span>`
        : '';
      return `
      <tr>
        <td style="text-align:center;"><input type="checkbox" class="pc1-batch-chk" data-idx="${i}" checked></td>
        <td style="white-space:nowrap;">${esc(p.pair_id)}${recBadge}</td>
        <td>${esc(p.hole_part)} <span class="pc-chip">${esc(p.hole_feature)}</span></td>
        <td style="color:#94a3b8;font-size:11px;">${esc(p.shaft_part)} <span class="pc-chip">${esc(p.shaft_feature)}</span></td>
        <td style="text-align:right;">${esc(p.nominal_dia)}</td>
        <td style="max-width:220px;font-size:11px;color:#94a3b8;">${esc(p.function_desc)}</td>
        <td style="white-space:nowrap;font-size:11px;">${priorityLabel[p.priority] || esc(p.priority)}</td>
      </tr>`;
    }).join('');
  }

  window.pc1BatchSelectAll = function (checked) {
    document.querySelectorAll('.pc1-batch-chk').forEach(c => { c.checked = checked; });
    const all = $('pc1-batch-all');
    if (all) all.checked = checked;
  };
  window.pc1BatchToggleAll = function (checked) {
    document.querySelectorAll('.pc1-batch-chk').forEach(c => { c.checked = checked; });
  };

  window.pc1BatchRun = async function () {
    const status  = $('pc1-batch-status');
    const runBtn  = $('pc1-batch-run');
    const checked = [...document.querySelectorAll('.pc1-batch-chk:checked')]
                      .map(c => parseInt(c.dataset.idx, 10));
    if (!checked.length) { if (status) status.textContent = '請至少勾選一個配對'; return; }

    const selected = checked.map(i => _batchPairs[i]);
    if (status) status.textContent = `執行中（${selected.length} 個配對）…`;
    if (runBtn) runBtn.disabled = true;

    try {
      const res  = await fetch('/api/matchmaking/batch', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(selected),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.msg);
      _batchCsv = data.csv || '';
      _batchReportRows = data.report_rows || [];
      _batchRenderResults(_batchReportRows);
      if (status) status.textContent = `完成！共 ${_batchReportRows.length} 筆推薦`;
      _show('pc1-batch-result');
    } catch (e) {
      if (status) status.textContent = '執行失敗：' + e.message;
    } finally {
      if (runBtn) runBtn.disabled = false;
    }
  };

  function _batchRenderResults(rows) {
    const tbody = $('pc1-batch-result-tbody');
    if (!tbody) return;
    tbody.innerHTML = rows.map(r => {
      const isErr     = !!r.error;
      const rowStyle  = isErr ? ' style="color:#f87171;"' : '';
      const fitCell   = isErr
        ? `<td colspan="8" style="color:#f87171;font-size:11px;">${esc(r.error)}</td>`
        : `<td><strong>${esc(r.recommended_fit)}</strong></td>
           <td style="font-size:11px;">${esc(r.fit_type)}</td>
           <td>${esc(r.hole_it) || '—'}</td>
           <td>${esc(r.shaft_it) || '—'}</td>
           <td style="white-space:nowrap;font-size:11px;">${_clearanceStr(r)}</td>
           <td style="font-size:11px;max-width:160px;">${esc(r.hole_process) || '—'}</td>
           <td style="font-size:11px;max-width:160px;">${esc(r.shaft_process) || '—'}</td>
           <td style="font-size:11px;">${esc(r.source) || '—'}</td>`;
      return `<tr${rowStyle}>
        <td style="white-space:nowrap;">${esc(r.pair_id)}</td>
        <td style="white-space:nowrap;">${esc(r.hole_part)}-${esc(r.hole_feature)}</td>
        <td style="white-space:nowrap;">${esc(r.shaft_part)}-${esc(r.shaft_feature)}</td>
        <td style="text-align:right;">${esc(r.nominal_dia)}</td>
        ${fitCell}
      </tr>`;
    }).join('');
  }

  function _clearanceStr(r) {
    const hi = r.max_clearance_um, lo = r.min_clearance_um;
    if (hi !== '' && hi != null && lo !== '' && lo != null) return `${lo} ~ ${hi}`;
    if (hi !== '' && hi != null) return `≤ ${hi}`;
    return '—';
  }

  window.pc1BatchDownloadCsv = function () {
    if (!_batchCsv) return;
    const blob = new Blob([_batchCsv], { type: 'text/csv;charset=utf-8' });
    const a    = document.createElement('a');
    a.href     = URL.createObjectURL(blob);
    a.download = `配合推薦報表_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  window.pc1ExportTxtReport = function () {
    const now   = new Date();
    const dateStr = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
    const sep   = '='.repeat(64);
    const dash  = '-'.repeat(64);
    let txt = '';

    txt += `${sep}\n`;
    txt += `  RAS-400 轉台系統 — 公差配合建議記錄\n`;
    txt += `  資料來源：GAI 系統查詢結果   建立日期：${dateStr}\n`;
    txt += `${sep}\n\n`;

    // ── 【一】GAI 系統建議配合總表 ──────────────────────────────────────
    txt += `${dash}\n`;
    txt += `【一】GAI 系統建議配合總表（依零件查詢結果）\n`;
    txt += `${dash}\n\n`;

    const savedEntries = Object.entries(_pc1PartStates)
      .filter(([, s]) => s.rawResults && s.rawResults.length);

    if (!savedEntries.length) {
      txt += '  （尚未在初版選取任何零件推薦）\n\n';
    } else {
      savedEntries.forEach(([partLabel, s]) => {
        const presets = PC1_PART_PAIRS.filter(p =>
          p.partA === partLabel || p.partB === partLabel || p.partB_label?.includes(partLabel.replace(/\(\d+\)/,''))
        );
        txt += `● ${partLabel} — `;
        if (presets.length > 1) {
          txt += `系統提示 ${presets.length} 種場景：\n`;
          presets.forEach((p, i) => {
            const reqTxt = p.required.join(' + ');
            const isSelected = s.activePreset === p;
            const marker = isSelected ? '▶ ' : '  ';
            // 根據 partLabel 是孔件(partA)還是軸件(partB)，顯示正確的配合對象
            const counterpart = p.partA === partLabel ? (p.partB_label || p.partB) : p.partA;
            txt += `  ${marker}場景 ${i+1}：${reqTxt}`;
            txt += `　→ 配合對象：${counterpart}`;
            txt += `　→ 推薦配合：${p.fit_text}\n`;
          });
        } else if (presets.length === 1) {
          txt += `只有一種場景，直接給出：\n`;
          const p = presets[0];
          const counterpart = p.partA === partLabel ? (p.partB_label || p.partB) : p.partA;
          txt += `  功能描述：${p.required.join(' + ')}（${counterpart}）\n`;
          txt += `  → 推薦配合：${p.fit_text}\n`;
        }
        // 最終選用
        const top = s.rawResults[0];
        if (top) {
          txt += `  ★ 本次選用配合：${top.ansi}（${top.type} — ${top.function}）\n`;
        }
        txt += '\n';
      });
    }

    // ── 【二】完整零件配合對照表 ──────────────────────────────────────
    txt += `${dash}\n`;
    txt += `【二】完整零件配合對照表（RAS-400 全系統）\n`;
    txt += `${dash}\n\n`;
    const colW = [16, 20, 10, 10];
    txt += `  ${'零件 A'.padEnd(colW[0])} ${'配合對象'.padEnd(colW[1])} ${'推薦配合'.padEnd(colW[2])} 配合類型\n`;
    txt += `  ${'─'.repeat(colW[0])} ${'─'.repeat(colW[1])} ${'─'.repeat(colW[2])} ${'─'.repeat(14)}\n`;
    PC1_PART_PAIRS.forEach(p => {
      txt += `  ${p.partA.padEnd(colW[0])} ${(p.partB_label||p.partB).padEnd(colW[1])} ${p.fit_text.padEnd(colW[2])} —\n`;
    });
    txt += '\n';

    // ── 【三】本次挑選的配合 + 分析原因 ────────────────────────────────
    txt += `${dash}\n`;
    txt += `【三】本次報告挑選的配合 + 分析原因\n`;
    txt += `${dash}\n\n`;

    if (!_batchReportRows.length) {
      txt += '  （尚未執行批量推薦，請先勾選配對並按「批量推薦」）\n\n';
    } else {
      _batchReportRows.forEach((r, i) => {
        if (r.error) {
          txt += `● 配對 ${r.pair_id}：${r.hole_part} — ${r.shaft_part}\n`;
          txt += `  ⚠ 推薦失敗：${r.error}\n\n`;
          return;
        }
        const label = String.fromCharCode(65 + i); // A, B, C...
        txt += `${'─'.repeat(64)}\n\n`;
        txt += `● 配合 ${label}：${r.hole_part}(${r.hole_feature}) 與 ${r.shaft_part}(${r.shaft_feature})\n`;
        txt += `  挑選配合：${r.recommended_fit}\n`;
        if (r.hole_it)  txt += `  孔（${r.hole_feature}）偏差：${r.hole_it}\n`;
        if (r.shaft_it) txt += `  軸（${r.shaft_feature}）偏差：${r.shaft_it}\n`;
        if (r.max_clearance_um != null || r.min_clearance_um != null) {
          txt += `  間隙/干涉範圍：${r.min_clearance_um ?? '?'} ~ ${r.max_clearance_um ?? '?'} μm\n`;
        }
        // 分析原因：從對應零件的 rawResults 找說明
        const partKey = Object.keys(_pc1PartStates).find(k =>
          k.replace(/\(\d+\)/,'') === r.hole_part || k.replace(/\(\d+\)/,'') === r.shaft_part
        );
        const rawRes = partKey ? (_pc1PartStates[partKey]?.rawResults || []) : [];
        const match  = rawRes.find(rr => rr.ansi === r.recommended_fit) || rawRes[0];
        if (match) {
          txt += `\n  【分析原因】\n`;
          txt += `  ${match.function || ''}\n`;
          if (match.note) txt += `  備註：${match.note}\n`;
          if (match.processes_hole?.length)  txt += `  孔製程：${match.processes_hole.join(' → ')}\n`;
          if (match.processes_shaft?.length) txt += `  軸製程：${match.processes_shaft.join(' → ')}\n`;
        }
        txt += '\n\n';
      });
    }

    txt += `\n${sep}\n`;
    txt += `  資料來源：\n`;
    txt += `  · Machinery's Handbook (ANSI B4.1 配合系統)\n`;
    txt += `  · GAI 系統查詢結果（基於 ansi_fits_updated.csv）\n`;
    txt += `${sep}\n`;

    const bom  = '﻿';  // UTF-8 BOM 確保 Windows 正確開啟
    const blob = new Blob([bom + txt], { type: 'text/plain;charset=utf-8' });
    const a    = document.createElement('a');
    a.href     = URL.createObjectURL(blob);
    a.download = `RAS400_公差配合建議記錄_${now.toISOString().slice(0,10)}.txt`;
    a.click();
    URL.revokeObjectURL(a.href);

    // 同步傳入 GAI 對話框（摘要版）
    if (typeof addMessage === 'function') {
      const savedEntries = Object.entries(_pc1PartStates)
        .filter(([, s]) => s.rawResults?.length);
      let summary = `<div style="font-size:0.9rem;">📄 <b>配合建議記錄已匯出</b>（${dateStr}）<br>`;
      if (savedEntries.length) {
        summary += `<br><b>【本次選用配合】</b><br>`;
        savedEntries.forEach(([part, s]) => {
          // 用使用者實際選的配合（activePreset.fit_text），而非 smart_fit 第一名
          const fitCode = s.activePreset?.fit_text || s.rawResults[0]?.ansi || '—';
          const counterpart = s.activePreset?.partB_label || s.activePreset?.partB || '';
          summary += `• <b>${part}</b> → <b>${fitCode}</b>　${counterpart ? '（' + counterpart + '）' : ''}<br>`;
        });
      }
      summary += `</div>`;
      addMessage('ai', summary);
    }
  };

})();
