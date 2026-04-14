// 全域狀態變數
let _bomScrollEl = null;
let _bomResizeObserver = null;
let selectedContactNode = null;
let contactPairs = [];
let editorPathData = [];

// 處理自定義產品架構圖的函式
function renderCustomBomTree(text, bubbleElement, intent) {
    let rawText = text;
    let finalHtml = '';

    try {
        const auditRegex = new RegExp('&lt;AUDIT_REPORT&gt;([\\s\\S]*?)&lt;\\/AUDIT_REPORT&gt;|<AUDIT_REPORT>([\\s\\S]*?)<\\/AUDIT_REPORT>');
        let auditMatch = rawText.match(auditRegex);

        if (auditMatch) {
            let report = (auditMatch[1] || auditMatch[2]).trim().split('\\n').join('<br>').split('\n').join('<br>');
            const auditLabel = window.CURRENT_LANG === 'en' ? '🔍 AI Self-Reflection & Audit Report:' : '🔍 AI 自我反思與稽核報告：';
            finalHtml += `<div style="background:#fefce8; border-left:4px solid #eab308; padding:10px; margin-bottom:15px; color:#854d0e; font-size:0.9rem; border-radius:4px; font-family: sans-serif;">
                <strong>${auditLabel}</strong><pre style="white-space: pre-wrap; font-family: inherit; margin-top: 5px;">${report}</pre>
            </div>`;
        }

        rawText = rawText.replace(new RegExp('&lt;DRAFT&gt;[\\s\\S]*?&lt;\\/DRAFT&gt;|<DRAFT>[\\s\\S]*?<\\/DRAFT>', 'g'), '');
        rawText = rawText.replace(new RegExp('&lt;AUDIT_REPORT&gt;[\\s\\S]*?&lt;\\/AUDIT_REPORT&gt;|<AUDIT_REPORT>[\\s\\S]*?<\\/AUDIT_REPORT>', 'g'), '');
        rawText = rawText.replace(new RegExp('&lt;FINAL_ANSWER&gt;|<FINAL_ANSWER>', 'g'), '').replace(new RegExp('&lt;\\/FINAL_ANSWER&gt;|<\\/FINAL_ANSWER>', 'g'), '');

        let formatted = rawText.split('\\n').join('<br>').split('\n').join('<br>');
        let bomNetworks = [];
        let layoutClass = 'layout-tree';

        let parsedIntent = intent;
        if (typeof intent === 'string' && intent.startsWith('{')) {
            try { parsedIntent = JSON.parse(intent); } catch (e) { }
        }

        if (parsedIntent === 'grid' || (parsedIntent && parsedIntent.layout === 'grid')) {
            layoutClass = 'layout-grid';
        }

        let enableContact = false;
        if (parsedIntent && (parsedIntent.contact === true || parsedIntent.contact === "True" || parsedIntent.contact === "true")) {
            enableContact = true;
        }

        let enableEdit = false;
        if (parsedIntent && (parsedIntent.edit === true || parsedIntent.edit === "True" || parsedIntent.edit === "true")) {
            enableEdit = true;
        }

        const bomRegex = /---BOM_START---([\s\S]*?)---BOM_END---/g;
        let match;
        let lastIndex = 0;

        while ((match = bomRegex.exec(formatted)) !== null) {
            finalHtml += formatted.substring(lastIndex, match.index);
            let listContent = match[1].trim().replace(/<br>/g, '\n');
            
            // [核心修正] 提取全域接觸數據，用於跨零件連線與導出
            const contactsMatch = listContent.match(/---CONTACTS_START---([\s\S]*?)---CONTACTS_END---/);
            if (contactsMatch) {
                const contactLines = contactsMatch[1].trim().split('\n');
                contactLines.forEach(line => {
                    const pairParts = line.split(',');
                    if (pairParts.length === 2) {
                        const f1 = pairParts[0].trim();
                        const f2 = pairParts[1].trim();
                        const p1 = f1.split('-')[0];
                        const p2 = f2.split('-')[0];
                        const id1 = `node-${p1}-${f1}`;
                        const id2 = `node-${p2}-${f2}`;
                        if (!contactPairs.some(cp => (cp.start === id1 && cp.end === id2) || (cp.end === id1 && cp.start === id2))) {
                            contactPairs.push({ start: id1, end: id2 });
                        }
                    }
                });
                // 移除 DSL 中的數據部分，避免干擾後續樹狀解析
                listContent = listContent.replace(/---CONTACTS_START---[\s\S]*?---CONTACTS_END---/, '').trim();
            }

            const lines = listContent.split('\n');

            let assemblyName = window.CURRENT_LANG === 'en' ? 'Product Structure' : '產品架構圖';
            let rootParts = [];
            let partStack = [];

            lines.forEach(line => {
                if (!line.trim()) return;
                if (line.trim().startsWith('#')) {
                    assemblyName = line.replace(/^#\s*/, '').trim();
                    return;
                }

                const leadingSpaceMatch = line.match(/^(\s*)/);
                const rawIndent = leadingSpaceMatch ? leadingSpaceMatch[1].length : 0;
                const cleanLine = line.trim();
                const isFeatureLine = cleanLine.match(/^[-*]\s*\d+-[PHS]-\d+(.*)/i) || cleanLine.startsWith('*');
                const partMatch = cleanLine.match(/^[-*]\s*(\d+)[-\s]+(.+)/i);

                if (partMatch && !isFeatureLine) {
                    const newPart = { id: parseInt(partMatch[1]), name: partMatch[1] + '-' + partMatch[2].trim(), features: [], children: [] };

                    if (partStack.length === 0) {
                        rootParts.push(newPart);
                        partStack.push({ depth: rawIndent, part: newPart });
                    } else {
                        while (partStack.length > 0 && partStack[partStack.length - 1].depth >= rawIndent) {
                            partStack.pop();
                        }
                        if (partStack.length === 0) {
                            rootParts.push(newPart);
                        } else {
                            partStack[partStack.length - 1].part.children.push(newPart);
                        }
                        partStack.push({ depth: rawIndent, part: newPart });
                    }
                    return;
                }

                const featureMatch = cleanLine.match(/^[-*]\s*([^\(\[\s]+)(.*)/);
                if (featureMatch && isFeatureLine) {
                    let attachTarget = null;
                    if (partStack.length > 0) {
                        attachTarget = partStack[partStack.length - 1].part;
                    } else {
                        const m = cleanLine.match(/^[-*]\s*(\d+)-/);
                        const partId = m ? m[1] : 'Unknown';
                        const featureSetName = window.CURRENT_LANG === 'en' ? 'Feature set' : '特徵集合';
                        attachTarget = { id: partId === 'Unknown' ? 999 : parseInt(partId), name: `${partId}-${featureSetName}`, features: [], children: [] };
                        rootParts.push(attachTarget);
                        partStack.push({ depth: 0, part: attachTarget });
                    }

                    const featureName = featureMatch[1].trim();
                    const featureType = ''; // 不再提取顯示 P/S/H
                    const tolRaw = featureMatch[2] || '';

                    // [新增] 解析象限標籤 [Q1]~[Q4]
                    const qMatch = cleanLine.match(/\[Q([1-4])\]/);
                    const quadrant = qMatch ? parseInt(qMatch[1]) : null;

                    let individuals = [];
                    let interactives = [];
                    const allTolerances = [];
                    const parenMatches = tolRaw.matchAll(/\((.*?)\)/g);
                    for (const match of parenMatches) {
                        allTolerances.push(...match[1].split(/[,，\s]+/).map(s => s.trim()).filter(s => s));
                    }
                    const bracketMatches = tolRaw.matchAll(/\[(.*?)\]/g);
                    for (const match of bracketMatches) {
                        const content = match[1];
                        if (!content.startsWith('Q')) { // 排除象限標籤
                            allTolerances.push(...content.split(/[,，\s]+/).map(s => s.trim()).filter(s => s));
                        }
                    }

                    const REF_TOLS = ['per', 'par', 'dis', 'con', 'pos', 'run', 'sym', 'ang'];
                    const IND_TOLS = ['dia', 'rad', 'cyl', 'fla', 'cir', 'str', 'flat'];
                    function classifyTol(t) {
                        const s = String(t || '').toLowerCase();
                        if (REF_TOLS.some(k => s.includes(k))) return 'ref';
                        if (IND_TOLS.some(k => s.includes(k))) return 'ind';
                        return 'ind';
                    }

                    allTolerances.forEach(tol => {
                        const type = classifyTol(tol);
                        if (type === 'ref') interactives.push(tol);
                        else individuals.push(tol);
                    });
                    attachTarget.features.push({ name: featureName, individuals: individuals, interactives: interactives, quadrant: quadrant });
                }
            });

            let parts = rootParts;
            const targetPart = (parsedIntent && parsedIntent.target_part) ? parsedIntent.target_part : null;
            if (targetPart) {
                function findMatchingParts(nodes, keyword) {
                    let result = [];
                    nodes.forEach(node => {
                        if (node.name && node.name.includes(keyword)) {
                            result.push(node);
                        } else if (node.children && node.children.length > 0) {
                            result = result.concat(findMatchingParts(node.children, keyword));
                        }
                    });
                    return result;
                }
                const filtered = findMatchingParts(parts, targetPart);
                if (filtered.length > 0) parts = filtered;
            }

            parts.sort((a, b) => a.id - b.id);
            parts.forEach(part => {
                if (part.features && part.features.length > 0) {
                    part.features.sort((fa, fb) => {
                        const getWeight = (s) => {
                            const m = s.match(/([PSH])/i);
                            if (!m) return 9;
                            const map = { 'P': 1, 'S': 2, 'H': 3 };
                            return map[m[1].toUpperCase()] || 9;
                        };
                        const getNum = (s) => {
                            const m = s.match(/(\d+)$/);
                            return m ? parseInt(m[1]) : 0;
                        };
                        const wa = getWeight(fa.name);
                        const wb = getWeight(fb.name);
                        if (wa !== wb) return wa - wb;
                        return getNum(fa.name) - getNum(fb.name);
                    });
                }
            });

            if (parts.length > 0) {
                let treeHtml = `<div class="bom-container ${layoutClass}">`;
                if (enableContact) {
                    const _hintText = window.CURRENT_LANG === 'en' ? '💡 Tip: Click any two feature nodes to draw a green "Hard Contact" line. Click the line to delete it.' : '💡 提示：點擊任意兩個特徵節點，即可畫出綠色的「硬接觸」連線。點擊連線可刪除。';
                    const _exportLabel = window.CURRENT_LANG === 'en' ? '💾 Export CSV' : '💾 匯出 CSV';
                    const _clearLabel = window.CURRENT_LANG === 'en' ? '🧹 Clear All Lines' : '🧹 清除所有接觸線';
                    treeHtml += `<div style="margin-bottom: 10px; color: #64748b; font-size: 0.9rem; text-align: center;">${_hintText}</div>
                                  <div style="display:flex; justify-content:center; gap:10px; margin-bottom: 10px;">
                                    <button class="export-lines-btn" onclick="exportContactLines()" style="background:#10b981; color:white; padding:5px 10px; border:none; border-radius:4px; font-weight:bold; cursor:pointer;">${_exportLabel}</button>
                                    <button class="clear-lines-btn" onclick="clearAllContactLines()">${_clearLabel}</button>
                                  </div>`;
                }

                if (layoutClass === 'layout-tree') {
                    treeHtml += `<div id="bom-tree-wrapper" class="bom-tree-canvas" style="position:relative;">`;
                } else {
                    treeHtml += `<div id="bom-tree-wrapper" style="position:relative; width:100%;">`;
                }

                if (enableContact) {
                    treeHtml += `<svg id="contact-lines-svg" style="position:absolute; top:0; left:0; width:100%; height:100%; pointer-events:none; z-index:50; overflow:visible;"></svg>`;
                }

                treeHtml += `<div class="bom-children">`;

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
                        const isGrid = layoutClass === 'layout-grid';
                        html += `<div class="bom-child">`;
                        if (!isGrid || !part.features || part.features.length === 0) {
                            html += `<div class="bom-node" style="border-color: #0f172a; padding: 10px; background: white; margin-bottom: 0;">${part.name}</div>`;
                        }
                        // 如果有特徵且是樹狀模式，加一條垂直連結線 (延長到 30px)
                        if (!isGrid && part.features && part.features.length > 0) {
                            html += `<div style="width:2px; height:30px; background:#0f172a; margin: 0 auto; z-index: 10;"></div>`;
                        }
                        localListText += `- ${part.name}<br>`;
                    }

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
                        bridges.sort((a, b) => (a.end - a.start) - (b.end - b.start));

                        const isGrid = layoutClass === 'layout-grid';
                        const ROW_H = 60; // 統一使用 60px 以符合 CSS 的 .bom-feature-row 高度
                        const NODE_BOX_W = isGrid ? 220 : 180; 
                        const GRID_NODE_LEFT_PAD = isGrid ? 20 : 0;
                        const RAIL_START = GRID_NODE_LEFT_PAD + NODE_BOX_W;
                        const COL_GAP = 110; 
                        const BRIDGE_GAP = 85;

                        const boxId = `box-${part.id}`;
                        const drfId = `drf-${part.id}`;

                        if (isGrid) {
                            html += `<div class="bom-grid-border-box" id="${boxId}" style="position: relative; flex: 0 0 auto; display: flex; align-items: center; padding: 20px; overflow: visible;">`;
                            // 提升 SVG 到網格盒子層級，確保能覆蓋零件 DRF 到特徵列表的空間
                            html += `<svg class="bom-svg-layer" id="svg-${boxId}" style="position: absolute; top:0; left:0; width: 100%; height:100%; pointer-events:none; z-index:0; overflow:visible;"></svg>`;
                            html += `<div class="bom-part-metadata" style="flex: 0 0 auto; position: relative; z-index: 10; margin-right: 40px;">
                                        <div class="bom-drf-box" id="${drfId}">${part.name} DRF</div>
                                     </div>`;
                        }

                        const maxIndsCount = Math.max(0, ...part.features.map(f => f.individuals.length));
                        const indBlockW = maxIndsCount * COL_GAP;
                        const bridgeBaseX = RAIL_START + indBlockW + 10;
                        const listH = part.features.length * ROW_H;
                        let minListWidth = 160;
                        if (maxIndsCount > 0 || bridges.length > 0) {
                            minListWidth = bridgeBaseX + bridges.length * BRIDGE_GAP + 60;
                        }

                        let trunkHtml = '';
                        let rowsHtml = '';
                        let railsHtml = '';
                        let bridgesHtml = '';

                        part.features.forEach((f, idx) => {
                            const isFirst = idx === 0;
                            const isLast = idx === part.features.length - 1;
                            const topY = isFirst ? ROW_H / 2 : 0;
                            const height = isLast && !isFirst ? ROW_H / 2 : (isFirst && isLast ? 0 : ROW_H);
                            const leftStyle = isGrid ? 'left: 0;' : 'left: 50%; transform: translateX(-50%);';

                            if (part.features.length > 1) {
                                trunkHtml += `<div style="position:absolute; ${leftStyle} top:${idx * ROW_H + topY}px; width:2px; height:${height}px; background:#0f172a;"></div>`;
                            }
                            if (isGrid && GRID_NODE_LEFT_PAD > 0) {
                                trunkHtml += `<div style="position:absolute; left:0; top:${idx * ROW_H + ROW_H / 2}px; width:${RAIL_START}px; height:2px; background:#0f172a;"></div>`;
                            }
                        });

                        part.features.forEach((f, idx) => {
                            const isLast = idx === part.features.length - 1 ? ' last-feature-row' : '';
                            const nodeId = `node-${part.id}-${f.name}`;
                            const clickAttr = enableContact ? `onclick="toggleContactNode('${nodeId}')"` : '';
                            
                            // [新增] 根據象限上色 (與調配報告色彩對齊)
                            const qColors = {
                                1: '#fee2e2', // Q1 Red (Critical)
                                2: '#dbeafe', // Q2 Blue (Maintain)
                                3: '#ffedd5', // Q3 Orange (Secondary)
                                4: '#dcfce7'  // Q4 Green (Loosen)
                            };
                            const qBorderColors = {
                                1: '#dc2626', 2: '#2563eb', 3: '#d97706', 4: '#16a34a'
                            };
                            const qStyle = f.quadrant ? `background-color: ${qColors[f.quadrant]}; border-color: ${qBorderColors[f.quadrant]}; border-width: 2px;` : '';

                            rowsHtml += `<div class="bom-feature-row${isLast}" id="${nodeId}-row"><div class="bom-feature-node" id="${nodeId}" ${clickAttr} style="${qStyle}">${f.name}</div></div>`;
                            
                            // 只有在 Grid 模式下才解析公差與連線
                            if (isGrid) {
                                const hasInd = f.individuals.length > 0;
                                if (hasInd) {
                                    let indHtml = '';
                                    f.individuals.forEach((t, tIdx) => {
                                        const indId = `ind-${part.id}-${f.name}-${tIdx}`;
                                        indHtml += `<div class="tol-individual-wrapper"><div class="tolerance-bubble tol-individual" id="${indId}"><span class="tol-code">${t}</span></div></div>`;
                                    });
                                    const rTop = idx * ROW_H + ROW_H / 2;
                                    railsHtml += `<div class="tol-rail-container" style="left:${RAIL_START}px; top:${rTop}px; width: auto;">${indHtml}</div>`;
                                }
                            }
                        });

                        if (isGrid) {
                            bridges.forEach((bridge, bIdx) => {
                                // [核心修正] 如果是組裝接觸標籤 (Con-)，我們只記錄連線關係，不產生紫色膠囊
                                if (bridge.tag.startsWith('Con-')) {
                                    const startNode = `node-${part.id}-${part.features[bridge.start].name}`;
                                    const endNode = `node-${part.id}-${part.features[bridge.end].name}`;
                                    if (!contactPairs.some(p => (p.start === startNode && p.end === endNode) || (p.end === startNode && p.start === endNode))) {
                                        contactPairs.push({ start: startNode, end: endNode });
                                    }
                                    return;
                                }

                                const lineX = bridgeBaseX + bIdx * BRIDGE_GAP;
                                const capsuleCY = (bridge.start * ROW_H + bridge.end * ROW_H + ROW_H) / 2;
                                const bridgeId = `bridge-${part.id}-${bIdx}`;
                                bridgesHtml += `<div class="tol-interactive-wrapper" id="${bridgeId}" style="left:${lineX}px; top:${capsuleCY}px;"><div class="tolerance-bubble tol-interactive"><span class="tol-code">${bridge.tag}</span></div></div>`;
                            });
                        }

                        bomNetworks.push({
                            partId: part.id, drfId: drfId, boxId: boxId,
                            features: part.features.map(f => `node-${part.id}-${f.name}`),
                            bridges: bridges.map((b, bIdx) => {
                                const realLineX = bridgeBaseX + bIdx * BRIDGE_GAP;
                                return { id: `bridge-${part.id}-${bIdx}`, startIdx: b.start, endIdx: b.end, xOffset: realLineX };
                            }),
                            rowH: ROW_H
                        });

                        const listMargin = isGrid ? 'margin-right: 20px;' : 'margin: 0 auto;';
                        if (isGrid) {
                            html += `<div class="bom-features-list" style="position: relative; flex: 0 0 auto; width:${minListWidth}px; min-width:${minListWidth}px; ${listMargin} height:${listH}px;">
                                        <div class="rows-layer"><div class="bom-tree-trunk">${trunkHtml}</div>${rowsHtml}</div>
                                        <div class="rails-layer" style="position: absolute; inset: 0; pointer-events: none; z-index: 5;">${railsHtml}</div>
                                        <div class="bridges-layer" style="position: absolute; inset: 0; pointer-events: none; z-index: 20;">${bridgesHtml}</div>
                                     </div>`;
                        } else {
                            // 樹狀模式：「垂直鏈條層級」
                            const treeTrunkH = (part.features.length - 1) * ROW_H;
                            // [核心修正] 讓主幹線從頂部 (top:0) 開始畫，並延伸到最後一個特徵面的中心
                            const treeTrunkHtml = part.features.length > 1 ? `<div style="position:absolute; left:50%; top:-10px; width:2px; height:${treeTrunkH + ROW_H/2 + 10}px; background:#0f172a; transform:translateX(-50%); z-index:0;"></div>` : '';
                            
                            html += `<div class="bom-features-list tree-view" style="position: relative; margin-top: 10px; min-width: ${NODE_BOX_W}px; width:100%; display:flex; flex-direction:column; align-items:center;">
                                        <div class="rows-layer" style="position:relative; width:100%; display:flex; flex-direction:column; align-items:center;">
                                            ${treeTrunkHtml}
                                            ${rowsHtml}
                                        </div>
                                     </div>`;
                        }
                        if (isGrid) html += `</div>`;
                    }

                    if (part.children && part.children.length > 0) {
                        html += `<div class="bom-children">`;
                        part.children.forEach(child => {
                            const childRes = renderPartNode(child);
                            html += childRes.html;
                            localListText += childRes.listText;
                        });
                        html += `</div>`;
                    }
                    html += `</div>`;
                    return { html: html, listText: localListText };
                }

                let sortedListText = '';
                if (parts.length === 1) {
                    const res = renderPartNode(parts[0], true);
                    treeHtml += res.html;
                    sortedListText += res.listText;
                } else {
                    treeHtml += `<div class="bom-child"><div class="bom-node root-node" id="node-root" style="border-color: #0f172a; font-weight: bold; background: #e2e8f0; font-size: 1.1rem; padding: 15px;">${assemblyName}</div><div class="bom-children">`;
                    parts.forEach(part => {
                        const res = renderPartNode(part);
                        treeHtml += res.html;
                        sortedListText += res.listText;
                    });
                    treeHtml += `</div></div>`;
                }

                treeHtml += `</div></div></div>`;

                const reAnalyzeMsg = (window.CURRENT_LANG === 'en') ? 
            'Please click "Tolerance Analysis" in the editor to see the updated path error.' : 
            '請點擊編輯器中的「執行公差分析」以查看更新後的路徑誤差。';
                const utf8Topology = encodeURIComponent(JSON.stringify(bomNetworks));
                const b64Topology = btoa(utf8Topology);
                const encodedTree = encodeURIComponent(treeHtml).replace(/'/g, "%27");

                let mainBtnClass = "open-bom-btn";
                let mainBtnLabel = (layoutClass === 'layout-grid') ? (window.CURRENT_LANG === 'en' ? "🔍 View Tolerance Network" : "🔍 查看公差網路圖") : (window.CURRENT_LANG === 'en' ? "🔍 View Product Structure" : "🔍 查看產品架構圖");

                if (enableContact) {
                    mainBtnClass = "open-bom-btn";
                    mainBtnLabel = (window.CURRENT_LANG === 'en') ? "🟢 Open Hard Contact Interface" : "🟢 開啟硬接觸連線介面";
                }

                // 恢復原本只顯示按鈕和清單的佈局，不將胖重的 SVG 樹塞進對話記錄
                finalHtml += `${sortedListText}<br><button class="${mainBtnClass}" onclick="openBomModal(decodeURIComponent('${encodedTree}'), '${b64Topology}')">${mainBtnLabel}</button>`;
                
                if (enableEdit) {
                    const encodedParts = encodeURIComponent(JSON.stringify(parts)).replace(/'/g, "%27");
                    const editBtnLabel = (window.CURRENT_LANG === 'en') ? "✏️ Edit Tolerance Path" : "✏️ 編輯公差路徑";
                    finalHtml += `<button class="open-editor-btn" onclick="openEditorModal(decodeURIComponent('${encodedParts}'))">${editBtnLabel}</button>`;
                }
            } else {
                const errorLabel = window.CURRENT_LANG === 'en' ? '(Failed to parse structure, keeping text output)' : '(解析產品結構圖失敗，維持文字輸出)';
                finalHtml += `<div style="color:gray;">${errorLabel}</div><br>${match[1].trim().replace(/\n/g, '<br>')}`;
            }

            lastIndex = match.index + match[0].length;
        }

        finalHtml += formatted.substring(lastIndex);
        bubbleElement.innerHTML = finalHtml;
        
    } catch (err) {
        console.error("Error rendering BOM Tree:", err);
        bubbleElement.innerHTML = text.split('\n').join('<br>') + `<br><div style="color:red; margin-top:10px;">[SVG Render Error] ${err.message}</div>`;
    }
}

/**
 * [新功能] 直接將解析後的結構渲染到容器 (例如左側面板)
 * 實現「問 A 答 A 並同步畫 A」的需求
 */
// 輔助函式：穩健地從 onclick 字串中提取屬性
function _extractEncodedParam(onclickStr) {
    if (!onclickStr) return null;
    try {
        // 使用正則表達式精確匹配 decodeURIComponent('...') 括號內的內容
        const match = onclickStr.match(/decodeURIComponent\('([^']*)'\)/);
        if (match && match[1]) {
            return decodeURIComponent(match[1]);
        }
        return null;
    } catch(e) {
        console.error("Param extraction failed:", e);
        return null;
    }
}

function renderStructureDirectly(dsl, container, intent) {
    if (!container) return;
    
    // 1. 使用現有的解析邏輯產生 HTML
    const tempEl = document.createElement('div');
    renderCustomBomTree(dsl, tempEl, intent);
    
    // 2. 提取解析後的內容與拓譜資料
    // 優先尋找符合意圖的按鈕
    let btn = null;
    if (intent && intent.edit) {
        btn = tempEl.querySelector('.open-editor-btn');
    }
    if (!btn) {
        btn = tempEl.querySelector('.open-bom-btn, .open-editor-btn');
    }
    
    if (!btn) {
        // 如果連按鈕都沒有，直接注入原始 HTML 並返回
        container.innerHTML = tempEl.innerHTML;
        return null;
    }
    
    const onclickStr = btn.getAttribute('onclick') || '';
    const paramData = _extractEncodedParam(onclickStr);
    
    // 情境 A：如果是編輯路徑按鈕
    if (btn.classList.contains('open-editor-btn')) {
        if (intent && intent.edit) {
            // [編輯模式] 靜默解析，直接返回資料給 chat.js
            return { treeHtml: '', b64Topology: '', partsJson: paramData, isEdit: true };
        }
    }

    // 情境 B：如果是 BOM 網路圖按鈕
    if (btn.classList.contains('open-bom-btn')) {
        const treeHtml = paramData;
        const b64Match = onclickStr.match(/,\s*'([^']*)'\)/);
        const b64Topology = b64Match ? b64Match[1] : '';
        
        // 更新全域網路拓譜資料
        if (b64Topology) {
            try { 
                const decoded = JSON.parse(decodeURIComponent(atob(b64Topology)));
                window.bomNetworks = decoded;
            } catch(e) { window.bomNetworks = []; }
        }

        // 如果雖然是 BOM 按鈕但意圖是編輯，一樣採靜默模式
        if (intent && intent.edit) {
            return { treeHtml, b64Topology, partsJson: '', isEdit: true };
        }
        
        // 快照此時的 contactPairs（由 renderCustomBomTree 解析 DSL 填入）
        const snapshotPairs = (contactPairs && contactPairs.length > 0) ? JSON.parse(JSON.stringify(contactPairs)) : [];

        // [正常模式] 注入 HTML 到容器
        container.innerHTML = treeHtml;

        // 5. 執行繪圖 (非同步以確保 DOM 已完成渲染)
        setTimeout(() => {
            window.__bomActiveDrawingRoot = container;
            container._localContactPairs = snapshotPairs;

            const localSvg = container.querySelector('#contact-lines-svg');
            if (localSvg) {
                drawContactLines(container, container._localContactPairs);
            }

            drawAllBomNetworks(window.__bomActiveDrawingRoot);
            container.scrollTop = 0;

            if (container.id === 'graph-container' || container.classList.contains('bom-container')) {
                if (_bomResizeObserver) _bomResizeObserver.disconnect();
                _bomResizeObserver = new ResizeObserver(() => {
                    drawAllBomNetworks(container);
                    const activeSvg = container.querySelector('#contact-lines-svg');
                    if (activeSvg) {
                        drawContactLines(container, container._localContactPairs);
                    }
                });
                _bomResizeObserver.observe(container);
            }
        }, 200);

        return { treeHtml, b64Topology, snapshotPairs };
    }
    return null;
}

function openBomModal(treeHtml, b64Topology, preloadedPairs) {
    const modalContainer = document.getElementById('bom-modal-container');
    modalContainer.innerHTML = treeHtml;
    document.getElementById('bom-modal-overlay').style.display = 'flex';
    window.__bomActiveDrawingRoot = modalContainer;
    selectedContactNode = null;

    // 若傳入預載的接觸配對（來自 DSL 解析快照），直接使用；否則清空再由 matingConstraints 補
    if (preloadedPairs && preloadedPairs.length > 0) {
        contactPairs = preloadedPairs;
    } else {
        contactPairs = [];
    }

    if (b64Topology) {
        try { window.bomNetworks = JSON.parse(decodeURIComponent(atob(b64Topology))); }
        catch (e) { window.bomNetworks = []; }
    } else { window.bomNetworks = []; }

    autoPopulateMatingLines(window.__bomActiveDrawingRoot);

    setTimeout(() => {
        if (modalContainer.querySelector('#contact-lines-svg')) drawContactLines(window.__bomActiveDrawingRoot);
        drawAllBomNetworks(window.__bomActiveDrawingRoot);
    }, 100);

    const modalContent = document.querySelector('.bom-modal-content');
    if (modalContent) {
        if (_bomScrollEl) _bomScrollEl.removeEventListener('scroll', _bomScrollHandler);
        _bomScrollEl = modalContent;
        _bomScrollEl.addEventListener('scroll', _bomScrollHandler, { passive: true });
    }
    attachBomObservers(modalContainer);
}

function closeBomModal() {
    document.getElementById('bom-modal-overlay').style.display = 'none';
    // [核心修正] 不再清空全域 contactPairs，以免影響左側圖框的顯示
    // contactPairs = []; 
    selectedContactNode = null;
    window.bomNetworks = [];
    window.__bomActiveDrawingRoot = document.getElementById('graph-container') || document;
}

function autoPopulateMatingLines(root = (window.__bomActiveDrawingRoot || document)) {
    if (!window.matingConstraints || window.matingConstraints.length === 0) return;
    window.matingConstraints.forEach(pair => {
        const [s, o] = pair;
        const sPartId = s.split('-')[0];
        const oPartId = o.split('-')[0];
        const sNodeId = `node-${sPartId}-${s}`;
        const oNodeId = `node-${oPartId}-${o}`;

        const elS = root === document ? document.getElementById(sNodeId) : root.querySelector('#' + sNodeId);
        const elO = root === document ? document.getElementById(oNodeId) : root.querySelector('#' + oNodeId);

        if (elS && elO) {
            const exists = contactPairs.some(p => (p.start === sNodeId && p.end === oNodeId) || (p.end === sNodeId && p.start === oNodeId));
            if (!exists) contactPairs.push({ start: sNodeId, end: oNodeId });
        }
    });
}

function _bomScrollHandler() {
    if (contactPairs.length > 0) drawContactLines(window.__bomActiveDrawingRoot);
    drawAllBomNetworks(window.__bomActiveDrawingRoot);
}

function attachBomObservers(root = document) {
    const wrapper = root === document ? document.getElementById('bom-tree-wrapper') : root.querySelector('#bom-tree-wrapper');
    if (!wrapper) return;
    if (_bomResizeObserver) _bomResizeObserver.disconnect();
    _bomResizeObserver = new ResizeObserver(() => {
        if (contactPairs.length > 0) drawContactLines(window.__bomActiveDrawingRoot);
        drawAllBomNetworks(window.__bomActiveDrawingRoot);
    });
    _bomResizeObserver.observe(wrapper);

    // 同時監聽彈窗容器本身（視窗 resize 會讓彈窗重排）
    const modalContent = document.querySelector('.bom-modal-content');
    if (modalContent) _bomResizeObserver.observe(modalContent);
}

function window_bomNetworks_clear() {
    window.bomNetworks = [];
}

function drawAllBomNetworks(root = (window.__bomActiveDrawingRoot || document)) {
    if (!window.bomNetworks) return;
    window.bomNetworks.forEach(net => {
        const svg = root === document ? document.getElementById('svg-' + net.boxId) : root.querySelector('#svg-' + net.boxId);
        if (!svg) return;
        const svgRect = svg.getBoundingClientRect();
        const parentRect = svg.parentElement.getBoundingClientRect();

        svg.setAttribute('width', parentRect.width);
        svg.setAttribute('height', parentRect.height);
        svg.setAttribute('viewBox', `0 0 ${parentRect.width} ${parentRect.height}`);

        let pathD = '';
        const getRelRect = (elId) => {
            const el = root === document ? document.getElementById(elId) : root.querySelector('#' + elId);
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return { left: r.left - svgRect.left, right: r.right - svgRect.left, top: r.top - svgRect.top, bottom: r.bottom - svgRect.top, cx: (r.left + r.width / 2) - svgRect.left, cy: (r.top + r.height / 2) - svgRect.top, width: r.width, height: r.height, el: el };
        };

        let trunkX = 0;
        let rowsData = [];
        net.features.forEach((fId, idx) => {
            const rNode = getRelRect(fId);
            const rRow = getRelRect(fId + '-row');
            if (rNode && rRow) {
                trunkX = Math.round(rNode.left - 30);
                rowsData.push({ idx: idx, id: fId, y: Math.round(rRow.cy), x: Math.round(rNode.left), nodeRect: rNode });
            }
        });

        const rDrf = getRelRect(net.drfId);
        if (rDrf && rowsData.length > 0) {
            const drfRight = Math.round(rDrf.right);
            const drfCy = Math.round(rDrf.cy);
            pathD += `M ${drfRight} ${drfCy} L ${trunkX} ${drfCy} `;
            if (rowsData.length > 1) {
                const minY = Math.min(drfCy, rowsData[0].y);
                const maxY = Math.max(drfCy, rowsData[rowsData.length - 1].y);
                pathD += `M ${trunkX} ${minY} L ${trunkX} ${maxY} `;
            } else if (rowsData.length === 1 && drfCy !== rowsData[0].y) {
                pathD += `M ${trunkX} ${drfCy} L ${trunkX} ${rowsData[0].y} `;
            }
            rowsData.forEach(r => pathD += `M ${trunkX} ${r.y} L ${r.x} ${r.y} `);
        }

        let bridgeCapsules = [];
        net.bridges.forEach(b => {
            const rCap = getRelRect(b.id);
            if (rCap) bridgeCapsules.push({ ...b, x: Math.round(rCap.cx), leftEdge: Math.round(rCap.left - 4), rightEdge: Math.round(rCap.right + 4) });
        });

        rowsData.forEach(row => {
            let maxBridgeX = 0;
            let activeBridges = bridgeCapsules.filter(b => b.startIdx === row.idx || b.endIdx === row.idx);
            if (activeBridges.length > 0) maxBridgeX = Math.max(...activeBridges.map(b => b.x));

            let hasIndividuals = false;
            let indFarRightCx = row.nodeRect.right;
            let indHtmlIdx = 0;
            const prefix = `node-${net.partId}-`;
            const fName = row.id.startsWith(prefix) ? row.id.substring(prefix.length) : row.id.split('-').pop();

            while (true) {
                const rInd = getRelRect(`ind-${net.partId}-${fName}-${indHtmlIdx}`);
                if (!rInd) break;
                hasIndividuals = true;
                indFarRightCx = Math.max(indFarRightCx, Math.round(rInd.cx));
                indHtmlIdx++;
            }

            if (maxBridgeX > 0 || hasIndividuals) {
                let endX = Math.round(Math.max(indFarRightCx, maxBridgeX));
                let startX = Math.round(row.nodeRect.right);
                let rowY = Math.round(row.y);
                if (endX < startX + 40) endX = startX + 40;
                pathD += `M ${startX} ${rowY} L ${endX} ${rowY} `;
            }
        });

        bridgeCapsules.forEach(b => {
            const startRow = rowsData.find(r => r.idx === b.startIdx);
            const endRow = rowsData.find(r => r.idx === b.endIdx);
            if (startRow && endRow) {
                const startY = Math.round(startRow.y) + 1;
                const endY = Math.round(endRow.y) - 1;
                pathD += `M ${b.x} ${startY} L ${b.x} ${endY} `;
            }
        });

        svg.innerHTML = `<path d="${pathD}" stroke="#0f172a" stroke-width="2" fill="none" stroke-linejoin="miter" stroke-linecap="butt" />`;
    });
}

function toggleContactNode(nodeId) {
    const el = document.getElementById(nodeId);
    if (!el) return;

    if (selectedContactNode === nodeId) {
        el.classList.remove('contact-selected');
        selectedContactNode = null;
    } else if (!selectedContactNode) {
        el.classList.add('contact-selected');
        selectedContactNode = nodeId;
    } else {
        const firstEl = document.getElementById(selectedContactNode);
        if (firstEl) firstEl.classList.remove('contact-selected');

        const exists = contactPairs.some(p => (p.start === selectedContactNode && p.end === nodeId) || (p.end === selectedContactNode && p.start === nodeId));
        if (!exists && selectedContactNode !== nodeId) {
            contactPairs.push({ start: selectedContactNode, end: nodeId });
            drawContactLines();
        }
        selectedContactNode = null;
    }
}

function drawContactLines(root = (window.__bomActiveDrawingRoot || document), dataOverride = null) {
    // 解決 ID 衝突：不要用 document.getElementById，而是從當前根節點向下查找
    const isDoc = (root === document);
    const svg = isDoc ? document.getElementById('contact-lines-svg') : root.querySelector('.contact-lines-svg, #contact-lines-svg');
    const wrapper = isDoc ? document.getElementById('bom-tree-wrapper') : root.querySelector('.bom-tree-canvas, #bom-tree-wrapper');
    
    if (!svg || !wrapper) return;

    // [核心修正] 強制同步 SVG 畫布尺寸，確保座標系統在 Resize 後與父容器完全一致
    const parentNode = svg.parentElement;
    const pW = parentNode.clientWidth || parentNode.offsetWidth;
    const pH = parentNode.clientHeight || parentNode.offsetHeight;
    
    // 如果寬度為 0 (可能剛載入尚未 Reflow)，則在 150ms 後重試一次，避免線條「消失」
    if (pW <= 0 && !root._bomRetryDraw) {
        root._bomRetryDraw = true;
        setTimeout(() => {
            root._bomRetryDraw = false;
            drawContactLines(root, dataOverride);
        }, 150);
        return;
    }

    if (pW > 0 && pH > 0) {
        svg.setAttribute('width', pW);
        svg.setAttribute('height', pH);
        svg.setAttribute('viewBox', `0 0 ${pW} ${pH}`);
    }

    svg.innerHTML = '';
    const svgRect = svg.getBoundingClientRect();
    // 如果畫布寬度為 0 且沒法重試了，才放棄渲染
    if (svgRect.width === 0 || svgRect.height === 0) return;

    // 優先使用傳入的數據 (dataOverride)，否則使用 root 底下的備份數據，最後才回退到全域
    const activePairs = dataOverride || root._localContactPairs || contactPairs;

    activePairs.forEach((pair, idx) => {
        // 使用屬性選擇器 [id="..."] 來避開 CSS 不支援數位開頭 ID (#1-P-1) 的問題
        const el1 = root.querySelector(`[id="${pair.start}"]`) || document.getElementById(pair.start);
        const el2 = root.querySelector(`[id="${pair.end}"]`) || document.getElementById(pair.end);
        if (!el1 || !el2) return;

        const r1 = el1.getBoundingClientRect();
        const r2 = el2.getBoundingClientRect();

        // 數學上最穩定的座標：直接相對於當前 SVG 畫布
        const x1 = r1.left - svgRect.left;
        const y1 = (r1.top + r1.height / 2) - svgRect.top;
        const x2 = r2.left - svgRect.left;
        const y2 = (r2.top + r2.height / 2) - svgRect.top;

        const verticalDist = Math.abs(y2 - y1);
        const bowAmount = Math.min(x1 * 0.8, Math.max(30, verticalDist * 0.3)); // 縮小彎曲，避免過長的水平伸展

        const cx1 = x1 - bowAmount, cy1 = y1 + (y2 - y1) * 0.1; 
        const cx2 = x2 - bowAmount, cy2 = y2 - (y2 - y1) * 0.1; 
        const pathData = `M ${x1} ${y1} C ${cx1} ${cy1}, ${cx2} ${cy2}, ${x2} ${y2}`;

        const line = document.createElementNS('http://www.w3.org/2000/svg', 'path');
        line.setAttribute('d', pathData);
        line.setAttribute('fill', 'none');
        line.setAttribute('stroke', '#22c55e');
        line.setAttribute('stroke-width', '4');
        line.setAttribute('stroke-linecap', 'round');
        line.setAttribute('style', 'pointer-events: auto; cursor: pointer; opacity: 0.8;');

        const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
        title.textContent = window.CURRENT_LANG === 'en' ? 'Double-click to remove' : '雙擊移除接觸線';
        line.appendChild(title);

        line.ondblclick = () => {
            activePairs.splice(idx, 1);
            drawContactLines(root, activePairs);
        };
        svg.appendChild(line);
    });
}

function clearAllContactLines() {
    const confirmMsg = window.CURRENT_LANG === 'en' ? "Are you sure you want to clear all contact lines?" : "確定要清除所有接觸線嗎？";
    if (confirm(confirmMsg)) {
        contactPairs = [];
        selectedContactNode = null;
        document.querySelectorAll('.bom-feature-node.contact-selected').forEach(el => el.classList.remove('contact-selected'));
        drawContactLines();
    }
}

window.addEventListener('resize', () => {
    const root = window.__bomActiveDrawingRoot || document;
    const modalOpen = document.getElementById('bom-modal-overlay').style.display === 'flex';
    if (modalOpen || root !== document) {
        if (contactPairs.length > 0) drawContactLines(root);
        drawAllBomNetworks(root);
    }
}, { passive: true });

function openEditorModal(partsJsonStr) {
    try {
        // [修正] 如果目前已有數據 (例如剛匯入 Excel)，提示使用者是否要覆蓋
        if (editorPathData && editorPathData.length > 0) {
            const confirmOverwrite = window.CURRENT_LANG === 'en' ? 
                "You have existing path data (possibly imported). Overwrite with default features?" : 
                "目前已有路徑數據（可能是匯入的）。是否要以預設特徵覆蓋？";
            if (!confirm(confirmOverwrite)) {
                // 不覆蓋，直接顯示現有數據
                renderEditorList();
                document.getElementById('editor-modal-overlay').style.display = 'flex';
                return;
            }
        }

        const parts = JSON.parse(partsJsonStr);
        editorPathData = [];
        const seenKeys = new Set();
        parts.forEach(part => {
            if (part.features) {
                part.features.forEach(f => {
                    const allTols = [...f.individuals, ...f.interactives];
                    // [核心修正] 只推送公差項，不再顯示基礎特徵名稱 (避免 1-P-1 等項目干擾)
                    if (allTols.length > 0) {
                        allTols.forEach(tol => {
                            const key = `${part.name}||${tol}`;
                            if (seenKeys.has(key)) return; // 跳過重複的 (同零件+同公差名)
                            seenKeys.add(key);
                            editorPathData.push({
                                type: 'feature',
                                name: tol,
                                val: 0.01,
                                bias: 0,
                                dist: 1,
                                part: part.name,
                                nominal_size: null,
                                it_grade: null
                            });
                        });
                    }
                    // 移除 else 分支，不再填補基礎特徵
                });
            }
        });
        renderEditorList();
        document.getElementById('editor-modal-overlay').style.display = 'flex';
    } catch (e) {
        alert(window.CURRENT_LANG === 'en' ? "Failed to parse data, cannot open editor" : "資料解析失敗，無法開啟編輯器");
    }
}

function closeEditorModal() {
    document.getElementById('editor-modal-overlay').style.display = 'none';
}

/**
 * 匯入 Excel 檔案並更新編輯器路徑數據
 * @param {HTMLInputElement} input 
 */
async function uploadExcelPath(input) {
    if (!input.files || input.files.length === 0) return;
    
    const file = input.files[0];
    const formData = new FormData();
    formData.append('file', file);
    
    const loadingMsg = window.CURRENT_LANG === 'en' ? "Importing Excel..." : "正在匯入 Excel...";
    console.log("[INFO]", loadingMsg);
    
    try {
        const resp = await fetch('/api/import_excel', {
            method: 'POST',
            body: formData
        });
        
        let data;
        try {
            data = await resp.json();
        } catch (je) {
            throw new Error(window.CURRENT_LANG === 'en' ? "Server response error" : "伺服器回應格式錯誤");
        }
        
        if (!resp.ok || data.error) {
            throw new Error(data.error || (window.CURRENT_LANG === 'en' ? "Unknown server error" : "未知的伺服器錯誤"));
        }

        if (data.pathData) {
            // 更新全域數據並重新渲染
            editorPathData = data.pathData.map(item => ({
                ...item,
                bias: item.bias || 0,
                dist: item.dist || 1
            }));
            renderEditorList();
            // [同步] 匯入成功後立即更新左側圖框
            renderPathFlowchart();
            
            const successMsg = window.CURRENT_LANG === 'en' ? "Excel path imported successfully!" : "Excel 路徑匯入成功！";
            console.log("[INFO]", successMsg);
            alert(successMsg);
        }
    } catch (e) {
        console.error("Import failed:", e);
        alert(e.message);
    } finally {
        input.value = ''; 
    }
}

function openAnalysisModal() {
    document.getElementById('analysis-modal-overlay').style.display = 'flex';
}

function closeAnalysisModal() {
    document.getElementById('analysis-modal-overlay').style.display = 'none';
}

function openAllocationModal() {
    document.getElementById('allocation-modal-overlay').style.display = 'flex';
}

function closeAllocationModal() {
    document.getElementById('allocation-modal-overlay').style.display = 'none';
}

function exportToLeftPanel() {
    closeEditorModal();
    renderPathFlowchart();
}

function renderPathFlowchart() {
    const container = document.getElementById('graph-container');
    if (!editorPathData || editorPathData.length === 0) {
        container.innerHTML = '<div class="graph-empty-state">目前公差路徑為空</div>';
        return;
    }
    
    let html = `<div style="padding: 20px; width: 100%; height: 100%; overflow: auto; background: #f8fafc; box-sizing: border-box;">
        <h3 style="margin-top: 0; margin-bottom: 20px; color: #1e293b; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px; text-align: center;">
            ${window.CURRENT_LANG === 'en' ? 'Tolerance Path Flowchart' : '公差路徑流程圖'}
        </h3>
        <div style="display: flex; flex-direction: column; align-items: center; gap: 10px;">`;

    editorPathData.forEach((node, idx) => {
        const isFeat = node.type === 'feature';
        const bgColor = isFeat ? '#eff6ff' : '#f0fdf4';
        const borderColor = isFeat ? '#3b82f6' : '#22c55e';
        const titleColor = isFeat ? '#1d4ed8' : '#15803d';
        
        const title = isFeat ? `${node.name} <span style="font-size:0.8rem;color:#64748b;">(${node.part || ''})</span>` : `${node.axis}`;
        
        html += `
        <div style="width: 280px; background: ${bgColor}; border: 2px solid ${borderColor}; border-radius: 8px; padding: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
            <div style="font-weight: bold; font-size: 1.1rem; color: ${titleColor}; margin-bottom: 8px; text-align: center;">
                ${title}
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 5px; text-align: center; font-size: 0.85rem; color: #475569;">
                <div><div style="color:#94a3b8;font-size:0.7rem;">Val</div><b>${node.val ?? 0}</b></div>
                <div><div style="color:#94a3b8;font-size:0.7rem;">Bias</div><b>${node.bias ?? 0}</b></div>
                <div><div style="color:#94a3b8;font-size:0.7rem;">Dist</div><b>${node.dist ?? 1}</b></div>
            </div>
        </div>
        `;
        
        if (idx < editorPathData.length - 1) {
            html += `<div style="width: 2px; height: 15px; background: #cbd5e1;"></div>`;
            html += `<div style="width: 0; height: 0; border-left: 6px solid transparent; border-right: 6px solid transparent; border-top: 8px solid #cbd5e1; margin-top: -2px;"></div>`;
        }
    });

    html += `</div></div>`;
    container.innerHTML = html;
}

function renderEditorList() {
    const container = document.getElementById('editor-list-container');
    let html = `<table class="editor-table">
      <thead><tr><th style="width:32px;"></th>
          <th>${window.CURRENT_LANG === 'en' ? 'A Path Code' : 'A 路徑代碼'}</th>
          <th>${window.CURRENT_LANG === 'en' ? 'E Nominal' : 'E 公稱尺寸'}</th>
          <th>${window.CURRENT_LANG === 'en' ? 'F IT Grade' : 'F IT 等級'}</th>
          <th>${window.CURRENT_LANG === 'en' ? 'B Value<br><span style="font-weight:normal;font-size:0.72rem;color:#64748b">(tra/rot/tol)</span>' : 'B 數值<br><span style="font-weight:normal;font-size:0.72rem;color:#64748b">（平移/旋轉/公差值）</span>'}</th>
          <th>${window.CURRENT_LANG === 'en' ? 'C Bias' : 'C 偏差值'}</th>
          <th>${window.CURRENT_LANG === 'en' ? 'D Ang Tol' : 'D 角度公差'}</th>
          <th style="width:60px;"></th></tr></thead><tbody>`;

    editorPathData.forEach((node, idx) => {
        const isFeat = node.type === 'feature';
        const rowClass = isFeat ? 'row-feature' : 'row-spatial';
        const colA = isFeat ? `<td class="cell-code feat">${node.name}<br><span class="cell-part">${node.part || ''}</span></td>`
            : `<td class="cell-code spatial"><input list="axis-list-${idx}" value="${node.axis || ''}" oninput="editorPathData[${idx}].axis=this.value; renderPathFlowchart();" class="axis-input" placeholder="traZ…"><datalist id="axis-list-${idx}">${['traX', 'traY', 'traZ', 'rotX', 'rotY', 'rotZ', 'cy1', 'co1', 'AngX', 'AngY', 'AngZ', 'PerX', 'PerY', 'PerZ'].map(ax => `<option value="${ax}">`).join('')}</datalist></td>`;
        
        const colE = `<td><input type="number" step="0.1" value="${node.nominal_size ?? ''}" oninput="updateNominal(${idx}, this.value)" class="cell-input" placeholder="-"></td>`;
        const colF = `<td><input type="text" value="${node.it_grade ?? ''}" oninput="updateITGrade(${idx}, this.value)" class="cell-input" placeholder="e.g. IT7"></td>`;
        
        const colB = `<td><input type="number" step="0.001" value="${node.val ?? 0}" oninput="editorPathData[${idx}].val=parseFloat(this.value)||0; renderPathFlowchart();" class="cell-input"></td>`;
        const colC = `<td><input type="number" step="0.001" value="${node.bias ?? 0}" oninput="editorPathData[${idx}].bias=parseFloat(this.value)||0; renderPathFlowchart();" class="cell-input"></td>`;
        const colD = `<td><input type="number" step="1" value="${node.dist ?? 1}" oninput="editorPathData[${idx}].dist=parseFloat(this.value)||1; renderPathFlowchart();" class="cell-input" placeholder="1"></td>`;

        html += `<tr class="${rowClass}"><td class="cell-drag">⠿</td>${colA}${colE}${colF}${colB}${colC}${colD}<td><button class="btn-remove-row" onclick="removeNode(${idx})">✕</button></td></tr>
             <tr class="row-insert"><td colspan="8"><button class="btn-insert" onclick="addSpatialNode(${idx + 1})">${window.CURRENT_LANG === 'en' ? '+ Insert tra/rot' : '＋ 插入 tra/rot'}</button></td></tr>`;
    });
    html += `</tbody></table>`;
    container.innerHTML = html;
}

function addSpatialNode(index) {
    editorPathData.splice(index, 0, { type: 'spatial', axis: 'traZ', val: 0.0, bias: 0, dist: 1 });
    renderEditorList();
}

function removeNode(index) {
    editorPathData.splice(index, 1);
    renderEditorList();
}

async function updateNominal(idx, val) {
    editorPathData[idx].nominal_size = parseFloat(val) || null;
    await triggerISOLookup(idx);
    renderPathFlowchart();
}

async function updateITGrade(idx, val) {
    editorPathData[idx].it_grade = val.trim() || null;
    await triggerISOLookup(idx);
    renderPathFlowchart();
}

async function triggerISOLookup(idx) {
    const item = editorPathData[idx];
    if (!item.nominal_size || !item.it_grade) return;
    
    const gradeRaw = item.it_grade.trim();
    const size = item.nominal_size;
    
    let url = '/api/lookup/tolerance';
    let body = { size_mm: size, it_grade: gradeRaw.toUpperCase() };

    // Regex to match Hole (H7) or Shaft (h6)
    const holeMatch = gradeRaw.match(/^([A-Z]{1,2})(\d+)$/);
    const shaftMatch = gradeRaw.match(/^([a-z]{1,2})(\d+)$/);

    if (holeMatch) {
        url = '/api/lookup/hole';
        body = { size_mm: size, tolerance_code: holeMatch[1], it_grade: 'IT' + holeMatch[2] };
    } else if (shaftMatch) {
        url = '/api/lookup/shaft';
        body = { size_mm: size, tolerance_code: shaftMatch[1], it_grade: 'IT' + shaftMatch[2] };
    }

    try {
        const resp = await fetch(url, { 
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body) 
        });
        const res = await resp.json();
        
        if (res.ok) {
            if (res.tolerance_μm !== undefined) {
                editorPathData[idx].val = res.tolerance_μm / 1000.0;
                editorPathData[idx].bias = 0;
            } else if (res.upper_dev_um !== undefined && res.lower_dev_um !== undefined) {
                const tol_um = Math.abs(res.upper_dev_um - res.lower_dev_um);
                editorPathData[idx].val = tol_um / 1000.0;
                editorPathData[idx].bias = (res.upper_dev_um + res.lower_dev_um) / 2000.0;
            }
            
            // Re-render only the inputs to avoid focus loss if possible, 
            // but for simplicity we re-render the whole list.
            const table = document.getElementById('editor-list-container');
            const scrollPos = table.scrollTop;
            renderEditorList();
            document.getElementById('editor-list-container').scrollTop = scrollPos;
        }
    } catch (e) {
        console.error("ISO Lookup Error:", e);
    }
}

