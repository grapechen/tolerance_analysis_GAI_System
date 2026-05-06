/*
========================================================================
[程式邏輯說明 (Main Logic)]

此檔案負責網頁的互動行為與 API 串接。

主要功能區塊：
1. API_BASE: 設定後端伺服器位址 (預設 Prot 7010)
2. Tab Switching: 切換分頁邏輯 (switchTab)
3. Standard Lookup: 一般公差查詢 (queryIT, queryShaft...)
4. ★ Smart Fit Logic: 
   - querySmartFit(): 呼叫 /api/recommend/smart_fit 搜尋配合建議
   - bridgeToMachine(): ★關鍵功能，將選定的公差轉換為機台精度要求
   - checkMachine(): 呼叫後端驗證機台能力

若要修改「計算公式」或「搜尋邏輯」，請專注於 bridgeToMachine 函式。
========================================================================
*/

const API_BASE = 'http://127.0.0.1:7010';
const DB = window.TOLERANCE_DATA || { it_tolerance: [], shaft_tolerance: [], hole_tolerance: [] };

// 全域變數供各模組存取
window.machines = [];
window.capabilities = [];

document.addEventListener('DOMContentLoaded', async () => {
    try {
        const res = await fetch(getApiUrl('/api/machines'));
        const data = await res.json();
        if (data.machines) {
            window.machines = data.machines;
            window.capabilities = data.capabilities || [];
            console.log(`✅ 成功載入 ${window.machines.length} 筆機台資料與 ${window.capabilities.length} 筆能力資料`);

            // 如果目前頁面有 initProcessKB (例如 製程媒合頁面)，則初始化
            if (typeof initProcessKB === 'function') {
                initProcessKB();
            }
        }
    } catch (e) {
        console.error("❌ 無法載入機台資料庫:", e);
    }
});

// [工具函式] URL 輔助函式：自動偵測是正式環境還是本地環境
function getApiUrl(endpoint) {
    // If running on same origin (files served by Flask), use relative path
    // Otherwise use API_BASE
    if (window.location.protocol.startsWith('http')) {
        return endpoint;
    }
    return API_BASE + endpoint;
}

function switchTab(tab) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

    // 尋找呼叫此分頁的按鈕並設為啟用狀態
    const btn = Array.from(document.querySelectorAll('.tab')).find(b => b.getAttribute('onclick')?.includes(`'${tab}'`));
    if (btn) btn.classList.add('active');

    const content = document.getElementById('tab-' + tab);
    if (content) content.classList.add('active');
}

function showResult(elementId, data, isError = false) {
    const el = document.getElementById(elementId);
    el.style.display = 'block';
    el.className = 'result';

    if (isError) {
        el.innerHTML = '<div class="error">❌ ' + (data.msg || data) + '</div>';
        return;
    }

    let html = '<div class="success">✅ 查詢成功</div>';
    const labelMap = {
        "it_grade": "IT 等級",
        "range_mm": "尺寸範圍 (mm)",
        "size_mm": "名目尺寸 (mm)",
        "tolerance_um": "公差值 (μm)",
        "upper_dev_um": "上偏差 (μm)",
        "lower_dev_um": "下偏差 (μm)",
        "tolerance_code": "公差代號",
        "fit_type": "配合類型",
        "hole": "孔",
        "shaft": "軸",
        "max_clearance_um": "最大間隙距離(um)",
        "min_clearance_um": "最小間隙距離(um)"
    };

    for (let [key, value] of Object.entries(data)) {
        if (key === 'ok') continue;
        let label = labelMap[key] || key.replace(/_/g, ' ');
        // Format object values (like nested hole/shaft info)
        let displayValue = value;
        if (typeof value === 'object' && value !== null) {
            displayValue = JSON.stringify(value);
        }
        html += '<div class="result-item"><span class="result-label">' + label + ':</span><span class="result-value">' + displayValue + '</span></div>';
    }
    el.innerHTML = html;
}

// --- [一般公差查詢] 靜態資料或基本 API 查詢功能 (不含智慧推薦) ---

