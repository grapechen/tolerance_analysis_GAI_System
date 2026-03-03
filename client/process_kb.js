/**
 * Process Knowledge Base - Logic & Data
 * Migrated from company.html
 */

const companies = [
    { company_id: "C_TONGTAI", company_name: "東台精機 Tongtai" },
    { company_id: "C_AWEA", company_name: "亞崴機電 AWEA" },
    { company_id: "C_YCM", company_name: "永進機械 YCM" },
    { company_id: "C_LATC", company_name: "雷應科技 i-LATC" },
    { company_id: "C_SUPERALLOY", company_name: "巧新科技 SuperAlloy" },
    { company_id: "C_BASSO", company_name: "鑽全實業 BASSO" }
];

const processes = [
    { process_id: "P_TURN", process_type: "TURNING", name: "CNC Lathe (數控車床)" },
    { process_id: "P_MILL", process_type: "CNC_MILLING", name: "CNC Milling Machine (數控銑床)" },
    { process_id: "P_VMC", process_type: "VMC_MILLING", name: "Vertical Machining Center (立式加工中心)" },
    { process_id: "P_HMC", process_type: "HMC_MILLING", name: "Horizontal Machining Center (臥式加工中心)" },
    { process_id: "P_5AX", process_type: "FIVE_AXIS_MILLING", name: "5-Axis Machining Center (五軸加工中心)" },
    { process_id: "P_MTURN", process_type: "MILL_TURN", name: "Mill-Turn (車銑複合)" },
    { process_id: "P_GRIND", process_type: "GRINDING", name: "Grinding Machine (磨床)" }
];

/* machines 與 capabilities 的資料已經從 excel 解析並獨立到 machines_data.js 中 */

// ---------- helpers (Same logic, slightly robust) ----------
const byId = (id) => document.getElementById(id); // Warning: this assumes standard index.html structure
const toNum = (v) => (v === "" || v == null) ? null : Number(v);
const clamp = (n) => Number.isFinite(n) ? n : null;

function companyName(company_id) {
    return companies.find(c => c.company_id === company_id)?.company_name || company_id;
}
function processTypeFromProcessId(pid) {
    return processes.find(p => p.process_id === pid)?.process_type || "UNKNOWN";
}
function getCap(machine_id) {
    return capabilities.find(c => c.machine_id === machine_id) || null;
}
function parseRpm(v) {
    if (v == null) return null;
    if (typeof v === "number") return v;
    const nums = String(v).match(/\d+/g);
    if (!nums) return null;
    return Math.max(...nums.map(n => Number(n)));
}

function parsePower(v) {
    if (v == null) return null;
    if (typeof v === "number") return v;
    // extract all numbers, take max
    const nums = String(v).match(/[\d.]+/g);
    if (!nums) return null;
    return Math.max(...nums.map(n => parseFloat(n)));
}
function getTravel(c, axis) {
    return c?.axes?.travel_mm?.[axis] ?? null;
}
// Helper to extract accuracy for scoring (Prioritize ISO)
function getAccVals(c) {
    if (!c?.accuracy) return null;
    // New structure: standards
    if (c.accuracy.standards) {
        // Prefer ISO > JIS > others
        const s = c.accuracy.standards;
        if (s.ISO_10791_4) return { ...s.ISO_10791_4, source: "ISO 10791-4" };
        if (s.ISO_230_2) return { ...s.ISO_230_2, source: "ISO 230-2" };
        if (s.JIS_B_6338) return { ...s.JIS_B_6338, source: "JIS B 6338" };
        // fallback to first key
        const k = Object.keys(s)[0];
        return { ...s[k], source: k };
    }
    // Old structure (flat)
    return c.accuracy;
}

function hasRepeatability(c) {
    const a = getAccVals(c);
    return (a?.repeatability_mm != null) || (a?.repeatability_um != null) || (a?.repeatability_arcsec != null);
}
function getRepeatabilityMm(c) {
    const a = getAccVals(c);
    if (a?.repeatability_mm != null) return a.repeatability_mm;
    if (a?.repeatability_um != null) {
        const v = parseFloat(a.repeatability_um);
        if (!isNaN(v)) return v / 1000.0;
    }
    return 999;
}
function hasPositioning(c) {
    const a = getAccVals(c);
    return (a?.positioning_mm != null) || (a?.positioning_arcsec != null);
}
function getPositioningMm(c) {
    const av = getAccVals(c);
    if (av?.positioning_mm != null) return av.positioning_mm;
    return 999;
}
function formatVal(v, unit = "") {
    if (v == null) return "—";
    return `${v}${unit}`;
}

