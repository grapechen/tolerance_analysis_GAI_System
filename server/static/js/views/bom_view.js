/**
 * bom_view.js - BOM 樹狀圖 View
 *
 * 職責：
 *   - 渲染 BOM DSL 樹狀結構到指定容器
 *   - 管理節點展開 / 收縮互動
 *   - 套用象限顏色 (Q1-Q4) 標記
 *
 * 不含業務邏輯或 API 呼叫。
 * 依賴 bom_renderer.js / bom_render.js 中的 renderCustomBomTree()。
 */

const BomView = (() => {
  let _containerEl = null;

  // ── 初始化 ────────────────────────────────────────────────────────────────

  function init(containerEl) {
    _containerEl = containerEl;
  }

  // ── 渲染 DSL ──────────────────────────────────────────────────────────────

  function renderDsl(dslText, intent = {}) {
    if (!_containerEl) return;
    _containerEl.innerHTML = '';

    const wrapped = dslText.startsWith('---BOM_START---')
      ? dslText
      : `---BOM_START---${dslText}---BOM_END---`;

    const tmp = document.createElement('div');
    if (typeof renderCustomBomTree === 'function') {
      renderCustomBomTree(wrapped, tmp, intent);
      while (tmp.firstChild) _containerEl.appendChild(tmp.firstChild);
    } else {
      _containerEl.textContent = '[BomView] renderCustomBomTree 未載入';
    }
  }

  // ── 更新象限標記 ──────────────────────────────────────────────────────────

  const QUADRANT_CLASSES = {
    1: 'q1-critical',
    2: 'q2-maintain',
    3: 'q3-minor',
    4: 'q4-relax',
  };

  function applyQuadrants(quadrantMap) {
    if (!_containerEl || !quadrantMap) return;
    Object.entries(quadrantMap).forEach(([name, q]) => {
      const nodes = _containerEl.querySelectorAll(`[data-name="${name}"]`);
      nodes.forEach(node => {
        Object.values(QUADRANT_CLASSES).forEach(cls => node.classList.remove(cls));
        if (QUADRANT_CLASSES[q]) node.classList.add(QUADRANT_CLASSES[q]);
      });
    });
  }

  // ── 清空 ──────────────────────────────────────────────────────────────────

  function clear() {
    if (_containerEl) _containerEl.innerHTML = '';
  }

  return { init, renderDsl, applyQuadrants, clear };
})();