async function queryIT() {
    const it = document.getElementById('it-grade').value.trim().toUpperCase();
    const size = parseFloat(document.getElementById('it-size').value);

    if (!it || isNaN(size)) {
        showResult('it-result', '請輸入正確的 IT 等級和尺寸', true);
        return;
    }

    const resultDiv = document.getElementById('it-result');
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = '<div style="color:#94a3b8">查詢中...</div>';

    try {
        const response = await fetch(getApiUrl('/api/lookup/tolerance'), {
            method: 'POST',
            body: JSON.stringify({ it_grade: it, size_mm: size }),
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();

        if (!data.ok) {
            showResult('it-result', data.msg || '查詢失敗', true);
            return;
        }

        showResult('it-result', {
            ok: true,
            size_mm: size,
            it_grade: it,
            tolerance_um: data.tolerance_μm,
            range_mm: data.range_mm
        });

    } catch (e) {
        console.error(e);
        showResult('it-result', '連線錯誤', true);
    }
}

async function queryShaft() {
    const code = document.getElementById('shaft-code').value.trim().toLowerCase();
    let it = document.getElementById('shaft-it').value.trim().toUpperCase();
    if (!it.startsWith('IT')) it = 'IT' + it;
    const size = parseFloat(document.getElementById('shaft-size').value);

    if (!code || !it || isNaN(size)) {
        showResult('shaft-result', '請輸入正確的參數', true);
        return;
    }

    const resultDiv = document.getElementById('shaft-result');
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = '<div style="color:#94a3b8">查詢中...</div>';

    try {
        const response = await fetch(getApiUrl('/api/lookup/shaft'), {
            method: 'POST',
            body: JSON.stringify({ tolerance_code: code, it_grade: it, size_mm: size }),
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();

        if (!data.ok) {
            showResult('shaft-result', data.msg || '查詢失敗', true);
            return;
        }

        const res = data.data;
        showResult('shaft-result', {
            ok: true,
            size_mm: size,
            tolerance_code: code,
            it_grade: it,
            upper_dev_um: res.upper,
            lower_dev_um: res.lower,
            range_mm: res.range
        });

    } catch (e) {
        console.error(e);
        showResult('shaft-result', '連線錯誤', true);
    }
}

async function queryHole() {
    const code = document.getElementById('hole-code').value.trim().toUpperCase();
    let it = document.getElementById('hole-it').value.trim().toUpperCase();
    if (!it.startsWith('IT')) it = 'IT' + it;
    const size = parseFloat(document.getElementById('hole-size').value);

    if (!code || !it || isNaN(size)) {
        showResult('hole-result', '請輸入正確的參數', true);
        return;
    }

    const resultDiv = document.getElementById('hole-result');
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = '<div style="color:#94a3b8">查詢中...</div>';

    try {
        const response = await fetch(getApiUrl('/api/tolerance/lookup'), {
            method: 'POST',
            body: JSON.stringify({ type: 'hole', code: code, grade: it, size: size }),
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();

        if (!data.ok) {
            showResult('hole-result', data.msg || '查詢失敗', true);
            return;
        }

        const res = data.data;
        showResult('hole-result', {
            ok: true,
            size_mm: size,
            tolerance_code: code,
            it_grade: it,
            upper_dev_um: res.upper,
            lower_dev_um: res.lower,
            range_mm: res.range
        });

    } catch (e) {
        console.error(e);
        showResult('hole-result', '連線錯誤', true);
    }
}

async function analyzeFit() {
    const size = parseFloat(document.getElementById('fit-size').value);
    const holeStr = document.getElementById('fit-hole').value.trim().toUpperCase();
    const shaftStr = document.getElementById('fit-shaft').value.trim().toLowerCase();

    if (isNaN(size) || !holeStr || !shaftStr) {
        showResult('fit-result', '請輸入正確的參數', true);
        return;
    }

    // [簡單驗證] 確認輸入格式是否正確 (例如: H7, h6)
    if (!holeStr.match(/([A-Z]+)(\d+)/) || !shaftStr.match(/([a-z]+)(\d+)/)) {
        showResult('fit-result', '格式錯誤 (例: H7, h6)', true);
        return;
    }

    // 這邊不需要手動解析，因為後端已有 fit API。
    // 為了保持一致性，我們直接呼叫後端 API 進行分析。

    const resultDiv = document.getElementById('fit-result');
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = '<div style="color:#94a3b8">分析中...</div>';

    const holeMatch = holeStr.match(/([A-Z]+)(\d+)/);
    const shaftMatch = shaftStr.match(/([a-z]+)(\d+)/);
    const holeCode = holeMatch[1];
    const holeIt = "IT" + holeMatch[2];
    const shaftCode = shaftMatch[1];
    const shaftIt = "IT" + shaftMatch[2];

    try {
        const response = await fetch(getApiUrl('/api/analyze/fit'), {
            method: 'POST',
            body: JSON.stringify({
                size_mm: size,
                hole_tolerance: holeStr,
                shaft_tolerance: shaftStr
            }),
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();

        if (!data.ok) {
            showResult('fit-result', data.msg || '查詢失敗：找不到對應公差', true);
            return;
        }

        showResult('fit-result', data);

    } catch (e) {
        console.error(e);
        showResult('fit-result', '連線錯誤', true);
    }
}

// --- [Smart Fit 與智慧推薦] 負責呼叫後端推薦系統與橋接機台資料 ---

// 全域維度狀態：{ '中速旋轉': 'required', '精確': 'optional', ... }
window._dimState = window._dimState || {};

async function _initDimensions() {
    const container = document.getElementById('smart-dim-groups');
    if (!container || container.dataset.loaded === 'true') return;
    try {
        const res = await fetch(getApiUrl('/api/matchmaking/dimensions'));
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
        console.error('[main] 載入維度失敗:', e);
    }
}

function cycleDim(btn) {
    const zh = btn.dataset.zh;
    const cur = window._dimState[zh] || '';
    const next = cur === '' ? 'required' : (cur === 'required' ? 'optional' : '');
    if (next === '') delete window._dimState[zh];
    else window._dimState[zh] = next;
    btn.classList.remove('dim-state-required', 'dim-state-optional');
    if (next) btn.classList.add('dim-state-' + next);
    _updateDimSummary();
}

function _updateDimSummary() {
    const required = Object.keys(window._dimState).filter(k => window._dimState[k] === 'required');
    const optional = Object.keys(window._dimState).filter(k => window._dimState[k] === 'optional');
    const summary  = document.getElementById('smart-dim-summary');
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
    const open  = panel.style.display === 'none' || !panel.style.display;
    panel.style.display = open ? 'block' : 'none';
    if (arrow) arrow.textContent = open ? '▾' : '▸';
    if (open) _initDimensions();
}

function clearAllDims() {
    window._dimState = {};
    document.querySelectorAll('#smart-dim-panel .dim-chip').forEach(c => {
        c.classList.remove('dim-state-required', 'dim-state-optional');
    });
    _updateDimSummary();
}

function _getDimensions() {
    const required = Object.keys(window._dimState).filter(k => window._dimState[k] === 'required');
    const optional = Object.keys(window._dimState).filter(k => window._dimState[k] === 'optional');
    return { required, optional };
}

async function querySmartFit() {
    const dims = _getDimensions();
    const useDims = (dims.required.length || dims.optional.length) > 0;

    let keywords = [];
    if (!useDims) {
        keywords = $('#smart-keywords').val();
        if (keywords && !Array.isArray(keywords)) keywords = [keywords];
        if (!keywords || keywords.length === 0) {
            showResult('smart-result', '請選擇關鍵字或勾選維度', true);
            return;
        }
    }

    const resultDiv = document.getElementById('smart-result');
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = '<div style="color:#94a3b8">搜尋中...</div>';

    try {
        const body = useDims ? { dimensions: dims } : { keywords };
        const response = await fetch(getApiUrl('/api/recommend/smart_fit'), {
            method: 'POST',
            body: JSON.stringify(body),
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();

        if (!data.ok) { showResult('smart-result', data.msg || '搜尋失敗', true); return; }
        if (data.results.length === 0) { showResult('smart-result', '找不到符合條件的配合建議', true); return; }

        const modeLabel = data.mode === 'dimensions' ? '維度' : '關鍵字';
        let html = `<div class="success">✅ ${modeLabel}模式：找到 ${data.results.length} 筆建議</div>`;
        data.results.forEach(item => {
            const hole  = item.hole_tol  || item.shaft || '';
            const shaft = item.shaft_dev || item.hole  || '';
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
            const matchedBadges = (item.matched_tags || []).map(t => `<span class="match-tag">${t}</span>`).join('');
            const canBridge = !/基準/.test(hole) && !/基準/.test(shaft);

            html += `
                <div class="result-item smart-result-item">
                    <div class="smart-result-title">${srcBadge} ${item.type} - ${item.function} ${scoreBadge}${approxWarn}</div>
                    <div class="smart-result-meta">
                        <span>孔: <b style="color:#fff">${hole || '-'}</b></span>
                        <span>軸: <b style="color:#fff">${shaft || '-'}</b></span>
                        <span>ANSI/編碼: ${item.ansi}</span>
                    </div>
                    <div class="smart-result-note">${item.note || ''}</div>
                    ${matchedBadges ? `<div class="match-tags">${matchedBadges}</div>` : ''}
                    ${canBridge ?
                        `<button class="smart-bridge-btn" onclick="bridgeToMachine('${h}', '${s}')">帶入機台篩選 ↓</button>` :
                        '<div class="bridge-disabled">（YRT100 螺栓鎖附固定，跳過 ISO 機台精度推導）</div>'}
                </div>
            `;
        });
        resultDiv.innerHTML = html;

    } catch (e) {
        console.error(e);
        showResult('smart-result', '連線錯誤，請確認伺服器已啟動', true);
    }
}

// [數據橋接核心] 將 Smart Fit 建議的公差 (如 H7) 轉換為具體的機台精度要求 (mm)
// 邏輯：產品公差 -> 取 1/3 ~ 1/4 作為機台目標重現性
async function bridgeToMachine(holeStr, shaftStr) {
    const sizeInput = document.getElementById('smart-size');
    const size = parseFloat(sizeInput.value);

    if (isNaN(size) || size <= 0) {
        alert("請在 Step 1 輸入有效的「加工直徑」以計算精度要求。");
        sizeInput.focus();
        return;
    }

    // 決定目標公差代號 (選取較嚴格的一方 -> IT 數字越小越嚴格)
    // 我們解析 IT 等級 (例如 H7 -> 7)，取較小的值作為機台需求目標。

    let targetCode = '';
    let targetIT = 100; // start high

    const parseIT = (str) => {
        const m = str.match(/([a-zA-Z]+)(\d+)/);
        if (m) return { code: m[1], it: parseInt(m[2]) };
        return null;
    };

    const hObj = parseIT(holeStr);
    const sObj = parseIT(shaftStr);

    if (hObj && hObj.it < targetIT) { targetIT = hObj.it; targetCode = holeStr; }
    if (sObj && sObj.it < targetIT) { targetIT = sObj.it; targetCode = shaftStr; }

    if (targetIT === 100) {
        alert("無法解析公差等級，請手動設定機台精度。");
        return;
    }

    // 查詢公差數值 (使用既有的查詢 API)
    // IT 等級格式: "IT" + 數字
    try {
        // We can use the existing queryIT logic API
        // IT grade format: "IT" + number
        const gradeStr = "IT" + targetIT;

        const response = await fetch(getApiUrl('/api/lookup/tolerance'), {
            method: 'POST',
            body: JSON.stringify({ it_grade: gradeStr, size_mm: size }),
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();

        if (!data.ok) {
            alert("查無此公差數值: " + data.msg);
            return;
        }

        const tolerance_um = data.tolerance_μm; // 例如: 25 (微米)

        // 計算機台精度要求
        // 讀取使用者選擇的 Cp 值 (預設為 3.0，即 1/3 安全係數)
        const cpSelect = document.getElementById('smart-cp');
        const safetyFactor = cpSelect ? parseFloat(cpSelect.value) : 3.0;

        const req_accuracy_mm = (tolerance_um / 1000.0) / safetyFactor;

        // 填入 Process KB 的篩選欄位
        // 如果使用者已經手動輸入，這裡會覆蓋掉，因為這是點擊了「帶入」按鈕的操作。
        const accInput = document.getElementById('f_accuracy'); // Repeatability
        const posInput = document.getElementById('f_positioning'); // Positioning

        // 通常 重現性 < 定位精度。
        // Process KB 是以此數值作為「最大允許值」(機台必須比這個好)。
        if (accInput) {
            accInput.value = req_accuracy_mm.toFixed(4);
            accInput.classList.add('flash-highlight'); // 加入閃爍特效提醒使用者
        }
        if (posInput) {
            // 定位精度通常比重現性寬鬆，這裡稍微放寬 1.5 倍
            posInput.value = (req_accuracy_mm * 1.5).toFixed(4);
        }

        // [UX 優化] 捲動到 Step 2 並自動觸發篩選
        document.querySelector('.kb-filter-grid').scrollIntoView({ behavior: 'smooth' });

        // 延遲一點點後自動點擊「開始篩選」，讓使用者有流暢的體驗
        setTimeout(() => {
            // 確保 Process KB 已初始化
            const runBtn = document.getElementById('btn_run');
            if (runBtn) runBtn.click();
        }, 800);

    } catch (e) {
        console.error(e);
        alert("連線錯誤");
    }
}

async function checkMachine() {
    const diameter = parseFloat(document.getElementById('check-diameter').value);
    const safety = parseFloat(document.getElementById('check-safety').value);

    if (isNaN(diameter) || diameter <= 0) {
        showResult('machine-result', '請輸入有效的直徑', true);
        return;
    }

    const resultDiv = document.getElementById('machine-result');
    resultDiv.style.display = 'block';
    resultDiv.innerHTML = '<div style="color:#94a3b8">分析中...</div>';

    try {
        const response = await fetch(getApiUrl('/api/recommend/machine_check'), {
            method: 'POST',
            body: JSON.stringify({ diameter, safety_factor: safety || 3.0 }),
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();

        if (!data.ok) {
            showResult('machine-result', data.msg || '驗證失敗', true);
            return;
        }

        const res = data.data;
        const machines = res.machines;

        let html = '<div class="success">✅ 分析完成</div>';
        html += `<div style="margin:8px 0; font-size:14px;">
            目標重現精度: <b style="color:#fdba74">${res.target_repeat_mm.toFixed(4)} mm</b>
            (IT7 / ${safety})
        </div>`;

        if (machines.length === 0) {
            html += '<div class="error" style="margin-top:10px">❌ 無合格機台 (所有機台精度皆不足)</div>';
        } else {
            html += `<div style="margin-bottom:10px; color:#94a3b8">共找到 ${machines.length} 台合格機台：</div>`;
            machines.forEach(m => {
                html += `
                    <div class="result-item machine-result-row">
                        <div style="flex: 1;">
                            <div class="machine-model">${m.model}</div>
                            <div class="machine-info">${m.company} | ${m.type}</div>
                            <div class="machine-reason" style="margin-top: 5px; color: #fbbf24; font-size: 13px; line-height: 1.4;">
                                💡 ${m.recommend_reason || '符合精度與加工規範'}
                            </div>
                        </div>
                        <div class="machine-val" style="min-width: 100px; text-align: right;">
                            <div class="machine-val-num">${m.repeatability_mm} mm</div>
                            <div class="machine-info">重現精度</div>
                        </div>
                    </div>
                `;
            });
        }
        resultDiv.innerHTML = html;

    } catch (e) {
        console.error(e);
        showResult('machine-result', '連線錯誤: ' + e, true);
    }
}

// --- [RAG 聊天機器人] 負責與 AI Agent (Port 7011) 進行對話串接 ---

async function queryChat() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    if (!message) return;

    // 在介面上顯示使用者訊息
    appendChatMessage('user', message);
    input.value = '';

    // 顯示「思考中...」狀態
    const loadingId = appendChatMessage('ai', '思考中...', true);

    try {
        const response = await fetch(getApiUrl('/api/chat'), {
            method: 'POST',
            body: JSON.stringify({ message }),
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await response.json();

        // Remove loading
        document.getElementById(loadingId).remove();

        if (data.ok) {
            appendChatMessage('ai', data.reply);
        } else {
            appendChatMessage('error', '錯誤: ' + (data.msg || '未知錯誤'));
        }
    } catch (e) {
        document.getElementById(loadingId)?.remove();
        console.error(e);
        appendChatMessage('error', '連線錯誤，請確認後端服務運作中');
    }
}

function appendChatMessage(role, text, isLoading = false) {
    const chatBox = document.getElementById('chat-history');
    const msgDiv = document.createElement('div');
    const id = 'msg-' + Date.now();
    msgDiv.id = id;

    msgDiv.className = 'chat-msg';

    if (role === 'user') {
        msgDiv.classList.add('chat-msg-user');
        msgDiv.innerHTML = text.replace(/\n/g, '<br>');
    } else if (role === 'ai') {
        msgDiv.classList.add('chat-msg-ai');
        // 基本的 Markdown 格式支援 (粗體、換行)
        if (isLoading) {
            msgDiv.classList.add('chat-loading');
            msgDiv.innerText = text;
        } else {
            // 轉換常見的 markdown 符號
            let formatted = text
                .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>') // Bold
                .replace(/\n/g, '<br>');
            msgDiv.innerHTML = formatted;
        }
    } else {
        msgDiv.classList.add('chat-msg-error');
        msgDiv.innerText = text;
    }

    chatBox.appendChild(msgDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
    return id;
}

// 允許按 Enter 鍵發送訊息
function handleChatKey(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        queryChat();
    }
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `組合件製程清單_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link); // Required for FF
    link.click();
    document.body.removeChild(link);
}
