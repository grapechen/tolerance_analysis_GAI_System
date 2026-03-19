const input = document.getElementById('chat-input');
const history = document.getElementById('chat-history');
const sendBtn = document.getElementById('send-btn');
const modelSelect = document.getElementById('model-select');

// Handle Enter key
input.addEventListener('keypress', function (e) {
  if (e.key === 'Enter') sendMessage();
});

sendBtn.addEventListener('click', sendMessage);

let chatHistory = [];

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
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ai`;
        
        const avatar = document.createElement('div');
        avatar.className = 'avatar';
        avatar.textContent = 'AI';
        
        const bubble = document.createElement('div');
        bubble.className = 'bubble';
        
        msgDiv.appendChild(avatar);
        msgDiv.appendChild(bubble);
        history.appendChild(msgDiv);
        
        // Use DOMPurify and render BOM Tree
        const sanitizedReply = typeof DOMPurify !== 'undefined' ? DOMPurify.sanitize(data.reply) : data.reply;
        renderCustomBomTree(sanitizedReply, bubble, data.intent);
        
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
  bubble.innerHTML = content; // User messages are usually plain text
  
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

// Modal closing logic
document.getElementById('close-bom-modal').addEventListener('click', closeBomModal);
document.getElementById('bom-modal-overlay').addEventListener('click', (e) => {
    if(e.target.id === 'bom-modal-overlay') closeBomModal();
});

document.getElementById('close-editor-modal').addEventListener('click', closeEditorModal);
document.getElementById('editor-modal-overlay').addEventListener('click', (e) => {
    if(e.target.id === 'editor-modal-overlay') closeEditorModal();
});
