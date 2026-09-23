/* LogLens dashboard — vanilla JS, hand-rolled Canvas chart. */

let lens = null;
let rawEntries = null;

// ---- tabs ----
document.querySelectorAll(".tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "timeline" && lens) drawTimeline();
  });
});

// ---- data loading ----
async function load() {
  try {
    const res = await fetch("/api/lens");
    lens = await res.json();
    renderSummary();
    renderLevels();
    renderClusters();
    renderErrors();
    renderAnomalies();
    drawTimeline();
    const raw = await fetch("/api/raw?limit=300");
    rawEntries = await raw.json();
    renderRaw();
  } catch (e) {
    console.error(e);
  }
}

function renderSummary() {
  const s = lens.summary;
  document.getElementById("k-lines").textContent = s.total_lines;
  document.getElementById("k-errors").textContent = s.error_count;
  document.getElementById("k-warns").textContent = s.warning_count;
  document.getElementById("k-events").textContent = s.unique_templates;
  document.getElementById("k-rate").textContent = (s.error_rate * 100).toFixed(1) + "%";
  const tr = lens.time_range;
  document.getElementById("k-range").textContent =
    tr.first ? tr.first.slice(0, 16) + " → " + tr.last.slice(0, 16) : "no timestamps";
}

function renderLevels() {
  const wrap = document.getElementById("levels-bars");
  const levels = lens.levels;
  const max = Math.max(...Object.values(levels), 1);
  const colors = { ERROR: "#f85149", CRITICAL: "#f85149", WARNING: "#d29922",
                   INFO: "#58a6ff", DEBUG: "#8957e5", TRACE: "#8957e5" };
  wrap.innerHTML = Object.entries(levels)
    .sort((a, b) => b[1] - a[1])
    .map(([lvl, n]) => `
      <div class="bar-row">
        <div class="bar-label">${lvl}</div>
        <div class="bar-track"><div class="bar-fill" style="width:${(n/max*100).toFixed(1)}%;background:${colors[lvl]||'#58a6ff'}"></div></div>
        <div class="bar-count">${n}</div>
      </div>`).join("");
}

function renderClusters() {
  const tbody = document.querySelector("#clusters-table tbody");
  tbody.innerHTML = lens.clusters.map((c, i) => `
    <tr>
      <td>${i + 1}</td>
      <td><b>${c.count}</b></td>
      <td><span class="level-badge level-${c.dominant_level}">${c.dominant_level}</span></td>
      <td class="template-cell">${esc(c.template)}</td>
      <td class="sample-cell">${esc(c.sample)}</td>
    </tr>`).join("");
}

function renderErrors() {
  const tbody = document.querySelector("#errors-table tbody");
  if (!lens.top_errors.length) {
    tbody.innerHTML = '<tr><td colspan="5" style="color:var(--muted);padding:20px">No errors found.</td></tr>';
    return;
  }
  tbody.innerHTML = lens.top_errors.map((c, i) => `
    <tr>
      <td>${i + 1}</td>
      <td><b>${c.count}</b></td>
      <td><span class="level-badge level-${c.dominant_level}">${c.dominant_level}</span></td>
      <td class="template-cell">${esc(c.template)}</td>
      <td class="sample-cell">${esc(c.sample)}</td>
    </tr>`).join("");
}

function renderAnomalies() {
  const wrap = document.getElementById("anomalies-list");
  if (!lens.anomalies.length) {
    wrap.innerHTML = '<div style="color:var(--muted);padding:20px">No anomalies detected.</div>';
    return;
  }
  wrap.innerHTML = lens.anomalies.map(a => `
    <div class="anomaly">
      <div class="time">⚠ ${a.time}</div>
      <div class="meta">count=${a.count} · expected≈${a.expected} · z-score=${a.zscore} · errors=${a.error}</div>
    </div>`).join("");
}