// ---------- Scoring Logic (Same logic) ----------
function scoreMachine(m, c, q) {
    const reasons = [];
    let ok = true;
    let score = 0;
    const ptype = processTypeFromProcessId(m.process_id);

    // Filters
    if (q.company !== "ALL" && m.company_id !== q.company) return fail("公司不符");
    if (q.process !== "ALL" && ptype !== q.process) return fail("製程類型不符");

    function fail(msg) {
        return { ok: false, score: 0, capScore: 0, confScore: 0, riskFlags: [], reasons: [`<span class="bad">✗ ${msg}</span>`] };
    }

    // Accuracy
    const targetAcc = parseFloat(q.accuracy);
    if (!isNaN(targetAcc) && targetAcc > 0) {
        if (!hasRepeatability(c)) {
            ok = false;
            reasons.push(`<span class="bad">✗ 缺 Positioning Repeatability 資料 (無法驗證 < ${q.accuracy} mm)</span>`);
        } else {
            const machRep = getRepeatabilityMm(c);
            if (machRep > targetAcc) {
                ok = false;
                reasons.push(`<span class="bad">✗ Positioning Repeatability 不足 (機台:${machRep} > 目標:${targetAcc})</span>`);
            } else {
                score += 20;
                const ratio = targetAcc / machRep;
                if (ratio >= 2) score += 10;
                reasons.push(`<span class="ok">✓ 符合 Positioning Repeatability (能力比 ${(ratio).toFixed(1)}x)</span>`);
            }
        }
    }

    // Positioning
    const targetPos = parseFloat(q.positioning);
    if (!isNaN(targetPos) && targetPos > 0) {
        if (!hasPositioning(c)) {
            ok = false;
            reasons.push(`<span class="bad">✗ 缺 Positioning Accuracy 資料</span>`);
        } else {
            const machPos = getPositioningMm(c);
            if (machPos > targetPos) {
                ok = false;
                reasons.push(`<span class="bad">✗ Positioning Accuracy 不足 (${machPos} > ${targetPos})</span>`);
            } else {
                score += 15;
                const ratio = targetPos / machPos;
                if (ratio >= 2) score += 5;
                reasons.push(`<span class="ok">✓ 符合 Positioning Accuracy (能力比 ${ratio.toFixed(1)}x)</span>`);
            }
        }
    }

    // Axes
    if (q.axes != null) {
        const axes = c?.axes?.count ?? null;
        if (axes == null) {
            ok = false;
            reasons.push(`<span class="bad">✗ 未提供軸數</span>`);
        } else if (axes < q.axes) {
            ok = false;
            reasons.push(`<span class="bad">✗ 軸數 ${axes} ＜ ${q.axes}</span>`);
        } else {
            score += 10 + (axes - q.axes);
            reasons.push(`<span class="ok">✓ 軸數 ${axes} ≥ ${q.axes}</span>`);
        }
    }

    // Travels
    const travelChecks = [{ axis: "X", need: q.x }, { axis: "Y", need: q.y }, { axis: "Z", need: q.z }];
    travelChecks.forEach(t => {
        if (t.need == null) return;
        const val = getTravel(c, t.axis);
        if (val == null) {
            ok = false;
            reasons.push(`<span class="bad">✗ 缺 ${t.axis} 行程資料</span>`);
        } else if (val < t.need) {
            ok = false;
            reasons.push(`<span class="bad">✗ ${t.axis} 行程 ${val} ＜ ${t.need}</span>`);
        } else {
            score += 8 + Math.min(5, Math.floor((val - t.need) / 200));
            reasons.push(`<span class="ok">✓ ${t.axis} 行程 ${val} ≥ ${t.need}</span>`);
        }
    });

    // RPM
    if (q.rpm != null) {
        const rpm = parseRpm(c?.spindle?.speed_max_rpm);
        if (rpm == null) {
            ok = false;
            reasons.push(`<span class="bad">✗ 缺轉速資料</span>`);
        } else if (rpm < q.rpm) {
            ok = false;
            reasons.push(`<span class="bad">✗ 主軸 ${rpm} ＜ ${q.rpm}</span>`);
        } else {
            score += 8;
            reasons.push(`<span class="ok">✓ 主軸 ${rpm} ≥ ${q.rpm}</span>`);
        }
    }


    // Power (New)
    if (q.power != null) {
        const kw = parsePower(c?.spindle?.power_kw);
        if (kw == null) {
            // ok = false; // Don't filter strictly if missing, maybe just warn? 
            // Let's filter strictly if user asks for it, but allow missing with penalty?
            // Usually if user specifies power, they need it.
            ok = false;
            reasons.push(`<span class="bad">✗ 缺馬達出力資料</span>`);
        } else if (kw < q.power) {
            ok = false;
            reasons.push(`<span class="bad">✗ 馬達出力 ${kw}kW ＜ ${q.power}kW</span>`);
        } else {
            score += 10 + Math.min(10, (kw - q.power));
            reasons.push(`<span class="ok">✓ 馬達出力 ${kw}kW ≥ ${q.power}kW (切削能力)</span>`);
        }
    }


    // Bar / Workpiece
    if (q.bar != null) {
        const bar = c?.work_envelope?.bar_capacity_mm ?? null;
        if (bar == null) { ok = false; reasons.push(`<span class="bad">✗ 缺棒材資料</span>`); }
        else if (bar < q.bar) { ok = false; reasons.push(`<span class="bad">✗ 棒材 ${bar} ＜ ${q.bar}</span>`); }
        else { score += 6; reasons.push(`<span class="ok">✓ 棒材 ${bar} ≥ ${q.bar}</span>`); }
    }
    if (q.work_d != null) {
        const d = c?.work_envelope?.max_workpiece_diameter_mm ?? null;
        if (d != null && d < q.work_d) { ok = false; reasons.push(`<span class="bad">✗ 工件直徑 ${d} ＜ ${q.work_d}</span>`); }
        else if (d != null) { score += 6; reasons.push(`<span class="ok">✓ 工件直徑 ${d} ≥ ${q.work_d}</span>`); }
        else { ok = false; reasons.push(`<span class="bad">✗ 缺直徑資料</span>`); }
    }
    if (q.work_l != null) {
        const L = c?.work_envelope?.max_workpiece_length_mm ?? null;
        if (L != null && L < q.work_l) { ok = false; reasons.push(`<span class="bad">✗ 工件長度 ${L} ＜ ${q.work_l}</span>`); }
        else if (L != null) { score += 6; reasons.push(`<span class="ok">✓ 工件長度 ${L} ≥ ${q.work_l}</span>`); }
        else { ok = false; reasons.push(`<span class="bad">✗ 缺長度資料</span>`); }
    }

    // --- Multi-dimensional Metrics ---
    let capScore = score;
    let confScore = 0;
    let riskFlags = [];

    if (c?.spindle?.speed_max_rpm) confScore += 20;
    if (getTravel(c, "X")) confScore += 20;
    if (c?.tooling?.magazine_capacity) confScore += 10;
    if (hasRepeatability(c)) {
        confScore += 30;
        const accVals = getAccVals(c);
        if (accVals?.source) confScore += 10;
    } else {
        riskFlags.push("MISSING_ACCURACY");
    }
    if (hasPositioning(c)) confScore += 10;

    const scenario = q.scenario || "GENERAL";
    if (scenario === "MOLD") {
        if (riskFlags.includes("MISSING_ACCURACY")) {
            score *= 0.5;
            reasons.push(`<span class="warn">⚠ [模具] 缺 Positioning Repeatability 資料，風險極高</span>`);
        } else {
            const rep = getRepeatabilityMm(c);
            if (rep <= 0.005) { score += 30; reasons.push(`<span class="ok">★ [模具] 超高 Positioning Repeatability (≦5µm)</span>`); }
            else if (rep <= 0.010) { score += 15; reasons.push(`<span class="ok">★ [模具] 高 Positioning Repeatability (≦10µm)</span>`); }
        }
        const rpm = parseRpm(c?.spindle?.speed_max_rpm);
        if (rpm && rpm >= 15000) { score += 10; reasons.push(`<span class="ok">★ [模具] 高轉速適合精修</span>`); }
    } else if (scenario === "AERO") {
        if (riskFlags.includes("MISSING_ACCURACY")) reasons.push(`<span class="warn">⚠ [航太] 缺 Positioning Repeatability 驗證資料</span>`);
    } else if (scenario === "MASS") {
        const rapidX = c?.feed?.rapid_m_per_min?.X;
        if (rapidX && rapidX >= 48) { score += 10; reasons.push(`<span class="ok">★ [量產] 快送速度優 (≧48m/min)</span>`); }
    }

    return {
        ok,
        score,
        capScore: Math.min(100, Math.round(capScore)),
        confScore: Math.min(100, confScore),
        riskFlags,
        reasons
    };
}

