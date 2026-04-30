/**
 * matchmaking_controller.js - 製程與機台媒合控制器
 *
 * 職責：
 *   - 處理媒合表單的提交事件
 *   - 呼叫 ChatApi.runMatchmaking
 *   - 將結果傳遞給 MatchmakingView 渲染
 *
 * 依賴：ChatApi, MatchmakingView（需先載入）
 */

const MatchmakingController = (() => {

  // ── 執行媒合 ──────────────────────────────────────────────────────────────

  async function run(keywords, diameter, safetyFactor = 1.0) {
    if (!keywords || keywords.length === 0) {
      MatchmakingView.showError('請選擇至少一個功能關鍵字');
      return;
    }
    if (!diameter || isNaN(diameter)) {
      MatchmakingView.showError('請輸入有效的加工直徑');
      return;
    }

    MatchmakingView.showLoading(true);

    try {
      const result = await ChatApi.runMatchmaking(keywords, parseFloat(diameter), parseFloat(safetyFactor));
      if (!result.ok) throw new Error(result.msg || '媒合失敗');

      MatchmakingView.renderResult(result);
    } catch (e) {
      MatchmakingView.showError(`媒合失敗: ${e.message}`);
    } finally {
      MatchmakingView.showLoading(false);
    }
  }

  // ── 初始化表單事件 ────────────────────────────────────────────────────────

  function bindForm(formEl, keywordsGetter, diameterGetter, safetyGetter) {
    if (!formEl) return;
    formEl.addEventListener('submit', async (e) => {
      e.preventDefault();
      await run(keywordsGetter(), diameterGetter(), safetyGetter?.() ?? 1.0);
    });
  }

  return { run, bindForm };
})();
