const form = document.getElementById("queryForm");
const questionInput = document.getElementById("question");
const statusNode = document.getElementById("status");
const chatBody = document.getElementById("chatBody");
const newChatBtn = document.getElementById("newChatBtn");
const deleteHistoryBtn = document.getElementById("deleteHistoryBtn");
const sessionList = document.getElementById("sessionList");
const sendBtn = document.getElementById("sendBtn");
const voiceBtn = document.getElementById("voiceBtn");
const themeSelect = document.getElementById("themeSelect");

const sessionStorageKey = "ai_db_session_id";
const themeStorageKey = "ai_db_theme";
const chartRefs = [];
let currentSessionId = null;

function createSessionId() {
  return (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : `sess_${Date.now()}`;
}

function getOrCreateSessionId() {
  let sessionId = localStorage.getItem(sessionStorageKey);
  if (!sessionId) {
    sessionId = createSessionId();
    localStorage.setItem(sessionStorageKey, sessionId);
  }
  return sessionId;
}

function setCurrentSession(sessionId) {
  currentSessionId = sessionId;
  localStorage.setItem(sessionStorageKey, sessionId);
}

setCurrentSession(getOrCreateSessionId());

function applyTheme(theme) {
  if (theme === "light" || theme === "dark") {
    document.body.setAttribute("data-theme", theme);
  } else {
    document.body.removeAttribute("data-theme");
  }
}

function initTheme() {
  const stored = localStorage.getItem(themeStorageKey) || "system";
  themeSelect.value = stored;
  applyTheme(stored);
  themeSelect.addEventListener("change", () => {
    const chosen = themeSelect.value || "system";
    localStorage.setItem(themeStorageKey, chosen);
    applyTheme(chosen);
  });
}

function setStatus(message) {
  statusNode.textContent = message;
}

async function getErrorMessage(response, fallback) {
  try {
    const data = await response.json();
    return data.detail || data.message || fallback;
  } catch {
    return fallback;
  }
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatColumnLabel(column) {
  const raw = String(column || "").trim();
  if (!raw) return "";

  const lower = raw.toLowerCase();
  if (lower === "id") return "No.";
  if (lower.endsWith("_id")) {
    const entity = lower.slice(0, -3).replace(/_/g, " ");
    return `${entity.replace(/\b\w/g, (m) => m.toUpperCase())} No.`;
  }
  return raw
    .replace(/_/g, " ")
    .replace(/\b\w/g, (m) => m.toUpperCase());
}

function tableHtml(columns, rows) {
  if (!columns || !columns.length) {
    return "<p>No rows returned.</p>";
  }
  const head = `<thead><tr>${columns.map((c) => `<th>${escapeHtml(formatColumnLabel(c))}</th>`).join("")}</tr></thead>`;
  const body = rows.map((r) => {
    const cells = columns.map((c) => `<td>${escapeHtml(r[c] ?? "")}</td>`).join("");
    return `<tr>${cells}</tr>`;
  }).join("");
  return `<table>${head}<tbody>${body}</tbody></table>`;
}

function fileBaseName(prefix = "output") {
  const stamp = new Date().toISOString().replace(/[\:\.]/g, "-");
  return `${prefix}_${stamp}`;
}

function downloadDataUrl(dataUrl, fileName) {
  const a = document.createElement("a");
  a.href = dataUrl;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function exportTableExcel(columns, rows, baseName) {
  if (!columns.length || !rows.length) {
    setStatus("No table data to export.");
    return;
  }
  const ordered = rows.map((r) => {
    const item = {};
    for (const col of columns) item[col] = r[col] ?? "";
    return item;
  });
  const sheet = XLSX.utils.json_to_sheet(ordered, { header: columns });
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, sheet, "Table");
  XLSX.writeFile(wb, `${baseName}.xlsx`);
  setStatus("Table downloaded as Excel.");
}

function exportTablePdf(columns, rows, baseName) {
  if (!columns.length || !rows.length) {
    setStatus("No table data to export.");
    return;
  }
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF({ orientation: "landscape" });
  const body = rows.map((r) => columns.map((c) => String(r[c] ?? "")));
  doc.autoTable({ head: [columns], body, styles: { fontSize: 8 } });
  doc.save(`${baseName}.pdf`);
  setStatus("Table downloaded as PDF.");
}

async function exportTableImage(tableWrapEl, baseName) {
  const tableEl = tableWrapEl.querySelector("table");
  if (!tableEl) {
    setStatus("No table data to export.");
    return;
  }
  const canvas = await html2canvas(tableEl, { backgroundColor: "#ffffff" });
  downloadDataUrl(canvas.toDataURL("image/png"), `${baseName}.png`);
  setStatus("Table downloaded as image.");
}

function exportChartExcel(chart, baseName) {
  if (!chart) {
    setStatus("No chart available to export.");
    return;
  }
  const labels = chart.data.labels || [];
  const firstSeries = (chart.data.datasets || [])[0] || { data: [] };
  const rows = labels.map((label, idx) => ({ label, value: firstSeries.data[idx] ?? null }));
  const sheet = XLSX.utils.json_to_sheet(rows, { header: ["label", "value"] });
  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, sheet, "ChartData");
  XLSX.writeFile(wb, `${baseName}.xlsx`);
  setStatus("Chart data downloaded as Excel.");
}

function exportChartPdf(chart, baseName) {
  if (!chart) {
    setStatus("No chart available to export.");
    return;
  }
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF({ orientation: "landscape" });
  const img = chart.toBase64Image();
  doc.addImage(img, "PNG", 10, 10, 270, 150);
  doc.save(`${baseName}.pdf`);
  setStatus("Chart downloaded as PDF.");
}

function exportChartImage(chart, baseName) {
  if (!chart) {
    setStatus("No chart available to export.");
    return;
  }
  downloadDataUrl(chart.toBase64Image(), `${baseName}.png`);
  setStatus("Chart downloaded as image.");
}

function appendExportControls(node, columns, rows, tableWrap, getChart) {
  const wrap = document.createElement("div");
  wrap.className = "export-wrap";

  const tableLabel = document.createElement("div");
  tableLabel.className = "label";
  tableLabel.textContent = "Download Table:";
  wrap.appendChild(tableLabel);

  const tExcel = document.createElement("button");
  tExcel.type = "button";
  tExcel.className = "export-btn";
  tExcel.textContent = "Excel";
  tExcel.addEventListener("click", () => exportTableExcel(columns, rows, fileBaseName("table")));

  const tPdf = document.createElement("button");
  tPdf.type = "button";
  tPdf.className = "export-btn";
  tPdf.textContent = "PDF";
  tPdf.addEventListener("click", () => exportTablePdf(columns, rows, fileBaseName("table")));

  const tImg = document.createElement("button");
  tImg.type = "button";
  tImg.className = "export-btn";
  tImg.textContent = "Image";
  tImg.addEventListener("click", async () => {
    await exportTableImage(tableWrap, fileBaseName("table"));
  });

  wrap.appendChild(tExcel);
  wrap.appendChild(tPdf);
  wrap.appendChild(tImg);

  const chartLabel = document.createElement("div");
  chartLabel.className = "label";
  chartLabel.textContent = "Download Chart:";
  wrap.appendChild(chartLabel);

  const cExcel = document.createElement("button");
  cExcel.type = "button";
  cExcel.className = "export-btn";
  cExcel.textContent = "Excel";

  const cPdf = document.createElement("button");
  cPdf.type = "button";
  cPdf.className = "export-btn";
  cPdf.textContent = "PDF";

  const cImg = document.createElement("button");
  cImg.type = "button";
  cImg.className = "export-btn";
  cImg.textContent = "Image";

  const graphButtons = [cExcel, cPdf, cImg];
  function updateGraphButtons() {
    const chart = getChart();
    const enabled = Boolean(chart);
    graphButtons.forEach((b) => {
      b.disabled = !enabled;
      b.title = enabled ? "" : "Create or request a chart first";
    });
  }

  cExcel.addEventListener("click", () => exportChartExcel(getChart(), fileBaseName("chart")));
  cPdf.addEventListener("click", () => exportChartPdf(getChart(), fileBaseName("chart")));
  cImg.addEventListener("click", () => exportChartImage(getChart(), fileBaseName("chart")));

  wrap.appendChild(cExcel);
  wrap.appendChild(cPdf);
  wrap.appendChild(cImg);
  node.appendChild(wrap);
  updateGraphButtons();

  return { updateGraphButtons };
}

function appendUserMessage(text) {
  const node = document.createElement("article");
  node.className = "message user";
  node.innerHTML = `<div>${escapeHtml(text)}</div>`;
  chatBody.appendChild(node);
  chatBody.scrollTop = chatBody.scrollHeight;
}

function renderDashboard(node, dashboard) {
  const title = dashboard.title || "Dashboard";
  const desc = dashboard.description || "";
  const kpis = Array.isArray(dashboard.kpis) ? dashboard.kpis : [];
  const charts = Array.isArray(dashboard.charts) ? dashboard.charts : [];

  const root = document.createElement("section");
  root.className = "dashboard-view ref-style";

  const shell = document.createElement("div");
  shell.className = "dashboard-shell";

  const rail = document.createElement("div");
  rail.className = "dashboard-rail";
  rail.innerHTML = `
    <button class="rail-btn active">⌂</button>
    <button class="rail-btn">▦</button>
    <button class="rail-btn">◯</button>
  `;
  shell.appendChild(rail);

  const board = document.createElement("div");
  board.className = "dashboard-board";

  const header = document.createElement("div");
  header.className = "dashboard-header";
  header.innerHTML = `
    <div>
      <h3>${escapeHtml(title)}</h3>
      <p>${escapeHtml(desc)}</p>
    </div>
    <div class="dashboard-tabs">
      <span>Month</span><span>Year</span><span class="active">Total</span>
    </div>
  `;
  board.appendChild(header);

  const kpiGrid = document.createElement("div");
  kpiGrid.className = "dashboard-kpis";
  const kpiSource = kpis.length ? kpis.slice(0, 4) : [
    { label: "Total Value", value: "-", trend: "" },
    { label: "Average", value: "-", trend: "" },
    { label: "Growth %", value: "-", trend: "" },
    { label: "Share %", value: "-", trend: "" },
  ];
  for (const kpi of kpiSource) {
    const card = document.createElement("div");
    card.className = "kpi-card";
    card.innerHTML = `
      <div class="kpi-label">${escapeHtml(kpi.label || "KPI")}</div>
      <div class="kpi-value">${escapeHtml(kpi.value ?? "-")}</div>
      <div class="kpi-trend">${escapeHtml(kpi.trend ?? "")}</div>
    `;
    kpiGrid.appendChild(card);
  }
  board.appendChild(kpiGrid);

  function addChartCard(container, chartSpec, className) {
    const panel = document.createElement("div");
    panel.className = className;
    panel.innerHTML = `<h4>${escapeHtml(chartSpec?.title || "Metric")}</h4>`;
    const canvasWrap = document.createElement("div");
    canvasWrap.className = "dashboard-chart-wrap";
    const canvas = document.createElement("canvas");
    canvasWrap.appendChild(canvas);
    panel.appendChild(canvasWrap);
    container.appendChild(panel);

    const labels = Array.isArray(chartSpec?.labels) ? chartSpec.labels : [];
    const datasets = Array.isArray(chartSpec?.datasets) ? chartSpec.datasets : [];
    if (labels.length && datasets.length) {
      const chart = new Chart(canvas.getContext("2d"), {
        type: chartSpec.type || "bar",
        data: { labels, datasets },
        options: { responsive: true, maintainAspectRatio: false },
      });
      chartRefs.push(chart);
    }
  }

  const midRow = document.createElement("div");
  midRow.className = "dashboard-row mid";
  addChartCard(midRow, charts[0], "dashboard-chart-card small");
  addChartCard(midRow, charts[1], "dashboard-chart-card small");
  addChartCard(midRow, charts[2], "dashboard-chart-card large");
  board.appendChild(midRow);

  const bottomRow = document.createElement("div");
  bottomRow.className = "dashboard-row bottom";
  addChartCard(bottomRow, charts[3], "dashboard-chart-card wide");
  addChartCard(bottomRow, charts[4], "dashboard-chart-card wide");
  board.appendChild(bottomRow);

  shell.appendChild(board);
  root.appendChild(shell);
  node.appendChild(root);
}

function appendAssistantMessage(data) {
  const node = document.createElement("article");
  node.className = "message assistant";

  node.innerHTML = `<div>${escapeHtml(data.summary || "No summary")}</div>`;

  if (data.dashboard) {
    renderDashboard(node, data.dashboard);
  } else {
    node.innerHTML += `<div class="table-wrap">${tableHtml(data.columns || [], data.rows || [])}</div>`;

    let messageChart = null;

    if (data.chart && data.chart.labels && data.chart.datasets) {
      const wrap = document.createElement("div");
      wrap.className = "chart-wrap";
      const canvas = document.createElement("canvas");
      wrap.appendChild(canvas);
      node.appendChild(wrap);
      const chart = new Chart(canvas.getContext("2d"), {
        type: data.chart.type || "bar",
        data: { labels: data.chart.labels, datasets: data.chart.datasets },
        options: { responsive: true, maintainAspectRatio: false },
      });
      chartRefs.push(chart);
      messageChart = chart;
    }

    const tableWrap = node.querySelector(".table-wrap");
    const exportUi = appendExportControls(node, data.columns || [], data.rows || [], tableWrap, () => messageChart);

    if ((data.columns || []).length >= 2 && (data.rows || []).length > 0) {
      appendChartBuilder(node, data.columns || [], data.rows || [], (chart) => {
        messageChart = chart;
        exportUi.updateGraphButtons();
      });
    }
  }

  const created = data.created_at ? new Date(data.created_at).toLocaleString() : "now";
  const footer = document.createElement("div");
  footer.className = "meta";
  footer.textContent = `${created} | ${data.rows?.length ?? 0} row(s)`;
  node.appendChild(footer);

  chatBody.appendChild(node);
  chatBody.scrollTop = chatBody.scrollHeight;
}

function appendChartBuilder(parentNode, columns, rows, onChartReady) {
  const builder = document.createElement("div");
  builder.className = "chart-builder";

  const xSelect = document.createElement("select");
  const y1Select = document.createElement("select");
  const y2Select = document.createElement("select");
  const y3Select = document.createElement("select");
  const typeSelect = document.createElement("select");
  const renderBtn = document.createElement("button");
  renderBtn.type = "button";
  renderBtn.textContent = "Create Chart";

  for (const col of columns) {
    const xOpt = document.createElement("option");
    xOpt.value = col;
    xOpt.textContent = `X: ${formatColumnLabel(col)}`;
    xSelect.appendChild(xOpt);

    const y1Opt = document.createElement("option");
    y1Opt.value = col;
    y1Opt.textContent = `Y1: ${formatColumnLabel(col)}`;
    y1Select.appendChild(y1Opt);

    const y2Opt = document.createElement("option");
    y2Opt.value = col;
    y2Opt.textContent = `Y2: ${formatColumnLabel(col)}`;
    y2Select.appendChild(y2Opt);

    const y3Opt = document.createElement("option");
    y3Opt.value = col;
    y3Opt.textContent = `Y3: ${formatColumnLabel(col)}`;
    y3Select.appendChild(y3Opt);
  }

  const noneOpt2 = document.createElement("option");
  noneOpt2.value = "";
  noneOpt2.textContent = "Y2: (None)";
  y2Select.insertBefore(noneOpt2, y2Select.firstChild);

  const noneOpt3 = document.createElement("option");
  noneOpt3.value = "";
  noneOpt3.textContent = "Y3: (None)";
  y3Select.insertBefore(noneOpt3, y3Select.firstChild);

  for (const type of ["bar", "line"]) {
    const tOpt = document.createElement("option");
    tOpt.value = type;
    tOpt.textContent = type;
    typeSelect.appendChild(tOpt);
  }

  const numericCol = columns.find((c) => rows.some((r) => Number.isFinite(Number(r[c]))));
  if (numericCol) y1Select.value = numericCol;
  if (columns.length > 1 && y1Select.value === xSelect.value) {
    xSelect.value = columns[0];
    y1Select.value = columns[1];
  }
  const otherNumeric = columns.filter((c) => c !== y1Select.value && rows.some((r) => Number.isFinite(Number(r[c]))));
  if (otherNumeric[0]) y2Select.value = otherNumeric[0];
  if (otherNumeric[1]) y3Select.value = otherNumeric[1];

  function buildDatasets(labels, yCols, chartType) {
    const palette = [
      { bg: "rgba(16,185,129,0.35)", border: "rgba(16,185,129,1)" },
      { bg: "rgba(59,130,246,0.35)", border: "rgba(59,130,246,1)" },
      { bg: "rgba(245,158,11,0.35)", border: "rgba(245,158,11,1)" },
    ];
    return yCols.map((yKey, idx) => {
      const colors = palette[idx % palette.length];
      return {
        label: formatColumnLabel(yKey),
        data: rows.map((r) => Number(r[yKey])),
        backgroundColor: colors.bg,
        borderColor: colors.border,
        borderWidth: 1,
        type: chartType,
      };
    });
  }

  const canvasWrap = document.createElement("div");
  canvasWrap.className = "chart-wrap";
  canvasWrap.hidden = true;
  const canvas = document.createElement("canvas");
  canvasWrap.appendChild(canvas);
  let customChart = null;

  renderBtn.addEventListener("click", () => {
    const xKey = xSelect.value;
    const yCols = [y1Select.value, y2Select.value, y3Select.value]
      .filter((v) => v)
      .filter((v, i, arr) => arr.indexOf(v) === i)
      .filter((v) => v !== xKey);

    if (!xKey || yCols.length === 0) {
      setStatus("Choose X and at least one Y column.");
      return;
    }

    const labels = rows.map((r) => String(r[xKey] ?? ""));
    for (const yKey of yCols) {
      const values = rows.map((r) => Number(r[yKey]));
      if (!values.some((v) => Number.isFinite(v))) {
        setStatus(`Selected column ${formatColumnLabel(yKey)} is not numeric.`);
        return;
      }
    }

    if (customChart) {
      customChart.destroy();
      customChart = null;
    }

    canvasWrap.hidden = false;
    customChart = new Chart(canvas.getContext("2d"), {
      type: typeSelect.value || "bar",
      data: {
        labels,
        datasets: buildDatasets(labels, yCols, typeSelect.value || "bar"),
      },
      options: { responsive: true, maintainAspectRatio: false },
    });
    chartRefs.push(customChart);
    if (typeof onChartReady === "function") {
      onChartReady(customChart);
    }
    setStatus(`Custom comparison chart created with ${yCols.length} metric(s).`);
  });

  builder.appendChild(xSelect);
  builder.appendChild(y1Select);
  builder.appendChild(y2Select);
  builder.appendChild(y3Select);
  builder.appendChild(typeSelect);
  builder.appendChild(renderBtn);
  parentNode.appendChild(builder);
  parentNode.appendChild(canvasWrap);
}

function clearCharts() {
  while (chartRefs.length) {
    const chart = chartRefs.pop();
    chart.destroy();
  }
}

async function loadSessionList() {
  try {
    const response = await fetch("/api/sessions");
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not load sessions");

    sessionList.innerHTML = "";
    const sessions = data.sessions || [];
    if (!sessions.length) {
      sessionList.innerHTML = "<p class=\"sidebar-empty\">No saved chats yet.</p>";
      return;
    }

    for (const item of sessions) {
      const row = document.createElement("div");
      row.className = "session-row";
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = `session-item${item.session_id === currentSessionId ? " active" : ""}`;

      const label = item.last_question || "Untitled chat";
      const shortLabel = label.length > 42 ? `${label.slice(0, 42)}...` : label;
      const secondary = `${item.turns} turn(s) | ${new Date(item.last_created_at).toLocaleString()}`;

      btn.innerHTML = `<span class=\"primary\">${escapeHtml(shortLabel)}</span><span class=\"secondary\">${escapeHtml(secondary)}</span>`;
      btn.addEventListener("click", async () => {
        if (item.session_id === currentSessionId) return;
        setCurrentSession(item.session_id);
        await loadHistory();
        await loadSessionList();
      });

      const deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.className = "session-delete";
      deleteBtn.title = "Delete this chat";
      deleteBtn.setAttribute("aria-label", "Delete this chat");
      deleteBtn.textContent = "×";
      deleteBtn.addEventListener("click", async (event) => {
        event.preventDefault();
        event.stopPropagation();
        const ok = window.confirm("Delete this chat permanently?");
        if (!ok) return;
        try {
          const response = await fetch(`/api/history/${encodeURIComponent(item.session_id)}`, { method: "DELETE" });
          if (!response.ok) {
            throw new Error(await getErrorMessage(response, "Could not delete chat"));
          }
          if (item.session_id === currentSessionId) {
            setCurrentSession(createSessionId());
            clearCharts();
            chatBody.innerHTML = "";
          }
          await loadSessionList();
          await loadHistory();
          setStatus("Chat deleted.");
        } catch (error) {
          setStatus(`Delete failed: ${error.message}`);
        }
      });

      row.appendChild(btn);
      row.appendChild(deleteBtn);
      sessionList.appendChild(row);
    }
  } catch (error) {
    setStatus(`Session list error: ${error.message}`);
  }
}

async function loadHistory() {
  setStatus("Loading history...");
  try {
    const response = await fetch(`/api/history/${encodeURIComponent(currentSessionId)}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not load history");

    clearCharts();
    chatBody.innerHTML = "";
    for (const item of data.items || []) {
      appendUserMessage(item.question || "");
      appendAssistantMessage(item);
    }
    setStatus(`Ready. ${data.items?.length ?? 0} turn(s) loaded.`);
  } catch (error) {
    setStatus(`History error: ${error.message}`);
  }
}

async function sendQuestion(question) {
  appendUserMessage(question);
  setStatus("Processing...");
  sendBtn.disabled = true;

  try {
    const response = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, session_id: currentSessionId }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Request failed");

    appendAssistantMessage(data);
    setStatus("Completed.");
    await loadSessionList();
  } catch (error) {
    setStatus(`Error: ${error.message}`);
    appendAssistantMessage({
      summary: `Error: ${error.message}`,
      columns: [],
      rows: [],
      chart: null,
      dashboard: null,
      created_at: new Date().toISOString(),
    });
  } finally {
    sendBtn.disabled = false;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!question) return;
  questionInput.value = "";
  await sendQuestion(question);
});

questionInput.addEventListener("keydown", async (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    const question = questionInput.value.trim();
    if (!question || sendBtn.disabled) return;
    questionInput.value = "";
    await sendQuestion(question);
  }
});

newChatBtn.addEventListener("click", async () => {
  setCurrentSession(createSessionId());
  clearCharts();
  chatBody.innerHTML = "";
  setStatus("New chat started.");
  await loadSessionList();
  questionInput.focus();
});

deleteHistoryBtn.addEventListener("click", async () => {
  const ok = window.confirm("Delete all chat history permanently?");
  if (!ok) return;
  try {
    // Use per-session deletion for maximum compatibility.
    const sessionsRes = await fetch("/api/sessions");
    if (!sessionsRes.ok) {
      throw new Error(await getErrorMessage(sessionsRes, "Could not load sessions"));
    }
    const sessionsData = await sessionsRes.json();
    const sessions = sessionsData.sessions || [];
    for (const s of sessions) {
      await fetch(`/api/history/${encodeURIComponent(s.session_id)}`, { method: "DELETE" });
    }
    setCurrentSession(createSessionId());
    clearCharts();
    chatBody.innerHTML = "";
    await loadSessionList();
    setStatus("All history deleted.");
  } catch (error) {
    setStatus(`Delete history failed: ${error.message}`);
  }
});

function initVoiceInput() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    voiceBtn.disabled = true;
    voiceBtn.title = "Speech recognition not supported in this browser";
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.lang = "en-US";
  recognition.continuous = false;
  recognition.interimResults = true;

  let listening = false;

  recognition.onstart = () => {
    listening = true;
    voiceBtn.classList.add("listening");
    setStatus("Listening...");
  };

  recognition.onresult = (event) => {
    let transcript = "";
    for (let i = event.resultIndex; i < event.results.length; i += 1) {
      transcript += event.results[i][0].transcript;
    }
    questionInput.value = transcript.trim();
  };

  recognition.onerror = () => {
    setStatus("Voice input error.");
  };

  recognition.onend = () => {
    listening = false;
    voiceBtn.classList.remove("listening");
    setStatus("Ready.");
  };

  voiceBtn.addEventListener("click", () => {
    if (!listening) {
      recognition.start();
    } else {
      recognition.stop();
    }
  });
}

initTheme();
initVoiceInput();
loadHistory();
loadSessionList();