function sortCandidates(list, sortMode) {
    const cmp = {
        "SCORE": (a, b) => b.score - a.score,
        "CAP": (a, b) => b.capScore - a.capScore,
        "CONF": (a, b) => b.confScore - a.confScore,
    }[sortMode] || ((a, b) => b.score - a.score);
    return list.sort(cmp);
}

// ---------- UI Rendering Logic ----------

// Init Function to bind events and initial render
function initProcessKB() {
    const selCompany = byId("f_company");
    if (!selCompany) return; // Guard in case connection fails

    // Fill Company Options
    if (selCompany.options.length <= 1) { // Prevent duplicate filling
        companies.forEach(c => {
            const opt = document.createElement("option");
            opt.value = c.company_id;
            opt.textContent = c.company_name;
            selCompany.appendChild(opt);
        });
    }

    // Sort Chips Logic
    const sortChips = document.querySelectorAll('#sort_btns .chip');
    sortChips.forEach(chip => {
        chip.onclick = () => {
            sortChips.forEach(c => c.classList.remove('on'));
            chip.classList.add('on');
            const sortInput = byId('f_sort');
            if (sortInput) sortInput.value = chip.dataset.sort;
            renderKB();
        };
    });

    // Run Button
    const btnRun = byId("btn_run");
    if (btnRun) btnRun.onclick = renderKB;

    // Report Button
    const btnReport = byId("btn_report");
    if (btnReport) {
        btnReport.onclick = exportMatchingReport;
    }

    // Reset Button
    const btnReset = byId("btn_reset");
    if (btnReset) btnReset.onclick = () => {
        selCompany.value = "ALL";
        byId("f_scenario").value = "GENERAL";
        byId("f_process").value = "ALL";
        ["f_part_name", "f_axes", "f_x", "f_y", "f_z", "f_rpm", "f_power", "f_bar", "f_work_d", "f_work_l", "f_accuracy", "f_positioning"].forEach(id => {
            const el = byId(id);
            if (el) el.value = "";
        });
        const sortInput = byId("f_sort");
        if (sortInput) sortInput.value = "SCORE";
        sortChips.forEach(c => c.classList.remove('on'));
        const defaultChip = document.querySelector('.chip[data-sort="SCORE"]');
        if (defaultChip) defaultChip.classList.add('on');

        updateFieldVisibility();
        renderKB();
    };

    const fProcess = byId("f_process");
    if (fProcess) fProcess.addEventListener('change', updateFieldVisibility);

    updateFieldVisibility();
    renderKB(); // Initial render
}