async function exportCSV() {
    const btn = document.querySelector('.btn-export');
    const originalText = btn.textContent;
    btn.textContent = window.CURRENT_LANG === 'en' ? "⏳ Generating CSV..." : "⏳ 產生 CSV 中...";
    btn.disabled = true;
    try {
        const res = await fetch('/api/export_tolerance_csv', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pathData: editorPathData, lang: window.CURRENT_LANG }) });
        if (!res.ok) throw new Error("Export failed");
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none'; a.href = url; a.download = "Tolerance_Path_Export.csv";
        document.body.appendChild(a); a.click(); document.body.removeChild(a); window.URL.revokeObjectURL(url);
        alert(window.CURRENT_LANG === 'en' ? "[SUCCESS] CSV file downloaded!" : "[SUCCESS] CSV 檔案下載成功！");
    } catch (e) {
        alert(window.CURRENT_LANG === 'en' ? "[ERROR] Export failed: " + e.message : "[ERROR] 匯出失敗: " + e.message);
    } finally {
        btn.textContent = originalText; btn.disabled = false;
    }
}

function runDeepAnalysis() {
    if (!editorPathData || editorPathData.length === 0) {
        alert(window.CURRENT_LANG === 'en' ? 'No path data to analyze.' : '路徑資料為空，請先開啟公差路徑編輯器。');
        return;
    }
    
    console.log("[DEBUG] Sending path data to analysis, items count:", editorPathData.length);

    const btn      = document.getElementById('btn-deep-analyze');
    const wrap     = document.getElementById('analyze-progress-wrap');
    const bar      = document.getElementById('analyze-progress-bar');
    const label    = document.getElementById('analyze-progress-label');
    const statusBox = document.getElementById('analysis-status-box');
    const initLabel = window.CURRENT_LANG === 'en' ? 'Computing Jacobian...' : '正在計算 Jacobian 矩陣...';

    if (btn) btn.disabled    = true;
    if (wrap) wrap.classList.remove('hidden-by-default');
    if (bar) bar.style.width    = '0%';
    if (label) label.textContent  = initLabel;
    
    if (statusBox) {
        statusBox.textContent = window.CURRENT_LANG === 'en' ? 'Analyzing...' : '分析中...';
        statusBox.className = 'status-box analyzing';
    }

    // [新] 讀取使用者設定的分析參數
    const nSamples = document.getElementById('mc-samples')?.value || 10000;
    const sigma    = document.getElementById('mc-sigma')?.value || 3.0;
    const distType = document.getElementById('mc-dist')?.value || 0;

    const encoded = encodeURIComponent(JSON.stringify(editorPathData));
    const url = `/api/analyze_tolerance_stream?pathData=${encoded}&n_samples=${nSamples}&sigma=${sigma}&dist_type=${distType}`;
    const es = new EventSource(url);

    es.onerror = () => {
        es.close();
        if (bar) { bar.style.width = '100%'; bar.style.background = '#ef4444'; }
        if (label) label.textContent = window.CURRENT_LANG === 'en' ? '❌ Connection failed. Check server.' : '❌ 連線失敗，請確認伺服器狀態。';
        if (btn) btn.disabled = false;
    };

    es.onmessage = (e) => {
        let payload;
        try { payload = JSON.parse(e.data); } catch { return; }

        if (payload.progress !== undefined) {
            const pct = Math.min(100, payload.progress);
            if (bar) bar.style.width   = pct + '%';
            
            const percentEl = document.getElementById('analyze-progress-percent');
            if (percentEl) percentEl.textContent = pct + '%';
            
            if (label) {
                label.textContent = (window.CURRENT_LANG === 'en' ? 'Analyzing... ' : '分析中... ') + pct + '%';
            }

            // 🐎 馬到成功：同步更新馬匹位置
            const horseRider = document.getElementById('horse-rider-wrapper');
            if (horseRider) {
                horseRider.style.left = `calc(${pct}% - ${pct * 1.1}px)`;
            }
        }

        if (payload.error) {
            es.close();
            if (bar) {
                bar.style.width    = '100%';
                bar.style.background = '#ef4444';
            }
            if (label) {
                label.textContent  = (window.CURRENT_LANG === 'en' ? 'Error: ' : '錯誤：') + payload.error;
            }
            if (btn) btn.disabled = false;
        }

        if (payload.result) {
            es.close();
            if (bar) bar.style.width   = '100%';
            if (label) label.textContent = window.CURRENT_LANG === 'en' ? '✅ Analysis complete!' : '✅ 分析完成！';
            
            // 更新狀態方塊為「已完成」
            if (statusBox) {
                statusBox.textContent = window.CURRENT_LANG === 'en' ? 'Completed' : '已完成';
                statusBox.className = 'status-box completed';
            }

            // 確保馬兒到達終點
            const horseRider = document.getElementById('horse-rider-wrapper');
            if (horseRider) horseRider.style.left = `calc(100% - 110px)`;

            if (btn) btn.disabled = false;

            // 稍微停頓讓使用者看到「已完成」的快感
            setTimeout(() => { 
                if (wrap) wrap.classList.add('hidden-by-default'); 
                closeAnalysisModal();
                mountDashboardToLeftPanel();
                if (typeof renderAnalysisResult === 'function') {
                    renderAnalysisResult(payload.result);
                }
            }, 1000);

            window._lastAnalysisResult = payload.result;
            window._lastPathData = JSON.parse(JSON.stringify(editorPathData));
            // 首次分析結果作為手動比對的基準（baseline）
            if (!window._baselineResult) {
                window._baselineResult = payload.result;
                window._baselinePathData = JSON.parse(JSON.stringify(editorPathData));
            }
        }
    };

    es.onerror = () => {
        es.close();
        label.textContent = window.CURRENT_LANG === 'en' ? 'Connection error.' : '連線中斷，請重試。';
        btn.disabled = false;
    };
}

