/* matchmaking.js — 製程與機台媒合 Modal（與 app.py 介面一模一樣）*/

// 全域維度狀態：{ '中速旋轉': 'required', '精確': 'optional', ... }
window._dimState = window._dimState || {};

// ── 開關 Modal ──
function openMatchmakingModal() {
  const modal = document.getElementById('matchmaking-modal');
  modal.classList.add('open');

  // 載入機台資料（若尚未載入）
  if (!window.machines || window.machines.length === 0) {
    _mmLoadMachines();
  }

  // 初始化 Select2 關鍵字下拉
  _mmInitSelect2();

  // 載入維度勾選 UI
  _mmInitDimensions();
}

function closeMatchmakingModal() {
  document.getElementById('matchmaking-modal').classList.remove('open');
}

// ── 載入機台資料 ──
async function _mmLoadMachines() {
  try {
    const res = await fetch('/api/machines');
    const data = await res.json();
    if (data.machines) {
      window.machines = data.machines;
      window.capabilities = data.capabilities || [];
      console.log(`✅ 媒合Modal：載入 ${window.machines.length} 台機台`);
      if (typeof initProcessKB === 'function') initProcessKB();
    }
  } catch (e) {
    console.error('❌ 無法載入機台資料:', e);
  }
}

// ── 初始化 Select2 關鍵字 ──
async function _mmInitSelect2() {
  // 避免重複初始化
  if ($('#smart-keywords').data('select2')) return;

  $('#smart-keywords').select2({
    dropdownParent: $('#matchmaking-panel'),
    placeholder: '選擇應用場景或功能 (可打字搜尋)',
    allowClear: false,
    width: '100%'
  });

  try {
    const res = await fetch('/api/keywords');
    const data = await res.json();
    if (data.ok && data.keywords) {
      const select = $('#smart-keywords');
      select.append('<option value=""></option>');
      data.keywords.forEach(kw => {
        select.append(new Option(kw, kw, false, false));
      });
      select.trigger('change');
    }
  } catch (e) {
    console.error('無法載入關鍵字:', e);
  }

  if (typeof initProcessKB === 'function') initProcessKB();
}

