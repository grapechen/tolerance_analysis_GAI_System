from flask import Flask, request, jsonify, render_template_string, send_from_directory
from flask_cors import CORS
from rag_server import get_rag_response
import os
import ollama
import google.generativeai as genai

app = Flask(__name__)
CORS(app)  # 允許來自 7010 的前端跨網域請求 (CORS)

# 設定 Google Gemini API Key
genai.configure(api_key="AIzaSyCGGqm6qeY8s8bA-xXIewEdb2sq5ecB8Rg")

# HTML Template for the Chat App
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ISO 286 AI 智能助手</title>
  <style>
    /* 幾何公差符號字體支援 */
    @font-face {
      font-family: 'GDT Symbols';
      src: local('GDTFONT'), local('GD&T Symbols'), local('ISO Symbols');
      font-display: swap;
    }
    
    :root {
      --bg-color: #0f172a;
      --chat-bg: #1e293b;
      --user-msg-bg: #3b82f6;
      --ai-msg-bg: #334155;
      --text-color: #f1f5f9;
      --input-bg: #334155;
      --border-color: #475569;
    }
    body {
      font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--bg-color);
      color: var(--text-color);
      margin: 0;
      display: flex;
      flex-direction: column;
      height: 100vh;
    }
    
    /* 幾何公差符號樣式 */
    .gdt-symbol {
      font-family: 'GDT Symbols', 'Segoe UI Symbol', 'Arial Unicode MS', sans-serif;
      font-size: 1.1em;
      font-weight: normal;
    }
    .header {
      padding: 15px 20px;
      background-color: var(--chat-bg);
      border-bottom: 1px solid var(--border-color);
      display: flex;
      align-items: center;
      justify-content: space-between;
      box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    .header h1 { margin: 0; font-size: 1.2rem; display: flex; align-items: center; gap: 10px; }
    .status-dot { width: 10px; height: 10px; background-color: #22c55e; border-radius: 50%; display: inline-block; }
    
    .model-selector {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    select {
      padding: 6px 12px;
      border-radius: 6px;
      background-color: var(--input-bg);
      color: white;
      border: 1px solid var(--border-color);
      outline: none;
      font-size: 0.9rem;
      min-width: 180px;
    }
    select option[data-cloud="true"] {
      background-color: #1e3a5f;
      font-weight: bold;
    }
    
    .chat-container {
      flex: 1;
      overflow-y: auto;
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 15px;
      scroll-behavior: smooth;
    }
    
    .message {
      display: flex;
      max-width: 80%;
      animation: fadeIn 0.3s ease;
    }
    .message.user {
      align-self: flex-end;
      flex-direction: row-reverse;
    }
    .message.ai {
      align-self: flex-start;
    }
    
    .avatar {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: bold;
      flex-shrink: 0;
      margin: 0 10px;
    }
    .user .avatar { background-color: #64748b; }
    .ai .avatar { background-color: #8b5cf6; }
    
    .bubble {
      padding: 12px 16px;
      border-radius: 12px;
      line-height: 1.6;
      font-size: 1rem;
      position: relative;
      word-wrap: break-word;
    }
    .user .bubble {
      background-color: var(--user-msg-bg);
      color: white;
      border-bottom-right-radius: 2px;
    }
    .ai .bubble {
      background-color: var(--ai-msg-bg);
      color: var(--text-color);
      border-bottom-left-radius: 2px;
      border: 1px solid var(--border-color);
    }
    
    .input-area {
      padding: 20px;
      background-color: var(--chat-bg);
      border-top: 1px solid var(--border-color);
      display: flex;
      gap: 10px;
    }
    input[type="text"] {
      flex: 1;
      padding: 12px 16px;
      border-radius: 24px;
      border: 1px solid var(--border-color);
      background-color: var(--input-bg);
      color: white;
      font-size: 1rem;
      outline: none;
      transition: border-color 0.2s;
    }
    input[type="text"]:focus {
      border-color: var(--user-msg-bg);
    }
    button {
      padding: 10px 24px;
      border-radius: 24px;
      border: none;
      background-color: var(--user-msg-bg);
      color: white;
      font-weight: bold;
      cursor: pointer;
      transition: opacity 0.2s;
    }
    button:hover { opacity: 0.9; }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    
    .typing-indicator {
      display: flex;
      gap: 4px;
      padding: 4px 8px;
    }
    .typing-dot {
      width: 6px;
      height: 6px;
      background-color: #94a3b8;
      border-radius: 50%;
      animation: bounce 1.4s infinite ease-in-out both;
    }
    .typing-dot:nth-child(1) { animation-delay: -0.32s; }
    .typing-dot:nth-child(2) { animation-delay: -0.16s; }
    
    @keyframes bounce {
      0%, 80%, 100% { transform: scale(0); }
      40% { transform: scale(1); }
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(10px); }
      to { opacity: 1; transform: translateY(0); }
    }
    
    /* Markdown style for AI response */
    /* Custom BOM Tree Styles (Grid Layout) */
    .bom-container {
      background: white;
      border-radius: 8px;
      margin-top: 10px;
      font-family: sans-serif;
      width: 100%;
      padding: 20px;
      box-sizing: border-box;
      position: relative; /* for SVG absolute positioning */
    }
    
    .bom-node {
      border: 2px solid #0f172a;
      padding: 10px 5px;
      background: white;
      color: #0f172a;
      text-align: center;
      position: relative;
      z-index: 2;
      width: 100%;
      box-sizing: border-box;
      word-wrap: break-word;
      line-height: 1.4;
      font-size: 0.9rem;
      font-weight: bold;
      border-radius: 4px;
    }
    
    .bom-node.root-node {
      width: fit-content;
      min-width: 250px;
      word-wrap: normal;
      padding: 12px 40px;
      font-size: 1.25rem;
      margin-bottom: 0;
      background: #f1f5f9;
      border-radius: 12px;
      box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
      border-color: #1e293b;
    }


    /* Layout specific modes */
    .layout-grid {
      display: block;
      overflow-x: auto; 
      width: 100%;
    }

    .layout-grid .bom-children {
      display: grid;
      /* 自適應 (Responsive): 依照螢幕寬度自動決定欄數。
         每個方塊最少佔 350px (因為加了交互公差會變很寬)，如果有剩餘空間就平均分配 (1fr)。
         如果螢幕夠寬就會排成 4 欄、3 欄，如果螢幕小一點就會變成 2 欄。 */
      grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
      gap: 30px; 
      width: 100%;
      /* 限制最小寬度，確保再怎麼擠也不會變成「全部排成一條直線深不見底」，
         如果螢幕真的太小 (小於 750px)，就會觸發父層的水平捲軸，保證至少維持 2 欄的感覺 */
      min-width: 750px; 
      margin: 0 auto;
      justify-items: center;
    }

    .layout-grid .bom-child {
      position: relative;
      display: flex;
      flex-direction: column;
      align-items: center;
      width: 100%;
      border: 2px dashed #0ea5e9; /* Dashed boundary similar to image */
      border-radius: 12px;
      padding: 15px;
      background: rgba(240, 249, 255, 0.4); /* Slight tint to define areas */
      box-sizing: border-box;
    }

    .layout-grid .bom-child::before, .layout-grid .bom-child::after {
      display: none !important;
    }
    
    /* Tree Layout Scroll Canvas */
    .layout-tree {
      display: block; /* Let it flow block-level so overflow-x works right */
      overflow-x: auto; 
    }
    
    .layout-tree .bom-tree-canvas {
      display: flex;
      flex-direction: column;
      align-items: center;
      width: max-content; 
      min-width: 100%; 
      padding: 20px 10px;
      margin: 0 auto; 
    }

    .layout-tree .bom-children {
      display: flex;
      flex-direction: row;
      justify-content: center; 
      width: 100%; 
      padding-top: 30px; /* Space for the line from parent */
      padding-bottom: 20px;
      position: relative;
    }

    /* Vertical line down from parent to the children's horizontal branch */
    .layout-tree .bom-children::before {
      content: '';
      position: absolute;
      top: 0;
      left: 50%;
      width: 2px;
      height: 30px;
      background-color: #0f172a;
      z-index: 1;
    }

    .layout-tree .bom-child {
      position: relative;
      padding-top: 25px; /* Space for horizontal connector */
      display: flex;
      flex-direction: column;
      flex: 0 0 auto; 
      padding-left: 5px; 
      padding-right: 5px;
    }

    /* Horizontal line across the top of siblings */
    .layout-tree .bom-child::before {
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 2px;
      background-color: #0f172a;
      z-index: 1;
    }

    /* Vertical connector UP to the horizontal line */
    .layout-tree .bom-child::after {
      content: '';
      position: absolute;
      top: 0;
      left: calc(50% - 1px);
      width: 2px;
      height: 25px;
      background-color: #0f172a;
    }

    /* First child logic for horizontal bar */
    .layout-tree .bom-child:first-child::before {
      left: 50%;
      width: 50%;
    }

    /* Last child logic for horizontal bar */
    .layout-tree .bom-child:last-child::before {
      left: 0;
      width: 50%;
    }
    
    /* Only child logic */
    .layout-tree .bom-child:only-child::before {
      display: none !important;
    }

    /* Root node logic: hide connectors above it */
    .layout-tree .bom-tree-canvas > .bom-child::before,
    .layout-tree .bom-tree-canvas > .bom-child::after {
      display: none !important;
    }
    
    .layout-tree .bom-tree-canvas > .bom-child {
      padding-top: 0;
    }

    /* Nested Feature Styles */
    .bom-features-list {
      display: flex;
      flex-direction: column;
      align-items: center;
      margin-top: 20px;
      position: relative;
      width: 100%;
    }
    
    .bom-feature-row {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 36px; /* 縮小列高，讓特徵排更緊湊 */
      position: relative;
      width: 100%;
    }

    /* Central vertical trunk passing THROUGH nodes (恢復貫穿線) */
    .bom-feature-row::after {
      content: '';
      position: absolute;
      left: calc(50% - 1px);
      top: -10px;
      width: 2px;
      height: 46px; /* 36 + 10 */
      background-color: #0f172a;
      z-index: 1;
    }
    
    .bom-feature-row:first-child::after {
      top: -20px;
      height: 56px; 
    }

    .bom-feature-row.last-feature-row::after {
      top: -10px;
      height: 28px; /* 停在最後一個節點的中心 */
    }

    .bom-feature-row:first-child.last-feature-row::after {
      top: -20px;
      height: 38px;
    }

    .bom-feature-node {
      border: 2px solid #0f172a;
      padding: 6px 10px;
      background: white;
      color: #0f172a;
      text-align: center;
      width: 120px;
      box-sizing: border-box;
      word-wrap: break-word;
      line-height: 1.3;
      font-size: 0.85rem;
      position: relative;
      z-index: 10;
      border-radius: 4px;
      cursor: pointer;
      transition: box-shadow 0.2s, border-color 0.2s, background-color 0.2s;
    }
    
    .bom-feature-node:hover {
      box-shadow: 0 0 8px rgba(34, 197, 94, 0.6);
      border-color: #22c55e;
    }
    
    .bom-feature-node.contact-selected {
      background-color: #dcfce7;
      border-color: #22c55e;
      box-shadow: 0 0 8px rgba(34, 197, 94, 0.8);
    }

    
    /* 從節點右側長出去的水平線 (公差的軌道起始線) */
    .bom-feature-node::after {
      content: '';
      position: absolute;
      top: calc(50% - 1px);
      right: -1000px; /* 向右拉長，會在 JS 中被 rail 蓋住或由 rail 取代 */
      width: 0; 
      height: 2px;
      background-color: transparent;
    }

    .tol-rail-container {
      position: absolute;
      left: 100%; /* 接在 bom-feature-node 右邊 */
      top: 50%;
      height: 2px;
      background-color: #a855f7; /* 改成紫色，因為圖二橋接線是紫色 */
      display: flex;
      align-items: center;
      padding-left: 20px; /* 給單一公差(橘色)一點空間 */
      box-sizing: border-box; /* 避免 padding 撐大影響斷線計算 */
      gap: 15px;
      z-index: 5;
    }

    /* 單一公差 (橘色) 置於 flex 容器中自然排列，不使用絕對定位避免相疊 */
    .tol-individual-wrapper {
      position: relative;
      background: white; /* 蓋住後面的紫線 */
      padding: 0 4px;
      z-index: 10;
    }

    .tolerance-bubble {
      font-size: 0.7rem;
      padding: 3px 8px;
      border-radius: 12px;
      color: white;
      font-weight: bold;
      white-space: nowrap;
      box-shadow: 0 2px 4px rgba(0,0,0,0.1);
      z-index: 15;
    }
    .tol-individual { background-color: white; border: 2px solid #f59e0b; color: #f59e0b; border-radius: 12px; font-style: italic; font-weight: bold;}
    
    .tol-interactive-wrapper {
      position: absolute;
      background: white;
      padding: 4px;
      z-index: 25;
      /* JS 會設定 left 和 top */
    }
    .tol-interactive { 
      background-color: white; 
      border: 2px solid #a855f7;
      color: #a855f7;
      font-weight: bold;
      font-style: italic;
    }

    /* Vertical Rungs for Bridges */
    .tol-bridge-rung {
      position: absolute;
      width: 2px;
      background-color: #a855f7;
      z-index: 20;
    }

    /* Modal Styles */
    .bom-modal-overlay {
      display: none;
      position: fixed;
      top: 0; left: 0; width: 100%; height: 100%;
      background: rgba(0,0,0,0.8);
      z-index: 1000;
      justify-content: center;
      align-items: center;
    }
    .bom-modal-content {
      background: #f8fafc;
      padding: 40px;
      border-radius: 12px;
      position: relative;
      max-width: 90%;
      max-height: 90%;
      overflow: auto;
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
    }
    .close-modal-btn {
      position: absolute;
      top: 10px; right: 15px;
      background: none; border: none;
      font-size: 24px; color: #64748b;
      cursor: pointer;
      padding: 0; margin: 0;
    }
    .close-modal-btn:hover { color: #0f172a; }
    
    .open-bom-btn {
      background: #3b82f6;
      color: white; border: none; padding: 8px 16px;
      border-radius: 8px; cursor: pointer;
      margin-top: 10px; font-weight: bold;
      transition: background 0.2s;
    }
    .open-bom-btn:hover { background: #2563eb; }
    
    .clear-lines-btn {
      background: #ef4444; color: white; border: none; padding: 6px 12px;
      border-radius: 6px; cursor: pointer;
      font-size: 0.85rem; font-weight: bold;
      position: absolute; top: 15px; left: 15px;
      transition: background 0.2s;
    }
    .clear-lines-btn:hover { background: #dc2626; }
    
    /* Tolerance Path Editor Styles */
    .editor-modal-overlay {
      display: none;
      position: fixed;
      top: 0; left: 0; width: 100%; height: 100%;
      background: rgba(0,0,0,0.8);
      z-index: 2000;
      justify-content: center;
      align-items: center;
    }
    .editor-modal-content {
      background: #f8fafc;
      padding: 30px;
      border-radius: 12px;
      position: relative;
      width: 700px;
      max-width: 90%;
      max-height: 90%;
      display: flex;
      flex-direction: column;
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
    }
    .editor-header {
      font-size: 1.2rem;
      font-weight: bold;
      margin-bottom: 20px;
      color: #0f172a;
    }
    .editor-list {
      flex: 1;
      overflow-y: auto;
      border: 1px solid #cbd5e1;
      border-radius: 8px;
      padding: 10px;
      background: white;
      margin-bottom: 20px;
    }
    .editor-row {
      display: flex;
      align-items: center;
      padding: 8px;
      border-bottom: 1px solid #f1f5f9;
      gap: 10px;
    }
    .editor-row.feature-row { background: #f8fafc; }
    .editor-row.spatial-row { background: #f0fdf4; border: 1px dashed #22c55e; }
    
    .editor-col { flex: 1; }
    .col-type { font-weight: bold; width: 80px; flex: none;}
    .col-name { width: 150px; flex: none; }
    .col-val { flex: 1; display:flex; align-items:center; gap:5px;}
    
    .editor-row input, .editor-row select {
      padding: 4px 8px;
      border: 1px solid #cbd5e1;
      border-radius: 4px;
      font-size: 0.9rem;
    }
    .btn-remove {
      background: #ef4444; color: white; border: none; padding: 4px 8px; border-radius: 4px; cursor: pointer;
    }
    .btn-add-between {
      display: block; width: 100%; background: #e2e8f0; border: 1px dashed #94a3b8; color: #64748b; padding: 5px; text-align: center; cursor: pointer; margin: 5px 0; border-radius: 4px; transition: 0.2s;
    }
    .btn-add-between:hover { background: #cbd5e1; color: #0f172a; }
    .editor-actions {
      display: flex; justify-content: flex-end; gap: 10px;
    }
    .btn-export {
      background: #10b981; color: white; border: none; padding: 10px 20px; border-radius: 8px; font-weight: bold; cursor: pointer;
    }
    .btn-export:hover { background: #059669; }
    .open-editor-btn {
      background: #10b981;
      color: white; border: none; padding: 8px 16px;
      border-radius: 8px; cursor: pointer;
      margin-top: 10px; margin-left: 10px; font-weight: bold;
      transition: background 0.2s;
    }
    .open-editor-btn:hover { background: #059669; }
  </style>
</head>
<body>

  <div class="header">
    <h1>
      <div class="status-dot"></div>
       AI 智能助手
    </h1>
    <div class="model-selector">
      <label for="model-select" style="font-size: 0.9rem; color: #94a3b8;">Model:</label>
      <select id="model-select">
        {% for model in models %}
        {% set model_lower = model.lower() %}
        {% set is_cloud = '-cloud' in model_lower or ':cloud' in model_lower or model_lower.startswith('gpt-oss') or model_lower.startswith('qwen3-vl') or model_lower.startswith('qwen3-v1') or model_lower.startswith('ministral-3') or model_lower.startswith('qwen3-coder') or model_lower.startswith('glm-5') or model_lower.startswith('glm-4') or model_lower.startswith('deepseek') or model_lower.startswith('minimax') or model_lower.startswith('gemini-3') or model_lower.startswith('kimi') or model_lower.startswith('qwen3.5') or model_lower.startswith('nemotron') %}
        <option value="{{ model }}" {% if model == current_model %}selected{% endif %} {% if is_cloud %}data-cloud="true"{% endif %}>
          {% if is_cloud %}☁️ {% endif %}{{ model }}
        </option>
        {% endfor %}
      </select>
    </div>
  </div>

  <div class="chat-container" id="chat-history">
    <!-- Welcome Message -->
    <div class="message ai">
      <div class="avatar">AI</div>
      <div class="bubble">
        你好！我是您的AI智能助手。<br>
        您可以問我像是：<br>
        • <strong>25mm H7</strong> (查詢單一公差)<br>
        • <strong>分析 25mm H7/h6</strong> (進行配合分析)<br>
        • <strong>精密迴轉滑台包含哪些零件？</strong> (畫出產品架構圖)<br>
        請問有什麼我可以幫您的嗎？
      </div>
    </div>
  </div>

  <div class="input-area">
    <input type="text" id="chat-input" placeholder="輸入您的問題..." autocomplete="off">
    <button onclick="sendMessage()" id="send-btn">發送</button>
  </div>

  <!-- Interactive BOM Modal -->
  <div class="bom-modal-overlay" id="bom-modal-overlay" onclick="if(event.target === this) closeBomModal()">
    <div class="bom-modal-content">
      <button class="close-modal-btn" onclick="closeBomModal()">&times;</button>
      <div id="bom-modal-container"></div>
    </div>
  </div>

  <!-- Tolerance Path Editor Modal -->
  <div class="editor-modal-overlay" id="editor-modal-overlay" onclick="if(event.target === this) closeEditorModal()">
    <div class="editor-modal-content">
      <button class="close-modal-btn" onclick="closeEditorModal()">&times;</button>
      <div class="editor-header">✏️ 公差路徑編輯器 (加入平移/旋轉)</div>
      <div class="editor-list" id="editor-list-container">
        <!-- Rendered by JS -->
      </div>
      <div class="editor-actions">
        <button class="btn-export" onclick="exportExcel()">⬇️ 匯出為 Excel 分析檔</button>
      </div>
    </div>
  </div>

  <script>
    const input = document.getElementById('chat-input');
    const history = document.getElementById('chat-history');
    const sendBtn = document.getElementById('send-btn');
    const modelSelect = document.getElementById('model-select');

    // Handle Enter key
    input.addEventListener('keypress', function (e) {
      if (e.key === 'Enter') sendMessage();
    });

    // 處理自定義產品架構圖的函式
    function renderCustomBomTree(text, bubbleElement, intent) {
        let formatted = text.replace(/\\n/g, '<br>');
        
        // Decide Layout based on Intent
        let layoutClass = 'layout-tree'; // Default is Horizontal tree
        if (intent && intent.layout === 'grid') {
            layoutClass = 'layout-grid';
        }
        
        let enableContact = intent && intent.contact === true;
        let enableEdit = intent && intent.edit === true;
        
        // 尋找 BOM 區塊
        const bomRegex = /---BOM_START---([\s\S]*?)---BOM_END---/g;
        let match;
        let lastIndex = 0;
        let finalHtml = '';
        
        while ((match = bomRegex.exec(formatted)) !== null) {
            finalHtml += formatted.substring(lastIndex, match.index);
            
            let listContent = match[1].trim();
            // 處理換行問題，統一轉換以利逐行解析
            listContent = listContent.replace(/<br>/g, '\\n');
            const lines = listContent.split('\\n');
            
            let currentPart = null;
            let assemblyName = '產品架構圖'; // 預設名稱
            
            // 逐行解析雙層/多層結構
            let rootParts = [];
            let partStack = []; // 追蹤目前的零件階層 [{depth: 0, part: obj}, {depth: 2, part: obj}]
            
            lines.forEach(line => {
                if (!line.trim()) return;
                
                if (line.trim().startsWith('#')) {
                    assemblyName = line.replace(/^#\s*/, '').trim();
                    return;
                }
                
                // 計算縮進深度 (以兩個空白或一個 Tab 為一單位)
                const leadingSpaceMatch = line.match(/^(\s*)/);
                const rawIndent = leadingSpaceMatch ? leadingSpaceMatch[1].length : 0;
                // 為了包容不同縮進格式，大致以2為一個層級，或者是抓實際相對深度
                
                const cleanLine = line.trim();
                const isFeatureLine = cleanLine.match(/^[-*]\s*\d+-[PHS]-\d+(.*)/i) || cleanLine.startsWith('*');
                const partMatch = cleanLine.match(/^[-*]\s*(\d+)-(.+)/i);
                
                if (partMatch && !isFeatureLine) {
                    const newPart = {
                        id: parseInt(partMatch[1]),
                        name: partMatch[1] + '-' + partMatch[2].trim(),
                        features: [],
                        children: []
                    };
                    
                    // 決定層級歸屬
                    if (partStack.length === 0) {
                        rootParts.push(newPart);
                        partStack.push({depth: rawIndent, part: newPart});
                    } else {
                        // 找到目前所屬的父節點 (從 stack 中往回找第一個 depth 比較小的)
                        while (partStack.length > 0 && partStack[partStack.length - 1].depth >= rawIndent) {
                            partStack.pop();
                        }
                        
                        if (partStack.length === 0) {
                            // 變成第一層
                            rootParts.push(newPart);
                        } else {
                            // 變成子零件
                            partStack[partStack.length - 1].part.children.push(newPart);
                        }
                        partStack.push({depth: rawIndent, part: newPart});
                    }
                    return;
                }
                
                // 特徵面解析 (掛在目前 stack 最頂層的零件上)
                const featureMatch = cleanLine.match(/^[-*]\s*([^\(\[\s]+)(.*)/);
                if (featureMatch && isFeatureLine) {
                    let attachTarget = null;
                    if (partStack.length > 0) {
                        attachTarget = partStack[partStack.length - 1].part;
                    } else {
                        // 如果沒有父節點，建一個孤立節點
                        const m = cleanLine.match(/^[-*]\s*(\d+)-/);
                        const partId = m ? m[1] : 'Unknown';
                        attachTarget = {
                            id: partId === 'Unknown' ? 999 : parseInt(partId),
                            name: `${partId}-特徵集合`,
                            features: [],
                            children: []
                        };
                        rootParts.push(attachTarget);
                        partStack.push({depth: 0, part: attachTarget});
                    }

                    const featureName = featureMatch[1].trim();
                    const extra = featureMatch[2].trim();
                    
                    let individuals = [];
                    let interactives = [];
                    const allTolerances = [];
                    
                    const parenMatch = extra.match(/\((.*?)\)/);
                    if (parenMatch) allTolerances.push(...parenMatch[1].split(/[,，\s]+/).map(s => s.trim()).filter(s => s));
                    
                    const bracketMatch = extra.match(/\[(.*?)\]/);
                    if (bracketMatch) allTolerances.push(...bracketMatch[1].split(/[,，\s]+/).map(s => s.trim()).filter(s => s));

                    const interactiveKeywords = ['par', 'per', 'dis', 'con', 'ang', 'sym', 'pos', 'run'];
                    allTolerances.forEach(tol => {
                        const isInteractive = interactiveKeywords.some(kw => tol.toLowerCase().includes(kw));
                        if (isInteractive) interactives.push(tol);
                        else individuals.push(tol);
                    });

                    attachTarget.features.push({
                        name: featureName,
                        individuals: individuals,
                        interactives: interactives
                    });
                }
            });

            console.log("Parsed BOM Structure:", JSON.stringify(rootParts, null, 2));
            
            // 將原本 flat structure 轉換為相容的形式，讓後面的 HTML 生成也能處理 children
            const parts = rootParts;            
            // 依照使用者要求，依據組裝順序 (從上到下: 1 -> 9)，對應圖表從左到右
            parts.sort((a, b) => a.id - b.id);

            // 對特徵面進行 P -> S -> H 排序
            parts.forEach(part => {
                if (part.features && part.features.length > 0) {
                    part.features.sort((fa, fb) => {
                        const nameA = fa.name;
                        const nameB = fb.name;
                        const getWeight = (s) => {
                            // 格式通常為 "3-P-1" 或 "P-1"
                            const m = s.match(/([PSH])/i);
                            if (!m) return 9;
                            const map = { 'P': 1, 'S': 2, 'H': 3 };
                            return map[m[1].toUpperCase()] || 9;
                        };
                        const getNum = (s) => {
                            const m = s.match(/(\d+)$/);
                            return m ? parseInt(m[1]) : 0;
                        };
                        
                        const wa = getWeight(nameA);
                        const wb = getWeight(nameB);
                        if (wa !== wb) return wa - wb;
                        return getNum(nameA) - getNum(nameB);
                    });
                }
            });
            
            if (parts.length > 0) {
                let treeHtml = `<div class="bom-container ${layoutClass}">`;
                
                if (enableContact) {
                     treeHtml += `<div style="margin-bottom: 10px; color: #64748b; font-size: 0.9rem; text-align: center;">
                                    💡 提示：點擊任意兩個特徵節點，即可畫出綠色的「硬接觸」連線。點擊連線可刪除。
                                  </div>
                                  <div style="display:flex; justify-content:center; gap:10px; margin-bottom: 10px;">
                                    <button class="export-lines-btn" onclick="exportContactLines()" style="background:#10b981; color:white; padding:5px 10px; border:none; border-radius:4px; font-weight:bold; cursor:pointer;">💾 匯出 Excel</button>
                                    <button class="clear-lines-btn" onclick="clearAllContactLines()">🧹 清除所有接觸線</button>
                                  </div>`;
                }
                
                // Canvas wrapper for proper centered scrolling in Tree view
                if (layoutClass === 'layout-tree') {
                    // Tree needs width: max-content from bom-tree-canvas class
                    treeHtml += `<div id="bom-tree-wrapper" class="bom-tree-canvas" style="position:relative;">`;
                } else {
                    treeHtml += `<div id="bom-tree-wrapper" style="position:relative; width:100%;">`;
                }
                
                if (enableContact) {
                    treeHtml += `<svg id="contact-lines-svg" style="position:absolute; top:0; left:0; width:100%; height:100%; pointer-events:none; z-index:50; overflow:visible;"></svg>`;
                }
                
                // Children Level
                treeHtml += `<div class="bom-children">`;
                
                // 遞迴函數來渲染零件樹
                function renderPartNode(part, isRoot = false) {
                    let html = '';
                    let localListText = '';
                    
                    if (isRoot) {
                        html += `
                        <div class="bom-child">
                            <div class="bom-node root-node" id="node-root" style="border-color: #0f172a; font-weight: bold; background: #e2e8f0; font-size: 1.1rem; padding: 15px;">
                                ${part.name || assemblyName}
                            </div>
                        `;
                    } else {
                        html += `
                        <div class="bom-child">
                            <div class="bom-node">${part.name}</div>
                        `;
                        // 加入純文字清單
                        localListText += `- ${part.name}<br>`;
                    }

                    // 特徵面渲染
                    if (part.features && part.features.length > 0) {
                        let bridges = [];
                        let tagToIndex = {}; 
                        
                        part.features.forEach((f, idx) => {
                            f.interactives.forEach(tag => {
                                if (!tagToIndex[tag]) tagToIndex[tag] = [];
                                tagToIndex[tag].push(idx);
                            });
                        });
                        
                        Object.keys(tagToIndex).forEach(tag => {
                            const indices = tagToIndex[tag];
                            if (indices.length >= 1) {
                                bridges.push({ tag: tag, start: indices[0], end: indices[indices.length - 1] });
                            }
                        });

                        const minListWidth = 200 + (bridges.length * 50);
                        html += `<div class="bom-features-list" style="min-width: ${minListWidth}px;">`;

                        part.features.forEach((f, idx) => {
                            let indHtml = '';
                            f.individuals.forEach(t => { indHtml += `<div class="tol-individual-wrapper"><span class="tolerance-bubble tol-individual">${t}</span></div>`; });

                            const hasTol = f.individuals.length > 0 || f.interactives.length > 0;
                            let maxBIdx = -1;
                            bridges.forEach((bridge, bIdx) => { if (idx >= bridge.start && idx <= bridge.end) maxBIdx = Math.max(maxBIdx, bIdx); });
                            
                            let railWidth = 0;
                            if (maxBIdx >= 0) railWidth = 80 + (maxBIdx * 50) + 2; 
                            else if (f.individuals.length > 0) railWidth = 70; 

                            const railHtml = hasTol ? `<div class="tol-rail-container" style="width: ${railWidth}px;">${indHtml}</div>` : '';
                            const isLast = idx === part.features.length - 1 ? ' last-feature-row' : '';
                            const nodeId = `node-${part.id}-${f.name}`;
                            let clickHandlerAttr = enableContact ? `onclick="toggleContactNode('${nodeId}')"` : '';

                            html += `
                                <div class="bom-feature-row${isLast}">
                                    <div class="bom-feature-node" id="${nodeId}" ${clickHandlerAttr}>${f.name}</div>
                                    ${railHtml}
                                </div>
                            `;
                            
                            // 更新文字清單
                            let tolText = '';
                            if (f.individuals.length > 0) tolText += ` (${f.individuals.join(', ')})`;
                            if (f.interactives.length > 0) tolText += ` [${f.interactives.join(', ')}]`;
                            localListText += `&nbsp;&nbsp;&nbsp;&nbsp;* ${f.name}${tolText}<br>`;
                        });

                        // 渲染橋接線
                        let startYCounts = {};
                        bridges.forEach((bridge, bIdx) => {
                            const rowHeight = 36; 
                            const startY = bridge.start * rowHeight + 18; 
                            const height = (bridge.end - bridge.start) * rowHeight + 2; 
                            const bridgeLeft = `calc(50% + 60px + ${80 + bIdx * 50}px)`; 
                            
                            if (!startYCounts[startY]) startYCounts[startY] = 0;
                            const currentCount = startYCounts[startY];
                            startYCounts[startY]++;

                            html += `
                                <div class="tol-bridge-rung" style="top: ${startY}px; height: ${height}px; left: ${bridgeLeft};"></div>
                            `;
                            
                            let labelY = startY + (height / 2);
                            let offsetX = "-50%";
                            let offsetY = "-50%";
                            
                            if (height <= 2) offsetX = `calc(-50% + ${currentCount * 55}px)`; 
                            else labelY = labelY + (currentCount * 25);

                            html += `
                                <div class="tol-interactive-wrapper" style="top: ${labelY}px; left: ${bridgeLeft}; transform: translate(${offsetX}, ${offsetY});">
                                    <span class="tolerance-bubble tol-interactive">${bridge.tag}</span>
                                </div>
                            `;
                        });
                        html += `</div>`;
                    }
                    
                    // 檢查並渲染子節點
                    if (part.children && part.children.length > 0) {
                        html += `<div class="bom-children">`;
                        part.children.forEach(child => {
                            const childRes = renderPartNode(child);
                            html += childRes.html;
                            localListText += childRes.listText;
                        });
                        html += `</div>`;
                    }
                    
                    html += `</div>`; // End .bom-child
                    return { html: html, listText: localListText };
                }
                
                let sortedListText = '';
                
                // 開始渲染樹狀結構
                // 為了相容之前的單根節點設計，如果有多個 root，我們會外面再包一層虛擬的頂層
                if (parts.length === 1) {
                    const res = renderPartNode(parts[0], true);
                    treeHtml += res.html;
                    sortedListText += res.listText;
                } else {
                    // 如果有平行多個主件，則自己組一個超級根節點
                    treeHtml += `
                        <div class="bom-child">
                            <div class="bom-node root-node" id="node-root" style="border-color: #0f172a; font-weight: bold; background: #e2e8f0; font-size: 1.1rem; padding: 15px;">
                                ${assemblyName}
                            </div>
                            <div class="bom-children">
                    `;
                    parts.forEach(part => {
                        const res = renderPartNode(part);
                        treeHtml += res.html;
                        sortedListText += res.listText;
                    });
                    treeHtml += `</div></div>`;
                }

                treeHtml += `</div></div></div>`; // End children, wrapper, container

                // 修正 encodeURIComponent() 預設不會將單引號 (') 編碼的漏洞，導致 onclick 的 JS 參數字串切斷
                const encodedTree = encodeURIComponent(treeHtml).replace(/'/g, "%27");
                
                let mainBtnClass = "open-bom-btn";
                let mainBtnLabel = "🔍 查看產品架構圖";
                
                if (enableContact) {
                    mainBtnClass = "open-editor-btn"; // Use green styling
                    mainBtnLabel = "🟢 開啟硬接觸連線介面";
                }
                
                finalHtml += `${sortedListText}<br>
                    <button class="${mainBtnClass}" onclick="openBomModal(decodeURIComponent('${encodedTree}'))">${mainBtnLabel}</button>`;
                
                if (enableEdit) {
                    // Also stringify parts for the editor
                    const encodedParts = encodeURIComponent(JSON.stringify(parts)).replace(/'/g, "%27");
                    finalHtml += `<button class="open-editor-btn" onclick="openEditorModal(decodeURIComponent('${encodedParts}'))">✏️ 編輯公差路徑</button>`;
                }

            } else {
                // 解析失敗就印出原文字
                // 回復原來的 listContent 顯示
                finalHtml += `<div style="color:gray;">(解析產品結構圖失敗，維持文字輸出)</div><br>${match[1].trim().replace(/\\n/g, '<br>')}`;
            }
            
            lastIndex = match.index + match[0].length;
        }
        
        finalHtml += formatted.substring(lastIndex);
        bubbleElement.innerHTML = finalHtml;
    }

    async function sendMessage() {
      const msg = input.value.trim();
      if (!msg) return;

      // Disable input
      input.disabled = true;
      sendBtn.disabled = true;

      // Add User Message
      addMessage('user', msg);
      input.value = '';

      // Add Loading Indicator
      const loadingId = addLoading();

      try {
        const selectedModel = modelSelect.value;
        const r = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: msg, model: selectedModel })
        });
        const data = await r.json();

        // Remove Loading
        document.getElementById(loadingId).remove();

        // Add AI Response
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
            history.scrollTop = history.scrollHeight;
            
            // 呼叫我們的自定義渲染器，並傳入意圖設定
            renderCustomBomTree(data.reply, bubble, data.intent);
            history.scrollTop = history.scrollHeight;
            
        } else {
          addMessage('ai', '⚠️ 發生錯誤：無法取得回應');
        }

      } catch (e) {
        document.getElementById(loadingId)?.remove();
        addMessage('ai', '❌ 網路錯誤：' + e);
      } finally {
        // Re-enable input
        input.disabled = false;
        sendBtn.disabled = false;
        input.focus();
      }
    }

    function addMessage(role, htmlContent) {
      const div = document.createElement('div');
      div.className = `message ${role}`;
      
      const avatar = document.createElement('div');
      avatar.className = 'avatar';
      avatar.textContent = role === 'user' ? 'You' : 'AI';
      
      const bubble = document.createElement('div');
      bubble.className = 'bubble';
      bubble.innerHTML = htmlContent;
      
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

    function openBomModal(treeHtml) {
      document.getElementById('bom-modal-container').innerHTML = treeHtml;
      document.getElementById('bom-modal-overlay').style.display = 'flex';
      // Rest lines on load
      contactPairs = [];
      selectedContactNode = null;
    }

    function closeBomModal() {
      document.getElementById('bom-modal-overlay').style.display = 'none';
      contactPairs = [];
      selectedContactNode = null;
    }
    
    // --- Contact Lines Logic ---
    let selectedContactNode = null;
    let contactPairs = [];
    
    function toggleContactNode(nodeId) {
        const el = document.getElementById(nodeId);
        if (!el) return;
        
        if (selectedContactNode === nodeId) {
            // Cancel selection
            el.classList.remove('contact-selected');
            selectedContactNode = null;
        } else if (!selectedContactNode) {
            // Select first node
            el.classList.add('contact-selected');
            selectedContactNode = nodeId;
        } else {
            // Select second node -> create line
            const firstEl = document.getElementById(selectedContactNode);
            if (firstEl) firstEl.classList.remove('contact-selected');
            
            // Check if pair already exists
            const exists = contactPairs.some(p => 
                (p.start === selectedContactNode && p.end === nodeId) || 
                (p.end === selectedContactNode && p.start === nodeId)
            );
            
            if (!exists && selectedContactNode !== nodeId) {
                contactPairs.push({ start: selectedContactNode, end: nodeId });
                drawContactLines();
            }
            selectedContactNode = null;
        }
    }
    
    function drawContactLines() {
        const svg = document.getElementById('contact-lines-svg');
        const wrapper = document.getElementById('bom-tree-wrapper');
        if (!svg || !wrapper) return;
        
        svg.innerHTML = ''; // Clear existing
        const wrapperRect = wrapper.getBoundingClientRect();
        
        contactPairs.forEach((pair, idx) => {
            const el1 = document.getElementById(pair.start);
            const el2 = document.getElementById(pair.end);
            if (!el1 || !el2) return;
            
            const rect1 = el1.getBoundingClientRect();
            const rect2 = el2.getBoundingClientRect();
            
            // 從特徵節點的「左側」拉線，避免穿越文字
            const x1 = rect1.left - wrapperRect.left;
            const y1 = (rect1.top + rect1.height / 2) - wrapperRect.top;
            
            const x2 = rect2.left - wrapperRect.left;
            const y2 = (rect2.top + rect2.height / 2) - wrapperRect.top;
            
            // 計算控制點畫出向左彎曲的貝茲曲線 (Bezier Curve)
            // 垂直距離越遠，往左邊拱出去的弧度越大，但限制最多 150px
            const verticalDist = Math.abs(y2 - y1);
            const bowAmount = Math.min(150, Math.max(50, verticalDist * 0.4));
            const minX = Math.min(x1, x2);
            
            const cx1 = minX - bowAmount;
            const cy1 = y1;
            const cx2 = minX - bowAmount;
            const cy2 = y2;
            
            const pathData = `M ${x1} ${y1} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${x2} ${y2}`;
            
            // Create path
            const line = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            line.setAttribute('d', pathData);
            line.setAttribute('fill', 'none');
            line.setAttribute('stroke', '#22c55e'); // Green
            line.setAttribute('stroke-width', '4');
            
            // Enable deleting the line by clicking it
            line.setAttribute('style', 'pointer-events: auto; cursor: pointer;');
            line.onclick = () => {
                contactPairs.splice(idx, 1);
                drawContactLines();
            };
            
            svg.appendChild(line);
        });
    }

    function clearAllContactLines() {
        if(confirm("確定要清除所有接觸線嗎？")) {
            contactPairs = [];
            selectedContactNode = null;
            document.querySelectorAll('.bom-feature-node.contact-selected').forEach(el => el.classList.remove('contact-selected'));
            drawContactLines();
        }
    }
    
    // Redraw lines when window resizes to ensure they stay attached to elements
    window.addEventListener('resize', () => {
        if (contactPairs.length > 0 && document.getElementById('bom-modal-overlay').style.display === 'flex') {
            drawContactLines();
        }
    });

    // --- Tolerance Editor Logic ---
    let editorPathData = []; // [{type: 'feature|spatial', name: '...', val: '...', axis: '...'}]

    function openEditorModal(partsJsonStr) {
      try {
        const parts = JSON.parse(partsJsonStr);
        editorPathData = [];
        
        // Flatten the features into a sequential list
        parts.forEach(part => {
          if (part.features) {
            part.features.forEach(f => {
              // Extract just the primary tolerance if possible or combine them
              let allTols = [...f.individuals, ...f.interactives];
              if (allTols.length > 0) {
                 allTols.forEach(tol => {
                   editorPathData.push({ type: 'feature', name: tol, val: 0.01, part: part.name }); // Default val
                 });
              } else {
                 editorPathData.push({ type: 'feature', name: f.name, val: 0.01, part: part.name }); // Fallback to feature name
              }
            });
          }
        });
        
        renderEditorList();
        document.getElementById('editor-modal-overlay').style.display = 'flex';
      } catch (e) {
        console.error("Error parsing parts for editor:", e);
        alert("資料解析失敗，無法開啟編輯器");
      }
    }

    function closeEditorModal() {
      document.getElementById('editor-modal-overlay').style.display = 'none';
    }

    function renderEditorList() {
      const container = document.getElementById('editor-list-container');
      let html = '';
      
      // Top add button
      html += `<div class="btn-add-between" onclick="addSpatialNode(0)">+ 安插平移/旋轉 (tra/rot)</div>`;

      editorPathData.forEach((node, idx) => {
        if (node.type === 'feature') {
          html += `
            <div class="editor-row feature-row">
              <div class="col-type">🔸 公差</div>
              <div class="col-name" style="color:#2563eb;">${node.name} <span style="font-size:0.7rem;color:gray">(${node.part || ''})</span></div>
              <div class="col-val">
                數值: <input type="number" step="0.001" value="${node.val}" onchange="updateNodeVal(${idx}, this.value)" style="width:80px;">
              </div>
            </div>
          `;
        } else {
          html += `
            <div class="editor-row spatial-row">
              <div class="col-type">🔹 空間</div>
              <div class="col-name">
                <select onchange="updateSpatialNode(${idx}, 'axis', this.value)">
                  <option value="traX" ${node.axis === 'traX' ? 'selected' : ''}>traX (平移 X)</option>
                  <option value="traY" ${node.axis === 'traY' ? 'selected' : ''}>traY (平移 Y)</option>
                  <option value="traZ" ${node.axis === 'traZ' ? 'selected' : ''}>traZ (平移 Z)</option>
                  <option value="rotX" ${node.axis === 'rotX' ? 'selected' : ''}>rotX (旋轉 X)</option>
                  <option value="rotY" ${node.axis === 'rotY' ? 'selected' : ''}>rotY (旋轉 Y)</option>
                  <option value="rotZ" ${node.axis === 'rotZ' ? 'selected' : ''}>rotZ (旋轉 Z)</option>
                </select>
              </div>
              <div class="col-val">
                名目尺寸: <input type="number" step="0.01" value="${node.val}" onchange="updateNodeVal(${idx}, this.value)" style="width:80px;">
              </div>
              <button class="btn-remove" onclick="removeNode(${idx})">刪除</button>
            </div>
          `;
        }
        
        // Add button strictly after this node
        html += `<div class="btn-add-between" onclick="addSpatialNode(${idx + 1})">+ 安插平移/旋轉 (tra/rot)</div>`;
      });
      
      container.innerHTML = html;
    }

    function addSpatialNode(index) {
      editorPathData.splice(index, 0, { type: 'spatial', axis: 'traZ', val: 0.0 });
      renderEditorList();
    }

    function removeNode(index) {
      editorPathData.splice(index, 1);
      renderEditorList();
    }

    function updateNodeVal(index, val) {
      editorPathData[index].val = parseFloat(val) || 0;
    }

    function updateSpatialNode(index, key, val) {
      editorPathData[index][key] = val;
    }

    async function exportExcel() {
       const btn = document.querySelector('.btn-export');
       const originalText = btn.textContent;
       btn.textContent = "⏳ 產生檔案中...";
       btn.disabled = true;
       
       try {
           const res = await fetch('/api/export_tolerance_excel', {
               method: 'POST',
               headers: {'Content-Type': 'application/json'},
               body: JSON.stringify({ pathData: editorPathData })
           });
           
           if (!res.ok) throw new Error("Export failed");
           
           // Download it!
           const blob = await res.blob();
           const url = window.URL.createObjectURL(blob);
           const a = document.createElement('a');
           a.href = url;
           a.download = "Tolerance_Path_Export.xlsx";
           document.body.appendChild(a);
           a.click();
           document.body.removeChild(a);
           window.URL.revokeObjectURL(url);
           
           alert("✅ Excel 檔案下載成功！可以直接餵給單機版程式分析。");
       } catch (e) {
           console.error(e);
           alert("❌ 匯出失敗: " + e.message);
       } finally {
           btn.textContent = originalText;
           btn.disabled = false;
       }
    }
    async function exportContactLines() {
        if (contactPairs.length === 0) {
            alert("目前沒有任何接觸線可以匯出！");
            return;
        }
        
        const btn = document.querySelector('.export-lines-btn');
        const originalText = btn.textContent;
        btn.textContent = "⏳ 產生檔案中...";
        btn.disabled = true;
        
        // 準備資料
        let exportData = contactPairs.map(p => {
            const startNode = document.getElementById(p.start);
            const endNode = document.getElementById(p.end);
            return {
                start: startNode ? startNode.textContent.trim() : p.start,
                end: endNode ? endNode.textContent.trim() : p.end
            };
        });
        
        try {
            const res = await fetch('/api/export_contact_lines', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ pairs: exportData })
            });
            
            if (!res.ok) throw new Error("Export failed");
            
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = "Contact_Lines_Export.xlsx";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
            alert("✅ 接觸連線 Excel 檔案下載成功！");
        } catch (e) {
            console.error(e);
            alert("❌ 匯出失敗: " + e.message);
        } finally {
            btn.textContent = originalText;
            btn.disabled = false;
        }
    }

  </script>
</body>
</html>
"""

@app.route('/')
def home():
    # Fetch available models from Ollama explicitly on localhost
    try:
        client = ollama.Client(host="http://localhost:11434")
        models_info = client.list()
        # client.list() returns a ListResponse object with a 'models' attribute
        # Each item in 'models' is a Model object with a 'model' attribute
        
        # Handle both object-style and dict-style access just in case
        model_names = []
        for m in models_info.models:
            if hasattr(m, 'model'):
                model_names.append(m.model)
            elif isinstance(m, dict) and 'name' in m:
                model_names.append(m['name'])
            elif isinstance(m, dict) and 'model' in m:
                model_names.append(m['model'])
            else:
                # Fallback or print warning
                print(f"Unknown model format: {m}")
        
        # Sort models: cloud models first (group 0), then local models (group 1)
        # Only models with explicit cloud indicators are considered cloud models
        cloud_model_prefixes = [
            'gpt-oss', 'qwen3-vl', 'qwen3-v1', 'ministral-3', 'qwen3-coder', 
            'glm-5', 'glm-4.7', 'glm-4.6', 'glm-4', 'deepseek-v3.2', 'deepseek-v3.1', 
            'deepseek3.1', 'deepseek-v3', 'minimax-m2', 'minimax', 'gemini-3', 
            'kimi', 'qwen3.5', 'nemotron-3'
        ]
        
        def is_cloud_model(name):
            """Check if a model is a cloud model
            Cloud models are identified by:
            1. Having '-cloud' or ':cloud' suffix
            2. Matching specific cloud model prefixes (excluding local models like gemma3:4b)
            """
            name_lower = name.lower()
            
            # First check for explicit cloud suffixes
            if '-cloud' in name_lower or ':cloud' in name_lower:
                return True
                
            # Check specific cloud prefixes (excluding gemma3 which can be local)
            for prefix in cloud_model_prefixes:
                if name_lower.startswith(prefix):
                    return True
                    
            return False
        
        def model_sort_key(name):
            """Sort key: (group, alphabetical_name)
            Group 0: Cloud models (上方)
            Group 1: Local models (下方)
            """
            if is_cloud_model(name):
                return (0, name.lower())  # Cloud models first
            else:
                return (1, name.lower())  # Local models second
        
        # 手動加入可以直接連線的雲端模型 (即使 Ollama 沒載入過)
        gemini_model = 'gemini-3-flash-preview:cloud'
        if gemini_model not in model_names:
            model_names.append(gemini_model)
            
        model_names.sort(key=model_sort_key)
                
    except Exception as e:
        print(f"Error fetching models: {e}")
        model_names = ['llama3.1:8b'] # Fallback

    # Default model: prefer suitable cloud models if available, otherwise use local
    current_model = None
    
    # Priority order for cloud models (prefer smaller, faster ones for default)
    preferred_cloud = [
        'gemini-3-flash-preview', 'gemma3:4b', 'gemma3:12b', 'gpt-oss:20b', 
        'ministral-3:8b', 'qwen3-coder-next:400b'
    ]
    for preferred in preferred_cloud:
        if preferred in model_names:
            current_model = preferred
            break
    
    # If no preferred cloud model, try any gemma3 or local model
    if not current_model:
        for m in model_names:
            if m.startswith('gemma3:') or m.startswith('llama3'):
                current_model = m
                break
    
    # Final fallback
    if not current_model:
        current_model = model_names[0] if model_names else 'llama3.1:8b'
    
    return render_template_string(HTML_TEMPLATE, models=model_names, current_model=current_model)

@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.get_json(force=True)
    user_msg = data.get("message", "")
    model_name = data.get("model", "llama3.1:8b")
    
    if not user_msg:
        return jsonify({"reply": "請輸入訊息"}), 400
    
    # 判斷是否為雲端模型 (這裡用簡單的字串判斷，您可以依實際情況修改)
    model_lower = model_name.lower()
    is_cloud = '-cloud' in model_lower or ':cloud' in model_lower or model_lower.startswith('gpt-oss') or model_lower.startswith('qwen3-vl') or model_lower.startswith('qwen3-v1') or model_lower.startswith('ministral-3') or model_lower.startswith('qwen3-coder') or model_lower.startswith('glm-4') or model_lower.startswith('deepseek') or model_lower.startswith('minimax')
    
    # [請注意!] 這裡填上您雲端機器的 Ngrok 或 Cloudflare 網址
    # 由於目前使用者遭遇 34.36.133.15 連線錯誤 (Google Cloud IP / ngrok)，暫時把這裡改回 localhost
    CLOUD_OLLAMA_URL = "http://localhost:11434"
    
    # 決定使用的 URL
    base_url = CLOUD_OLLAMA_URL if is_cloud else "http://localhost:11434"
    
    print(f"📡 接收到對話請求 - 訊息: '{user_msg}', 模型: {model_name}, 網址: {base_url}")
    
    try:
        # --- 恢復：意圖計算與隱藏 Prompt 構建 ---
        bom_intent = {
            "layout": "tree", # Default to standard tree diagram for parts/features
            "contact": False,
            "edit": False
        }
        
        if any(k in user_msg for k in ["參考", "公差", "網路圖"]):
            bom_intent["layout"] = "grid" # dense tolerances need grid
            
        if any(k in user_msg for k in ["接觸", "連接", "硬接觸"]):
            bom_intent["contact"] = True # Show SVG contact lines
            bom_intent["layout"] = "grid" # contact lines also need grid layout
            
        if any(k in user_msg for k in ["編輯", "路徑", "安插", "tra", "rot"]):
            bom_intent["edit"] = True # Show Edit Path button
            
        hidden_prompt = user_msg
        is_diagnostic = any(k in user_msg for k in ["檢查", "確認", "缺少", "漏掉"])
        
        if (bom_intent["layout"] == "grid" or bom_intent["contact"] or bom_intent["edit"]) and not is_diagnostic:
            if not any(k in user_msg for k in ["列出", "包含", "零件", "特徵", "架構"]):
                hidden_prompt = user_msg + "\n\n[系統最高行為準則]：這是一個觸發圖表互動UI的請求。請你「絕對務必」在回答的最後，附上精密迴轉滑台完整的零件與特徵面公差層級清單。這個清單「必須」包裹在 ---BOM_START--- 與 ---BOM_END--- 之間！且第一行必須是 `# 精密迴轉滑台`。\n\n🚨 [階層結構規定]：如果某零件屬於另一個零件的子組件，請使用兩個空格進行縮進（例如 `- 零件A\\n  - 子零件B`）。\n🚨 [標章規定]：每個零件下方必須包含其擁有的特徵面（以 `*` 開頭），且特徵面後方必須包含括號內的公差。絕對不准只列出零件名稱而漏掉特徵面與公差！\n🚨 [重要自檢機制]：在輸出清單前，請務必自我檢查：任何在方括號 `[ ]` 內的交互參考公差，其指向的目標特徵面必須真的存在且非自己。如果發現不合理的參考，請直接刪除該項目。沒有這些標籤，前端介面將直接崩潰，請嚴格遵守！"

        # 1. 取得 RAG Context (從 graph_rag 或是原本的邏輯)
        from graph_rag import _triplets_context_cache, build_triplets_context, get_knowledge_triplets, set_latest_report, _latest_machine_report, QA_PROMPT
        
        # 確保知識庫已載入
        if _triplets_context_cache is None:
            triplets = get_knowledge_triplets('0213_export.csv')
            _triplets_context_cache = build_triplets_context(triplets)
            
        # 2. 判斷是否走 Gemini 原生 API
        if "gemini" in model_lower:
            print(f"🚀 使用 Gemini 原生 API 推論: {model_name}")
            # 根據剛才實測清單，正確名稱應為 gemini-3-flash-preview
            actual_model = "gemini-3-flash-preview" 
            model = genai.GenerativeModel(actual_model)
            
            # 使用與 graph_rag 相同的 robust Smart RAG 過濾邏輯
            import re
            domain_dict = ["底座", "滑台", "螺桿", "導軌", "平台", "蝸輪", "蝸桿", "軸承", "軸", "交互參考", "平行度", "垂直度", "同心度", "圓柱度", "輪廓度", "距離", "位置", "特徵", "零件", "配合", "基準", "公差", "交互", "確認", "檢查", "缺少", "漏掉", "上板", "固定座", "間隔環", "螺帽"]
            keywords = [word for word in domain_dict if word in user_msg]
            eng_num_keywords = re.findall(r'[a-zA-Z0-9]+', user_msg)
            keywords.extend(eng_num_keywords)
            keywords = list(set([k for k in keywords if len(k) >= 2]))
            
            all_lines = _triplets_context_cache.split('\n')
            relevant_lines = []
            assembly_keywords = ["精密迴轉滑台", "滑台", "組合件"]
            
            for line in all_lines:
                line_lower = line.lower()
                if not line.strip(): continue
                if any(k.lower() in line_lower for k in keywords) or any(ak.lower() in line_lower for ak in assembly_keywords):
                    relevant_lines.append(line)
            
            context = "\n".join(relevant_lines) if relevant_lines else _triplets_context_cache
            
            if _latest_machine_report:
                context = f"【最新機台報表】：\n{_latest_machine_report}\n\n{context}"

            prompt = QA_PROMPT.format(context=context, question=hidden_prompt)
            print(f"🕵️ Gemini Smart RAG: 找到 {len(relevant_lines)} 條相關資料")
            
            response = model.generate_content(prompt)
            reply = response.text
            return jsonify({"reply": reply})

        # 3. 走原本的 RAG 邏輯 (Ollama)
        from graph_rag import get_graph_rag_response
        reply = get_graph_rag_response(hidden_prompt, model_name=model_name, base_url=base_url)

        
        # 判斷是否為「產品架構與零件」相關的查詢
        is_bom_request = any(k in hidden_prompt for k in ["包含", "零件", "特徵", "架構", "結構", "BOM"])
        
        # 若 GraphRAG 找不到實體資料
        if "找不到相關資料" in reply:
            if is_bom_request:
                print("⚠️ 真實 GraphRAG 無法回答結構問題，直接阻斷以防止 rag_server 產生幻覺。")
                reply = "抱歉，在本地產品架構中找不到您詢問的零件或特徵面。請確認您的拼字是否與清單相符（例如：'1-底座'）。"
            else:
                print("⚠️ 圖譜知識庫無相關資料，轉交給工程資料庫 (rag_server) 查詢一般知識...")
                from rag_server import get_rag_response
                fallback_reply = get_rag_response(user_msg, model_name=model_name)
                if "無法識別" not in fallback_reply and fallback_reply.strip():
                    reply = fallback_reply

    except Exception as e:
        import sys
        with open('sys_exec.txt', 'w', encoding='utf-8') as f:
            f.write(f"exe: {sys.executable}\npath: {sys.path}\nerror: {e}")
        print(f"⚠️ GraphRAG 匯入或執行失敗: {e}")
        print(f"⚠️ 正在使用的 Python: {sys.executable}")
        reply = f"❌ 圖資料庫 (GraphRAG) 執行發生錯誤: {e}。請聯絡系統管理員。"
        bom_intent = {}
        
    return jsonify({"reply": reply, "intent": bom_intent})

@app.route('/api/export_tolerance_excel', methods=['POST'])
def export_tolerance_excel():
    data = request.get_json()
    path_data = data.get('pathData', [])
    
    import io
    import pandas as pd
    
    # Build dataframe representing the specific structure seen in User's screenshot
    # Columns: 路徑代碼, 數值, 偏差值, 距離 (or similar format required by the standalone GUI)
    rows = []
    
    for item in path_data:
        if item.get('type') == 'feature':
            rows.append({
                "路徑代碼": item.get('name'),
                "數值": item.get('val', 0.01),
                "偏差值": 0,
                "距離": 1  # 預設距離
            })
        elif item.get('type') == 'spatial':
            rows.append({
                "路徑代碼": item.get('axis'),
                "數值": item.get('val', 0.0),
                "偏差值": 0,
                "距離": 1  # 預設距離
            })
            
    df = pd.DataFrame(rows)
    
    # Write to memory buffer
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='TolerancePath')
    
    output.seek(0)
    
    from flask import send_file
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='Tolerance_Path_Export.xlsx'
    )

@app.route('/api/export_contact_lines', methods=['POST'])
def export_contact_lines():
    data = request.get_json()
    pairs = data.get('pairs', [])
    
    import io
    import pandas as pd
    
    rows = []
    for pair in pairs:
        rows.append({
            "特徵面 1": pair.get('start'),
            "特徵面 2": pair.get('end'),
            "連結類型": "硬接觸"
        })
        
    df = pd.DataFrame(rows)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='ContactLines')
    
    output.seek(0)
    
    from flask import send_file
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='Contact_Lines_Export.xlsx'
    )

@app.route('/api/sync_report', methods=['POST'])
def sync_report():
    """
    接收前端送來的機台媒合報表(純文字)，直接存入全域記憶體供 AI 短期記憶使用。
    """
    try:
        data = request.get_json()
        report_text = data.get('reportText', '')
        
        if not report_text:
            return jsonify({"ok": False, "msg": "沒有收到報表內容"}), 400
            
        import graph_rag
        graph_rag.set_latest_report(report_text)
        
        print(f"✅ 成功接收並更新最新機台媒合報表 (長度: {len(report_text)})")
        return jsonify({"ok": True, "msg": "報表同步成功"})
        
    except Exception as e:
        return jsonify({"ok": False, "msg": f"同步失敗: {str(e)}"}), 500

if __name__ == '__main__':
    print("啟動 AI 聊天助手伺服器...")
    print("請訪問: http://127.0.0.1:7011")
    app.run(host='0.0.0.0', port=7011, debug=True)