// ── Dashboard Logic ──
let currentDashboardTab = 'summary';
let currentAxis = 'X';
window.currentAxis = 'X';
let activeChart = null;


function mountDashboardToLeftPanel() {
    const container = document.getElementById('graph-container');
    const tmpl = document.getElementById('dashboard-layout-template');
    if (!container || !tmpl) return;

    container.innerHTML = tmpl.innerHTML;
    // 稍微延遲讓 DOM 更新完成後觸發 tab 切換與圖表渲染
    setTimeout(() => {
        switchDashboardTab('summary');
    }, 50);
}

// (暫不刪除 openDashboard() / closeDashboard()，以免有些地方仍殘留呼叫)
function openDashboard() {
    mountDashboardToLeftPanel();
}

function closeDashboard() {
    // 若原有用到了 modal，現在已經在左邊了，就不需要處理 display='none'
}

function switchDashboardTab(tab) {
    currentDashboardTab = tab;
    
    // 更新側邊欄樣式
    document.querySelectorAll('.side-tab').forEach(btn => {
        btn.classList.toggle('active', btn.getAttribute('onclick').includes(`'${tab}'`));
    });

    const filterWrap = document.getElementById('axis-filter-wrap');
    const titleEl = document.getElementById('dashboard-title');
    const chartCont = document.getElementById('chart-container');
    const summaryCont = document.getElementById('summary-content');

    // 根據標籤決定是否顯示軸向過濾器
    filterWrap.style.display = (tab === 'summary') ? 'none' : 'flex';
    
    // 更新中心標題
    const titles = {
        summary: window.CURRENT_LANG === 'en' ? 'Analysis Summary' : '公差分析摘要',
        dist: window.CURRENT_LANG === 'en' ? 'Error Distribution' : '誤差分佈直方圖',
        sens: window.CURRENT_LANG === 'en' ? 'Sensitivity Analysis' : '敏感度分析',
        cont: window.CURRENT_LANG === 'en' ? 'Contribution Analysis' : '貢獻度分析',
        '3d': window.CURRENT_LANG === 'en' ? '3D Error Scatter' : '3D 空間誤差散佈'
    };
    titleEl.textContent = titles[tab] || '';

    // 根據標籤動態注入軸向過濾器內容
    if (tab === '3d') {
        const isAngle = currentAxis.startsWith('a');
        const transLabel = window.CURRENT_LANG === 'en' ? 'Translation (mm)' : '平移誤差 (mm)';
        const rotLabel   = window.CURRENT_LANG === 'en' ? 'Rotation (arc_sec)' : '旋轉誤差 (arc_sec)';
        
        filterWrap.innerHTML = `
            <button class="axis-btn ${!isAngle ? 'active' : ''}" data-axis="X" onclick="filterAxis('X')">${transLabel}</button>
            <button class="axis-btn ${isAngle ? 'active' : ''}" data-axis="aX" onclick="filterAxis('aX')">${rotLabel}</button>
        `;
    } else if (tab !== 'summary') {
        // 恢復 6 軸選擇器
        filterWrap.innerHTML = `
            <button class="axis-btn ${currentAxis === 'X' ? 'active' : ''}" data-axis="X" onclick="filterAxis('X')">X</button>
            <button class="axis-btn ${currentAxis === 'Y' ? 'active' : ''}" data-axis="Y" onclick="filterAxis('Y')">Y</button>
            <button class="axis-btn ${currentAxis === 'Z' ? 'active' : ''}" data-axis="Z" onclick="filterAxis('Z')">Z</button>
            <button class="axis-btn ${currentAxis === 'aX' ? 'active' : ''}" data-axis="aX" onclick="filterAxis('aX')">Rx</button>
            <button class="axis-btn ${currentAxis === 'aY' ? 'active' : ''}" data-axis="aY" onclick="filterAxis('aY')">Ry</button>
            <button class="axis-btn ${currentAxis === 'aZ' ? 'active' : ''}" data-axis="aZ" onclick="filterAxis('aZ')">Rz</button>
        `;
    }

    // 切換顯示模式
    if (tab === 'summary') {
        chartCont.style.display = 'none';
        summaryCont.style.display = 'grid';
        renderSummary();
    } else {
        chartCont.style.display = 'block';
        summaryCont.style.display = 'none';
        renderCurrentChart();
    }
}

