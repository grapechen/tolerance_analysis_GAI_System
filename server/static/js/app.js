const input = document.getElementById('chat-input');
const history = document.getElementById('chat-history');
const sendBtn = document.getElementById('send-btn');
const modelSelect = document.getElementById('model-select');
const graphContainer = document.getElementById('graph-container');

// Handle Enter key
input.addEventListener('keypress', function (e) {
  if (e.key === 'Enter') sendMessage();
});

sendBtn.addEventListener('click', sendMessage);

let chatHistory = [];

/**
 * Strip BOM DSL blocks from reply text and return { cleanText, dslBlocks[] }
 */
function stripBomDsl(replyText) {
  const bomRegex = /---BOM_START---([\s\S]*?)---BOM_END---/g;
  const dslBlocks = [];
  let match;
  while ((match = bomRegex.exec(replyText)) !== null) {
    dslBlocks.push(match[1]);
  }
  const cleanText = replyText.replace(bomRegex, '').trim();
  return { cleanText, dslBlocks };
}

/**
 * Render BOM DSL blocks into the left-panel #graph-container
 */
function renderDslToGraphPanel(dslBlocks, intent) {
  if (!dslBlocks || dslBlocks.length === 0) return;

  // Clear previous graph
  graphContainer.innerHTML = '';

  dslBlocks.forEach(rawBom => {
    // Re-wrap so renderCustomBomTree can parse it
    const wrappedText = '---BOM_START---' + rawBom + '---BOM_END---';
    const tempDiv = document.createElement('div');
    renderCustomBomTree(wrappedText, tempDiv, intent);
    // Move rendered children into graph container
    while (tempDiv.firstChild) {
      graphContainer.appendChild(tempDiv.firstChild);
    }
  });
}