function exportMatchingReport() {
    const q = readQuery();
    const candidates = machines.map(m => {
        const cap = getCap(m.machine_id);
        const ev = scoreMachine(m, cap, q);
        return { m, cap, ...ev };
    });

    const okList = candidates.filter(x => x.ok);
    sortCandidates(okList, q.sort);

    let content = `機台媒合報表\n`;
    content += `==========================\n`;
    content += `目標零件: ${q.partName}\n`;
    content += `應用場景: ${q.scenario}\n`;
    content += `目標需求:\n`;
    content += `  - 重現精度: ${q.accuracy || "未指定"} mm\n`;
    content += `  - 定位精度: ${q.positioning || "未指定"} mm\n`;
    content += `  - 行程需求 (X/Y/Z): ${q.x || "—"} / ${q.y || "—"} / ${q.z || "—"} mm\n`;
    content += `  - 主軸轉速: ${q.rpm || "—"} RPM / ${q.power || "—"} kW\n`;
    content += `==========================\n\n`;

    if (okList.length === 0) {
        content += `無符合條件的推薦機台。\n`;
    } else {
        content += `推薦清單 (共 ${okList.length} 台):\n`;
        okList.forEach((x, i) => {
            const m = x.m;
            content += `${i + 1}. [${m.brand} ${m.model}] (Score: ${x.score})\n`;
            content += `   廠商: ${companyName(m.company_id)}\n`;
            content += `   規格符合度: ${x.capScore}% | 資料信賴度: ${x.confScore}%\n`;
            content += `   推薦理由:\n`;
            x.reasons.forEach(r => {
                // 移除 HTML tag
                const plain = r.replace(/<[^>]*>/g, "").trim();
                content += `     - ${plain}\n`;
            });
            content += `\n`;
        });
    }

    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `Matching_Report_${q.partName}_${new Date().toISOString().slice(0, 10)}.txt`;
    a.click();
    URL.revokeObjectURL(url);

    // 匯出報表的同時，自動將文字報表同步到 AI 的短期記憶中
    syncReportToAI(content);
}

