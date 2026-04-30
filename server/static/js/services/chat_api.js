/**
 * chat_api.js - AI 對話 API Service
 *
 * 封裝 /api/chat、/api/matchmaking 的後端呼叫。
 */

const ChatApi = (() => {

  /**
   * 傳送聊天訊息
   * @param {string} message
   * @param {Array}  history        - 對話歷史 [{role, content}]
   * @param {string} model          - Ollama 模型名稱
   * @param {Object} context        - { current_path, current_analysis, current_allocation, current_pmi_session_id }
   * @returns {Promise<{reply, intent}>}
   */
  function sendMessage(message, history = [], model = '', context = {}) {
    return ApiClient.post('/api/chat', {
      message,
      history,
      model,
      ...context,
    });
  }

  /**
   * 執行製程與機台媒合
   * @param {string[]} keywords
   * @param {number}   diameter
   * @param {number}   safety_factor
   */
  function runMatchmaking(keywords, diameter, safety_factor = 1.0) {
    return ApiClient.post('/api/matchmaking', { keywords, diameter, safety_factor });
  }

  /**
   * 取得公差分析串流 URL（供 EventSource 使用）
   * @param {Array}  pathData
   * @param {Object} options - { n_samples, sigma, dist_type }
   * @returns {EventSource}
   */
  function createAnalysisStream(pathData, options = {}) {
    const params = new URLSearchParams({
      pathData:  JSON.stringify(pathData),
      n_samples: options.n_samples ?? 10000,
      sigma:     options.sigma     ?? 3.0,
      dist_type: options.dist_type ?? 0,
    });
    return new EventSource(`/api/analyze_tolerance_stream?${params}`);
  }

  /**
   * 上傳 Excel 路徑檔案
   * @param {File} file
   * @returns {Promise<{pathData}>}
   */
  async function importExcel(file) {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch('/api/import_excel', { method: 'POST', body: formData });
    if (!response.ok) throw new Error(`匯入失敗: HTTP ${response.status}`);
    return response.json();
  }

  return { sendMessage, runMatchmaking, createAnalysisStream, importExcel };
})();