async function sendMessage() {
  const msg = input.value.trim();
  if (!msg) return;

  // Disable input
  input.disabled = true;
  sendBtn.disabled = true;

  // Add User Message
  addMessage('user', msg);

  // Save to Chat History
  chatHistory.push({ role: 'user', content: msg });

  input.value = '';

  // Add Loading Indicator
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
        current_path: (typeof editorPathData !== 'undefined') ? editorPathData : null,
        current_analysis: window._lastAnalysisResult || null,
        current_pmi_session_id: window._stepSessionId || null  // [Phase 4] PMI Session
      })
    });
    const data = await r.json();

    // [New] Handle Direct Nominal Size Input (e.g. "5-P-6 的公稱尺寸是 25")
    const nominalInputRegex = /([\w\-]+)(?:的)?公稱尺寸(?:是|為)?\s*(\d+(?:\.\d+)?)/;
    const nMatch = msg.match(nominalInputRegex);
    if (nMatch && typeof editorPathData !== 'undefined') {
        const target = nMatch[1];
        const size = nMatch[2];
        const idx = editorPathData.findIndex(item => item.name === target || item.axis === target);
        if (idx !== -1 && typeof updateNominal === 'function') {
            updateNominal(idx, size);
        }
    }

    // Remove Loading
    document.getElementById(loadingId).remove();

    if (data.reply) {
        // Step 1: Parse Thought Tags
        let finalReply = data.reply;
        
        // [New] Handle automatic Tolerance Adjustments from AI tags
        const adjustRegex = /<ADJUST_TOLERANCE\s+target="([^"]+)"\s+grade="([^"]+)"\s*\/>/g;
        let adjustMatch;
        while ((adjustMatch = adjustRegex.exec(finalReply)) !== null) {
            const targetName = adjustMatch[1];
            const targetGrade = adjustMatch[2];
            if (typeof editorPathData !== 'undefined') {
                const idx = editorPathData.findIndex(item => item.name === targetName || item.axis === targetName);
                if (idx !== -1 && typeof updateITGrade === 'function') {
                    console.log(`[AI] Adjusting ${targetName} to ${targetGrade}`);
                    updateITGrade(idx, targetGrade);
                }
            }
        }
        // Clean tags from reply
        finalReply = finalReply.replace(adjustRegex, '').trim();

        // [Phase 2] Handle PMI Highlight from AI tags
        const highlightPmiRegex = /<HIGHLIGHT_PMI\s+label="([^"]+)"\s*\/>/g;
        let hMatch;
        while ((hMatch = highlightPmiRegex.exec(finalReply)) !== null) {
            const label = hMatch[1];
            if (typeof PmiPanel !== 'undefined') {
                console.log(`[AI] Highlighting PMI: ${label}`);
                PmiPanel.onAiHighlight(label);
                openStepViewerPanel();  // 帶起 3D 查看器面板
            }
        }
        // Clean tags from reply
        finalReply = finalReply.replace(highlightPmiRegex, '').trim();

        let thoughtHtml = '';
        const thoughtMatch = finalReply.match(/<thought>([\s\S]*?)<\/thought>/);
        if (thoughtMatch) {
            const thoughtText = thoughtMatch[1].trim();
            thoughtHtml = `
              <div class="thought-container">
                <div class="thought-header" onclick="this.parentElement.classList.toggle('collapsed')"></div>
                <div class="thought-content">${thoughtText}</div>
              </div>
            `;
            finalReply = finalReply.replace(/<thought>[\s\S]*?<\/thought>/, '').trim();
        }

        // Step 2: Strip DSL from reply
        const { cleanText, dslBlocks } = stripBomDsl(finalReply);

        // Step 3: Render into right panel
        const sanitized = typeof DOMPurify !== 'undefined' ? DOMPurify.sanitize(cleanText) : cleanText;
        // 將換行符號轉為 <br>
        const textHtml = thoughtHtml + sanitized.split('\n').join('<br>');

        if (textHtml.trim()) {
          addMessage('ai', textHtml);
        }

        // Step 4: Render graphs into left panel #graph-container
        if (dslBlocks.length > 0) {
          renderDslToGraphPanel(dslBlocks, data.intent);
        }

        chatHistory.push({ role: 'assistant', content: data.reply });
        history.scrollTop = history.scrollHeight;

    } else {
      addMessage('ai', '[WARN] 發生錯誤：無法取得回應');
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

function addMessage(role, content) {
  const div = document.createElement('div');
  div.className = `message ${role}`;

  const avatar = document.createElement('div');
  avatar.className = 'avatar';
  avatar.textContent = role === 'user' ? 'You' : 'AI';

  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.innerHTML = content;

  if (role === 'user') {
    div.appendChild(bubble);
    div.appendChild(avatar);
  } else {
    div.appendChild(avatar);
    div.appendChild(bubble);
  }

  history.appendChild(div);
  history.scrollTop = history.scrollHeight;
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
  history.appendChild(div);
  history.scrollTop = history.scrollHeight;
  return id;
}

// ========== Left Panel Button Events ==========

const panelBtnPrompts = {
  parts:    '畫出產品架構圖，列出所有零件',
  features: '畫出所有零件的特徵面結構圖',
  network:  '畫出公差網路圖',
  contact:  '畫出組裝接觸關係圖',
  step_viewer: '開啟 STEP 3D 檢視器',  // Phase 2
  analysis: '進行公差分析',
  edit_path: '編輯公差路徑',
  allocation: '進行公差調配'
};

document.querySelectorAll('.panel-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const action = btn.dataset.action;
    if (!action) return;

    // step_viewer 直接開面板，不送 AI 訊息
    if (action === 'step_viewer') {
      openStepViewerPanel();
      return;
    }

    if (!panelBtnPrompts[action]) return;

    // Toggle active state
    document.querySelectorAll('.left-btn-grid .panel-btn').forEach(b => b.classList.remove('active'));
    if (!btn.classList.contains('analysis-btn')) {
      btn.classList.add('active');
    }

    // Inject prompt into input and auto-send
    const prompt = panelBtnPrompts[action];
    if (prompt) {
      input.value = prompt;
      sendMessage();
    }

    // Direct UI Triggers (Defensive)
    if (action === 'analysis' && typeof openAnalysisModal === 'function') openAnalysisModal();
    if (action === 'allocation' && typeof openAllocationModal === 'function') openAllocationModal();
  });
});

// ========== Panel Resizer: 可拖曳分隔線 ==========

(function initResizer() {
  const resizer = document.getElementById('panel-resizer');
  const leftPanel = document.querySelector('.left-panel');
  const appLayout = document.querySelector('.app-layout');

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

    // 限制最小 250px、最大為容器寬度的 60%
    const minWidth = 250;
    const maxWidth = containerRect.width * 0.6;
    newWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));

    leftPanel.style.width = newWidth + 'px';
  });

  document.addEventListener('mouseup', () => {
    if (!isResizing) return;
    isResizing = false;
    resizer.classList.remove('dragging');
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  });
})();