function filterAxis(axis) {
    currentAxis = axis;
    window.currentAxis = axis;
    
    const isAngle = axis.startsWith('a');
    
    document.querySelectorAll('.axis-btn').forEach(btn => {
        const btnAxis = btn.getAttribute('data-axis');
        const btnIsAngle = btnAxis && btnAxis.startsWith('a');
        
        if (currentDashboardTab === '3d') {
            // 3D 模式下，按鈕只有「平移」與「旋轉」兩大類
            btn.classList.toggle('active', (isAngle && btnIsAngle) || (!isAngle && !btnIsAngle));
        } else {
            // 一般模式，精確匹配軸向
            btn.classList.toggle('active', btnAxis === axis);
        }
    });

    renderCurrentChart();
    renderSummary();
}

function renderSummary() {
    const res = window._lastAnalysisResult;
    const cont = document.getElementById('summary-content');
    if (!res || !cont) return;

    const isEn = window.CURRENT_LANG === 'en';
    const fmt = (v) => (v != null ? Number(v).toFixed(4) : '0.0000');
    
    // 根據目前選取的軸向獲取對應 RSS 與 Monte Carlo 統計值
    const rss = res[`rss_${currentAxis}`] || res.rss_X || 0;
    const mc_std = res[`mc_${currentAxis}_std`] || res.mc_X_std || 0;
    const mc_max = res[`mc_${currentAxis}_max`] || res.mc_X_max || 0;
    const isAngle = currentAxis.startsWith('a');
    const unit = isAngle ? 'arc_sec' : 'mm';
    // 讀取使用者設定的 sigma，讓 RSS ±Nσ 顯示與參數一致
    const sigmaSetting = parseFloat(document.getElementById('mc-sigma')?.value) || 3.0;

    // 最大貢獻來源：依目前軸向的貢獻度排序
    const axisKey = isAngle ? currentAxis.substring(1).toLowerCase() : currentAxis.toLowerCase();
    const contribList = isAngle ? (res.angle_contribution || []) : (res.contribution || []);
    const topContrib = contribList.length > 0
        ? [...contribList].sort((a, b) => (b[axisKey] || 0) - (a[axisKey] || 0))[0]
        : null;

    cont.innerHTML = `
        <div class="summary-card">
            <h4>RSS ${isEn ? 'Range' : '極值範圍'} (±${sigmaSetting}σ) (${unit})</h4>
            <div class="value">±${fmt(rss * sigmaSetting)}</div>
        </div>
        <div class="summary-card">
            <h4>MC ${isEn ? 'Worst Case (sampled)' : '最壞情況 (MC 取樣)'} (${unit})</h4>
            <div class="value">±${fmt(mc_max)}</div>
        </div>
        <div class="summary-card">
            <h4>MC ${isEn ? 'Std Dev (σ)' : '標準差 (σ)'} (${unit})</h4>
            <div class="value">${fmt(mc_std)}</div>
        </div>
        <div class="summary-card">
            <h4>${isEn ? 'Max Contribution' : '最大貢獻來源'} (${currentAxis})</h4>
            <div class="value">${topContrib ? topContrib.name : 'N/A'}</div>
        </div>
    `;
    cont.className = 'summary-grid';
}

