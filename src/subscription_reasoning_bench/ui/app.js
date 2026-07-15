const state = { summary: { configs: [], paired: [], total_runs: 0 }, sort: "accuracy", filter: "", signature: "" };

const el = (id) => document.getElementById(id);
const pct = (value) => `${(100 * value).toFixed(1)}%`;
const seconds = (ms) => `${(ms / 1000).toFixed(1)}s`;
const signedPct = (value) => `${value >= 0 ? "+" : ""}${(100 * value).toFixed(1)} pp`;

function filteredRows() {
  const needle = state.filter.toLowerCase();
  const rows = state.summary.configs.filter((row) => row.label.toLowerCase().includes(needle));
  const key = state.sort;
  return rows.sort((a, b) => {
    if (key === "latency") return a.latency_p50_ms - b.latency_p50_ms;
    if (key === "turns") return b.native_turns_mean - a.native_turns_mean;
    return b.end_to_end_accuracy - a.end_to_end_accuracy;
  });
}

function renderMetrics() {
  const rows = state.summary.configs;
  el("total-runs").textContent = state.summary.total_runs.toLocaleString();
  el("config-count").textContent = rows.length.toString();
  el("best-accuracy").textContent = rows.length ? pct(Math.max(...rows.map((r) => r.end_to_end_accuracy))) : "—";
  el("fastest-latency").textContent = rows.length ? seconds(Math.min(...rows.map((r) => r.latency_p50_ms))) : "—";
}

function renderChart() {
  const rows = filteredRows().slice(0, 16);
  const chart = el("comparison-chart");
  chart.innerHTML = "";
  if (!rows.length) return;
  const maxLatency = Math.max(...rows.map((r) => r.latency_p50_ms), 1);
  const maxTurns = Math.max(...rows.map((r) => r.native_turns_mean), 1);
  rows.forEach((row) => {
    const metric = state.sort === "latency" ? row.latency_p50_ms / maxLatency : state.sort === "turns" ? row.native_turns_mean / maxTurns : row.end_to_end_accuracy;
    const value = state.sort === "latency" ? seconds(row.latency_p50_ms) : state.sort === "turns" ? row.native_turns_mean.toFixed(2) : pct(row.end_to_end_accuracy);
    const div = document.createElement("div");
    div.className = "bar-row";
    div.innerHTML = `<div class="bar-label" title="${row.label}">${row.label}</div><div class="bar-track"><div class="bar-fill ${state.sort}" style="width:${Math.max(0.5, 100 * metric)}%"></div></div><div class="bar-value">${value}</div>`;
    chart.appendChild(div);
  });
}

function renderTable() {
  const rows = filteredRows();
  el("empty-state").hidden = state.summary.configs.length !== 0;
  el("result-table").innerHTML = rows.map((row) => {
    const ci = row.accuracy_ci95 ? `${pct(row.accuracy_ci95[0])}–${pct(row.accuracy_ci95[1])}` : "—";
    return `<tr><td title="${row.label}">${row.label}</td><td>${row.completed}/${row.runs}</td><td><span class="pill">${pct(row.end_to_end_accuracy)}</span></td><td>${ci}</td><td>${seconds(row.latency_p50_ms)}</td><td>${row.native_turns_mean.toFixed(2)}</td><td>${row.subagent_calls}</td><td><span class="pill ${row.protocol_violations ? "warn" : ""}">${row.protocol_violations}</span></td></tr>`;
  }).join("");
}

function renderPairs() {
  const pairs = state.summary.paired.slice().sort((a, b) => Math.abs(b.accuracy_delta_right_minus_left) - Math.abs(a.accuracy_delta_right_minus_left)).slice(0, 12);
  el("paired-list").innerHTML = pairs.length ? pairs.map((pair) => {
    const ci = pair.delta_ci95 ? `[${signedPct(pair.delta_ci95[0])}, ${signedPct(pair.delta_ci95[1])}]` : "";
    return `<article class="pair"><p>${pair.right}<br>minus<br>${pair.left}</p><strong>${signedPct(pair.accuracy_delta_right_minus_left)}</strong><small>n=${pair.n} ${ci}</small></article>`;
  }).join("") : `<div class="empty"><strong>需要至少两个配置</strong><p>paired delta 会按 task + attempt 自动对齐。</p></div>`;
}

function render() { renderMetrics(); renderChart(); renderTable(); renderPairs(); }

async function load() {
  try {
    const response = await fetch("/api/summary", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const nextSummary = await response.json();
    const nextSignature = JSON.stringify(nextSummary);
    if (nextSignature !== state.signature) {
      state.summary = nextSummary;
      state.signature = nextSignature;
      render();
    }
    el("status").className = "status ready";
    el("status").innerHTML = "<i></i> 本地结果已同步";
  } catch (error) {
    el("status").className = "status error";
    el("status").innerHTML = `<i></i> 读取失败：${error.message}`;
  }
}

el("sort-select").addEventListener("change", (event) => { state.sort = event.target.value; renderChart(); });
el("filter").addEventListener("input", (event) => { state.filter = event.target.value; renderChart(); renderTable(); });
load();
setInterval(load, 10000);