// ========== Step Viewer Panel Resizer ==========
(function initStepViewerResizer() {
  const resizer = document.getElementById('step-viewer-resizer');
  const panel = document.getElementById('step-viewer-panel');
  const appLayout = document.querySelector('.app-layout');

  if (!resizer || !panel) return;

  let isResizing = false;

  resizer.addEventListener('mousedown', (e) => {
    isResizing = true;
    resizer.classList.add('dragging');
    resizer.style.background = '#0ea5e9';
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
  });

  resizer.addEventListener('mouseenter', () => {
    if (!isResizing) {
      resizer.style.background = '#0ea5e9';
    }
  });

  resizer.addEventListener('mouseleave', () => {
    if (!isResizing) {
      resizer.style.background = '#cbd5e1';
    }
  });

  document.addEventListener('mousemove', (e) => {
    if (!isResizing) return;

    const containerRect = appLayout.getBoundingClientRect();

    // 計算新的寬度（從右邊界往左算）
    let newWidth = containerRect.right - e.clientX;

    // 限制最小 380px、最大為容器寬度的 65%
    const minWidth = 380;
    const maxWidth = containerRect.width * 0.65;
    newWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));

    panel.style.width = newWidth + 'px';
  });

  document.addEventListener('mouseup', () => {
    if (!isResizing) return;
    isResizing = false;
    resizer.classList.remove('dragging');
    resizer.style.background = '#cbd5e1';
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  });
})();

// ========== Modal closing logic ==========

document.getElementById('close-bom-modal').addEventListener('click', closeBomModal);
document.getElementById('bom-modal-overlay').addEventListener('click', (e) => {
    if(e.target.id === 'bom-modal-overlay') closeBomModal();
});

document.getElementById('close-editor-modal').addEventListener('click', closeEditorModal);
document.getElementById('editor-modal-overlay').addEventListener('click', (e) => {
    if(e.target.id === 'editor-modal-overlay') closeEditorModal();
});

// ========== STEP 3D Viewer Panel (Phase 2) ==========

function openStepViewerPanel() {
  const panel = document.getElementById('step-viewer-panel');
  const resizer = document.getElementById('step-viewer-resizer');
  if (panel) {
    panel.style.display = 'flex';
    if (resizer) {
      resizer.style.display = 'block';
    }
    // 初始化 Three.js（如果還沒初始化）
    if (typeof StepViewer !== 'undefined' && !window._stepViewerInitialized) {
      StepViewer.init('step-viewer-container');
      window._stepViewerInitialized = true;
    }
  }
}

function closeStepViewerPanel() {
  const panel = document.getElementById('step-viewer-panel');
  const resizer = document.getElementById('step-viewer-resizer');
  if (panel) {
    panel.style.display = 'none';
    if (resizer) {
      resizer.style.display = 'none';
    }
  }
}

/**
 * 上傳 STEP 檔案
 */
function uploadStepFile(file) {
  if (!file) return;

  console.log(`📤 上傳 STEP: ${file.name}`);

  const formData = new FormData();
  formData.append('stp_file', file);

  fetch('/api/step/upload', {
    method: 'POST',
    body: formData
  })
    .then(r => r.json())
    .then(data => {
      if (!data.ok) {
        alert(`❌ 上傳失敗: ${data.error}`);
        return;
      }

      window._stepSessionId = data.session_id;
      console.log(`✅ Session 建立: ${data.session_id}`);

      // 提示用户下一步
      alert(`✅ STEP 檔案已上傳。\n請上傳 XLSX 檔案，然後點擊「比對 & 解析 PMI」。`);

      // 清空XLSX輸入框
      const xlsxInput = document.getElementById('xlsx-file-input');
      if (xlsxInput) {
        xlsxInput.value = '';
      }
    })
    .catch(err => {
      console.error('❌ 錯誤:', err);
      alert('發生錯誤: ' + err.message);
    });
}

