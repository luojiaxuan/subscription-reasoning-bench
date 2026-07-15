const state = {
  summary: { configs: [], paired: [], total_runs: 0 },
  research: { configs: [], total_runs: 0, config_count: 0 },
  sort: "accuracy",
  filter: "",
  summarySignature: "",
  researchSignature: "",
};

const colors = ["#0b776d", "#dd6b42", "#173f55", "#8d5a97", "#a77a17", "#46754b", "#b94c63", "#607d8b"];
const el = (id) => document.getElementById(id);
const pct = (value) => value == null ? "—" : `${(100 * value).toFixed(1)}%`;
const seconds = (ms) => ms == null ? "—" : `${(ms / 1000).toFixed(1)}s`;
const number = (value, digits = 2) => value == null ? "—" : Number(value).toFixed(digits);
const roundNumber = (value) => value == null ? "—" : Number(value).toFixed(1);
const signedPct = (value) => `${value >= 0 ? "+" : ""}${(100 * value).toFixed(1)} pp`;
const escapeHtml = (value) => String(value).replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
})[character]);

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
  el("best-accuracy").textContent = rows.length ? pct(Math.max(...rows.map((row) => row.end_to_end_accuracy))) : "—";
  el("fastest-latency").textContent = rows.length ? seconds(Math.min(...rows.map((row) => row.latency_p50_ms))) : "—";
}

function renderChart() {
  const rows = filteredRows().slice(0, 16);
  const chart = el("comparison-chart");
  chart.innerHTML = "";
  if (!rows.length) return;
  const maxLatency = Math.max(...rows.map((row) => row.latency_p50_ms), 1);
  const maxTurns = Math.max(...rows.map((row) => row.native_turns_mean), 1);
  rows.forEach((row) => {
    const metric = state.sort === "latency" ? row.latency_p50_ms / maxLatency : state.sort === "turns" ? row.native_turns_mean / maxTurns : row.end_to_end_accuracy;
    const value = state.sort === "latency" ? seconds(row.latency_p50_ms) : state.sort === "turns" ? row.native_turns_mean.toFixed(2) : pct(row.end_to_end_accuracy);
    const div = document.createElement("div");
    div.className = "bar-row";
    div.innerHTML = `<div class="bar-label" title="${escapeHtml(row.label)}">${escapeHtml(row.label)}</div><div class="bar-track"><div class="bar-fill ${state.sort}" style="width:${Math.max(0.5, 100 * metric)}%"></div></div><div class="bar-value">${value}</div>`;
    chart.appendChild(div);
  });
}

function renderTable() {
  const rows = filteredRows();
  el("empty-state").hidden = state.summary.configs.length !== 0;
  el("result-table").innerHTML = rows.map((row) => {
    const ci = row.accuracy_ci95 ? `${pct(row.accuracy_ci95[0])}–${pct(row.accuracy_ci95[1])}` : "—";
    return `<tr><td title="${escapeHtml(row.label)}">${escapeHtml(row.label)}</td><td>${row.completed}/${row.runs}</td><td><span class="pill">${pct(row.end_to_end_accuracy)}</span></td><td>${ci}</td><td>${seconds(row.latency_p50_ms)}</td><td>${row.native_turns_mean.toFixed(2)}</td><td>${row.subagent_calls}</td><td><span class="pill ${row.protocol_violations ? "warn" : ""}">${row.protocol_violations}</span></td></tr>`;
  }).join("");
}

function renderPairs() {
  const pairs = state.summary.paired.slice().sort((a, b) => Math.abs(b.accuracy_delta_right_minus_left) - Math.abs(a.accuracy_delta_right_minus_left)).slice(0, 12);
  el("paired-list").innerHTML = pairs.length ? pairs.map((pair) => {
    const ci = pair.delta_ci95 ? `[${signedPct(pair.delta_ci95[0])}, ${signedPct(pair.delta_ci95[1])}]` : "";
    return `<article class="pair"><p>${escapeHtml(pair.right)}<br>minus<br>${escapeHtml(pair.left)}</p><strong>${signedPct(pair.accuracy_delta_right_minus_left)}</strong><small>n=${pair.n} ${ci}</small></article>`;
  }).join("") : `<div class="empty"><strong>需要至少两个配置</strong><p>paired delta 会按 task + attempt 自动对齐。</p></div>`;
}

function svgNode(name, attributes = {}, text = "") {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
  if (text) node.textContent = text;
  return node;
}

function renderResearchMetrics() {
  const rows = state.research.configs;
  const improvements = rows.map((row) => row.normalized_improvement_mean).filter((value) => value != null);
  const totalRuns = state.research.total_runs;
  const reached = rows.reduce((sum, row) => sum + row.target_reach_rate * row.runs, 0);
  el("research-runs").textContent = totalRuns.toLocaleString();
  el("research-configs").textContent = state.research.config_count.toString();
  el("research-best-gain").textContent = improvements.length ? pct(Math.max(...improvements)) : "—";
  el("research-target-rate").textContent = totalRuns ? pct(reached / totalRuns) : "—";
}

