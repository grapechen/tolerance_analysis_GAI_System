/**
 * pmi_panel.js - PMI 清單面板控制器
 * ========================================
 * 管理 #pmi-list-container 的清單項目與點擊事件
 */

const PmiPanel = (() => {
    let _pmiRows = [];
    let _sessionId = null;
    let _checkedRows = new Set();

    /**
     * 初始化渲染 PMI 清單（帶勾選框）
     */
    function render(pmiRows, sessionId) {
        _pmiRows = pmiRows;
        _sessionId = sessionId;
        _checkedRows.clear();

        const container = document.getElementById('pmi-list-container');
        if (!container) {
            console.error('❌ #pmi-list-container 元素不存在');
            return;
        }

        container.innerHTML = '';

        if (!pmiRows || pmiRows.length === 0) {
            container.innerHTML = '<p style="padding:10px; color:#999;">沒有 PMI 項目</p>';
            return;
        }

        const ul = document.createElement('ul');
        ul.style.cssText = 'list-style:none; padding:0; margin:0;';

        pmiRows.forEach((row, idx) => {
            const li = document.createElement('li');
            li.style.cssText = `
                padding: 6px 4px;
                border-bottom: 1px solid #eee;
                cursor: pointer;
                transition: background-color 0.2s;
                display: flex;
                align-items: center;
                gap: 6px;
            `;
            li.onmouseover = () => li.style.backgroundColor = '#f5f5f5';
            li.onmouseout = () => li.style.backgroundColor = 'transparent';

            // 勾選框
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.style.cssText = 'cursor:pointer; margin:0;';
            checkbox.onchange = (e) => {
                e.stopPropagation();
                if (checkbox.checked) {
                    _checkedRows.add(idx);
                } else {
                    _checkedRows.delete(idx);
                }
                console.log(`✓ PMI [${idx}] 勾選狀態: ${checkbox.checked}`);
                if (typeof StepViewer !== 'undefined' && StepViewer.syncHighlights) {
                    StepViewer.syncHighlights(Array.from(_checkedRows));
                }
            };

            // 預設樣式處理
            let typeColor = '#999';
            let icon = '';
            let prefix = '';
            if (row.is_datum || row.is_feature_only) {
                typeColor = '#10b981'; // 綠
                // 若為特徵面，顯示冰塊，若為基準則顯示紅旗
                icon = row.is_feature_only ? '🧊' : '🚩';
            } else if (row.is_interactive) {
                typeColor = '#a121f0'; // 紫
                icon = '🎯';
                prefix = '[交互] ';
            } else {
                typeColor = '#ffa500'; // 橘
                icon = '🎯';
                prefix = '[個別] ';
            }

            const labelSpan = document.createElement('span');
            labelSpan.style.cssText = `
                color: ${typeColor};
                font-weight: bold;
                font-size: 12px;
                flex: 1;
            `;

            // 去除原有的 label 前綴避免重複，然後重新組合
            let displayLabel = row.label || '(未命名)';
            displayLabel = displayLabel.replace(/\[交互\] /g, '').replace(/\[個別\] /g, '');
            // 去除原有的圖示避免重複
            displayLabel = displayLabel.replace(/🎯 |📐 |🚩 |🧊 /g, '');
            
            labelSpan.innerHTML = `<span style="margin-right:4px;">${icon}</span>${prefix}${displayLabel}`;

            labelSpan.onclick = (e) => {
                e.stopPropagation();
                checkbox.checked = !checkbox.checked;
                checkbox.dispatchEvent(new Event('change'));
            };

            li.appendChild(checkbox);
            li.appendChild(labelSpan);
            ul.appendChild(li);
        });

        container.appendChild(ul);
        console.log(`✅ PMI 清單已渲染 (${pmiRows.length} 項，帶勾選框)`);
    }

    /**
     * 點擊清單項目時的回調
     */
    function onRowClick(rowIndex) {
        console.log(`🔍 點選 PMI [${rowIndex}]: ${_pmiRows[rowIndex]?.label}`);
        if (typeof StepViewer !== 'undefined') {
            StepViewer.highlightPmiRow(rowIndex);
        }
    }

    /**
     * AI 指令觸發高亮（基於標籤子串）
     */
    function onAiHighlight(labelSubstring) {
        if (!labelSubstring) return;

        const idx = _pmiRows.findIndex(r =>
            r.label.toLowerCase().includes(labelSubstring.toLowerCase())
        );

        if (idx !== -1) {
            console.log(`✨ AI 高亮：${_pmiRows[idx].label}`);
            onRowClick(idx);
            scrollToRow(idx);
        } else {
            console.warn(`⚠️ 找不到符合的 PMI: ${labelSubstring}`);
        }
    }

    /**
     * 滾動清單至指定項目
     */
    function scrollToRow(rowIndex) {
        const container = document.getElementById('pmi-list-container');
        if (!container) return;

        const items = container.querySelectorAll('li');
        if (items[rowIndex]) {
            items[rowIndex].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    /**
     * 全選所有 PMI 項目
     */
    function selectAll() {
        const checkboxes = document.querySelectorAll('#pmi-list-container input[type="checkbox"]');
        checkboxes.forEach((cb, idx) => {
            cb.checked = true;
            _checkedRows.add(idx);
        });
        console.log(`✓ 已全選 ${checkboxes.length} 項`);
        if (typeof StepViewer !== 'undefined' && StepViewer.syncHighlights) {
            StepViewer.syncHighlights(Array.from(_checkedRows));
        }
    }

    /**
     * 全清所有勾選
     */
    function clearAll() {
        const checkboxes = document.querySelectorAll('#pmi-list-container input[type="checkbox"]');
        checkboxes.forEach((cb) => {
            cb.checked = false;
        });
        _checkedRows.clear();
        console.log('✓ 已清除所有勾選');
        if (typeof StepViewer !== 'undefined' && StepViewer.syncHighlights) {
            StepViewer.syncHighlights([]);
        }
    }

    /**
     * 取得所有勾選的 PMI 索引
     * @returns {Array<number>} 勾選的行索引
     */
    function getAllChecked() {
        return Array.from(_checkedRows).sort((a, b) => a - b);
    }

    /**
     * 清空清單
     */
    function clear() {
        const container = document.getElementById('pmi-list-container');
        if (container) {
            container.innerHTML = '';
        }
        _pmiRows = [];
        _sessionId = null;
        _checkedRows.clear();
    }

    // 暴露公共 API
    return {
        render,
        onRowClick,
        onAiHighlight,
        selectAll,
        clearAll,
        getAllChecked,
        clear
    };
})();