function renderCurrentChart() {
    const res = window._lastAnalysisResult;
    const container = document.getElementById('chart-container');
    if (!res || !container) {
        if (container) container.innerHTML = '<div class="empty-msg">請先點擊「執行深度分析」...</div>';
        return;
    }

    const isEn = window.CURRENT_LANG === 'en';

    // 確保 DOM 已更新再畫圖
    requestAnimationFrame(() => {
        if (activeChart && typeof activeChart.destroy === 'function') {
            activeChart.destroy();
            activeChart = null; 
        }

        const isAngle = currentAxis.startsWith('a');
        const unitLabel = isAngle ? 'arc_second' : 'mm';

        let options = {
            chart: { type: 'bar', height: '100%', toolbar: { show: true }, animations: { enabled: true } },
            colors: ['#0ea5e9'],
            plotOptions: { bar: { borderRadius: 4, horizontal: false, columnWidth: '55%' } },
            dataLabels: { enabled: true, formatter: (v) => (v != null ? Number(v).toFixed(1) : '0'), style: { fontSize: '10px' } },
            xaxis: { 
                type: 'category',
                title: { text: isEn ? 'Path Code' : '路徑代號', style: { color: '#64748b' } },
                labels: { style: { colors: '#94a3b8' }, rotate: -90, maxHeight: 120 }
            },
            yaxis: { 
                title: { text: currentDashboardTab === 'sens' ? 'Sensitivity (%)' : 'Contribution (%)', style: { color: '#64748b' } },
                labels: { style: { colors: '#94a3b8' } } 
            },
            tooltip: { theme: 'dark' },
            grid: { borderColor: 'rgba(148, 163, 184, 0.1)' }
        };

        if (currentDashboardTab === 'dist') {
            const axisIdxMap = { 'X': 0, 'Y': 1, 'Z': 2, 'aX': 3, 'aY': 4, 'aZ': 5 };
            const ptIdx = axisIdxMap[currentAxis] !== undefined ? axisIdxMap[currentAxis] : 0;
            const rawData = res.mc_raw ? res.mc_raw.map(row => row[ptIdx]) : [];
            const { labels, counts } = calculateHistogram(rawData);
            
            const distTitle = `${currentAxis}-distribution${isAngle ? '(angle)' : ''}`;
            options = {
                chart: { type: 'area', height: '100%', toolbar: { show: true } },
                title: { text: distTitle, style: { color: '#e2e8f0', fontSize: '16px' } },
                colors: ['#0ea5e9'],
                series: [{ name: isEn ? 'times' : '次數', data: counts }],
                stroke: { curve: 'smooth', width: 2 },
                fill: { type: 'gradient', gradient: { shadeIntensity: 1, opacityFrom: 0.5, opacityTo: 0.05 } },
                xaxis: { 
                    categories: labels, 
                    tickAmount: 8,
                    title: { text: `tolerance(${unitLabel})`, style: { color: '#64748b' } },
                    labels: { style: { colors: '#94a3b8' } }
                },
                yaxis: { title: { text: isEn ? 'times' : '次數', style: { color: '#64748b' } } },
                grid: { borderColor: 'rgba(148, 163, 184, 0.1)' }
            };
        } else if (currentDashboardTab === 'sens' || currentDashboardTab === 'cont') {
            const key = currentDashboardTab === 'sens' ? 
                        (isAngle ? 'angle_sensitivity' : 'sensitivity') : 
                        (isAngle ? 'angle_contribution' : 'contribution');
            
            const dataArr = res[key] || [];
            // 如果是 aX, aY, aZ，對準 x, y, z 到小寫
            const axisKey = isAngle ? currentAxis.substring(1).toLowerCase() : currentAxis.toLowerCase(); 
            
            const chartTitle = `${currentAxis}-${currentDashboardTab === 'sens' ? 'sensitivity' : 'contribution'}${isAngle ? '(angle)' : ''}`;
            
            const sortedData = dataArr.map(item => ({
                name: item.name,
                val: parseFloat(item[axisKey] || item.value || 0)
            })).sort((a,b) => b.val - a.val).slice(0, 15);

            options.title = { text: chartTitle, style: { color: '#e2e8f0', fontSize: '16px' } };
            options.series = [{
                name: currentDashboardTab === 'sens' ? 'Sensitivity' : 'Contribution (%)',
                data: sortedData.map(d => d.val)
            }];
            options.xaxis.categories = sortedData.map(d => d.name);
        } else if (currentDashboardTab === '3d') {
            container.innerHTML = `
                <div id="three-scatter-loading" style="position:absolute; top:50%; left:50%; transform:translate(-50%, -50%); color:#94a3b8; font-family:sans-serif;">
                    ${isEn ? 'Initializing 3D Scatter View...' : '正在初始化 3D 散點圖...'}
                </div>
                <div id="three-scatter-canvas" style="width:100%; height:500px; background:#f8fafc; border-radius:8px; overflow:hidden;"></div>
            `;
            // 強制延遲執行，確保 DOM 完全渲染且寬高計算完成
            setTimeout(() => {
                const canvasEl = document.getElementById('three-scatter-canvas');
                if (canvasEl) {
                    render3DScatter(canvasEl, res);
                }
            }, 250);
            return;
        }

        activeChart = new ApexCharts(container, options);
        activeChart.render().catch(err => {
            console.error("ApexCharts failed to render:", err);
            container.innerHTML = `<div class="error-msg">${isEn ? 'Chart render failed' : '圖表渲染失敗'}: ${err.message}</div>`;
        });
    });
}