/**
 * 上傳 XLSX 檔案到已有的 session
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

  fetch('/api/step/upload_xlsx', {
    method: 'POST',
    body: formData
  })
    .then(r => r.json())
    .then(data => {
      if (!data.ok) {
        alert(`❌ 上傳失敗: ${data.error}`);
        return;
      }

      console.log(`✅ XLSX 已上傳: ${data.xlsx_filename}`);
      alert(`✅ XLSX 檔案已上傳。\n現在點擊「比對 & 解析 PMI」進行比對。`);
    })
    .catch(err => {
      console.error('❌ XLSX 上傳錯誤:', err);
      alert('發生錯誤: ' + err.message);
    });
}

/**
 * 比對 & 解析 PMI
 * 在 STEP 和 XLSX 都上傳後調用此函數進行比對和解析
 */
function parsePMI() {
  if (!window._stepSessionId) {
    alert('❌ 請先上傳 STEP 檔案');
    return;
  }

  console.log(`🔍 開始比對 & 解析 PMI (Session: ${window._stepSessionId})`);

  fetch('/api/step/parse_pmi', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: window._stepSessionId })
  })
    .then(r => r.json())
    .then(data => {
      if (!data.ok) {
        alert(`❌ 解析失敗: ${data.error}`);
        return;
      }

      console.log(`✅ PMI 解析完成: ${data.n_pmi_rows} 項`);

      // 載入幾何到 Three.js
      if (typeof StepViewer !== 'undefined') {
        StepViewer.loadAllGeometry(window._stepSessionId);
      }

      // 填充 PMI 清單面板
      if (typeof PmiPanel !== 'undefined') {
        PmiPanel.render(data.pmi_rows, window._stepSessionId);
      }

      alert(`✅ PMI 比對完成！\n• ${data.n_faces} 個面\n• ${data.n_pmi_rows} 個 PMI 項目`);
    })
    .catch(err => {
      console.error('❌ 錯誤:', err);
      alert('發生錯誤: ' + err.message);
    });
}

/**
 * [Phase 5] 執行組合件接觸分析
 * 呼叫 /api/step/asm_contact 子進程，並在完成後渲染接觸圖
 */
function runAssemblyContactAnalysis() {
  if (!window._stepSessionId) {
    alert('❌ 請先上傳 STEP 檔案');
    return;
  }

  console.log(`🔧 執行組合件接觸分析 (Session: ${window._stepSessionId})...`);
  const btn = event && event.target ? event.target : null;
  if (btn) {
    btn.disabled = true;
    btn.textContent = '⏳ 分析中...';
  }

  fetch('/api/step/asm_contact', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: window._stepSessionId })
  })
    .then(r => r.json())
    .then(data => {
      if (!data.ok) {
        alert(`❌ 分析失敗: ${data.error}`);
        if (btn) {
          btn.disabled = false;
          btn.textContent = '🔧 執行組合件分析';
        }
        return;
      }

      console.log(`✅ 組合件分析完成: ${data.contacts ? data.contacts.length : 0} 個接觸對`);

      // [Phase 5] 渲染接觸圖
      if (typeof renderAsmContactsFromStep !== 'undefined' && data.contacts) {
        renderAsmContactsFromStep(data.contacts);
        addMessage('ai', '🔗 組合件接觸分析完成，接觸圖已更新。');
      }

      // 自動切換到接觸圖視圖
      const contactBtn = document.querySelector('[data-action="contact"]');
      if (contactBtn) {
        contactBtn.click();
      }

      if (btn) {
        btn.disabled = false;
        btn.textContent = '🔧 執行組合件分析';
      }
    })
    .catch(err => {
      console.error('❌ 錯誤:', err);
      alert('❌ 分析發生錯誤: ' + err.message);
      if (btn) {
        btn.disabled = false;
        btn.textContent = '🔧 執行組合件分析';
      }
    });
}

/**
 * 導出 PMI BOM CSV（同時保存到 MySQL）
 */
function exportStepCSV() {
  if (!window._stepSessionId) {
    alert('❌ 請先上傳 STEP 檔案');
    return;
  }

  // 收集勾選的 PMI 索引
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
        return response.json().then(data => {
          throw new Error(data.error || '導出失敗');
        });
      }
      return response.blob().then(blob => ({ blob, response }));
    })
    .then(({ blob, response }) => {
      // 從 Content-Disposition 頭部提取檔案名
      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = 'PMI_Export.csv';
      if (contentDisposition) {
        const match = contentDisposition.match(/filename="(.+?)"/);
        if (match) filename = match[1];
      }

      // 觸發瀏覽器下載
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