// ── 載入維度結構並 render（從 /api/matchmaking/dimensions）──
async function _mmInitDimensions() {
  const container = document.getElementById('smart-dim-groups');
  if (!container || container.dataset.loaded === 'true') return;

  try {
    const res = await fetch('/api/matchmaking/dimensions');
    const data = await res.json();
    if (!data.ok) return;

    let html = '';
    data.groups.forEach(g => {
      html += `<div class="smart-dim-group">
        <span class="smart-dim-group-label">${g.group_zh}</span>
        <div class="smart-dim-chips">`;
      g.items.forEach(it => {
        const safeZh = it.zh.replace(/"/g, '&quot;');
        html += `<button type="button" class="dim-chip"
                    data-zh="${safeZh}" data-en="${it.en}"
                    onclick="cycleDim(this)" title="${it.en}">
                  ${it.zh}
                </button>`;
      });
      html += `</div></div>`;
    });
    container.innerHTML = html;
    container.dataset.loaded = 'true';
  } catch (e) {
    console.error('[matchmaking] 載入維度失敗:', e);
  }
}

// 切換 chip 狀態：空 → required → optional → 空
function cycleDim(btn) {
  const zh = btn.dataset.zh;
  const cur = window._dimState[zh] || '';
  const next = cur === '' ? 'required' : (cur === 'required' ? 'optional' : '');
  if (next === '') {
    delete window._dimState[zh];
  } else {
    window._dimState[zh] = next;
  }
  btn.classList.remove('dim-state-required', 'dim-state-optional');
  if (next) btn.classList.add('dim-state-' + next);
  _updateDimSummary();
}

function _updateDimSummary() {
  const required = Object.keys(window._dimState).filter(k => window._dimState[k] === 'required');
  const optional = Object.keys(window._dimState).filter(k => window._dimState[k] === 'optional');
  const summary = document.getElementById('smart-dim-summary');
  const clearBtn = document.getElementById('smart-dim-clear-btn');
  if (!required.length && !optional.length) {
    summary.textContent = '未選擇維度';
    summary.classList.remove('has-selection');
    if (clearBtn) clearBtn.style.display = 'none';
  } else {
    const parts = [];
    if (required.length) parts.push(`必選 ${required.length}`);
    if (optional.length) parts.push(`可選 ${optional.length}`);
    summary.textContent = '已選 ' + parts.join(' / ');
    summary.classList.add('has-selection');
    if (clearBtn) clearBtn.style.display = 'inline-block';
  }
}

function toggleDimPanel() {
  const panel = document.getElementById('smart-dim-panel');
  const arrow = document.getElementById('smart-dim-toggle-arrow');
  const open = panel.style.display === 'none' || !panel.style.display;
  panel.style.display = open ? 'block' : 'none';
  if (arrow) arrow.textContent = open ? '▾' : '▸';
}

function clearAllDims() {
  window._dimState = {};
  document.querySelectorAll('#smart-dim-panel .dim-chip').forEach(c => {
    c.classList.remove('dim-state-required', 'dim-state-optional');
  });
  _updateDimSummary();
}

function _mmGetDimensions() {
  const required = Object.keys(window._dimState).filter(k => window._dimState[k] === 'required');
  const optional = Object.keys(window._dimState).filter(k => window._dimState[k] === 'optional');
  return { required, optional };
}

// ── Smart Fit 查詢（Step 1）──
async function querySmartFit() {
  const dims = _mmGetDimensions();
  const useDims = (dims.required.length || dims.optional.length) > 0;

  let keywords = [];
  if (!useDims) {
    keywords = $('#smart-keywords').val();
    if (keywords && !Array.isArray(keywords)) keywords = [keywords];
    if (!keywords || keywords.length === 0) {
      showMMResult('smart-result', '請選擇關鍵字或勾選維度', true);
      return;
    }
  }

  const resultDiv = document.getElementById('smart-result');
  resultDiv.style.display = 'block';
  resultDiv.innerHTML = '<div style="color:#94a3b8">搜尋中...</div>';

  try {
    const body = useDims ? { dimensions: dims } : { keywords };
    const res = await fetch('/api/recommend/smart_fit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const data = await res.json();

    if (!data.ok) { showMMResult('smart-result', data.msg || '搜尋失敗', true); return; }
    if (!data.results.length) { showMMResult('smart-result', '找不到符合條件的配合建議', true); return; }

    const modeLabel = data.mode === 'dimensions' ? '維度' : '關鍵字';
    let html = `<div class="success">✅ ${modeLabel}模式：找到 ${data.results.length} 筆建議</div>`;
    data.results.forEach(item => {
      // 新欄位：hole_tol（孔公差）/ shaft_dev（軸偏差）；舊欄位 shaft/hole alias
      const hole = item.hole_tol || item.shaft || '';
      const shaft = item.shaft_dev || item.hole || '';
      const h = hole.replace(/'/g, "\\'");
      const s = shaft.replace(/'/g, "\\'");
      const src = item.source || 'ANSI';
      const srcBadge = ({
        'ANSI':         '<span class="src-badge src-ansi">ANSI</span>',
        'YRT100':       '<span class="src-badge src-yrt">YRT100</span>',
        'RAS400_custom':'<span class="src-badge src-ras">RAS400</span>',
      })[src] || '';
      const approxWarn = item.is_approx ? ' <span class="approx-warn" title="軸偏差為近似值，不在 ABC 協議範圍">⚠ 近似值</span>' : '';
      const scoreBadge = (item.score != null) ? `<span class="score-badge" title="必選+可選命中加權">${item.score}</span>` : '';
      const matchedBadges = (item.matched_tags || []).map(t =>
        `<span class="match-tag">${t}</span>`).join('');

      // 非 ISO 代號（YRT100）不能 bridge to machine
      const canBridge = !/基準/.test(hole) && !/基準/.test(shaft);

      html += `
        <div class="result-item smart-result-item">
          <div class="smart-result-title">${srcBadge} ${item.type} - ${item.function} ${scoreBadge}${approxWarn}</div>
          <div class="smart-result-meta">
            <span>孔: <b style="color:#1d4ed8">${hole || '-'}</b></span>
            <span>軸: <b style="color:#15803d">${shaft || '-'}</b></span>
            <span>ANSI/編碼: ${item.ansi}</span>
          </div>
          <div class="smart-result-note">${item.note || ''}</div>
          ${matchedBadges ? `<div class="match-tags">${matchedBadges}</div>` : ''}
          ${canBridge ? `<button type="button" class="smart-bridge-btn" onclick="bridgeToMachine('${h}','${s}')">帶入機台篩選 ↓</button>` : '<div class="bridge-disabled">（YRT100 螺栓鎖附固定，跳過 ISO 機台精度推導）</div>'}
        </div>`;
    });
    resultDiv.innerHTML = html;
  } catch (e) {
    showMMResult('smart-result', '連線錯誤：' + e.message, true);
  }
}

// ── 橋接：Smart Fit → 機台精度 ──
async function bridgeToMachine(holeStr, shaftStr) {
  const size = parseFloat(document.getElementById('smart-size').value);
  if (isNaN(size) || size <= 0) {
    alert('請在 Step 1 輸入有效的「加工直徑」以計算精度要求。');
    return;
  }

  const parseIT = (str) => { const m = str.match(/([a-zA-Z]+)(\d+)/); return m ? { code: m[1], it: parseInt(m[2]) } : null; };
  let targetIT = 100;
  const hObj = parseIT(holeStr), sObj = parseIT(shaftStr);
  if (hObj && hObj.it < targetIT) targetIT = hObj.it;
  if (sObj && sObj.it < targetIT) targetIT = sObj.it;
  if (targetIT === 100) { alert('無法解析公差等級，請手動設定機台精度。'); return; }

  try {
    const res = await fetch('/api/lookup/tolerance', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ it_grade: 'IT' + targetIT, size_mm: size })
    });
    const data = await res.json();
    if (!data.ok) { alert('查無此公差數值: ' + data.msg); return; }

    const tolerance_um = data['tolerance_μm'];
    const cpSelect = document.getElementById('smart-cp');
    const safetyFactor = cpSelect ? parseFloat(cpSelect.value) : 3.0;
    const req_mm = (tolerance_um / 1000.0) / safetyFactor;

    const accInput = document.getElementById('f_accuracy');
    const posInput = document.getElementById('f_positioning');
    if (accInput) { accInput.value = req_mm.toFixed(4); accInput.classList.add('flash-highlight'); }
    if (posInput) { posInput.value = (req_mm * 1.5).toFixed(4); }

    document.querySelector('#matchmaking-panel .kb-filter-grid')?.scrollIntoView({ behavior: 'smooth' });
    setTimeout(() => { const btn = document.getElementById('btn_run'); if (btn) btn.click(); }, 800);
  } catch (e) {
    alert('連線錯誤：' + e.message);
  }
}

// ── 單選/多選切換 ──
function toggleKeywordMode(isMultiple) {
  const select = $('#smart-keywords');
  let val = select.val();
  select.select2('destroy');
  select.prop('multiple', isMultiple);
  if (!isMultiple && Array.isArray(val)) val = val[0] || '';
  if (isMultiple && !Array.isArray(val)) val = val ? [val] : [];
  select.select2({ dropdownParent: $('#matchmaking-panel'), placeholder: '選擇應用場景或功能 (可打字搜尋)', allowClear: true, width: '100%' });
  select.val(val).trigger('change');
}

// ── 工具函式 ──
function showMMResult(id, msg, isError) {
  const el = document.getElementById(id);
  if (!el) return;
  el.style.display = 'block';
  el.innerHTML = `<div style="color:${isError ? '#f87171' : '#4ade80'}">${msg}</div>`;
}

// ── 點 overlay 背景關閉 ──
document.addEventListener('DOMContentLoaded', () => {
  const modal = document.getElementById('matchmaking-modal');
  if (modal) {
    modal.addEventListener('click', e => { if (e.target === modal) closeMatchmakingModal(); });
  }
});