function calculateHistogram(data, bins = 100) {
    if (data.length === 0) return { labels: [], counts: [] };
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min;
    const step = range / bins;
    const counts = new Array(bins).fill(0);
    const labels = [];

    for (let i = 0; i < bins; i++) {
        labels.push((min + i * step).toFixed(4));
    }

    data.forEach(val => {
        let idx = Math.floor((val - min) / step);
        if (idx >= bins) idx = bins - 1;
        counts[idx]++;
    });

    return { labels, counts };
}

function render3DScatter(canvasCont, res) {
    const isEn = window.CURRENT_LANG === 'en';
    if (!canvasCont || !res || !res.mc_raw) {
        if (canvasCont) canvasCont.innerHTML = '<div style="color:#94a3b8; padding:20px;">' + 
            (window.CURRENT_LANG==='en'?'No raw Monte Carlo data available for 3D view.':'無 Monte Carlo 原始數據，無法顯示 3D 散點圖。') + '</div>';
        return;
    }

    // 取得寬高，若為 0 則延遲再試一次
    let width = canvasCont.offsetWidth;
    let height = canvasCont.offsetHeight;
    if (width === 0 || height === 0) {
        console.warn("Canvas dimensions are zero. Retrying in 100ms...");
        setTimeout(() => render3DScatter(canvasCont, res), 100);
        return;
    }

    const loadingEl = document.getElementById('three-scatter-loading');
    if (loadingEl) loadingEl.style.display = 'none';

    canvasCont.innerHTML = '';
    console.log(`Initializing 3D Scatter: ${width}x${height}, Points: ${res.mc_raw.length}`);
    const RAD_TO_ARCSEC = 206264.8;

    // 判斷當前是「平移」還是「旋轉」模式
    // currentAxis 來自全局變量 (X, Y, Z, aX, aY, aZ)
    const isRotationMode = ['aX', 'aY', 'aZ'].includes(window.currentAxis);
    const unit = isRotationMode ? (isEn ? 'arc_sec' : '角秒') : 'mm';
    const titleText = isRotationMode ? (isEn ? '(Rotation Error) 3D Distribution' : '(旋轉誤差) 3D 分佈') : (isEn ? '(Translation Error) 3D Distribution' : '(平移誤差) 3D 分佈');

    if (!window.THREE) {
        canvasCont.innerHTML = `<div class="error-msg">${isEn ? 'Three.js library not loaded.' : '尚未載入 Three.js 函式庫。'}</div>`;
        return;
    }

    const scene = new THREE.Scene();
    scene.background = null; // 透明背景

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(window.devicePixelRatio);
    canvasCont.appendChild(renderer.domElement);

    const controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    // 數據取樣：res.mc_raw 是 [10000, 6] 的陣列
    // 索引 0,1,2 = X,Y,Z (mm); 3,4,5 = aX,aY,aZ (rad)
    const rawData = res.mc_raw;
    const count = rawData.length;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);

    // 計算適當縮放
    let pts = rawData.map(row => {
        if (isRotationMode) {
            return [row[3] * RAD_TO_ARCSEC, row[4] * RAD_TO_ARCSEC, row[5] * RAD_TO_ARCSEC];
        } else {
            return [row[0], row[1], row[2]];
        }
    });

    // --- 計算統計數據與比例 ---
    const getStats = (vals) => {
        const n = vals.length;
        if (n === 0) return { mean: 0, sigma: 0 };
        const mean = vals.reduce((a, b) => a + b, 0) / n;
        const sigma = Math.sqrt(vals.reduce((a, b) => a + (b - mean) ** 2, 0) / n);
        return { mean, sigma };
    };

    const statsX = getStats(pts.map(p => p[0]));
    const statsY = getStats(pts.map(p => p[1]));
    const statsZ = getStats(pts.map(p => p[2]));

    // 設定場景縮放 (以最大 3-sigma 範圍為基準)
    const maxSigma = Math.max(statsX.sigma, statsY.sigma, statsZ.sigma, 0.00001);
    const maxVal = maxSigma * 3; // 3-sigma 顯示範圍
    const boxScale = 5.0 / (maxSigma * 3.5); // 讓 3-sigma 框約佔場景一半

    pts.forEach((p, i) => {
        positions[i * 3]     = (p[0] - statsX.mean) * boxScale;
        positions[i * 3 + 1] = (p[1] - statsY.mean) * boxScale;
        positions[i * 3 + 2] = (p[2] - statsZ.mean) * boxScale;

        // 二進位判定：任一軸超出 3-sigma 即為紅色 (法規與單機版邏輯)
        const isOutlier = (Math.abs(p[0] - statsX.mean) > 3 * statsX.sigma) ||
                          (Math.abs(p[1] - statsY.mean) > 3 * statsY.sigma) ||
                          (Math.abs(p[2] - statsZ.mean) > 3 * statsZ.sigma);

        if (isOutlier) {
            colors[i * 3]     = 1.0;  // R
            colors[i * 3 + 1] = 0.28; // G (略暗的紅)
            colors[i * 3 + 2] = 0.2;  // B
        } else {
            colors[i * 3]     = 0.13; // R
            colors[i * 3 + 1] = 0.77; // G (綠色)
            colors[i * 3 + 2] = 0.36; // B
        }
    });

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

    const material = new THREE.PointsMaterial({ size: 0.06, vertexColors: true, transparent: true, opacity: 0.9 });
    const cloud = new THREE.Points(geometry, material);
    scene.add(cloud);

    // --- 繪製 3-Sigma 公差框 (Bounding Box) ---
    const boxGeom = new THREE.BoxGeometry(
        statsX.sigma * 6 * boxScale,
        statsY.sigma * 6 * boxScale,
        statsZ.sigma * 6 * boxScale
    );
    const boxEdges = new THREE.EdgesGeometry(boxGeom);
    const boxLine  = new THREE.LineSegments(boxEdges, new THREE.LineBasicMaterial({ color: 0x475569, transparent: true, opacity: 0.6 }));
    scene.add(boxLine);

    // 填色平面 (與單機版一致，增加半透明感)
    const boxMesh = new THREE.Mesh(boxGeom, new THREE.MeshBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.05 }));
    scene.add(boxMesh);

    // 輔助網格中心對齊
    const grid = new THREE.GridHelper(10, 10, 0x94a3b8, 0xe2e8f0);
    grid.rotation.x = Math.PI / 2;
    grid.position.z = - (statsZ.sigma * 3 * boxScale); // 稍微沉到底部
    scene.add(grid);

    // 如果是旋轉模式，加上一個灰色的參考平面 (像截圖中那樣)
    if (isRotationMode) {
        const planeGeom = new THREE.PlaneGeometry(10, 10);
        const planeMat  = new THREE.MeshBasicMaterial({ color: 0x94a3b8, transparent: true, opacity: 0.2, side: THREE.DoubleSide });
        const plane = new THREE.Mesh(planeGeom, planeMat);
        scene.add(plane);
    }

    // 座標軸輔助 (紅色 X, 綠色 Y, 藍色 Z)
    const axes = new THREE.AxesHelper(6);
    scene.add(axes);

    camera.position.set(10, 10, 12);
    camera.lookAt(0, 0, 0);

    // 標題與軸標籤 (使用 Canvas 畫簡單貼圖或 CSS)
    const labelDiv = document.createElement('div');
    labelDiv.style.position = 'absolute';
    labelDiv.style.top = '10px';
    labelDiv.style.left = '10px';
    labelDiv.style.color = '#1e293b';
    labelDiv.style.fontFamily = "'Times New Roman', serif";
    labelDiv.style.fontSize = '1.1rem';
    labelDiv.style.fontWeight = 'bold';
    labelDiv.style.pointerEvents = 'none';
    labelDiv.innerHTML = `${titleText}<br><span style="font-size:0.8rem; color:#64748b;">(Units: ${unit}, Range: ±${maxVal.toFixed(4)})</span>`;
    canvasCont.appendChild(labelDiv);

    function animate() {
        if (!document.getElementById('three-scatter-canvas')) return;
        requestAnimationFrame(animate);
        controls.update();
        renderer.render(scene, camera);
    }
    animate();

    // 處理視窗縮放
    window.addEventListener('resize', () => {
        if (!canvasCont.isConnected) return;
        const w = canvasCont.clientWidth;
        const h = canvasCont.clientHeight;
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h);
    });
}

