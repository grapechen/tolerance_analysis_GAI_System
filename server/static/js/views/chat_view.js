/**
 * chat_view.js - 聊天介面 View
 *
 * 職責：
 *   - 渲染用戶 / AI 訊息泡
 *   - 顯示 / 移除載入指示器
 *   - 解析並渲染 BOM DSL 區塊
 *   - 建立 thought 摺疊區塊
 *
 * 不含任何業務邏輯或 API 呼叫。
 */

const ChatView = (() => {
  let _historyEl  = null;
  let _inputEl    = null;
  let _sendBtnEl  = null;
  let _graphEl    = null;
  let _loadingCnt = 0;

  // ── 初始化 ────────────────────────────────────────────────────────────────

  function init({ historyEl, inputEl, sendBtnEl, graphEl }) {
    _historyEl = historyEl;
    _inputEl   = inputEl;
    _sendBtnEl = sendBtnEl;
    _graphEl   = graphEl;
  }

  // ── 訊息渲染 ──────────────────────────────────────────────────────────────

  function appendUserMessage(text) {
    _append('user', _escape(text));
  }

  function appendAiMessage(html) {
    const sanitized = typeof DOMPurify !== 'undefined' ? DOMPurify.sanitize(html) : html;
    _append('ai', sanitized);
  }

  function _append(role, html) {
    if (!_historyEl) return;
    const div = document.createElement('div');
    div.className = `message ${role}-message`;
    div.innerHTML = html;
    _historyEl.appendChild(div);
    scrollToBottom();
  }

  function _escape(text) {
    return text.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  // ── 載入指示器 ────────────────────────────────────────────────────────────

  function showLoading() {
    _loadingCnt++;
    const id  = `loading-${_loadingCnt}`;
    const div = document.createElement('div');
    div.id        = id;
    div.className = 'message ai-message loading';
    div.innerHTML = '<span class="dot"></span><span class="dot"></span><span class="dot"></span>';
    _historyEl?.appendChild(div);
    scrollToBottom();
    return id;
  }

  function removeLoading(id) {
    document.getElementById(id)?.remove();
  }

  // ── 輸入鎖定 ──────────────────────────────────────────────────────────────

  function lockInput(locked) {
    if (_inputEl)   _inputEl.disabled   = locked;
    if (_sendBtnEl) _sendBtnEl.disabled = locked;
    if (!locked && _inputEl) _inputEl.focus();
  }

  // ── BOM DSL ───────────────────────────────────────────────────────────────

  function stripBomDsl(replyText) {
    const regex    = /---BOM_START---([\s\S]*?)---BOM_END---/g;
    const dslBlocks = [];
    let match;
    while ((match = regex.exec(replyText)) !== null) dslBlocks.push(match[1]);
    return { cleanText: replyText.replace(regex, '').trim(), dslBlocks };
  }

  function renderDslBlocks(dslBlocks, intent) {
    if (!_graphEl || !dslBlocks?.length) return;
    _graphEl.innerHTML = '';
    dslBlocks.forEach(raw => {
      const wrapped = '---BOM_START---' + raw + '---BOM_END---';
      const tmp     = document.createElement('div');
      if (typeof renderCustomBomTree === 'function') renderCustomBomTree(wrapped, tmp, intent);
      while (tmp.firstChild) _graphEl.appendChild(tmp.firstChild);
    });
  }

  // ── Thought 區塊 ──────────────────────────────────────────────────────────

  function buildThoughtBlock(text) {
    return `<div class="thought-container">
      <div class="thought-header" onclick="this.parentElement.classList.toggle('collapsed')"></div>
      <div class="thought-content">${text}</div>
    </div>`;
  }

  // ── 捲動 ──────────────────────────────────────────────────────────────────

  function scrollToBottom() {
    if (_historyEl) _historyEl.scrollTop = _historyEl.scrollHeight;
  }

  return {
    init, appendUserMessage, appendAiMessage,
    showLoading, removeLoading, lockInput,
    stripBomDsl, renderDslBlocks, buildThoughtBlock, scrollToBottom,
  };
})();
