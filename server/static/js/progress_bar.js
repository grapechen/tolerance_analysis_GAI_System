/**
 * progress_bar.js - 實時進度條顯示模組
 * 使用 Server-Sent Events (SSE) 接收後端進度更新
 */

const ProgressBar = (() => {
    let eventSource = null;
    let currentProgress = {};

    /**
     * 初始化進度條
     */
    function init() {
        createProgressUI();
        connectSSE();
        console.log('✅ ProgressBar 初始化完成');
    }

    /**
     * 創建進度條 HTML 元素
     */
    function createProgressUI() {
        // 檢查是否已存在
        if (document.getElementById('progress-overlay')) {
            return;
        }

        const html = `
            <div id="progress-overlay" style="display: none;">
                <div class="progress-modal">
                    <div class="progress-header">
                        <h3 id="progress-title">處理中...</h3>
                        <button class="progress-close" onclick="ProgressBar.hide()">✕</button>
                    </div>
                    <div class="progress-body">
                        <div id="progress-message" class="progress-message">準備中...</div>
                        <div class="progress-bar-container">
                            <div id="progress-bar" class="progress-bar" style="width: 0%">
                                <span class="progress-text">0%</span>
                            </div>
                        </div>
                        <div class="progress-stats">
                            <span id="progress-current">0</span> /
                            <span id="progress-total">0</span>
                            <span id="progress-time" class="progress-time">耗時: 0s</span>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // 添加 CSS
        const style = document.createElement('style');
        style.textContent = `
            #progress-overlay {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.5);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10000;
            }

            .progress-modal {
                background: white;
                border-radius: 8px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
                min-width: 400px;
                max-width: 600px;
            }

            .progress-header {
                padding: 16px;
                border-bottom: 1px solid #eee;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }

            .progress-header h3 {
                margin: 0;
                font-size: 16px;
            }

            .progress-close {
                background: none;
                border: none;
                font-size: 24px;
                cursor: pointer;
                color: #999;
            }

            .progress-close:hover {
                color: #333;
            }

            .progress-body {
                padding: 20px;
            }

            .progress-message {
                margin-bottom: 16px;
                font-size: 14px;
                color: #666;
                min-height: 20px;
            }

            .progress-bar-container {
                width: 100%;
                height: 24px;
                background: #f0f0f0;
                border-radius: 4px;
                overflow: hidden;
                margin-bottom: 12px;
            }

            .progress-bar {
                height: 100%;
                background: linear-gradient(90deg, #4CAF50, #45a049);
                display: flex;
                align-items: center;
                justify-content: center;
                transition: width 0.3s ease;
                min-width: 0;
            }

            .progress-text {
                color: white;
                font-size: 12px;
                font-weight: bold;
                text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
            }

            .progress-stats {
                font-size: 13px;
                color: #999;
                display: flex;
                justify-content: space-between;
            }

            .progress-time {
                margin-left: auto;
            }

            /* 完成狀態 */
            .progress-bar.completed {
                background: linear-gradient(90deg, #4CAF50, #45a049);
            }

            /* 錯誤狀態 */
            .progress-bar.error {
                background: linear-gradient(90deg, #f44336, #da190b);
            }
        `;
        document.head.appendChild(style);

        // 添加 HTML
        document.body.insertAdjacentHTML('beforeend', html);
    }

    /**
     * 連接 SSE 流
     */
    function connectSSE() {
        if (eventSource) {
            eventSource.close();
        }

        eventSource = new EventSource('/api/step/progress');

        eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'update' || data.type === 'all_progress') {
                    currentProgress = data.data || {};
                    updateDisplay();
                }
            } catch (e) {
                console.error('❌ SSE 數據解析錯誤:', e);
            }
        };

        eventSource.onerror = (error) => {
            console.error('❌ SSE 連接錯誤:', error);
        };
    }

    /**
     * 更新進度顯示
     */
    function updateDisplay() {
        const overlay = document.getElementById('progress-overlay');
        if (!overlay) return;

        // 只有當有活動進度時才顯示
        const hasProgress = Object.values(currentProgress).some(p => p.status === 'running');

        if (!hasProgress) {
            return;
        }

        overlay.style.display = 'flex';

        // 取得第一個活動進度（通常只有一個）
        for (const [sessionId, progress] of Object.entries(currentProgress)) {
            if (progress.status === 'running' || progress.status === 'completed' || progress.status === 'error') {
                updateProgressDisplay(progress);
                break;
            }
        }
    }

    /**
     * 更新單個進度
     */
    function updateProgressDisplay(progress) {
        const percentage = Math.min(progress.percentage || 0, 100);

        // 更新標題
        document.getElementById('progress-title').textContent =
            progress.operation === 'parse_pmi' ? '📊 解析 PMI...' :
            progress.operation === 'asm_contact' ? '🔍 接觸分析...' :
            progress.operation === 'tessellate' ? '🔺 三角化...' :
            '處理中...';

        // 更新消息
        document.getElementById('progress-message').textContent = progress.message || '處理中...';

        // 更新進度條
        const progressBar = document.getElementById('progress-bar');
        progressBar.style.width = percentage + '%';

        // 移除狀態類
        progressBar.classList.remove('completed', 'error');
        if (progress.status === 'completed') {
            progressBar.classList.add('completed');
            document.getElementById('progress-title').textContent += ' ✅';
        } else if (progress.status === 'error') {
            progressBar.classList.add('error');
            document.getElementById('progress-title').textContent += ' ❌';
        }

        // 更新百分比文本
        const textElement = progressBar.querySelector('.progress-text');
        if (textElement) {
            textElement.textContent = Math.round(percentage) + '%';
        }

        // 更新計數
        document.getElementById('progress-current').textContent = progress.current || 0;
        document.getElementById('progress-total').textContent = progress.total || 0;

        // 更新耗時
        const elapsed = Math.round(progress.elapsed || 0);
        document.getElementById('progress-time').textContent =
            `耗時: ${elapsed}s`;
    }

    /**
     * 顯示進度條
     */
    function show(message = '處理中...') {
        const overlay = document.getElementById('progress-overlay');
        if (overlay) {
            overlay.style.display = 'flex';
        }
    }

    /**
     * 隱藏進度條
     */
    function hide() {
        const overlay = document.getElementById('progress-overlay');
        if (overlay) {
            overlay.style.display = 'none';
        }
    }

    /**
     * 清理資源
     */
    function dispose() {
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
    }

    return {
        init,
        show,
        hide,
        dispose,
        connectSSE,
        updateDisplay
    };
})();

// 頁面加載時初始化
document.addEventListener('DOMContentLoaded', () => {
    ProgressBar.init();
});

// 頁面卸載時清理
window.addEventListener('beforeunload', () => {
    ProgressBar.dispose();
});