function renderRaw() {
  const tbody = document.querySelector("#raw-table tbody");
  tbody.innerHTML = rawEntries.map(e => `
    <tr>
      <td>${e.line}</td>
      <td style="font-size:11px;color:var(--muted)">${e.time ? e.time.slice(0,19) : "–"}</td>
      <td><span class="level-badge level-${e.level}">${e.level}</span></td>
      <td style="font-size:12px">${esc(e.source)}</td>
      <td class="sample-cell">${esc(e.message)}</td>
    </tr>`).join("");
}

// ---- Canvas timeline chart ----
function drawTimeline() {
  const canvas = document.getElementById("chart-timeline");
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  const W = rect.width, H = rect.height;
  ctx.clearRect(0, 0, W, H);

  const data = lens.timeline;
  if (!data.length) {
    ctx.fillStyle = "#8b949e";
    ctx.font = "14px sans-serif";
    ctx.fillText("No timestamped entries to plot.", 20, 30);
    return;
  }

  const padL = 50, padR = 20, padT = 20, padB = 40;
  const plotW = W - padL - padR, plotH = H - padT - padB;
  const maxVal = Math.max(...data.map(d => d.total), 1);

  // grid
  ctx.strokeStyle = "#21262d";
  ctx.lineWidth = 1;
  ctx.fillStyle = "#8b949e";
  ctx.font = "11px sans-serif";
  for (let i = 0; i <= 4; i++) {
    const y = padT + plotH - (plotH * i / 4);
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(W - padR, y);
    ctx.stroke();
    ctx.fillText(Math.round(maxVal * i / 4), 8, y + 4);
  }

  // x labels (first, middle, last)
  const xLabels = [0, Math.floor(data.length / 2), data.length - 1];
  xLabels.forEach(i => {
    const x = padL + (plotW * i / (data.length - 1 || 1));
    const label = data[i].time.slice(5, 16); // MM-DD HH:MM
    ctx.fillText(label, x - 25, H - 12);
  });

  const barW = Math.max(1, plotW / data.length - 1);

  // stacked bars: info (bottom), warning, error (top)
  for (let i = 0; i < data.length; i++) {
    const x = padL + (plotW * i / (data.length - 1 || 1)) - barW / 2;
    const d = data[i];
    let yCursor = padT + plotH;

    // info
    if (d.info) {
      const h = plotH * d.info / maxVal;
      ctx.fillStyle = "rgba(88,166,255,0.5)";
      ctx.fillRect(x, yCursor - h, barW, h);
      yCursor -= h;
    }
    // warning
    if (d.warning) {
      const h = plotH * d.warning / maxVal;
      ctx.fillStyle = "rgba(210,153,34,0.7)";
      ctx.fillRect(x, yCursor - h, barW, h);
      yCursor -= h;
    }
    // error
    if (d.error) {
      const h = plotH * d.error / maxVal;
      ctx.fillStyle = "rgba(248,81,73,0.85)";
      ctx.fillRect(x, yCursor - h, barW, h);
    }
  }

  // total line
  ctx.strokeStyle = "#58a6ff";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  for (let i = 0; i < data.length; i++) {
    const x = padL + (plotW * i / (data.length - 1 || 1));
    const y = padT + plotH - (plotH * data[i].total / maxVal);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // anomaly markers
  const anomTimes = new Set(lens.anomalies.map(a => a.time));
  ctx.fillStyle = "#f85149";
  for (let i = 0; i < data.length; i++) {
    if (anomTimes.has(data[i].time)) {
      const x = padL + (plotW * i / (data.length - 1 || 1));
      ctx.beginPath();
      ctx.arc(x, padT + 6, 4, 0, Math.PI * 2);
      ctx.fill();
    }
  }
}

function esc(s) {
  const div = document.createElement("div");
  div.textContent = s == null ? "" : String(s);
  return div.innerHTML;
}

window.addEventListener("resize", () => { if (lens) drawTimeline(); });
load();
