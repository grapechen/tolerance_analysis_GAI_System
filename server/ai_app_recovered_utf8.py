import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import ollama
from dotenv import load_dotenv
from scripts.triplets_extractor import get_mating_constraints

# 頛?啣?霈
load_dotenv()


app = Flask(__name__)
CORS(app)  # ?迂靘 7010 ??蝡航楊蝬脣?隢? (CORS)


# HTML Template for the Chat App
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title {% if lang == 'en' %}data-v="2.0"{% else %}data-v="2.0"{% endif %}>{% if lang == 'en' %}ISO 286 AI Intelligent Assistant{% else %}ISO 286 AI ?箄?拇?{% endif %}</title>
  <style>
    /* 撟曆??砍榆蝚西?摮??舀 */
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
      flex-direction: row; /* ?撌血?Ｘ */
      height: 100vh;
      overflow: hidden;
    }
    
    /* 撌血?Ｘ雿? */
    #left-panel {
      flex: 1;
      min-width: 0;
      background: #0d1117;
      display: flex;
      flex-direction: column;
      border-right: 1px solid var(--border-color);
      position: relative;
    }
    #right-panel {
      width: 480px; /* 撠店??撖砍漲 */
      flex-shrink: 0;
      display: flex;
      flex-direction: column;
      background: var(--bg-color);
    }
    
    #diagram-canvas {
      flex: 1;
      overflow: auto;
      padding: 20px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .canvas-placeholder {
      color: #475569;
      font-size: 1.2rem;
      text-align: center;
    }

    /* 閬??? CSS 撣?嚗?粹?閮剝＊蝷綽?蝣箔??喃噶瘝?????銋?撅斤??批捆 */
    /* ???撅斤??身??block嚗誑靘踹閬???典停憿舐內嚗?蝒??Ｘ銝??*/
    .bom-network-svg { display: block; }
    .contact-lines-svg { display: block; }

    /* ??摰孵憿舐摨血撥??*/
    .panel-tabs {
      display: flex;
      background: #1e293b;
      padding: 10px 15px;
      gap: 12px;
      border-bottom: 2px solid #3b82f6; 
      min-height: 55px;
      align-items: center;
    }
    .panel-tab-btn {
      background: transparent;
      border: none;
      color: #94a3b8;
      padding: 8px 15px;
      border-radius: 4px;
      cursor: pointer;
      font-weight: 600;
      transition: all 0.2s;
      font-size: 0.9rem;
    }
    .panel-tab-btn.active {
      background: var(--user-msg-bg);
      color: white;
    }
    .panel-tab-btn:hover:not(.active) {
      background: #334155;
      color: var(--text-color);
    }
    
    /* 撟曆??砍榆蝚西?璅?? */
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
      overflow-x: auto; /* Enable horizontal scroll */
      scrollbar-width: thin;
      scrollbar-color: #888 #f1f1f1;
    }
    
    .bom-container::-webkit-scrollbar {
      height: 8px;
    }
    .bom-container::-webkit-scrollbar-track {
      background: #f1f1f1;
      border-radius: 10px;
    }
    .bom-container::-webkit-scrollbar-thumb {
      background: #888;
      border-radius: 10px;
    }
    .bom-container::-webkit-scrollbar-thumb:hover {
      background: #555;
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
      border-radius: 8px; /* 憓???隞亙????*/
      transition: border-color 0.2s, box-shadow 0.2s;
    }
    
    .layout-tree .bom-node {
      display: block;
      width: fit-content;
      margin: 0 auto;
      min-width: 150px;
      padding: 10px 15px;
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


    /* ?? Grid 璅∪? ?? */
    /* ?寧憭??芸????? (Flex Wrap / Masonry-style) */
    .layout-grid {
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      gap: 15px;
      padding: 20px;
    }
    .layout-grid .bom-child {
      position: relative;
      margin-left: 0;
      padding-left: 0;
      /* 霈雯?澆??寞??批捆?芷?祝摨佗?銝?蝖砍?皛?100% */
      width: fit-content;
      display: flex;
      flex-direction: column;
      align-items: center;
    }
    .layout-grid .bom-children {
      display: flex;
      flex-direction: row;
      flex-wrap: wrap;
      justify-content: center;
      align-items: flex-start;
      gap: 30px; 
      width: 100%;
    }

    .bom-grid-border-box {
      border: 1px dashed #64748b;
      border-radius: 8px;
      padding: 15px;
      margin-top: 10px;
      box-shadow: 0 4px 6px rgba(0,0,0,0.05);
      background-color: transparent;
      display: flex;
      align-items: center; /* 霈椰??DRF ??渡敺菟?蝵桐葉撠? */
      gap: 20px;
    }
    
    .bom-part-metadata {
      display: flex;
      flex-direction: column;
      align-items: center;
      min-width: 100px;
      padding-top: 10px;
    }
    
    .bom-drf-box {
      border: 2px solid #0f172a;
      padding: 8px 12px;
      background: white;
      color: #0f172a;
      font-weight: bold;
      font-size: 0.9rem;
      text-align: center;
      border-radius: 4px;
      margin-bottom: 15px;
      min-width: 80px;
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
      width: fit-content; /* ?寧 fit-content 瘥?max-content ?渡帘摰?*/
      min-width: 100%; 
      padding: 20px 10px;
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
      top: -30px;
      left: 50%; /* 雿輻 50% ?? transform ?渡移皞?*/
      transform: translateX(-50%);
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
      align-items: center; /* 撘瑕?ㄐ?Ｙ? `.bom-node` ??`.bom-features-list` ?券?典甇?葉憭?*/
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
      left: 50%;
      transform: translateX(-50%);
      width: 2px;
      height: 25px;
      background-color: #0f172a;
    }
    
    /* ?梯???惜?寧?暺??寧?韐? (甇?Ⅱ蝯?: bom-container.layout-tree > bom-tree-canvas > bom-children > bom-child) */
    .bom-container.layout-tree > .bom-tree-canvas > .bom-children::before,
    .bom-container.layout-tree > .bom-tree-canvas > .bom-children > .bom-child::before,
    .bom-container.layout-tree > .bom-tree-canvas > .bom-children > .bom-child::after {
      display: none !important;
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



    /* Ensure the line from parent box goes down to meet the branch */
    .layout-tree .bom-node::after {
        content: '';
        position: absolute;
        bottom: -32px;
        left: 50%;
        transform: translateX(-50%);
        width: 2px;
        height: 32px; /* ??bom-children ??padding-top ?賊??Ⅱ靽??*/
        background-color: #0f172a;
        display: none;
    }

    .layout-tree .bom-node + .bom-children,
    .layout-tree .bom-node + .bom-features-list {
        margin-top: 0; /* padding-top on bom-children already provides the spacing */
    }

    /* Only show the line if there are actually children or features */
    .layout-tree .bom-child:has(> .bom-children) > .bom-node::after,
    .layout-tree .bom-child:has(> .bom-features-list) > .bom-node::after {
        display: block;
    }
    
    .layout-tree .bom-tree-canvas > .bom-child {
      padding-top: 0;
    }


    /* ??????????????????????????????????????????????
       ?砍榆蝬脰楝銝惜?嗆?
       Layer A: rows-layer  (蝭暺擃?
       Layer B: rails-layer (瘞游像頠? + 璈??)
       Layer C: bridges-layer (蝝怨?蝺?+ 蝝怨??)
       ?????????????????????????????????????????????? */

    .layout-grid .bom-features-list {
      position: relative;
      flex: 1;
    }

    .bom-features-list {
      position: relative;  /* ???absolute 摮?蝝?摨扳??? */
      flex-shrink: 0;      /* ?脫迫??flex 摰孵銝剛◤?漲?? */
      margin-top: 0;
      /* height/width ??JS 閮剖?嚗Ⅱ靽?list ?賢捆蝝???撠?雿??? */
    }

    /* ?? Layer A: rows-layer ?? */
    .rows-layer {
      position: relative;
      z-index: 10;
    }

    .bom-feature-row {
      position: relative;
      background: transparent;
      height: 50px; /* ?箔?撠???頞喳???摨?*/
      display: flex;
      align-items: center;
    }
    .layout-tree .bom-feature-row {
      justify-content: center;
    }
    /* Grid 璅∪?蝭暺??喃?蝘鳴?霈椰?渡?蝛箇策 trunk */
    .layout-grid .bom-feature-node {
      margin-left: 30px;
    }
    /* ?芣???Grid 璅∪?銝?瘨?HTML trunk ???嚗 SVG ?亦恣?ree 璅∪???閬?嚗?*/
    .layout-grid .bom-tree-trunk {
      display: none;
    }

    /* ?? 蝭暺?摮??? */
    .bom-feature-node {
      border: 2px solid #0f172a;
      padding: 6px 10px;
      background: white;
      color: #0f172a;
      width: 100px; /* 蝮格?撖砍漲隞交?撠?渡征?踝?銝西????湧?餈葉敹?*/
      text-align: center; /* 撘瑕??蝵桐葉 */
      box-sizing: border-box;
      word-wrap: break-word;
      line-height: 1.3;
      font-size: 0.85rem;
      position: relative;
      z-index: 10;
      border-radius: 6px;
      cursor: pointer;
      transition: box-shadow 0.2s, border-color 0.2s, background-color 0.2s;
      flex-shrink: 0;
    }

    .bom-feature-node.contact-selected {
      background-color: #f0fdf4;
      border-color: #22c55e;
      box-shadow: 0 0 10px rgba(34, 197, 94, 0.3);
    }

    /* 璈怠?頠?蝺捆?剁?蝘駁???航嚗?雿璈????Flex 摰孵 */
    .tol-rail-container {
      position: absolute;
      display: flex;
      align-items: center;
      gap: 12px;
      padding-right: 4px;
      transform: translateY(-50%); /* 靽格迤??嚗??游??移皞?銝剜暺?銝?*/
      pointer-events: none; /* Let SVG clicks pass if any */
      /* left/top/width ?函 JS 閮剖? */
    }

    /* 璈???ㄨ撅歹??賢???頠?蝺?霈??瘚格頠?銝?*/
    .tol-individual-wrapper {
      position: relative;
      background: white;
      padding: 2px 4px;
      flex-shrink: 0;
      pointer-events: auto;  /* rails-layer pointer-events:none嚗ㄐ??? */
      z-index: 10;
    }

    /* ?? SVG 摨惜????怠? ?? */
    .bom-svg-layer {
      position: absolute;
      top: 0; left: 0; width: 100%; height: 100%;
      pointer-events: none;
      z-index: 0;
    }

    /* 蝣箔????暺 SVG ????*/
    .bom-part-metadata, .bom-feature-node, .tolerance-bubble {
      position: relative;
      z-index: 10;
    }

    /* 蝝怨???ㄨ撅歹?隞交??亦?銝剖?暺?券? */
    .tol-interactive-wrapper {
      position: absolute;
      transform: translate(-50%, -50%); /* 靽格迤????X ?宏嚗?霅蔭銝剛楊?亦? */
      background: white;   /* ??璈蝺忽???唳 */
      padding: 0; /* padding 蝘餃鋆⊿ bubble */
      border-radius: 20px;
      z-index: 20;
    }

    /* ?? DRF ?? (Grid 璅∪?) ?? */
    .bom-part-metadata {
      position: relative;
    }

    /* ?? ?砍榆??憭? ?? */
    .tolerance-bubble {
      display: inline-flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 4px 12px;
      border-radius: 20px;
      background: white;
      font-size: 0.75rem;
      font-weight: bold;
      line-height: 1.2;
      white-space: nowrap;
      min-width: 75px;
      box-sizing: border-box;
      border: 1.5px solid currentColor;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }

    .tolerance-bubble span.part-name {
      font-size: 0.7rem;
      color: inherit;
      margin-bottom: 1px;
    }

    .tolerance-bubble span.tol-code {
      font-style: italic;
      font-size: 0.8rem;
      color: inherit;
    }

    .tol-individual  { color: #f97316; }
    .tol-interactive { color: #a855f7; }


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
      width: 860px;
      max-width: 95%;
      max-height: 90%;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      box-shadow: 0 10px 25px rgba(0,0,0,0.5);
    }
    .editor-header {
      font-size: 1.2rem;
      font-weight: bold;
      margin-bottom: 16px;
      color: #0f172a;
    }
    .editor-list {
      flex: 1;
      overflow-y: auto;
      border-radius: 8px;
      background: white;
      margin-bottom: 12px;
    }

    /* ????閰衣?銵典??砍榆頝臬?蝺刻摩??????*/

    /* 銵冽?湧? */
    .editor-table {
      width: 100%; border-collapse: collapse;
      font-size: 0.875rem;
    }
    .editor-table thead th {
      background: #1e3a5f; color: white;
      padding: 8px 10px; text-align: center;
      border: 1px solid #2d5082; font-size: 0.82rem;
      white-space: nowrap;
    }
    /* 憟????*/
    .row-feature { background: #fafafa; }
    .row-feature:hover { background: #eff6ff; }
    .row-spatial { background: #f0fdf4; font-style: italic; }
    .row-spatial:hover { background: #dcfce7; }
    .row-insert td { padding: 0; background: transparent; border: none; }

    /* ?? td */
    .editor-table tbody td {
      padding: 5px 8px;
      border: 1px solid #e2e8f0;
      vertical-align: middle;
    }
    /* A 甈?頝臬?隞?Ⅳ */
    .cell-code { font-weight: bold; min-width: 120px; }
    .cell-code.feat  { color: #f97316; } /* 璈 = ?砍榆 */
    .cell-code.spatial { color: #22c55e; } /* 蝬 = 蝛粹?頠?*/
    /* datalist 頛詨獢??臭????航?梯撓??*/
    .axis-input {
      width: 100%; border: none; background: transparent;
      font-weight: bold; color: #22c55e;
      font-size: 0.875rem; padding: 0;
      cursor: text;
    }
    .axis-input:focus { outline: 1px solid #22c55e; border-radius: 3px; }
    .cell-part { font-size: 0.67rem; color: #94a3b8; font-weight: normal; }

    /* B/C/D 甈撓?交? */
    .cell-input {
      width: 100%; box-sizing: border-box;
      border: 1px solid #cbd5e1; border-radius: 4px;
      padding: 4px 6px; font-size: 0.875rem;
      text-align: right; background: white;
    }
    .cell-input:focus {
      outline: 2px solid #3b82f6; border-color: transparent;
    }

    /* ?????*/
    .btn-insert {
      display: block; width: 100%;
      background: transparent; border: 1px dashed #94a3b8;
      color: #94a3b8; padding: 3px; font-size: 0.75rem;
      cursor: pointer; transition: 0.15s;
    }
    .btn-insert:hover { background: #f1f5f9; color: #475569; border-color: #64748b; }

    /* ?芷?? */
    .btn-remove-row {
      background: none; border: none; color: #ef4444;
      cursor: pointer; font-size: 1rem; padding: 2px 6px;
    }
    .btn-remove-row:hover { background: #fee2e2; border-radius: 4px; }

    /* ????雿? */
    .cell-drag { color: #cbd5e1; text-align: center; cursor: grab; user-select: none; }

    .editor-actions {
      display: flex; justify-content: flex-end; gap: 10px; margin-top: 16px;
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

  <div id="left-panel">
    <div id="panel-active-tabs" class="panel-tabs">
      <!-- Buttons will be injected here dynamically -->
    </div>
    <div id="diagram-canvas">
      <div class="canvas-placeholder">
        {% if lang == 'en' %}AI charts will be displayed here{% else %}AI ?”撠甇方?憿舐內{% endif %}
      </div>
    </div>
  </div>

  <div id="right-panel">
    <div class="header">
      <h1><span class="status-dot"></span> {% if lang == 'en' %}AI Intelligent Assistant{% else %}AI ?箄?拇?{% endif %}</h1>
      <div class="model-selector">
        <label for="model-select" style="font-size: 0.9rem; color: #94a3b8;">Model:</label>
        <select id="model-select">
          {% for model in models %}
          {% set model_lower = model.lower() %}
          {% set is_cloud = (
            '-cloud' in model_lower or ':cloud' in model_lower or
            model_lower.startswith('gpt-oss') or model_lower.startswith('qwen3-vl') or
            model_lower.startswith('qwen3-v1') or model_lower.startswith('ministral-3') or
            model_lower.startswith('qwen3-coder') or model_lower.startswith('glm-5') or
            model_lower.startswith('glm-4') or model_lower.startswith('deepseek') or
            model_lower.startswith('minimax') or model_lower.startswith('gemini-3') or
            model_lower.startswith('kimi') or model_lower.startswith('qwen3.5') or
            model_lower.startswith('nemotron')
          ) %}
          <option value="{{ model }}" {% if model == current_model %}selected{% endif %} {% if is_cloud %}data-cloud="true"{% endif %}>
            {% if is_cloud %}?? {% endif %}{{ model }}
          </option>
          {% endfor %}
        </select>
      </div>
    </div>

    <div class="chat-container" id="chat-history">
      <div class="message ai">
        <div class="avatar">AI</div>
        <div class="bubble">
          {% if lang == 'en' %}
          Hello! I am your AI intelligent assistant.<br>
          You can ask me things like:<br>
          ??<strong>25mm H7</strong> (Single tolerance query)<br>
          ??<strong>Analyze 25mm H7/h6</strong> (Fit analysis)<br>
          ??<strong>What parts does the precision slide contain?</strong> (Product structure diagram)<br>
          Is there anything I can help you with?
          {% else %}
          雿末嚗??舀?I?箄?拇???br>
          ?典隞亙????荔?<br>
          ??<strong>25mm H7</strong> (?亥岷?桐??砍榆)<br>
          ??<strong>?? 25mm H7/h6</strong> (?脰?????)<br>
          ??<strong>蝎曉?餈渲?皛??芯??嗡辣嚗?/strong> (?怠?Ｗ??嗆???<br>
          隢???暻潭??臭誑撟急??嚗?          {% endif %}
        </div>
      </div>
    </div>

    <div class="input-area">
      <input type="text" id="chat-input" placeholder="{% if lang == 'en' %}Enter your question...{% else %}頛詨?函???...{% endif %}" autocomplete="off">
      <button onclick="sendMessage()" id="send-btn">{% if lang == 'en' %}Send{% else %}?潮% endif %}</button>
    </div>
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
      <div class="editor-header">?? {% if lang == 'en' %}Tolerance Path Editor (Add Translation/Rotation){% else %}?砍榆頝臬?蝺刻摩??(?撟喟宏/??){% endif %}</div>
      <div class="editor-list" id="editor-list-container">
        <!-- Rendered by JS -->
      </div>
      <div class="editor-actions">
        <button class="btn-export" onclick="exportCSV()">漎? {% if lang == 'en' %}Export as CSV{% else %}?臬??CSV ??瑼% endif %}</button>
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

    // ???芸?蝢拍?瑽??撘?    function switchPanelView(viewType) {
        // ?湔?????(?? Active 璅??嚗?銝宏?文隞?撅斤? class)
        document.querySelectorAll('.panel-tab-btn').forEach(btn => btn.classList.remove('active'));
        const activeBtn = document.getElementById(`tab-${viewType}`);
        if (activeBtn) activeBtn.classList.add('active');

        const wrapper = document.getElementById('bom-tree-wrapper');
        if (!wrapper) return;

        // 憒?暺??嚗??閰脣?撅?(銝蜓??remove ?嗡?嚗祕?曄???
        if (viewType === 'tolerance') {
            wrapper.classList.add('view-tolerance');
            setTimeout(drawAllBomNetworks, 100);
        }
        else if (viewType === 'contact') {
            wrapper.classList.add('view-contact');
            setTimeout(drawContactLines, 100);
        }
        else if (viewType === 'bom') {
            // ?箸?嗡辣閬?嚗??撣?蝝楊暺??臭誑閬?瘙?ㄐ remove ?嗡?嚗?            // 雿???瘙?頝?蝒?璅???氬???????        }
    }

    // ???湔撌血?Ｘ??
    function updatePanelButtons(content, intent) {
        const tabBar = document.getElementById('panel-active-tabs');
        if (!tabBar) return;
        tabBar.innerHTML = '';

        // 瑼Ｘ?批捆?????曉祝?菜葫璇辣
        const hasBomTags = content.includes('---BOM_START---');
        const hasCommonSymbols = /[#\-\*]/.test(content); // ?芾???#, -, * 
        const hasIntent = intent && (intent.tab === 'bom' || intent.tab === 'tolerance' || intent.tab === 'feature');

        if (!hasBomTags && !hasCommonSymbols && !hasIntent) {
            console.log("[UI-DEBUG] No diagram content detected in reply.");
            return;
        }

        // ?菜葫蝝啁?憿
        const hasFeatures = /\*/.test(content) || (intent && intent.tab === 'feature');
        const hasTolerance = /[\(\)\[\]]/.test(content) || (intent && intent.tab === 'tolerance');
        const hasContact = /蝯??亥孛|Contact/.test(content) || (intent && intent.tab === 'contact');

        console.log("[UI-DEBUG] Buttons update triggered.", {hasFeatures, hasTolerance, hasContact});

        // ?芸?閫???亥孛撠?(撘瑕??? Regex)
        if (hasContact) {
            contactPairs = [];
            // ?曉祝瘥?璅??嚗?湔憭征?潸?銝???ID 蝯? (憒?9-H-1 ??10-P-1)
            const contactRegex = /\*?\s*([a-zA-Z0-9\-]+)\s*\(蝯??亥孛\)\s*\[([^\]]+)\]/g;
            let match;
            while ((match = contactRegex.exec(content)) !== null) {
                const id1 = match[1].trim();
                const id2 = match[2].trim();
                const node1 = `node-${id1}`;
                const node2 = `node-${id2}`;
                contactPairs.push({ start: node1, end: node2 });
                console.log("[UI-DEBUG] Auto-detected contact pair:", node1, "->", node2);
            }
        }

        // ?箸??嚗隞?(靽?憿舐內)
        tabBar.innerHTML += `<button id="tab-bom" class="panel-tab-btn active" onclick="switchPanelView('bom')">? ${CURRENT_LANG==='en'?'Parts':'?嗡辣'}</button>`;
        
        if (hasFeatures) {
            tabBar.innerHTML += `<button id="tab-feature" class="panel-tab-btn" onclick="switchPanelView('feature')">? ${CURRENT_LANG==='en'?'Features':'?孵噩??}</button>`;
        }
        if (hasTolerance) {
            tabBar.innerHTML += `<button id="tab-tolerance" class="panel-tab-btn" onclick="switchPanelView('tolerance')">?? ${CURRENT_LANG==='en'?'Tolerance':'?砍榆蝬脰楝'}</button>`;
        }
        if (hasContact) {
            tabBar.innerHTML += `<button id="tab-contact" class="panel-tab-btn" onclick="switchPanelView('contact')">? ${CURRENT_LANG==='en'?'Contact':'蝖祆閫賊??'}</button>`;
        }

        // ?芸??詨??摩
        let defaultTab = 'bom';
        if (intent && intent.tab) {
            if (intent.tab === 'tolerance' && hasTolerance) defaultTab = 'tolerance';
            else if (intent.tab === 'contact' && hasContact) defaultTab = 'contact';
            else if (intent.tab === 'feature' && hasFeatures) defaultTab = 'feature';
        }
        
        switchPanelView(defaultTab);
    }

    function renderCustomBomTree(text, bubbleElement, intent) {
        let rawText = text;
        let finalHtml = '';
        
        try {
            // ??銝衣蝡＊蝷?AUDIT_REPORT (?舀?? < > ?鋡怨歲?怎? &lt; &gt;)
            const auditRegex = new RegExp('&lt;AUDIT_REPORT&gt;([\\\\s\\\\S]*?)&lt;\\\\/AUDIT_REPORT&gt;|<AUDIT_REPORT>([\\\\s\\\\S]*?)<\\\\/AUDIT_REPORT>');
            let auditMatch = rawText.match(auditRegex);
            
            if (auditMatch) {
                let report = (auditMatch[1] || auditMatch[2]).trim().split('\\\\n').join('<br>').split('\\n').join('<br>');
                const auditLabel = CURRENT_LANG === 'en' ? '?? AI Self-Reflection & Audit Report:' : '?? AI ?芣???蝔賣?勗?嚗?;
                finalHtml += `<div style="background:#fefce8; border-left:4px solid #eab308; padding:10px; margin-bottom:15px; color:#854d0e; font-size:0.9rem; border-radius:4px; font-family: sans-serif;">
                    <strong>${auditLabel}</strong><pre style="white-space: pre-wrap; font-family: inherit; margin-top: 5px;">${report}</pre>
                </div>`;
            }
            
            // 撠雁??蝐文?摮葡銝剔宏?歹??踹?撟脫?恍
            rawText = rawText.replace(new RegExp('&lt;DRAFT&gt;[\\\\s\\\\S]*?&lt;\\\\/DRAFT&gt;|<DRAFT>[\\\\s\\\\S]*?<\\\\/DRAFT>', 'g'), '');
            rawText = rawText.replace(new RegExp('&lt;AUDIT_REPORT&gt;[\\\\s\\\\S]*?&lt;\\\\/AUDIT_REPORT&gt;|<AUDIT_REPORT>[\\\\s\\\\S]*?<\\\\/AUDIT_REPORT>', 'g'), '');
            rawText = rawText.replace(new RegExp('&lt;FINAL_ANSWER&gt;|<FINAL_ANSWER>', 'g'), '').replace(new RegExp('&lt;\\\\/FINAL_ANSWER&gt;|<\\\\/FINAL_ANSWER>', 'g'), '');
            
            let formatted = rawText.split('\\\\n').join('<br>').split('\\n').join('<br>');
            
            // ???鋆?蝯?SVG 雿輻?鼓????            let bomNetworks = [];
            
            // Decide Layout based on Intent
            let layoutClass = 'layout-tree'; // Default is Horizontal tree
            
            // 蝣箔? intent ?臭??迤蝣箇??拐辣 (?航???◤?嗆?摮葡?喲? Json string)
            let parsedIntent = intent;
            if (typeof intent === 'string' && intent.startsWith('{')) {
                try {
                    parsedIntent = JSON.parse(intent);
                } catch(e) {}
            }
            
            // ?望?膩 `intent` ?航?臬?銝脖??航?舐隞塚?????            if (parsedIntent === 'grid' || (parsedIntent && parsedIntent.layout === 'grid')) {
                layoutClass = 'layout-grid';
            }
            
            // ?孵?? contact 摮葡??賣?(Python boolean -> JS string "True")
            let enableContact = false;
            if (parsedIntent) {
                if (parsedIntent.contact === true || parsedIntent.contact === "True" || parsedIntent.contact === "true") {
                    enableContact = true;
                }
            }
            
            let enableEdit = false;
            if (parsedIntent) {
                if (parsedIntent.edit === true || parsedIntent.edit === "True" || parsedIntent.edit === "true") {
                    enableEdit = true;
                }
            }
        
        // Fallback: ??AI ??瘝? BOM 璅惜嚗??批捆?絲靘? BOM 蝯?嚗? 璅? + - N-?嗡辣??嚗??銝?蝐?        if (!formatted.includes('---BOM_START---')) {
            const plainBomRegex = /(#\s*[\u4e00-\u9fa5a-zA-Z0-9]+(?:<br>|\n)\s*(?:[-*]\s*\d+-[\u4e00-\u9fa5a-zA-Z0-9]+(?:<br>|\n)\s*)+)/;
            const plainMatch = formatted.match(plainBomRegex);
            if (plainMatch) {
                formatted = formatted.replace(plainMatch[0], '---BOM_START---' + plainMatch[0] + '---BOM_END---');
            }
        }

        // 撠 BOM ?憛?        const bomRegex = /---BOM_START---([\\s\\S]*?)---BOM_END---/g;
        let match;
        let lastIndex = 0;
        
        while ((match = bomRegex.exec(formatted)) !== null) {
            finalHtml += formatted.substring(lastIndex, match.index);
            
            let listContent = match[1].trim();
            // ??????嚗絞銝頧?隞亙??閫??
            listContent = listContent.replace(/<br>/g, '\\n');
            const lines = listContent.split('\\n');
            
            let currentPart = null;
            let assemblyName = CURRENT_LANG === 'en' ? 'Product Structure' : '?Ｗ??嗆???; // ?身?迂
            
            // ??閫???惜/憭惜蝯?
            let rootParts = [];
            let partStack = []; // 餈質馱?桀??隞園?撅?[{depth: 0, part: obj}, {depth: 2, part: obj}]
            
            lines.forEach(line => {
                if (!line.trim()) return;
                
                if (line.trim().startsWith('#')) {
                    assemblyName = line.replace(/^#\s*/, '').trim();
                    return;
                }
                
                // 閮?蝮桅脫楛摨?(隞亙?征?賣?銝??Tab ?箔??桐?)
                const leadingSpaceMatch = line.match(/^(\s*)/);
                const rawIndent = leadingSpaceMatch ? leadingSpaceMatch[1].length : 0;
                // ?箔??捆銝?蝮桅脫撘?憭扯隞??箔??惜蝝???祕?撠楛摨?                
                const cleanLine = line.trim();
                const isFeatureLine = cleanLine.match(/^[-*]\s*\d+-[PHS]-\d+(.*)/i) || cleanLine.startsWith('*');
                const partMatch = cleanLine.match(/^[-*]\s*(\d+)[-\s]+(.+)/i);
                
                if (partMatch && !isFeatureLine) {
                    const newPart = {
                        id: parseInt(partMatch[1]),
                        name: partMatch[1] + '-' + partMatch[2].trim(),
                        features: [],
                        children: []
                    };
                    
                    // 瘙箏?撅斤?甇詨惇
                    if (partStack.length === 0) {
                        rootParts.push(newPart);
                        partStack.push({depth: rawIndent, part: newPart});
                    } else {
                        // ?曉?桀??撅祉??嗥?暺?(敺?stack 銝剖??蝚砌???depth 瘥?撠?)
                        while (partStack.length > 0 && partStack[partStack.length - 1].depth >= rawIndent) {
                            partStack.pop();
                        }
                        
                        if (partStack.length === 0) {
                            // 霈?蝚砌?撅?                            rootParts.push(newPart);
                        } else {
                            // 霈?摮隞?                            partStack[partStack.length - 1].part.children.push(newPart);
                        }
                        partStack.push({depth: rawIndent, part: newPart});
                    }
                    return;
                }
                
                // ?孵噩?Ｚ圾??(??桀? stack ??惜?隞嗡?)
                const featureMatch = cleanLine.match(/^[-*]\s*([^\(\[\s]+)(.*)/);
                if (featureMatch && isFeatureLine) {
                    let attachTarget = null;
                    if (partStack.length > 0) {
                        attachTarget = partStack[partStack.length - 1].part;
                    } else {
                        // 憒?瘝??嗥?暺?撱箔??迨蝡?暺?                        const m = cleanLine.match(/^[-*]\s*(\d+)-/);
                        const partId = m ? m[1] : 'Unknown';
                        const featureSetName = CURRENT_LANG === 'en' ? 'Feature set' : '?孵噩??';
                        attachTarget = {
                            id: partId === 'Unknown' ? 999 : parseInt(partId),
                            name: `${partId}-${featureSetName}`,
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
                    
                    // 雿輻 g flag ?????銝剜??摰?                    const parenMatches = extra.matchAll(/\((.*?)\)/g);
                    for (const match of parenMatches) {
                        allTolerances.push(...match[1].split(/[,嚗s]+/).map(s => s.trim()).filter(s => s));
                    }
                    
                    const bracketMatches = extra.matchAll(/\[(.*?)\]/g);
                    for (const match of bracketMatches) {
                        allTolerances.push(...match[1].split(/[,嚗s]+/).map(s => s.trim()).filter(s => s));
                    }

                    // ??鈭支?)?砍榆嚗??怎換?脫???                    const REF_TOLS = ['per', 'par', 'dis', 'con', 'pos', 'run', 'sym', 'ang'];

                    // ??砍榆嚗??脰???                    const IND_TOLS = ['dia', 'rad', 'cyl', 'flat', 'cir']; 

                    function classifyTol(t) {
                      const s = String(t || '').toLowerCase();
                      if (REF_TOLS.some(k => s.includes(k))) return 'ref';
                      if (IND_TOLS.some(k => s.includes(k))) return 'ind';
                      return 'ind'; // 銝隞颱?皜???身??IND嚗???銝嚗?                    }

                    allTolerances.forEach(tol => {
                        const type = classifyTol(tol);
                        if (type === 'ref') interactives.push(tol);
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
            
            // ?交敺垢 intent.target_part ?脰??蕪
            let parts = rootParts;
            const targetPart = (parsedIntent && parsedIntent.target_part) ? parsedIntent.target_part : null;
            if (targetPart) {
                // ?艘??嚗??湔ㄤ璅嫣葉?曉?迂??targetPart ??暺?                function findMatchingParts(nodes, keyword) {
                    let result = [];
                    nodes.forEach(node => {
                        const nameMatch = node.name && node.name.includes(keyword);
                        if (nameMatch) {
                            result.push(node);
                        } else if (node.children && node.children.length > 0) {
                            const childMatches = findMatchingParts(node.children, keyword);
                            result = result.concat(childMatches);
                        }
                    });
                    return result;
                }
                const filtered = findMatchingParts(parts, targetPart);
                if (filtered.length > 0) parts = filtered;
                // ?亙??冽銝嚗???剁??踹?蝛箇?恍嚗?            }
            
            // 靘雿輻??瘙?靘?蝯?????
            parts.sort((a, b) => a.id - b.id);

            // 撠敺菟?脰? P -> S -> H ??
            parts.forEach(part => {
                if (part.features && part.features.length > 0) {
                    part.features.sort((fa, fb) => {
                        const nameA = fa.name;
                        const nameB = fb.name;
                        const getWeight = (s) => {
                            // ?澆??虜??"3-P-1" ??"P-1"
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
                     const _hintText = CURRENT_LANG === 'en'
                         ? '? Tip: Click any two feature nodes to draw a green "Hard Contact" line. Click the line to delete it.'
                         : '? ?內嚗??遙??敺萇?暺??喳?怠蝬?′?亥孛?????????臬?扎?;
                     const _exportLabel = CURRENT_LANG === 'en' ? '? Export CSV' : '? ?臬 CSV';
                     const _clearLabel = CURRENT_LANG === 'en' ? '?完 Clear All Lines' : '?完 皜??閫貊?';
                     treeHtml += `<div style="margin-bottom: 10px; color: #64748b; font-size: 0.9rem; text-align: center;">
                                    ${_hintText}
                                  </div>
                                  <div style="display:flex; justify-content:center; gap:10px; margin-bottom: 10px;">
                                    <button class="export-lines-btn" onclick="exportContactLines()" 
                                            style="background:#10b981; color:white; padding:5px 10px; border:none; 
                                                   border-radius:4px; font-weight:bold; cursor:pointer;">
                                      ${_exportLabel}
                                    </button>
                                    <button class="clear-lines-btn" onclick="clearAllContactLines()">
                                      ${_clearLabel}
                                    </button>
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
                
                // ?艘?賣靘葡?隞嗆邦
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
                        // 撠蝬脫??(Grid) 璅∪?嚗隞嗅?蝔望?勗椰?渡? DRF 璅?獢＊蝷綽??隞仿??隞??璅寧???(Tree) ???敺菟??敹?憿舐內?嗡辣?迂?孵?
                        const isGrid = layoutClass === 'layout-grid';
                        html += `
                        <div class="bom-child">
                        `;
                        if (!isGrid || !part.features || part.features.length === 0) {
                            html += `<div class="bom-node" style="border-color: #0f172a; padding: 10px; background: white;">${part.name}</div>`;
                        }
                        // ?蝝?摮???                        localListText += `- ${part.name}<br>`;
                    }

                    // ?孵噩?Ｘ葡??                    if (part.features && part.features.length > 0) {
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
                            // ?喃蝙?芾楊銝??(LLM 瞍??虫?蝡?嚗?閬?摰?箔??嗡?摮文?換?脰???隞亙?閰脣撌桃?交?憭望?∪耦
                            if (indices.length >= 1) {
                                bridges.push({ tag: tag, start: indices[0], end: indices[indices.length - 1] });
                            }
                        });

                        // 撠??亦?靘?頝刻? (end - start) ?勗??啣之??
                        // 蝣箔??剜??典?湛?蝚砌?頠?嚗璈憭嚗??璇漱??                        bridges.sort((a, b) => (a.end - a.start) - (b.end - b.start));


                        const isGrid = layoutClass === 'layout-grid';
                        // 撠?ROW_H ??CSS `.bom-feature-row { height: 50px; }` 蝯??郊嚗圾瘙箏??港?蝘颱誑???典?蝺?憿?                        const ROW_H = 50;
                        const NODE_BOX_W = 200;        // ???游?撖砍漲蝯阡???敺萇?暺?(憒?7-?批摰?...)
                        const GRID_NODE_LEFT_PAD = isGrid ? 30 : 0;  // .layout-grid .bom-feature-node { margin-left:30px }
                        const RAIL_START = GRID_NODE_LEFT_PAD + NODE_BOX_W; // 蝭暺??x嚗???韏琿?嚗?                        const COL_GAP = 95;            // 璈??甈祝 (蝔凝?曉之?踹?????憭芷)
                        const BRIDGE_GAP = 70;         // 璈蝺偌撟喲?頝?
                        // ?? ???ㄨ?折??獢?(?? Grid 璅∪?) ??
                        const boxId = `box-${part.id}`;
                        const drfId = `drf-${part.id}`;
                        
                        if (isGrid) {
                            html += `<div class="bom-grid-border-box" id="${boxId}" style="position: relative; flex: 0 0 auto;">`;
                        }

                        // Grid 璅∪? DRF ?寞?
                        if (isGrid) {
                            html += `
                                <div class="bom-part-metadata" style="flex: 0 0 auto; position: relative; z-index: 10;">
                                    <div class="bom-drf-box" id="${drfId}">${part.name} DRF</div>
                                </div>
                            `;
                        }

                        // 閮?閰脤隞嗡葉?憭批撌格???函?甈?祝摨?                        const maxIndsCount = Math.max(0, ...part.features.map(f => f.individuals.length));
                        const indBlockW = maxIndsCount * COL_GAP;
                        const bridgeBaseX = RAIL_START + indBlockW + 10;
                        const listH = part.features.length * ROW_H;
                        
                        // 閮????憭批祝摨佗?撘瑕閮剖??踹?鋡怠隞?Masonry 憯葬????                        let minListWidth = 160; // 蝯??香 160px嚗?銝?嗡辣蝭暺?摮?撠箏站銝璅∩?璅??蝣箔??迤?偌撟喳?銝剖?朣?                        if (maxIndsCount > 0 || bridges.length > 0) {
                            minListWidth = bridgeBaseX + bridges.length * BRIDGE_GAP + 60; // ?? padding 隞仿頞
                        }

                        // ??? ?蝡?銝脩敞蝛????????????????????????????????
                        let trunkHtml   = '';  // Layer 0: trunk嚗?摨惜嚗?                        let rowsHtml    = '';  // Layer A: rows
                        let railsHtml   = '';  // Layer B: rails
                        let bridgesHtml = '';  // Layer C: bridges

                        // trunk嚗?典??蝡? L/T/I ??靘?伐?瘨?銝?蝒??摮???                        part.features.forEach((f, idx) => {
                            const isFirst = idx === 0;
                            const isLast  = idx === part.features.length - 1;
                            const topY    = isFirst ? ROW_H / 2 : 0;
                            const height  = isLast && !isFirst ? ROW_H / 2 : (isFirst && isLast ? 0 : ROW_H);

                            const leftStyle = isGrid ? 'left: 0;' : 'left: 50%; transform: translateX(-50%);';
                            // 憒??芣?銝??銝?閬??渡?嚗???剜挾
                            if (part.features.length > 1) {
                                trunkHtml += `<div style="position:absolute; ${leftStyle} top:${idx * ROW_H + topY}px; width:2px; height:${height}px; background:#0f172a;"></div>`;
                            }
                            // 瘥?敺?單?啁?暺?璈怠?畾?(??Grid 璅∪?銝?閬?Tree 璅∪??孵噩?Ｗ歇蝵桐葉?⊿?璈怎?)
                            // 璈怎?敺?left:0 撱嗡撓??RAIL_START嚗‵皛?trunk ??feature-node ??rail 銋??征??                            if (isGrid && GRID_NODE_LEFT_PAD > 0) {
                                trunkHtml += `<div style="position:absolute; left:0; top:${idx * ROW_H + ROW_H / 2}px; width:${RAIL_START}px; height:2px; background:#0f172a;"></div>`;
                            }
                        });

                        // Layer A: Rows ?芣?蝭暺撌梧?蝘駁 Trunk, Rails, Bridges ??HTML ?潭
                        part.features.forEach((f, idx) => {
                            const isLast = idx === part.features.length - 1 ? ' last-feature-row' : '';
                            const nodeId = `node-${part.id}-${f.name}`;
                            const clickAttr = enableContact ? `onclick="toggleContactNode('${nodeId}')"` : '';
                            rowsHtml += `
                                <div class="bom-feature-row${isLast}" id="${nodeId}-row">
                                    <div class="bom-feature-node" id="${nodeId}" ${clickAttr}>${f.name}</div>
                                </div>`;

                            // ?犖?砍榆璈???(Layer B ??雿??曉?芰??批捆)
                            const hasInd = f.individuals.length > 0;
                            if (hasInd) {
                                let indHtml = '';
                                f.individuals.forEach((t, tIdx) => {
                                    const indId = `ind-${part.id}-${f.name}-${tIdx}`;
                                    indHtml += `<div class="tol-individual-wrapper"><div class="tolerance-bubble tol-individual" id="${indId}"><span class="tol-code">${t}</span></div></div>`;
                                });
                                // 靘??閬??捆?刻?????瘙箏?雿蔭
                                const rTop = idx * ROW_H + ROW_H / 2;
                                // ?ㄐ銝 railW 撱園?暺?嚗??芾?鞎祆???                                railsHtml += `<div class="tol-rail-container" style="left:${RAIL_START}px; top:${rTop}px; width: auto;">${indHtml}</div>`;
                            }

                            // ?湔??皜
                            let tolText = '';
                            if (f.individuals.length > 0) tolText += ` (${f.individuals.join(', ')})`;
                            if (f.interactives.length > 0) tolText += ` [${f.interactives.join(', ')}]`;
                            localListText += `&nbsp;&nbsp;&nbsp;&nbsp;* ${f.name}${tolText}<br>`;
                        });

                        // 蝝怨璈??
                        bridges.forEach((bridge, bIdx) => {
                            const lineX    = bridgeBaseX + bIdx * BRIDGE_GAP;
                            const capsuleCY = (bridge.start * ROW_H + bridge.end * ROW_H + ROW_H) / 2;
                            const bridgeId = `bridge-${part.id}-${bIdx}`;
                            
                            bridgesHtml += `
                                <div class="tol-interactive-wrapper" id="${bridgeId}" style="left:${lineX}px; top:${capsuleCY}px;">
                                    <div class="tolerance-bubble tol-interactive">
                                        <span class="tol-code">${bridge.tag}</span>
                                    </div>
                                </div>`;
                        });

                        // ?憛雯?潛?撣??摩??銝?
                        bomNetworks.push({
                            partId: part.id,
                            drfId: drfId,
                            boxId: boxId,
                            features: part.features.map(f => `node-${part.id}-${f.name}`),
                            bridges: bridges.map((b, bIdx) => {
                                // ?????閮?憟賜??祕 X 摨扳?嚗??? 0
                                const realLineX = bridgeBaseX + bIdx * BRIDGE_GAP;
                                return {
                                    id: `bridge-${part.id}-${bIdx}`,
                                    startIdx: b.start,
                                    endIdx: b.end,
                                    xOffset: realLineX
                                };
                            }),
                            rowH: ROW_H
                        });

                        // 蝯? HTML嚗?銝?SVG 摨惜嚗?                        // 閮剖? min-width 銝行溶??flex: 0 0 auto ?踹?鋡?flex 摰孵撘瑕??嗥葬????SVG
                        const listMargin = isGrid ? 'margin-right: 20px;' : 'margin: 0 auto;';
                        html += `<div class="bom-features-list" style="position: relative; flex: 0 0 auto; width:${minListWidth}px; min-width:${minListWidth}px; ${listMargin} height:${listH}px;">`;
                        html += `<svg class="bom-svg-layer" id="svg-${boxId}" style="position: absolute; top:0; left:0; min-width: 100%; width: 100%; height:100%; pointer-events:none; z-index:0;"></svg>`;
                        html += `
                            <div class="rows-layer">
                                <div class="bom-tree-trunk">${trunkHtml}</div>
                                ${rowsHtml}
                            </div>
                            <div class="rails-layer" style="position: absolute; inset: 0; pointer-events: none; z-index: 5;">${railsHtml}</div>
                            <div class="bridges-layer" style="position: absolute; inset: 0; pointer-events: none; z-index: 20;">${bridgesHtml}</div>
                        </div>`;
                        
                        // ????獢?                        if (isGrid) {
                            html += `</div>`;
                        }
                    }
                    
                    // 瑼Ｘ銝行葡??蝭暺?                    if (part.children && part.children.length > 0) {
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
                
                // ??皜脫?璅寧?蝯?
                // ?箔??詨捆銋???寧?暺身閮?憒?????root嚗???憭??銝撅方??祉??惜
                if (parts.length === 1) {
                    const res = renderPartNode(parts[0], true);
                    treeHtml += res.html;
                    sortedListText += res.listText;
                } else {
                    // 憒??像銵??蜓隞塚??撌梁?銝??蝝蝭暺?                    treeHtml += `
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

                // ?郊撠?銵冽葡?撌血?Ｘ
                const diagramCanvas = document.getElementById('diagram-canvas');
                if (diagramCanvas) {
                    diagramCanvas.innerHTML = treeHtml;
                    // ?見閫?? topology 隞乩噶?怎?
                    const utf8Topology = encodeURIComponent(JSON.stringify(bomNetworks));
                    const b64Topology = btoa(utf8Topology);
                    
                    // 隤輻 Modal ?詨???憪??摩嚗?雿?澆椰?Ｘ
                    if (b64Topology) {
                        try {
                            const utf8Str = atob(b64Topology);
                            const jsonStr = decodeURIComponent(utf8Str);
                            window.bomNetworks = JSON.parse(jsonStr);
                        } catch(e) { window.bomNetworks = []; }
                    }
                    
                    setTimeout(() => {
                        const canvas = document.getElementById('diagram-canvas');
                        if (document.getElementById('contact-lines-svg')) drawContactLines(canvas);
                        drawAllBomNetworks(canvas);
                    }, 100);
                    
                    // Attach observer for panel
                    attachBomObservers(diagramCanvas);
                    
                    // ?啣?嚗蜓??圈?踵?????(?靽桀儔撌血??銝???憿?
                    updatePanelButtons(rawText, parsedIntent);
                }

                // ?芸????? (靘? AI Intent)
                if (intent && intent.tab === 'tolerance') {
                    switchPanelView('tolerance');
                } else if (intent && intent.tab === 'bom') {
                    switchPanelView('bom');
                } else {
                    // ?身????BOM
                    switchPanelView('bom');
                }

                // 敺孵?蝘駁 open-bom-btn ??蝒????????摮?                finalHtml += `<div class="bom-list-text">${sortedListText}</div>`;

            } else {
                // 閫??憭望?撠勗?箏???
                // ?儔????listContent 憿舐內
                const errorLabel = CURRENT_LANG === 'en' ? '(Failed to parse structure, keeping text output)' : '(閫???Ｗ?蝯??仃??蝬剜???頛詨)';
                finalHtml += `<div style="color:gray;">${errorLabel}</div><br>${match[1].trim().replace(/\\n/g, '<br>')}`;
            }
            
            lastIndex = match.index + match[0].length;
        }
        
        finalHtml += formatted.substring(lastIndex);
        bubbleElement.innerHTML = finalHtml;
        
        } catch (err) {
            console.error("Error rendering BOM Tree:", err);
            bubbleElement.innerHTML = text + `<br><div style="color:red; margin-top:10px;">[SVG Render Error] ${err.message}</div>`;
        }
    }

    let chatHistory = [];
    const CURRENT_LANG = {{ lang|tojson }};
    window.matingConstraints = {{ mating_constraints|tojson if mating_constraints else [] }};

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
          body: JSON.stringify({ message: msg, model: selectedModel, history: chatHistory.slice(-6), lang: CURRENT_LANG })
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
            
            // ?澆???芸?蝢拇葡?嚗蒂?喳??閮剖?
            renderCustomBomTree(data.reply, bubble, data.intent);
            
            // Save AI response to history
            chatHistory.push({ role: 'assistant', content: data.reply });
            history.scrollTop = history.scrollHeight;
            
        } else {
          const errMsg = (CURRENT_LANG === 'en') ? '[WARN] Error: Unable to get response' : '[WARN] ?潛??航炊嚗瘜?敺???;
          addMessage('ai', errMsg);
        }

      } catch (e) {
        try { document.getElementById(loadingId)?.remove(); } catch(_) {}
        addMessage('ai', '[ERROR] 蝬脰楝?航炊嚗? + e);
      } finally {
        // Re-enable input ??蝣箔???瘞賊?鋡恍??啣???        input.disabled = false;
        sendBtn.disabled = false;
        sendBtn.style.pointerEvents = 'auto';
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

    let _bomScrollEl = null;  // ?? scroll listener ??蝝?靘踵皜

    function openBomModal(treeHtml, b64Topology) {
      document.getElementById('bom-modal-container').innerHTML = treeHtml;
      document.getElementById('bom-modal-overlay').style.display = 'flex';
      contactPairs = [];
      selectedContactNode = null;
      
      if (b64Topology) {
          try {
              const utf8Str = atob(b64Topology);
              const jsonStr = decodeURIComponent(utf8Str);
              window.bomNetworks = JSON.parse(jsonStr);
          } catch(e) {
              console.error("Failed to parse bomNetworks topology", e);
              window.bomNetworks = [];
          }
      } else {
          window.bomNetworks = [];
      }

      // ?芸??寞?敺垢?喃???matingConstraints 撱箇????
      autoPopulateMatingLines(document.getElementById('bom-modal-overlay'));

      // 撠辣?脫??瑁 300ms嚗??CSS ??瑁????漣璅?蝘?(getBoundingClientRect 銝?甇亙?憿?
      setTimeout(() => {
        const modalEl = document.getElementById('bom-modal-overlay');
        if (modalEl && modalEl.style.display === 'flex') {
            if (document.getElementById('contact-lines-svg')) drawContactLines(modalEl);
            drawAllBomNetworks(modalEl);
            console.log("[UI-DEBUG] Modal drawing triggered after 300ms delay.");
        }
      }, 300);

      // modal content ?脣???閬?蝜?      const modalContent = document.querySelector('.bom-modal-content');
      if (modalContent) {
        if (_bomScrollEl) _bomScrollEl.removeEventListener('scroll', _bomScrollHandler);
        _bomScrollEl = modalContent;
        _bomScrollEl.addEventListener('scroll', _bomScrollHandler, { passive: true });
      }

      // ResizeObserver 瘥?window resize ?湔?
      attachBomObservers(modalEl);
    }

    function autoPopulateMatingLines(scope = document) {
        if (!window.matingConstraints || window.matingConstraints.length === 0) return;
        
        window.matingConstraints.forEach(pair => {
            const [s, o] = pair;
            const sPartId = s.split('-')[0];
            const oPartId = o.split('-')[0];
            const sNodeId = `node-${sPartId}-${s}`;
            const oNodeId = `node-${oPartId}-${o}`;
            
            if (scope.getElementById(sNodeId) && scope.getElementById(oNodeId)) {
                const exists = contactPairs.some(p => 
                    (p.start === sNodeId && p.end === oNodeId) || 
                    (p.end === sNodeId && p.start === oNodeId)
                );
                if (!exists) {
                    contactPairs.push({ start: sNodeId, end: oNodeId });
                }
            }
        });
    }

    function _bomScrollHandler() {
      if (contactPairs.length > 0) drawContactLines();
      drawAllBomNetworks();
    }

    let _bomResizeObserver = null;
    function attachBomObservers(scope = document) {
      // 頛?賢?嚗??典?敺?Scope ?抒???
      const findInScope = (id) => (scope === document) ? document.getElementById(id) : scope.querySelector(`[id="${id}"]`);

      const wrapper = findInScope('bom-tree-wrapper');
      if (!wrapper) return;
      if (_bomResizeObserver) _bomResizeObserver.disconnect();
      _bomResizeObserver = new ResizeObserver(() => {
        if (contactPairs.length > 0) drawContactLines(scope);
        drawAllBomNetworks(scope);
      });
      _bomResizeObserver.observe(wrapper);
    }

    function closeBomModal() {
      document.getElementById('bom-modal-overlay').style.display = 'none';
      contactPairs = [];
      selectedContactNode = null;
      window.bomNetworks = [];
    }

    // --- SVG Tolerance Network Drawing Logic ---
    function drawAllBomNetworks(scope = document) {
        if (!window.bomNetworks) return;
        
        // 頛?賢?嚗??典?敺?Scope ?抒???
        const findInScope = (id) => (scope === document) ? document.getElementById(id) : scope.querySelector(`[id="${id}"]`);

        window.bomNetworks.forEach(net => {
            const svg = findInScope('svg-' + net.boxId);
            if (!svg) return;
            
            // 撘瑕?? (Force Reflow) 蝣箔? SVG ??Parent 撠箏站?郊
            void svg.offsetWidth;
            const parent = svg.parentElement;
            const parentRect = parent.getBoundingClientRect();
            
            svg.setAttribute('width', parentRect.width);
            svg.setAttribute('height', parentRect.height);
            svg.setAttribute('viewBox', `0 0 ${parentRect.width} ${parentRect.height}`);
            
            // ?望 SVG 撌脰身??100% 撖祇?嚗皞??摰 parent (蝛拙??批?)
            const originRect = parentRect;
            
            let pathD = '';
            
            const getRelRect = (elId) => {
                const el = findInScope(elId);
                if (!el) return null;
                const r = el.getBoundingClientRect();
                return {
                    left: r.left - originRect.left,
                    right: r.right - originRect.left,
                    top: r.top - originRect.top,
                    bottom: r.bottom - originRect.top,
                    cx: (r.left + r.width / 2) - originRect.left,
                    cy: (r.top + r.height / 2) - originRect.top,
                    width: r.width,
                    height: r.height,
                    el: el
                };
            };

            // ?? 1. ??Trunk (DRF ?啣??孵噩?? ??
            let trunkX = 0;
            let rowsData = [];
            net.features.forEach((fId, idx) => {
                const rNode = getRelRect(fId);
                const rRow = getRelRect(fId + '-row');
                if (rNode && rRow) {
                    trunkX = Math.round(rNode.left - 30); // GRID_NODE_LEFT_PAD
                    rowsData.push({ idx: idx, id: fId, y: Math.round(rRow.cy), x: Math.round(rNode.left), nodeRect: rNode });
                }
            });

            const rDrf = getRelRect(net.drfId);
            if (rDrf && rowsData.length > 0) {
                const drfRight = Math.round(rDrf.right);
                const drfCy = Math.round(rDrf.cy);
                
                // 敺?DRF ?喟垢銝剖???
                pathD += `M ${drfRight} ${drfCy} L ${trunkX} ${drfCy} `;
                
                if (rowsData.length > 1) {
                    // ?怠??渡蜇蝺?蝣箔?敺?擃?撱嗡撓?唳?雿?嚗???drfCy嚗?蝺?                    const minY = Math.min(drfCy, rowsData[0].y);
                    const maxY = Math.max(drfCy, rowsData[rowsData.length - 1].y);
                    pathD += `M ${trunkX} ${minY} L ${trunkX} ${maxY} `;
                } else if (rowsData.length === 1 && drfCy !== rowsData[0].y) {
                    // 憒??芣?銝撅支? Y 頠詨??箸?鈭?????鋆???挾?擃?撌?                    pathD += `M ${trunkX} ${drfCy} L ${trunkX} ${rowsData[0].y} `;
                }
                
                // ?急?撅斗偌撟單??                rowsData.forEach(r => {
                    pathD += `M ${trunkX} ${r.y} L ${r.x} ${r.y} `;
                });
            }

            // ?園???換?脰???鞈? (?冽?斗 Rail ???/ 霈?)
            let bridgeCapsules = [];
            net.bridges.forEach(b => {
                const rCap = getRelRect(b.id);
                if (rCap) {
                    bridgeCapsules.push({
                        ...b,
                        x: Math.round(rCap.cx),
                        leftEdge: Math.round(rCap.left - 4), // 憿???margin
                        rightEdge: Math.round(rCap.right + 4)
                    });
                }
            });

            // ?? 2. ??Rails ??Bridges ??
            rowsData.forEach(row => {
                let maxBridgeX = 0;
                let activeBridges = bridgeCapsules.filter(b => b.startIdx === row.idx || b.endIdx === row.idx);
                if (activeBridges.length > 0) {
                    maxBridgeX = Math.max(...activeBridges.map(b => b.x));
                }

                let hasIndividuals = false;
                let indFarRightCx = row.nodeRect.right;
                let indHtmlIdx = 0;
                
                // 靽格迤?孵噩?Ｗ?蝔勗?賢??怎??(憒?1-P-1) 撠 pop() ?芣?唳?敺?畾萇???
                const prefix = `node-${net.partId}-`;
                const fName = row.id.startsWith(prefix) ? row.id.substring(prefix.length) : row.id.split('-').pop();

                while(true) {
                    const rInd = getRelRect(`ind-${net.partId}-${fName}-${indHtmlIdx}`);
                    if (!rInd) break;
                    hasIndividuals = true;
                    indFarRightCx = Math.max(indFarRightCx, Math.round(rInd.cx));
                    indHtmlIdx++;
                }

                if (maxBridgeX > 0 || hasIndividuals) {
                    // 憒???蝝?蝺?蝯?蝎曄Ⅱ????蝝?銝剖?暺?(cx)
                    let endX = Math.round(Math.max(indFarRightCx, maxBridgeX));
                    
                    // ??隞亦?暺?湧?蝺???粹??哨?靽???蝔桀祝摨衣? feature ?Ｗ?蝢??                    let startX = Math.round(row.nodeRect.right);
                    let rowY = Math.round(row.y);
                    
                    // 摰鋆?嚗???暺漣璅??箔?瘥???嚗撥?嗥?箔?璇頝???亦?璈怎?
                    if (endX < startX + 40) {
                        endX = startX + 40;
                    }
                    
                    pathD += `M ${startX} ${rowY} L ${endX} ${rowY} `;
                }
            });

            // ?怠???Bridge Rungs
            bridgeCapsules.forEach(b => {
                const startRow = rowsData.find(r => r.idx === b.startIdx);
                const endRow = rowsData.find(r => r.idx === b.endIdx);
                if (startRow && endRow) {
                    // 蝺祝??2px嚗??抒葬 1px (<-- stroke-width/2)嚗甇Ｗ??渡??剖蝛踵偌撟單帖蝺耦????                    const startY = Math.round(startRow.y) + 1;
                    const endY = Math.round(endRow.y) - 1;
                    pathD += `M ${b.x} ${startY} L ${b.x} ${endY} `;
                }
            });

            // 撠??楝敺?蝑?伐?銝血???舐???            svg.innerHTML = `<path d="${pathD}" stroke="#0f172a" stroke-width="2" fill="none" stroke-linejoin="miter" stroke-linecap="butt" />`;
            if (pathD.length > 0) {
                console.log(`[UI-DEBUG] Scanned box ${net.boxId}, Path length: ${pathD.length}`);
            } else {
                console.warn(`[UI-DEBUG] Warning: Path empty for ${net.boxId}`);
            }
        });
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
    
    function drawContactLines(scope = document) {
        // 頛?賢?嚗??典?敺?Scope ?抒???
        const findInScope = (id) => (scope === document) ? document.getElementById(id) : scope.querySelector(`[id="${id}"]`);

        const svg = findInScope('contact-lines-svg');
        const wrapper = findInScope('bom-tree-wrapper');
        if (!svg || !wrapper) return;
        
        svg.innerHTML = ''; // Clear existing
        const wrapperRect = wrapper.getBoundingClientRect();
        
        contactPairs.forEach((pair, idx) => {
            const el1 = findInScope(pair.start);
            const el2 = findInScope(pair.end);
            if (!el1 || !el2) return;
            
            const rect1 = el1.getBoundingClientRect();
            const rect2 = el2.getBoundingClientRect();
            
            // 敺敺萇?暺??椰?氬?蝺??踹?蝛輯???
            const x1 = rect1.left - wrapperRect.left;
            const y1 = (rect1.top + rect1.height / 2) - wrapperRect.top;
            
            const x2 = rect2.left - wrapperRect.left;
            const y2 = (rect2.top + rect2.height / 2) - wrapperRect.top;
            
            // 閮??批暺?箏?撌血??脩?鞎?脩? (Bezier Curve)
            // ?頝頞?嚗?撌阡??勗?餌?撘批漲頞之嚗???憭?150px
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
            
            // Enable deleting the line by double-clicking it
            line.setAttribute('style', 'pointer-events: auto; cursor: pointer;');
            // ???豢筑?內霈蝙?刻??閬???            const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
            title.textContent = CURRENT_LANG === 'en' ? 'Double-click to remove contact line' : '??蝘駁?亥孛蝺?;
            line.appendChild(title);
            
            line.ondblclick = () => {
                contactPairs.splice(idx, 1);
                drawContactLines();
            };
            
            svg.appendChild(line);
        });
    }

    function clearAllContactLines() {
        const confirmMsg = CURRENT_LANG === 'en' ? "Are you sure you want to clear all contact lines?" : "蝣箏?閬??斗??閫貊???";
        if(confirm(confirmMsg)) {
            contactPairs = [];
            selectedContactNode = null;
            document.querySelectorAll('.bom-feature-node.contact-selected').forEach(el => el.classList.remove('contact-selected'));
            drawContactLines();
        }
    }
    
    // window resize 雿 fallback嚗蜓閬?蝜芰 ResizeObserver 鞎痊嚗?    window.addEventListener('resize', () => {
        if (contactPairs.length > 0 && document.getElementById('bom-modal-overlay').style.display === 'flex') {
            drawContactLines();
        }
    }, { passive: true });

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
        const alertMsg = CURRENT_LANG === 'en' ? "Failed to parse data, cannot open editor" : "鞈?閫??憭望?嚗瘜??楊頛臬";
        alert(alertMsg);
      }
    }

    function closeEditorModal() {
      document.getElementById('editor-modal-overlay').style.display = 'none';
    }

    function renderEditorList() {
      const container = document.getElementById('editor-list-container');

      // 銵券
      let html = `
        <table class="editor-table">
          <thead>
            <tr>
              <th style="width:32px;"></th>
              <th>{% if lang == 'en' %}A Path Code{% else %}A 頝臬?隞?Ⅳ{% endif %}</th>
              <th>{% if lang == 'en' %}B Value<br><span style="font-weight:normal;font-size:0.72rem;color:#64748b">(tra/rot/tol)</span>{% else %}B ?詨?br><span style="font-weight:normal;font-size:0.72rem;color:#64748b">嚗像蝘???/?砍榆?潘?</span>{% endif %}</th>
              <th>{% if lang == 'en' %}C Bias<br><span style="font-weight:normal;font-size:0.72rem;color:#64748b">(Tolerance zone offset)</span>{% else %}C ?榆??br><span style="font-weight:normal;font-size:0.72rem;color:#64748b">嚗撌桀葆?宏?潘?</span>{% endif %}</th>
              <th>{% if lang == 'en' %}D Ang Tol<br><span style="font-weight:normal;font-size:0.72rem;color:#64748b">Conv. Distance</span>{% else %}D 閫漲?砍榆<br><span style="font-weight:normal;font-size:0.72rem;color:#64748b">頧?頝</span>{% endif %}</th>
              <th style="width:60px;"></th>
            </tr>
          </thead>
          <tbody>`;

      editorPathData.forEach((node, idx) => {
        const isFeat = node.type === 'feature';
        const rowClass = isFeat ? 'row-feature' : 'row-spatial';

        // A甈??砍榆隞?Ⅳ嚗霈嚗? 蝛粹?頠賂?datalist 銝? + ?芰頛詨嚗?        const colA = isFeat
          ? `<td class="cell-code feat">${node.name}<br><span class="cell-part">${node.part || ''}</span></td>`
          : `<td class="cell-code spatial">
               <input list="axis-list-${idx}" value="${node.axis || ''}"
                 oninput="editorPathData[${idx}].axis=this.value"
                 class="axis-input" placeholder="traZ??>
               <datalist id="axis-list-${idx}">
                 ${['traX','traY','traZ','rotX','rotY','rotZ','cy1','co1','AngX','AngY','AngZ','PerX','PerY','PerZ'].map(ax =>
                   `<option value="${ax}">`).join('')}
               </datalist>
             </td>`;

        // B甈??詨?        const colB = `<td><input type="number" step="0.001" value="${node.val ?? 0}"
                        onchange="editorPathData[${idx}].val=parseFloat(this.value)||0"
                        class="cell-input"></td>`;

        // C甈??榆?潘??砍榆撣嗅?蝘鳴??身 0嚗?        const colC = `<td><input type="number" step="0.001" value="${node.bias ?? 0}"
                        onchange="editorPathData[${idx}].bias=parseFloat(this.value)||0"
                        class="cell-input"></td>`;

        // D甈?閫漲?砍榆頧?頝嚗??Ang/Per ?砍榆???儔嚗?閮剔征嚗?        const isAngular = isFeat && /ang|per/i.test(node.name);
        const colD = `<td><input type="number" step="1" value="${node.dist ?? (isAngular ? 100 : '')}"
                        ${!isAngular && !isFeat ? '' : ''}
                        onchange="editorPathData[${idx}].dist=parseFloat(this.value)||0"
                        class="cell-input" placeholder="${isAngular ? '100' : ''}"></td>`;

        html += `
          <tr class="${rowClass}">
            <td class="cell-drag">??/td>
            ${colA}${colB}${colC}${colD}
            <td><button class="btn-remove-row" onclick="removeNode(${idx})">??/button></td>
          </tr>
          <tr class="row-insert">
            <td colspan="6">
              <button class="btn-insert" onclick="addSpatialNode(${idx+1})">
                ${CURRENT_LANG === 'en' ? '+ Insert tra/rot' : '嚗?? tra/rot'}
              </button>
            </td>
          </tr>`;
      });

      html += `</tbody></table>`;
      container.innerHTML = html;
    }

    function addSpatialNode(index) {
      editorPathData.splice(index, 0, { type: 'spatial', axis: 'traZ', val: 0.0, bias: 0, dist: 0 });
      renderEditorList();
    }

    function removeNode(index) {
      editorPathData.splice(index, 1);
      renderEditorList();
    }

    async function exportCSV() {
       const btn = document.querySelector('.btn-export');
       const originalText = btn.textContent;
       btn.textContent = CURRENT_LANG === 'en' ? "??Generating CSV..." : "???Ｙ? CSV 銝?..";
       btn.disabled = true;
       
       try {
           const res = await fetch('/api/export_tolerance_csv', {
               method: 'POST',
               headers: {'Content-Type': 'application/json'},
               body: JSON.stringify({ pathData: editorPathData, lang: CURRENT_LANG })
           });
           
           if (!res.ok) throw new Error("Export failed");
           
           const blob = await res.blob();
           const url = window.URL.createObjectURL(blob);
           const a = document.createElement('a');
           a.style.display = 'none';
           a.href = url;
           a.download = "Tolerance_Path_Export.csv";
           document.body.appendChild(a);
           a.click();
           document.body.removeChild(a);
           window.URL.revokeObjectURL(url);
           
           alert(CURRENT_LANG === 'en' ? "[SUCCESS] CSV file downloaded!" : "[SUCCESS] CSV 瑼?銝???嚗?);
       } catch (e) {
           console.error(e);
           alert(CURRENT_LANG === 'en' ? "[ERROR] Export failed: " : "[ERROR] ?臬憭望?: " + e.message);
       } finally {
           btn.textContent = originalText;
           btn.disabled = false;
       }
    }

    async function exportContactLines() {
        if (contactPairs.length === 0) {
            alert(CURRENT_LANG === 'en' ? "No contact lines to export!" : "?桀?瘝?隞颱??亥孛蝺隞亙?綽?");
            return;
        }
        
        const btn = document.querySelector('.export-lines-btn');
        const originalText = btn.textContent;
        btn.textContent = CURRENT_LANG === 'en' ? "??Generating CSV..." : "???Ｙ? CSV 銝?..";
        btn.disabled = true;
        
        let exportData = contactPairs.map(p => {
            const startNode = document.getElementById(p.start);
            const endNode = document.getElementById(p.end);
            return {
                start: startNode ? startNode.textContent.trim() : p.start,
                end: endNode ? endNode.textContent.trim() : p.end
            };
        });
        
        try {
            const res = await fetch('/api/export_contact_lines_csv', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ pairs: exportData, lang: CURRENT_LANG })
            });
            
            if (!res.ok) throw new Error("Export failed");
            
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = "Contact_Lines_Export.csv";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);
            
            alert(CURRENT_LANG === 'en' ? "[SUCCESS] Contact lines CSV downloaded!" : "[SUCCESS] ?亥孛??? CSV 瑼?銝???嚗?);
        } catch (e) {
            console.error(e);
            alert(CURRENT_LANG === 'en' ? "[ERROR] Export failed: " + e.message : "[ERROR] ?臬憭望?: " + e.message);
        } finally {
            btn.textContent = originalText;
            btn.disabled = false;
        }
    }

  </script>
</body>
</html>
"""


def get_available_models():
    """
    ???桀??祆??歇閮剖????AI 璅∪??”??    ????閮剔? localhost:11434 ?潮?瘙?? Ollama 銝剔?璅∪?嚗?    銝血??砍?蝡舀芋?脰?????摨?隞亙?閮剖??身?貊?芋??    """
    # Fetch available models from Ollama explicitly on localhost
    try:
        client = ollama.Client(host="http://localhost:11434")
        models_info = client.list()
        model_names = []
        for m in models_info.models:
            # Handle different versions of ollama-python return types
            m_name = None
            if hasattr(m, "model"):
                m_name = m.model
            elif hasattr(m, "name"):
                m_name = m.name
            elif isinstance(m, dict):
                m_name = m.get("model") or m.get("name")
            
            if m_name:
                model_names.append(m_name)

        cloud_model_prefixes = [
            "gpt-oss", "qwen3-vl", "qwen3-v1", "ministral-3", "qwen3-coder",
            "glm-5", "glm-4.7", "glm-4.6", "glm-4", "deepseek-v3.2",
            "deepseek-v3.1", "deepseek3.1", "deepseek-v3", "minimax-m2",
            "minimax", "gemini-3", "kimi", "qwen3.5", "nemotron-3",
        ]

        def is_cloud_model(name):
            name_lower = name.lower()
            if "-cloud" in name_lower or ":cloud" in name_lower:
                return True
            for prefix in cloud_model_prefixes:
                if name_lower.startswith(prefix):
                    return True
            return False

        def model_sort_key(name):
            if is_cloud_model(name):
                return (0, name.lower())
            else:
                return (1, name.lower())

        manual_cloud_models = [
            "gpt-oss:120b-cloud", "deepseek3.1:671b-cloud", "qwen3-coder:480b-cloud",
            "ministral-3:8b-cloud", "glm-4.7:cloud", "minimax-m2:cloud",
        ]

        import re
        final_model_dict = {}
        for m in model_names + manual_cloud_models:
            m_lower = m.lower()
            if "gemini" in m_lower:
                continue
            match = re.match(r"^([a-z\-]+)(?:[\d\.\-v]*)(?:[:\-].*)?$", m_lower)
            if match:
                base_family = match.group(1).strip("-")
                if base_family.startswith("deepseek"): base_family = "deepseek"
                elif base_family.startswith("qwen"): base_family = "qwen"
                elif base_family.startswith("glm"): base_family = "glm"
                elif base_family.startswith("gpt"): base_family = "gpt"
            else:
                base_family = m_lower.split(":")[0]

            if base_family not in final_model_dict:
                final_model_dict[base_family] = m
            else:
                current_best = final_model_dict[base_family]
                is_m_cloud = "cloud" in m_lower
                is_curr_cloud = "cloud" in current_best.lower()
                if is_m_cloud and not is_curr_cloud:
                    final_model_dict[base_family] = m
                elif is_m_cloud == is_curr_cloud:
                    if len(m) > len(current_best):
                        final_model_dict[base_family] = m

        model_names = list(final_model_dict.values())
        model_names.sort(key=model_sort_key)
    except Exception as e:
        print(f"Error fetching models: {e}")
        model_names = ["llama3.1:8b"]

    current_model = None
    preferred_cloud = [
        "gemma3:4b", "gemma3:12b", "minimax-m2:cloud",
        "gpt-oss:120b-cloud", "ministral-3:8b-cloud", "qwen3-coder:480b-cloud",
    ]
    for preferred in preferred_cloud:
        if any(str(m) == str(preferred) for m in model_names):
            current_model = preferred
            break

    if not current_model:
        for m in model_names:
            if m.startswith("gemma3:") or m.startswith("llama3"):
                current_model = m
                break

    if not current_model:
        current_model = model_names[0] if model_names else "llama3.1:8b"

    return model_names, current_model


@app.route("/")
def home():
    """
    ?垢蝬脤???桅?頝舐 (蝜?銝剜?????    ?皜脫?憟賜? HTML 璅⊥嚗蒂撣嗅?舐?芋??銵刻???蝝?璇辣??    """
    model_names, current_model = get_available_models()
    constraints = get_mating_constraints()
    return render_template_string(
        HTML_TEMPLATE, 
        models=model_names, 
        current_model=current_model, 
        lang="zh-TW",
        mating_constraints=constraints
    )


@app.route("/en")
def home_en():
    """
    ?垢蝬脤????頝舐??    ?皜脫?憟賜? HTML 璅⊥嚗蒂閮剖?隤??箄?誑??憭?蝟餅?氬?    """
    model_names, current_model = get_available_models()
    constraints = get_mating_constraints()
    return render_template_string(
        HTML_TEMPLATE, 
        models=model_names, 
        current_model=current_model, 
        lang="en",
        mating_constraints=constraints
    )


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """
    ??雿輻??閰梯?瘙? API??    ?交雿輻??閮???璅∪??風?脣?閰梧??斗?臬?粹蝡舀芋?誑瘙箏? Ollama URL嚗?    ?嗅??澆 rag_engine ?脰? RAG (瑼Ｙ揣憓撥??) ??銝血???AI ????瑽澈 (BOM) ??鞈???    """
    data = request.get_json(force=True)
    user_msg = data.get("message", "")
    model_name = data.get("model", "llama3.1:8b")
    history = data.get("history", [])
    lang = data.get("lang", "zh-TW")

    if not user_msg:
        reply_msg = "Please enter a message" if lang == "en" else "隢撓?亥???
        return jsonify({"reply": reply_msg}), 400

    # ?斗?臬?粹蝡舀芋??(?ㄐ?函陛?桃?摮葡?斗嚗?臭誑靘祕??瘜耨??
    model_lower = model_name.lower()
    is_cloud = (
        "-cloud" in model_lower
        or ":cloud" in model_lower
        or model_lower.startswith("gpt-oss")
        or model_lower.startswith("qwen3-vl")
        or model_lower.startswith("qwen3-v1")
        or model_lower.startswith("ministral-3")
        or model_lower.startswith("qwen3-coder")
        or model_lower.startswith("glm-4")
        or model_lower.startswith("deepseek")
        or model_lower.startswith("minimax")
    )

    # [隢釣??] ?ㄐ憛思??券蝡舀??函? Ngrok ??Cloudflare 蝬脣?
    # ?望?桀?雿輻???34.36.133.15 ????航炊 (Google Cloud IP / ngrok)嚗???ㄐ?孵? localhost
    CLOUD_OLLAMA_URL = "http://localhost:11434"

    # 瘙箏?雿輻??URL
    base_url = CLOUD_OLLAMA_URL if is_cloud else "http://localhost:11434"

    print(
        f"[INFO] ?交?啣?閰梯?瘙?- 閮: '{user_msg}', 璅∪?: {model_name}, 蝬脣?: {base_url}"
    )

    try:
        from rag_engine import ask_rag_engine

        reply, bom_intent = ask_rag_engine(
            user_msg, model_name=model_name, base_url=base_url, history=history, lang=lang
        )
    except Exception as e:
        import sys

        with open("sys_exec.txt", "w", encoding="utf-8") as f:
            f.write(f"exe: {sys.executable}\npath: {sys.path}\nerror: {e}")
        print(f"[WARN] GraphRAG ?臬?銵仃?? {e}")
        print(f"[WARN] 甇?雿輻??Python: {sys.executable}")
        reply = f"[ERROR] ???澈 (GraphRAG) ?瑁??潛??航炊: {e}???舐窗蝟餌絞蝞∠??～?
        bom_intent = {}

    return jsonify({"reply": reply, "intent": bom_intent})


@app.route("/api/machines", methods=["GET"])
def get_machines():
    """
    ??璈鞈?摨怎? API??    霈???data/machines_data.json ?抒?璈鞈?憭曆蒂?蝯血?蝡胯?    """
    import json
    import os

    file_path = os.path.join(os.path.dirname(__file__), "data", "machines_data.json")
    if not os.path.exists(file_path):
        return jsonify({"ok": False, "msg": "?曆??唳??啗???}), 404

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"ok": False, "msg": f"閫??鞈?憭望?: {str(e)}"}), 500


@app.route("/api/export_tolerance_csv", methods=["POST"])
def export_tolerance_csv():
    """
    ?臬?砍榆頝臬?鞈???API??    ?交?垢蝺刻摩?典靘??砍榆頝臬?鞈?嚗??嗉?? pandas DataFrame嚗?    銝虫誑 CSV 瑼??澆??蝯虫蝙?刻脰?銝???    """
    data = request.get_json()
    path_data = data.get("pathData", [])
    lang = data.get("lang", "zh-TW")

    import io
    import pandas as pd

    rows = []
    for item in path_data:
        if item.get("type") == "feature":
            rows.append(
                {
                    "頝臬?隞?Ⅳ" if lang != 'en' else "Path Code": item.get("name"),
                    "?詨?撟喟宏??頧撌桀?" if lang != 'en' else "Value(tra/rot/tol)": item.get("val", 0.01),
                    "?榆???砍榆撣嗅?蝘餃?" if lang != 'en' else "Bias(offset)": item.get("bias", 0),
                    "閫漲?砍榆頧?頝" if lang != 'en' else "Ang Tol Dist": item.get("dist", "") or "",
                }
            )
        elif item.get("type") == "spatial":
            rows.append(
                {
                    "頝臬?隞?Ⅳ" if lang != 'en' else "Path Code": item.get("axis"),
                    "?詨?撟喟宏??頧撌桀?" if lang != 'en' else "Value(tra/rot/tol)": item.get("val", 0.0),
                    "?榆???砍榆撣嗅?蝘餃?" if lang != 'en' else "Bias(offset)": item.get("bias", 0),
                    "閫漲?砍榆頧?頝" if lang != 'en' else "Ang Tol Dist": item.get("dist", "") or "",
                }
            )

    df = pd.DataFrame(rows)

    output = io.StringIO()
    df.to_csv(output, index=False, encoding="utf-8-sig")
    csv_content = output.getvalue()

    from flask import Response

    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=Tolerance_Path_Export.csv"},
    )


@app.route("/api/export_contact_lines_csv", methods=["POST"])
def export_contact_lines_csv():
    """
    ?臬?亥孛???鞈???API??    ?交?垢蝯?璅?(BOM Tree) ?恍銝???隞嗥敺菟??嚗?    頧???DataFrame 銝虫誑 CSV ?澆??隞乩?銝???    """
    data = request.get_json()
    pairs = data.get("pairs", [])
    lang = data.get("lang", "zh-TW")

    import io
    import pandas as pd

    rows = []
    for pair in pairs:
        rows.append(
            {
                "?孵噩??1" if lang != 'en' else "Feature 1": pair.get("start"),
                "?孵噩??2" if lang != 'en' else "Feature 2": pair.get("end"),
                "???憿?" if lang != 'en' else "Connection Type": "蝖祆閫? if lang != 'en' else "Hard Contact",
            }
        )

    df = pd.DataFrame(rows)

    output = io.StringIO()
    df.to_csv(output, index=False, encoding="utf-8-sig")
    csv_content = output.getvalue()

    from flask import Response

    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=Contact_Lines_Export.csv"},
    )


@app.route("/api/sync_report", methods=["POST"])
def sync_report():
    """
    ?交?垢?????啣??銵?蝝?摮?嚗?亙??亙???園?靘?AI ?剜?閮雿輻??    """
    try:
        data = request.get_json()
        report_text = data.get("reportText", "")

        if not report_text:
            return jsonify({"ok": False, "msg": "瘝??嗅?梯”?批捆"}), 400

        import graph_rag

        graph_rag.set_latest_report(report_text)

        print(f"[SUCCESS] ???交銝行?唳??唳??啣??銵?(?瑕漲: {len(report_text)})")
        return jsonify({"ok": True, "msg": "?梯”?郊??"})

    except Exception as e:
        return jsonify({"ok": False, "msg": f"?郊憭望?: {str(e)}"}), 500


if __name__ == "__main__":
    print("?? AI ?予?拇?隡箸???..")
    print("隢赤?? http://127.0.0.1:7011")
    app.run(host="0.0.0.0", port=7011, debug=True)