function readQuery() {
    return {
        company: byId("f_company")?.value || "ALL",
        process: byId("f_process")?.value || "ALL",
        scenario: byId("f_scenario")?.value || "GENERAL",
        accuracy: byId("f_accuracy")?.value || "",
        positioning: byId("f_positioning")?.value || "",
        axes: toNum(byId("f_axes")?.value),
        x: toNum(byId("f_x")?.value),
        y: clamp(toNum(byId("f_y")?.value)),
        z: clamp(toNum(byId("f_z")?.value)),
        rpm: clamp(toNum(byId("f_rpm")?.value)),
        power: clamp(toNum(byId("f_power")?.value)),
        bar: clamp(toNum(byId("f_bar")?.value)),
        work_d: clamp(toNum(byId("f_work_d")?.value)),
        work_l: clamp(toNum(byId("f_work_l")?.value)),
        sort: byId("f_sort")?.value || "SCORE",
        partName: byId("f_part_name")?.value || "未命名零件"
    };
}

function renderKB() {
    const q = readQuery();
    const candidates = machines.map(m => {
        const cap = getCap(m.machine_id);
        const ev = scoreMachine(m, cap, q);
        return { m, cap, ...ev };
    });

    const okList = candidates.filter(x => x.ok);
    const badList = candidates.filter(x => !x.ok);
    sortCandidates(okList, q.sort);

    const k_all = byId("k_all"); if (k_all) k_all.textContent = candidates.length;
    const k_ok = byId("k_ok"); if (k_ok) k_ok.textContent = okList.length;
    const k_bad = byId("k_bad"); if (k_bad) k_bad.textContent = badList.length;
    const k_top = byId("k_top"); if (k_top) k_top.textContent = okList.length ? okList[0].score : "—";

    const res = byId("kb-result"); // Renamed to avoid collision with other specific implementation
    if (!res) return;

    res.innerHTML = "";
    okList.forEach((x, idx) => res.appendChild(renderItem(x, idx + 1, true)));

    if (badList.length) {
        const div = document.createElement("div");
        div.className = "muted";
        div.style.marginTop = "10px";
        div.textContent = `以下為被淘汰的候選：`;
        res.appendChild(div);
        badList.slice(0, 10).forEach((x, idx) => res.appendChild(renderItem(x, idx + 1, false)));
        if (badList.length > 10) {
            const more = document.createElement("div");
            more.className = "tiny";
            more.style.marginTop = "6px";
            more.textContent = `（另有 ${badList.length - 10} 筆淘汰結果未顯示）`;
            res.appendChild(more);
        }
    }
}

