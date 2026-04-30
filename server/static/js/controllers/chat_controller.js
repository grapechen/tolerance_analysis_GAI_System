/**
 * chat_controller.js - 聊天介面控制器
 *
 * 職責：
 *   - 處理用戶輸入事件（Enter / 發送按鈕）
 *   - 維護對話歷史狀態
 *   - 解析 AI 回覆中的特殊標籤（ADJUST_TOLERANCE, HIGHLIGHT_PMI, thought）
 *   - 協調 ChatApi（資料） 與 ChatView（渲染）
 *
 * 依賴：ChatApi, ChatView（需先載入）
 */

const ChatController = (() => {
  let _chatHistory = [];
  let _currentModel = '';

  // ── 初始化 ────────────────────────────────────────────────────────────────

  function init(modelSelectEl) {
    _currentModel = modelSelectEl ? modelSelectEl.value : '';
    if (modelSelectEl) {
      modelSelectEl.addEventListener('change', () => {
        _currentModel = modelSelectEl.value;
      });
    }
  }

  // ── 發送訊息 ──────────────────────────────────────────────────────────────

  async function sendMessage(message) {
    if (!message.trim()) return;

    ChatView.lockInput(true);
    ChatView.appendUserMessage(message);

    _chatHistory.push({ role: 'user', content: message });

    const loadingId = ChatView.showLoading();

    const context = {
      current_path:             window.editorPathData        ?? null,
      current_analysis:         window._lastAnalysisResult   ?? null,
      current_allocation:       window._lastAllocationResult ?? null,
      current_pmi_session_id:   window._stepSessionId        ?? null,
    };

    try {
      const data = await ChatApi.sendMessage(
        message,
        _chatHistory.slice(-6),
        _currentModel,
        context,
      );

      ChatView.removeLoading(loadingId);
      _handleReply(data, message);

    } catch (e) {
      ChatView.removeLoading(loadingId);
      ChatView.appendAiMessage(`[ERROR] 網路錯誤：${e.message}`);
    } finally {
      ChatView.lockInput(false);
    }
  }

  // ── 回覆處理 ──────────────────────────────────────────────────────────────

  function _handleReply(data, originalMsg) {
    if (!data.reply) {
      ChatView.appendAiMessage('[WARN] 發生錯誤：無法取得回應');
      return;
    }

    let finalReply = data.reply;

    // [1] ADJUST_TOLERANCE 標籤
    const adjustRegex = /<ADJUST_TOLERANCE\s+target="([^"]+)"\s+grade="([^"]+)"\s*\/>/g;
    let m;
    while ((m = adjustRegex.exec(finalReply)) !== null) {
      const [, target, grade] = m;
      if (window.editorPathData && typeof window.updateITGrade === 'function') {
        const idx = window.editorPathData.findIndex(
          item => item.name === target || item.axis === target
        );
        if (idx !== -1) window.updateITGrade(idx, grade);
      }
    }
    finalReply = finalReply.replace(adjustRegex, '').trim();

    // [2] 公稱尺寸直接輸入
    const nominalRegex = /([\w\-]+)(?:的)?公稱尺寸(?:是|為)?\s*(\d+(?:\.\d+)?)/;
    const nMatch = originalMsg.match(nominalRegex);
    if (nMatch && window.editorPathData && typeof window.updateNominal === 'function') {
      const [, target, size] = nMatch;
      const idx = window.editorPathData.findIndex(
        item => item.name === target || item.axis === target
      );
      if (idx !== -1) window.updateNominal(idx, size);
    }

    // [3] HIGHLIGHT_PMI 標籤
    const highlightRegex = /<HIGHLIGHT_PMI\s+label="([^"]+)"\s*\/>/g;
    while ((m = highlightRegex.exec(finalReply)) !== null) {
      const label = m[1];
      if (typeof PmiPanel !== 'undefined') {
        PmiPanel.onAiHighlight(label);
        if (typeof openStepViewerPanel === 'function') openStepViewerPanel();
      }
    }
    finalReply = finalReply.replace(highlightRegex, '').trim();

    // [4] <thought> 標籤
    let thoughtHtml = '';
    const thoughtMatch = finalReply.match(/<thought>([\s\S]*?)<\/thought>/);
    if (thoughtMatch) {
      thoughtHtml = ChatView.buildThoughtBlock(thoughtMatch[1].trim());
      finalReply  = finalReply.replace(/<thought>[\s\S]*?<\/thought>/, '').trim();
    }

    // [5] BOM DSL 區塊
    const { cleanText, dslBlocks } = ChatView.stripBomDsl(finalReply);

    const textHtml = thoughtHtml + cleanText.split('\n').join('<br>');
    if (textHtml.trim()) ChatView.appendAiMessage(textHtml);

    if (dslBlocks.length > 0) ChatView.renderDslBlocks(dslBlocks, data.intent);

    _chatHistory.push({ role: 'assistant', content: data.reply });
    ChatView.scrollToBottom();
  }

  // ── 公開 API ──────────────────────────────────────────────────────────────

  return { init, sendMessage };
})();