// ────────── Excel 調配歷史同步 ──────────
async function saveAllocationHistory() {
    if (!window._lastAnalysisResult || !window._lastPathData) return;
    
    try {
        const res = await fetch('/api/save_allocation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                pathData: window._lastPathData,
                result:   window._lastAnalysisResult,
                lang:     window.CURRENT_LANG
            })
        });
        const data = await res.json();
        if (data.ok) {
            console.log("Excel History Synced:", data.msg);
        }
    } catch (e) {
        console.error("Failed to sync Excel history:", e);
    }
}

async function downloadAnalysisExcel() {
    if (!window._lastAnalysisResult) {
        alert(window.CURRENT_LANG === 'en' ? 'No analysis result. Run tolerance analysis first.' : '尚無分析結果，請先執行公差分析。');
        return;
    }
    try {
        const res = await fetch('/api/export_analysis_excel', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                pathData: window._lastPathData || [],
                result:   window._lastAnalysisResult,
                lang:     window.CURRENT_LANG,
            }),
        });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const blob = await res.blob();
        const url  = window.URL.createObjectURL(blob);
        const a    = document.createElement('a');
        a.style.display = 'none';
        a.href     = url;
        a.download = 'Tolerance_Analysis_Report.xlsx';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    } catch (e) {
        alert((window.CURRENT_LANG === 'en' ? 'Excel export failed: ' : 'Excel 匯出失敗：') + e.message);
    }
}