function renderItem(x, rank, passed) {
    const m = x.m, c = x.cap;
    const ptype = processTypeFromProcessId(m.process_id);
    const comp = companyName(m.company_id);
    const item = document.createElement("div");
    item.className = "item";

    const scoreClass = passed ? (x.score >= 35 ? "score ok" : "score warn") : "score bad";

    // Safety check for standards
    const getStandardText = (stdObj, type) => {
        if (stdObj?.standards) {
            const s = stdObj.standards;
            let out = [];
            if (s.ISO_10791_4 && type === 'rep') out.push(`ISO: ${s.ISO_10791_4.repeatability_mm}mm`);
            if (s.ISO_10791_4 && type === 'pos') out.push(`ISO: ${s.ISO_10791_4.positioning_mm}mm`);
            if (s.JIS_B_6338 && type === 'rep') out.push(`JIS: ±${s.JIS_B_6338.repeatability_mm}mm`);
            if (s.JIS_B_6338 && type === 'pos') out.push(`JIS: ${s.JIS_B_6338.positioning_mm}mm`);
            if (out.length) return out.join(" / ");
        }
        return null;
    }

    const repText = getStandardText(c?.accuracy, 'rep') || (getAccVals(c)?.repeatability_mm != null ? getAccVals(c).repeatability_mm + " mm" : "—");
    const posText = getStandardText(c?.accuracy, 'pos') || (getAccVals(c)?.positioning_mm != null ? getAccVals(c).positioning_mm + " mm" : "—");

    const top = document.createElement("div");
    top.className = "top";
    top.innerHTML = `
        <div>
          <div style="font-weight:800; color: #e2e8f0;">${passed ? `#${rank} ` : ""}${m.brand} ${m.model}</div>
          <div class="tiny">${comp} ｜ ${ptype} </div>
        </div>
        <div style="text-align:right">
            <div class="${scoreClass}">${passed ? `Score ${x.score}` : "Rejected"}</div>
            <div class="tiny" style="margin-top:2px">
                規格: ${x.capScore}% ｜ 信賴: ${x.confScore}%
            </div>
        </div>
    `;
    item.appendChild(top);

    const mid = document.createElement("div");
    mid.className = "mid";

    const rpm = parseRpm(c?.spindle?.speed_max_rpm);
    const axes = c?.axes?.count ?? null;
    const X = getTravel(c, "X"), Y = getTravel(c, "Y"), Z = getTravel(c, "Z");
    const bar = c?.work_envelope?.bar_capacity_mm ?? null;

    mid.innerHTML = `
        <div class="kv"><div>軸數</div><div>${formatVal(axes)}</div></div>
        <div class="kv"><div>行程 X/Y/Z (mm)</div><div>${[X, Y, Z].map(v => v ?? "—").join(" / ")}</div></div>
        <div class="kv"><div>主軸轉速 / 功率</div><div>${c?.spindle?.speed_max_rpm ?? "—"} rpm <span style="color:#d2a8ff">(${c?.spindle?.power_kw ?? "?"} kW)</span></div></div>
        <div class="kv"><div>棒材能力</div><div>${formatVal(bar, " mm")}</div></div>
        <div class="kv"><div>Positioning Rep.</div><div>${repText}</div></div>
        <div class="kv"><div>Positioning Acc.</div><div>${posText}</div></div>
        <div class="kv"><div>資料來源</div><div><a href="${m.source?.url || "#"}" target="_blank" style="color:#60a5fa;text-decoration:none">${m.source?.name || "—"}</a></div></div>
    `;
    item.appendChild(mid);

    const det = document.createElement("details");
    det.innerHTML = `
        <summary>查看推論理由 / 備註</summary>
        <div class="reason">
          ${x.reasons.map(r => `<div>${r}</div>`).join("")}
          ${(!c ? `<div class="bad">✗ 找不到 Capability 記錄</div>` : "")}
          ${(c?.accuracy?.notes ? `<div class="warn">ℹ 精度備註: ${c.accuracy.notes}</div>` : "")}
          ${(c?.axes?.notes ? `<div class="warn">ℹ 軸向備註: ${c.axes.notes}</div>` : "")}
        </div>
    `;
    item.appendChild(det);

    return item;
}

function updateFieldVisibility() {
    const pVal = byId("f_process").value;
    const mills = document.querySelectorAll('.grp-mill');
    const turns = document.querySelectorAll('.grp-turn');

    // Simple logic: if ALL or specific mill, show mill fields. If ALL or turn, show turn fields.
    // Optimization: Hide irrelevant fields to clean UI

    const showMill = (pVal === 'ALL' || pVal.includes('MILL') || pVal === 'VMC_MILLING' || pVal === 'HMC_MILLING' || pVal === 'FIVE_AXIS_MILLING');
    const showTurn = (pVal === 'ALL' || pVal === 'TURNING' || pVal === 'MILL_TURN');

    mills.forEach(el => el.style.display = showMill ? '' : 'none');
    turns.forEach(el => el.style.display = showTurn ? '' : 'none');
}

/**
 * 自動將前端產生的「文字報表」同步到 AI 記憶體中 (報表直接注入法)
 * 呼叫 ai_app.py 的 /api/sync_report 端點
 * @param {string} reportText - 剛生成的機台媒合報表純文字內容
 */
async function syncReportToAI(reportText) {
    try {
        const res = await fetch('http://127.0.0.1:7011/api/sync_report', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reportText: reportText })
        });

        const result = await res.json();
        if (result.ok) {
            console.log(`✅ AI 報表記憶同步成功: ${result.msg}`);
        } else {
            console.warn(`⚠️ AI 報表同步失敗: ${result.msg}`);
        }
    } catch (e) {
        // 靜默失敗 — AI 伺服器可能沒開，不影響主頁功能
        console.warn('⚠️ 無法同步報表到 AI (AI 伺服器可能離線):', e.message);
    }
}