function renderResearchChart() {
  const rows = state.research.configs.filter((row) => row.curve && row.curve.length);
  const chart = el("research-chart");
  const legend = el("research-legend");
  chart.innerHTML = "";
  legend.innerHTML = "";
  el("research-empty").hidden = rows.length !== 0;
  if (!rows.length) return;

  const width = 940;
  const height = 360;
  const margin = { top: 22, right: 24, bottom: 48, left: 64 };
  const points = rows.flatMap((row) => row.curve);
  const minRound = Math.min(...points.map((point) => point.round_index));
  const maxRound = Math.max(...points.map((point) => point.round_index));
  let minScore = Math.min(...points.map((point) => point.score_mean));
  let maxScore = Math.max(...points.map((point) => point.score_mean));
  if (minScore === maxScore) { minScore -= 0.5; maxScore += 0.5; }
  const scorePadding = (maxScore - minScore) * 0.08;
  minScore -= scorePadding;
  maxScore += scorePadding;
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;
  const x = (roundIndex) => margin.left + ((roundIndex - minRound) / Math.max(1, maxRound - minRound)) * innerWidth;
  const y = (score) => margin.top + (1 - (score - minScore) / (maxScore - minScore)) * innerHeight;
  const svg = svgNode("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "各模型配置随研究轮次变化的平均得分曲线" });

  for (let index = 0; index <= 4; index += 1) {
    const value = minScore + ((maxScore - minScore) * index) / 4;
    const yPosition = y(value);
    svg.appendChild(svgNode("line", { x1: margin.left, x2: width - margin.right, y1: yPosition, y2: yPosition, class: "grid-line" }));
    svg.appendChild(svgNode("text", { x: margin.left - 10, y: yPosition + 4, class: "axis-label", "text-anchor": "end" }, value.toFixed(2)));
  }

  const xTickCount = Math.min(8, Math.max(1, maxRound - minRound));
  const renderedTicks = new Set();
  for (let index = 0; index <= xTickCount; index += 1) {
    const value = Math.round(minRound + ((maxRound - minRound) * index) / xTickCount);
    if (renderedTicks.has(value)) continue;
    renderedTicks.add(value);
    svg.appendChild(svgNode("text", { x: x(value), y: height - 17, class: "axis-label", "text-anchor": "middle" }, value.toString()));
  }
  svg.appendChild(svgNode("text", { x: margin.left + innerWidth / 2, y: height - 2, class: "axis-title", "text-anchor": "middle" }, "research round"));

  rows.forEach((row, index) => {
    const color = colors[index % colors.length];
    const polyline = svgNode("polyline", {
      points: row.curve.map((point) => `${x(point.round_index)},${y(point.score_mean)}`).join(" "),
      fill: "none",
      stroke: color,
      "stroke-width": 3,
      "stroke-linecap": "round",
      "stroke-linejoin": "round",
    });
    svg.appendChild(polyline);
    row.curve.forEach((point) => {
      const circle = svgNode("circle", { cx: x(point.round_index), cy: y(point.score_mean), r: 3.8, fill: color, class: "curve-point" });
      circle.appendChild(svgNode("title", {}, `${row.label} · round ${point.round_index} · score ${point.score_mean.toFixed(3)} · n=${point.n}`));
      svg.appendChild(circle);
    });
    const item = document.createElement("span");
    const swatch = document.createElement("i");
    swatch.style.background = color;
    item.appendChild(swatch);
    item.appendChild(document.createTextNode(row.label));
    legend.appendChild(item);
  });
  chart.appendChild(svg);
}

function renderResearchTable() {
  el("research-table").innerHTML = state.research.configs.map((row) => (
    `<tr><td title="${escapeHtml(row.label)}">${escapeHtml(row.label)}</td><td>${row.completed}/${row.runs}</td><td>${number(row.final_score_mean, 3)}</td><td><span class="pill research-gain">${pct(row.normalized_improvement_mean)}</span></td><td>${number(row.auc_over_rounds_mean, 3)}</td><td>${roundNumber(row.first_improvement_round_mean)}</td><td>${roundNumber(row.best_improvement_round_mean)}</td><td>${pct(row.late_gain_fraction_mean)}</td><td>${pct(row.target_reach_rate)}</td><td><span class="pill ${row.early_termination_rate ? "warn" : ""}">${pct(row.early_termination_rate)}</span></td><td>${number(row.total_native_turns_mean, 1)}</td><td>${number(row.total_tool_calls_mean, 1)}</td><td>${number(row.total_subagent_calls_mean, 1)}</td></tr>`
  )).join("");
}

function renderShort() { renderMetrics(); renderChart(); renderTable(); renderPairs(); }
function renderResearch() { renderResearchMetrics(); renderResearchChart(); renderResearchTable(); }

async function load() {
  try {
    const [summaryResponse, researchResponse] = await Promise.all([
      fetch("/api/summary", { cache: "no-store" }),
      fetch("/api/research-summary", { cache: "no-store" }),
    ]);
    if (!summaryResponse.ok) throw new Error(`summary HTTP ${summaryResponse.status}`);
    if (!researchResponse.ok) throw new Error(`research HTTP ${researchResponse.status}`);
    const [nextSummary, nextResearch] = await Promise.all([summaryResponse.json(), researchResponse.json()]);
    const nextSummarySignature = JSON.stringify(nextSummary);
    const nextResearchSignature = JSON.stringify(nextResearch);
    if (nextSummarySignature !== state.summarySignature) {
      state.summary = nextSummary;
      state.summarySignature = nextSummarySignature;
      renderShort();
    }
    if (nextResearchSignature !== state.researchSignature) {
      state.research = nextResearch;
      state.researchSignature = nextResearchSignature;
      renderResearch();
    }
    el("status").className = "status ready";
    el("status").innerHTML = "<i></i> 本地结果已同步";
  } catch (error) {
    el("status").className = "status error";
    el("status").innerHTML = `<i></i> 读取失败：${escapeHtml(error.message)}`;
  }
}

el("sort-select").addEventListener("change", (event) => { state.sort = event.target.value; renderChart(); });
el("filter").addEventListener("input", (event) => { state.filter = event.target.value; renderChart(); renderTable(); });
load();
setInterval(load, 10000);
