/* matchmaking.js — 製程與機台媒合 Modal（與 app.py 介面一模一樣）*/

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

// ── Smart Fit 查詢（Step 1）──
async function querySmartFit() {
  let keywords = $('#smart-keywords').val();
  if (keywords && !Array.isArray(keywords)) keywords = [keywords];
  if (!keywords || keywords.length === 0) {
    showMMResult('smart-result', '請選擇至少一個關鍵字', true);
    return;
  }

  const resultDiv = document.getElementById('smart-result');
  resultDiv.style.display = 'block';
  resultDiv.innerHTML = '<div style="color:#94a3b8">搜尋中...</div>';

  try {
    const res = await fetch('/api/recommend/smart_fit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keywords })
    });
    const data = await res.json();

    if (!data.ok) { showMMResult('smart-result', data.msg || '搜尋失敗', true); return; }
    if (!data.results.length) { showMMResult('smart-result', '找不到符合條件的配合建議', true); return; }

    let html = `<div class="success">✅ 找到 ${data.results.length} 筆建議</div>`;
    data.results.forEach(item => {
      const h = (item.hole || '').replace(/'/g, "\\'");
      const s = (item.shaft || '').replace(/'/g, "\\'");
      html += `
        <div class="result-item smart-result-item">
          <div class="smart-result-title">${item.type} - ${item.function}</div>
          <div class="smart-result-meta">
            <span>軸: <b style="color:#fff">${item.shaft || '-'}</b></span>
            <span>孔: <b style="color:#fff">${item.hole || '-'}</b></span>
            <span>ANSI: ${item.ansi}</span>
          </div>
          <div class="smart-result-note">${item.note}</div>
          ${(h || s) ? `<button type="button" class="smart-bridge-btn" onclick="bridgeToMachine('${h}','${s}')">帶入機台篩選 ↓</button>` : ''}
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
