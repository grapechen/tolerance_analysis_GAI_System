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
      body: JSON.stringify({ message: msg, model: selectedModel, history: chatHistory.slice(-6) })
    });
    const data = await r.json();

    // Remove Loading
    document.getElementById(loadingId).remove();

    if (data.reply) {
        // Step 1: Strip DSL from reply
        const { cleanText, dslBlocks } = stripBomDsl(data.reply);

        // Step 2: Render pure text into right panel chat bubble
        const sanitized = typeof DOMPurify !== 'undefined' ? DOMPurify.sanitize(cleanText) : cleanText;
        const textHtml = removeTags(sanitized).split('\n').join('<br>');

        if (textHtml.trim()) {
          addMessage('ai', textHtml);
        }

        // Step 3: Render graphs into left panel #graph-container
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
  analysis: '進行公差分析'
};

document.querySelectorAll('.panel-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const action = btn.dataset.action;
    if (!action || !panelBtnPrompts[action]) return;

    // Toggle active state
    document.querySelectorAll('.left-btn-grid .panel-btn').forEach(b => b.classList.remove('active'));
    if (!btn.classList.contains('analysis-btn')) {
      btn.classList.add('active');
    }

    // Inject prompt into input and auto-send
    const prompt = panelBtnPrompts[action];
    input.value = prompt;
    sendMessage();
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

// ========== Modal closing logic ==========

document.getElementById('close-bom-modal').addEventListener('click', closeBomModal);
document.getElementById('bom-modal-overlay').addEventListener('click', (e) => {
    if(e.target.id === 'bom-modal-overlay') closeBomModal();
});

document.getElementById('close-editor-modal').addEventListener('click', closeEditorModal);
document.getElementById('editor-modal-overlay').addEventListener('click', (e) => {
    if(e.target.id === 'editor-modal-overlay') closeEditorModal();
});