// 目前調配模式：'auto' | 'compare'
window._allocMode = 'auto';

function setAllocMode(mode) {
    window._allocMode = mode;
    const isEn = window.CURRENT_LANG === 'en';
    document.getElementById('alloc-mode-auto').classList.toggle('active', mode === 'auto');
    document.getElementById('alloc-mode-compare').classList.toggle('active', mode === 'compare');
    document.getElementById('alloc-auto-params').style.display = mode === 'auto' ? '' : 'none';
    document.getElementById('alloc-compare-hint').style.display = mode === 'compare' ? '' : 'none';
    
    // 更新主按鈕文字
    const runBtn = document.getElementById('btn-run-allocation');
    if (runBtn) {
        if (mode === 'auto') {
            runBtn.innerHTML = `🤖 ${isEn ? 'Run Auto Allocation' : '執行自動調配'}`;
        } else {
            runBtn.innerHTML = `📊 ${isEn ? 'Run Manual Matching' : '執行手動匹配'}`;
        }
    }
    
    document.getElementById('allocation-result-area').style.display = 'none';
}

async function runAllocation() {
    const isEn = window.CURRENT_LANG === 'en';

    if (!editorPathData || editorPathData.length === 0) {
        alert(isEn ? 'No path data to allocate.' : '路徑資料為空，請先編輯。');
        return;
    }
    if (!window._lastAnalysisResult) {
        alert(isEn ? 'Please run Tolerance Analysis first.' : '請先執行一次公差分析。');
        return;
    }

    const mode = window._allocMode || 'auto';

    // 手動比對模式需要 baseline
    if (mode === 'compare' && !window._baselineResult) {
        alert(isEn ? 'No baseline found. The first Tolerance Analysis result will be used as baseline automatically next time.' : '找不到基準結果。首次公差分析的結果將自動作為基準，請再次執行後比對。');
        return;
    }

    const btn       = document.getElementById('btn-run-allocation');
    const wrap      = document.getElementById('allocation-progress-wrap');
    const statusBox = document.getElementById('allocation-status-box');
    const resultArea= document.getElementById('allocation-result-area');

    if (btn) btn.disabled = true;
    if (wrap) wrap.classList.remove('hidden-by-default');
    if (statusBox) { 
        statusBox.textContent = isEn ? (mode === 'auto' ? 'Solving...' : 'Analyzing...') : '計算中...'; 
        statusBox.className = 'status-box analyzing'; 
    }

    // [關鍵修正] 在執行任何調配前，先捕捉目前的編輯器狀態作為「修改前」基準
    const prevPathSnapshot = JSON.parse(JSON.stringify(editorPathData));

    try {
        if (mode === 'auto') {
            // ── 自動調配 ──────────────────────────────────────────────
            const target = parseFloat(document.getElementById('alloc-target')?.value) || 0.05;
            const weight = document.getElementById('alloc-weight')?.value || 'medium';
            const axis   = document.getElementById('alloc-axis')?.value   || 'Z';

            const res  = await fetch('/api/run_allocation', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mode, target, weight, axis,
                    pathData:       editorPathData,
                    analysisResult: window._lastAnalysisResult
                })
            });
            const data = await res.json();
            if (!data.ok) throw new Error(data.error || 'Allocation failed');

            // 更新 editorPathData 並重新渲染表格
            editorPathData = data.newPathData;
            renderEditorList();

            // [新增] 迭代次數累加與即時報表
            window.__allocationRound = (window.__allocationRound || 0) + 1;
            const strategyLabel = (window.CURRENT_LANG === 'en') ? 
                (weight === 'precision' ? 'Precision Focus (Q1)' : 'Cost Focus (Q4)') :
                (weight === 'precision' ? '精度考量 (主攻 Q1)' : '成本考量 (考慮 Q4)');

            if (typeof renderAllocationResult === 'function') {
                renderAllocationResult({
                    report: data.report || {},
                    target,
                    axis,
                    strategy: strategyLabel,
                    dsl: data.dsl,
                    prevPathData: prevPathSnapshot, // 修改前的快照
                    newPathData: data.newPathData,
                    analysisResult: data.analysisResult 
                });
            }

            // 儲存調配結果供 LLM 與 導出報表使用
            window._lastAllocationResult = {
                mode: 'auto', axis, target, weight,
                newPathData: data.newPathData,
                prevPathData: prevPathSnapshot, // 使用點擊前的快照
                analysisResult: data.analysisResult,
                report: data.report
            };

            if (statusBox) { statusBox.textContent = isEn ? 'Completed' : '已完成'; statusBox.className = 'status-box completed'; }

            // 顯示結果提示
            if (resultArea) {
                resultArea.style.display = 'block';
                resultArea.innerHTML = `<div style="padding:8px 12px; background:#f0fdf4; border:1px solid #bbf7d0; border-radius:6px; font-size:0.85rem; color:#166534;">
                    ${isEn ? `✅ Manual allocation done (${axis}-axis, target RSS ±${target}). Editor updated — re-run Tolerance Analysis to verify.`
                           : `✅ 手動調配完成（${axis} 軸，目標 RSS ±${target}）。公差值已更新，請重新執行公差分析確認結果。`}
                </div>`;
            }

        } else {
            // ── 手動比對 ──────────────────────────────────────────────
            const res  = await fetch('/api/run_allocation', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mode: 'compare',
                    pathData:       editorPathData, // [新增] 送出路徑資料以供後端重新分析
                    baseline:       window._baselineResult,
                    analysisResult: window._lastAnalysisResult
                })
            });
            const data = await res.json();
            if (!data.ok) throw new Error(data.error || 'Compare failed');
            
            // [同步] 使用重新分析的結果更新前端快照
            if (data.analysisResult) {
                window._lastAnalysisResult = data.analysisResult;
                window._lastPathData = JSON.parse(JSON.stringify(editorPathData));
            }

            if (statusBox) { statusBox.textContent = isEn ? 'Completed' : '已完成'; statusBox.className = 'status-box completed'; }
            
            // 儲存調配結果
            window._lastAllocationResult = { 
                mode: 'compare', 
                report: data.report,
                prevPathData: window._baselinePathData || prevPathSnapshot, // 優先使用基準路徑
                newPathData: data.newPathData,
                analysisResult: data.analysisResult
            };

            // 統一使用 renderAllocationResult 渲染專業報表
            if (typeof renderAllocationResult === 'function') {
                renderAllocationResult({
                    mode: 'compare',
                    report: data.report,
                    axis: document.getElementById('alloc-axis')?.value || 'Z',
                    prevPathData: window._baselinePathData || prevPathSnapshot, // 優先使用基準基準點
                    newPathData: data.newPathData,
                    analysisResult: data.analysisResult
                });
            }

            if (resultArea) {
                resultArea.style.display = 'block';
                resultArea.innerHTML = `<div style="padding:8px 12px; background:#f0f9ff; border:1px solid #bae6fd; border-radius:6px; font-size:0.85rem; color:#0369a1;">
                    ${isEn ? '📊 Manual Matching report generated below.' : '📊 已產出手動匹配分析報告（見下方對話框）。'}
                </div>`;
            }
        }

        // 同步存 Excel 歷程
        await fetch('/api/save_allocation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pathData: editorPathData, result: window._lastAnalysisResult, lang: window.CURRENT_LANG })
        });

    } catch (e) {
        console.error('Allocation failed:', e);
        if (statusBox) { statusBox.textContent = isEn ? 'Failed' : '失敗'; statusBox.className = 'status-box failed'; }
        alert(isEn ? `Allocation failed: ${e.message}` : `調配失敗：${e.message}`);
    } finally {
        if (btn) btn.disabled = false;
        if (wrap) wrap.classList.add('hidden-by-default');
    }
}

async function exportContactLines() {
    if (contactPairs.length === 0) {
        alert(window.CURRENT_LANG === 'en' ? "No contact lines to export!" : "目前沒有任何接觸線可以匯出！");
        return;
    }
    const btn = document.querySelector('.export-lines-btn');
    const originalText = btn.textContent;
    btn.textContent = window.CURRENT_LANG === 'en' ? "⏳ Generating CSV..." : "⏳ 產生 CSV 中...";
    btn.disabled = true;
    let exportData = contactPairs.map(p => {
        const startNode = document.getElementById(p.start);
        const endNode = document.getElementById(p.end);

        // 優先從節點文字提取名，如果抓不到，則從 ID 轉換 (node-1-1-P-1 -> 1-P-1)
        const getName = (id, el) => {
            if (el) return el.textContent.trim();
            const parts = id.split('-');
            if (parts.length >= 3) return parts.slice(2).join('-');
            return id;
        };

        return { start: getName(p.start, startNode), end: getName(p.end, endNode) };
    });
    try {
        const res = await fetch('/api/export_contact_lines_csv', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pairs: exportData, lang: window.CURRENT_LANG }) });
        if (!res.ok) throw new Error("Export failed");
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none'; a.href = url; a.download = "Contact_Lines_Export.csv";
        document.body.appendChild(a); a.click(); document.body.removeChild(a); window.URL.revokeObjectURL(url);
        alert(window.CURRENT_LANG === 'en' ? "[SUCCESS] Contact lines CSV downloaded!" : "[SUCCESS] 接觸連線 CSV 檔案下載成功！");
    } catch (e) {
        alert(window.CURRENT_LANG === 'en' ? "[ERROR] Export failed: " + e.message : "[ERROR] 匯出失敗: " + e.message);
    } finally {
        btn.textContent = originalText; btn.disabled = false;
    }
}

/**
 * [Phase 5] 從 STEP 組合件接觸分析結果渲染接觸圖
 * 將 asm_worker 的 JSON 輸出轉換為接觸線對並渲染
 */
function renderAsmContactsFromStep(contactsData) {
    if (!contactsData || !Array.isArray(contactsData)) {
        console.warn('[renderAsmContactsFromStep] Invalid contacts data');
        return;
    }

    // 清空現有接觸線
    contactPairs = [];

    // 轉換每個接觸對
    contactsData.forEach(contact => {
        const comp1 = contact.comp1_name || contact.comp1 || '';
        const comp2 = contact.comp2_name || contact.comp2 || '';

        if (!comp1 || !comp2) return;

        // 提取零件編號（假設格式為 "5" 或 "5-P-1" 或完整名稱）
        // 如果只有數字，嘗試找到相應的特徵節點
        const extractPartId = (name) => {
            const match = name.match(/^(\d+)/);
            return match ? match[1] : name;
        };

        const part1Id = extractPartId(comp1);
        const part2Id = extractPartId(comp2);

        // 構建節點 ID（格式：node-{partId}-{featureName}）
        // 如果沒有特定特徵，使用零件編號作為特徵名
        const nodeId1 = `node-${part1Id}-${comp1}`;
        const nodeId2 = `node-${part2Id}-${comp2}`;

        // 避免重複
        if (!contactPairs.some(cp =>
            (cp.start === nodeId1 && cp.end === nodeId2) ||
            (cp.start === nodeId2 && cp.end === nodeId1)
        )) {
            contactPairs.push({ start: nodeId1, end: nodeId2 });
        }
    });

    console.log(`[Phase 5] Loaded ${contactPairs.length} assembly contact pairs from STEP`);

    // 重繪接觸圖（如果有接觸視圖已開啟）
    if (window._contactCanvasInitialized) {
        redrawContactGraph();
    }
}

/**
 * 重繪接觸圖（用於更新或初次繪製）
 */
function redrawContactGraph() {
    const graphContainer = document.getElementById('graph-container');
    if (!graphContainer) return;

    if (contactPairs.length === 0) {
        graphContainer.innerHTML = '<p style="padding:10px; color:#999;">無接觸對</p>';
        return;
    }

    // 觸發重新渲染（委派給現有的 BOM 渲染邏輯）
    // 如果有需要，可以在此處調用 renderCustomBomTree 或其他渲染函數
    console.log('[redrawContactGraph] Contact pairs updated, ready for rendering');
}
