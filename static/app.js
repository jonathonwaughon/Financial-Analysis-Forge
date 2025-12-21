/*
File name: app.js
Created: 12/21/2025 04:38 PM
Purpose: Frontend helpers for parsing + rendering tables
Notes:
- Uses websocket for progress and REST APIs for data
Used: Yes
*/

let ws = null;

function connectProgressWS() {
    const log = document.getElementById("progressLog");
    const statusText = document.getElementById("statusText");

    if (!log) {
        return;
    }

    const proto = (location.protocol === "https:") ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws/progress`);

    ws.onmessage = (ev) => {
        const msg = ev.data || "";

        if (statusText) {
            statusText.textContent = msg;
        }

        log.textContent += msg + "\n";
        log.scrollTop = log.scrollHeight;

        // 🔥 Key: auto-refresh when parsing finishes
        const lower = msg.toLowerCase();
        if (lower.includes("parse complete") || lower.includes("income statement parsing done")) {
            loadIncomeStatementDetails();
            loadIncomeStatementPeriods();
        }
    };

    ws.onclose = () => {
        log.textContent += "[progress websocket disconnected]\n";
    };
}


async function startParse() {
    const res = await fetch("/api/parse", { method: "POST" });
    const data = await res.json();

    if (!data.ok) {
        alert(data.error || "Parse failed to start.");
        return;
    }

    // No fixed delay — websocket will trigger refresh on "Parse complete"
}


function renderTable(containerId, columns, rows) {
    const container = document.getElementById(containerId);
    if (!container) {
        return;
    }

    if (!columns || columns.length === 0) {
        container.innerHTML = "<div class='muted'>No data.</div>";
        return;
    }

    let html = "<table class='table'><thead><tr>";
    for (const c of columns) {
        html += `<th>${escapeHtml(String(c))}</th>`;
    }
    html += "</tr></thead><tbody>";

    for (const r of rows) {
        html += "<tr>";
        for (const c of columns) {
            const v = (r[c] === null || r[c] === undefined) ? "" : String(r[c]);
            html += `<td>${escapeHtml(v)}</td>`;
        }
        html += "</tr>";
    }

    html += "</tbody></table>";
    container.innerHTML = html;
}

function escapeHtml(s) {
    return s
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

async function loadIncomeStatementDetails() {
    const container = document.getElementById("detailsTable");
    if (!container) {
        return;
    }

    const res = await fetch("/api/income-statement/details");
    const data = await res.json();

    if (!data.ok) {
        container.innerHTML = "<div class='muted'>Failed to load details.</div>";
        return;
    }

    renderTable("detailsTable", data.columns, data.rows);
}

async function loadIncomeStatementPeriods() {
    const sel = document.getElementById("periodSelect");
    if (!sel) {
        return;
    }

    const res = await fetch("/api/income-statement/periods");
    const data = await res.json();

    sel.innerHTML = "";

    const periods = (data && data.periods) ? data.periods : [];
   if (periods.length === 0) {
        const opt = document.createElement("option");
        opt.value = "";
        opt.textContent = "No periods yet (click Parse / Refresh)";
        sel.appendChild(opt);
        renderTable("dataTable", [], []);
        return;
    }


    for (const p of periods) {
        const opt = document.createElement("option");
        opt.value = p;
        opt.textContent = p;
        sel.appendChild(opt);
    }

    // Default = first (most recent)
    sel.value = periods[0];
    await loadIncomeStatementForSelectedPeriod();
}

function renderMetrics(metrics) {
    const row = document.getElementById("metricsRow");
    if (!row) {
        return;
    }

    row.innerHTML = "";

    const keys = Object.keys(metrics || {});
    if (keys.length === 0) {
        row.innerHTML = "<div class='muted'>No metrics available.</div>";
        return;
    }

    for (const k of keys) {
        const v = metrics[k];
        const display = (v === null || v === undefined || v === "") ? "—" : String(v);

        const div = document.createElement("div");
        div.className = "metric-card";
        div.innerHTML = `
            <div class="metric-name">${escapeHtml(k)}</div>
            <div class="metric-value">${escapeHtml(display)}</div>
        `;
        row.appendChild(div);
    }
}

async function loadIncomeStatementMetrics(period) {
    const res = await fetch(`/api/income-statement/metrics?period=${encodeURIComponent(period)}`);
    const data = await res.json();

    if (!data.ok) {
        renderMetrics({});
        return;
    }

    renderMetrics(data.metrics || {});
}






async function loadIncomeStatementForSelectedPeriod() {
    const sel = document.getElementById("periodSelect");
    if (!sel) {
        return;
    }

    const period = sel.value;
    if (!period) {
        renderTable("dataTable", [], []);
        renderMetrics({});
        return;
    }

    // Metrics first (feels nice)
    await loadIncomeStatementMetrics(period);

    // Then the full statement table for that period
    const res = await fetch(`/api/income-statement/data?period=${encodeURIComponent(period)}`);
    const data = await res.json();

    if (!data.ok) {
        renderTable("dataTable", [], []);
        return;
    }

    renderTable("dataTable", data.columns, data.rows);
}

