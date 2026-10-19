// Client-side port of Pitching_Metrics.py's summarize_pitch_types() and
// compare_shapes_to_mlb(), so the dashboard runs entirely in the browser
// (no server needed - suitable for GitHub Pages).

function mean(arr) {
  return arr.reduce((a, b) => a + b, 0) / arr.length;
}
function max(arr) {
  return Math.max(...arr);
}

// Mirrors PitchingMetrics.summarize_pitch_types(): groups by PitchType and
// computes mean velocity, max velocity, mean spin rate, mean vertical break,
// mean horizontal break.
function summarizePitchTypes(rows) {
  const groups = {};
  for (const row of rows) {
    if (!groups[row.pitchType]) groups[row.pitchType] = [];
    groups[row.pitchType].push(row);
  }
  const summary = {};
  for (const [pitchType, group] of Object.entries(groups)) {
    summary[pitchType] = {
      velocityAvg: round2(mean(group.map((r) => r.velocity))),
      velocityMax: round2(max(group.map((r) => r.velocity))),
      spinAvg: round2(mean(group.map((r) => r.spinRate))),
      ivbAvg: round2(mean(group.map((r) => r.verticalBreak))),
      hbAvg: round2(mean(group.map((r) => r.horizontalBreak))),
    };
  }
  return summary;
}

function round2(n) {
  return Math.round(n * 100) / 100;
}

// Mirrors PitchingMetrics.compare_shapes_to_mlb(): for each of the user's
// pitch types, finds the MLB pitch with the closest shape (IVB + HB), with
// MLB horizontal break re-aligned to a right-handed frame (GLV = glove side,
// negative; ARM = arm side, positive; then flipped for lefties).
function compareShapesToMLB(summary, mlbData) {
  const results = [];

  for (const [yourPitch, stats] of Object.entries(summary)) {
    const ivbUser = stats.ivbAvg;
    const hbUser = stats.hbAvg;

    let bestDiff = Infinity;
    let bestMatch = null;

    for (const row of mlbData) {
      const ivbMlb = row.vertical;
      const raw = row.horizontalRaw.trim().toUpperCase();

      let hbMlb;
      if (raw.endsWith("GLV")) {
        hbMlb = -parseFloat(raw.replace("GLV", "").trim());
      } else if (raw.endsWith("ARM")) {
        hbMlb = parseFloat(raw.replace("ARM", "").trim());
      } else {
        const parsed = parseFloat(raw);
        if (Number.isNaN(parsed)) continue;
        hbMlb = parsed;
      }

      let hbMlbAligned = hbMlb;
      if (row.hand.trim().toUpperCase() === "L") {
        hbMlbAligned *= -1;
      }

      const shapeDiff = Math.abs(ivbUser - ivbMlb) + Math.abs(hbUser - hbMlbAligned);

      if (shapeDiff < bestDiff) {
        bestDiff = shapeDiff;
        bestMatch = {
          yourPitch,
          player: row.player,
          mlbPitch: row.pitch,
          ivb: round2(ivbMlb),
          hb: round2(hbMlbAligned),
          diff: round2(shapeDiff),
        };
      }
    }

    if (bestMatch) results.push(bestMatch);
  }

  return results;
}

function playerKeyFromCsvName(name) {
  const trimmed = name.trim();
  if (trimmed.includes(",")) {
    const [last, first] = trimmed.split(",").map((s) => s.trim());
    return `${first} ${last}`;
  }
  return trimmed;
}

function filterByDateRange(rows, startDate, endDate) {
  if (!startDate && !endDate) return rows;
  return rows.filter((row) => {
    const d = new Date(row.date);
    if (startDate && d < new Date(startDate)) return false;
    if (endDate && d > new Date(endDate)) return false;
    return true;
  });
}

const PITCH_COLORS = {
  Fastball: "#1f77b4",
  Curveball: "#ff7f0e",
  Slider: "#2ca02c",
  Changeup: "#d62728",
  Sinker: "#9467bd",
  Cutter: "#8c564b",
};
function colorFor(pitchType, index) {
  if (PITCH_COLORS[pitchType]) return PITCH_COLORS[pitchType];
  const palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"];
  return palette[index % palette.length];
}

let chartInstance = null;

function renderDashboard() {
  const pitcher = document.getElementById("pitcher").value;
  const startDate = document.getElementById("start_date").value;
  const endDate = document.getElementById("end_date").value;

  const allRows = PITCHER_DATA[pitcher] || [];
  const errorBox = document.getElementById("error-box");
  const dashboard = document.getElementById("dashboard");

  if (allRows.length === 0) {
    errorBox.style.display = "block";
    errorBox.innerHTML = `<h2>No data found for '${pitcher}' yet.</h2>`;
    dashboard.style.display = "none";
    return;
  }

  const rows = filterByDateRange(allRows, startDate, endDate);
  if (rows.length === 0) {
    errorBox.style.display = "block";
    errorBox.innerHTML = `<h2>No pitches for '${pitcher}' in that date range.</h2>`;
    dashboard.style.display = "none";
    return;
  }

  errorBox.style.display = "none";
  dashboard.style.display = "block";

  const summary = summarizePitchTypes(rows);
  const matches = compareShapesToMLB(summary, MLB_DATA);

  renderSummaryTable(summary);
  renderComparisonTable(matches);
  renderChart(rows);
}

function renderSummaryTable(summary) {
  const tbody = document.getElementById("summary-tbody");
  tbody.innerHTML = "";
  for (const [pitchType, s] of Object.entries(summary)) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${pitchType}</td>
      <td>${s.velocityAvg}</td>
      <td>${s.velocityMax}</td>
      <td>${s.spinAvg}</td>
      <td>${s.ivbAvg}</td>
      <td>${s.hbAvg}</td>
    `;
    tbody.appendChild(tr);
  }
}

function renderComparisonTable(matches) {
  const tbody = document.getElementById("comparison-tbody");
  tbody.innerHTML = "";
  for (const m of matches) {
    const playerKey = playerKeyFromCsvName(m.player);
    const link = PLAYER_LINKS[playerKey];
    const playerHtml = link
      ? `<a href="${link}" target="_blank">${playerKey}</a>`
      : playerKey;

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${m.yourPitch}</td>
      <td>${playerHtml}</td>
      <td>${m.mlbPitch}</td>
      <td>${m.ivb}</td>
      <td>${m.hb}</td>
      <td>${m.diff}</td>
    `;
    tbody.appendChild(tr);
  }
}

function renderChart(rows) {
  const ctx = document.getElementById("pitch-shapes-chart").getContext("2d");

  const byType = {};
  for (const row of rows) {
    if (!byType[row.pitchType]) byType[row.pitchType] = [];
    byType[row.pitchType].push({ x: row.horizontalBreak, y: row.verticalBreak });
  }

  const datasets = Object.entries(byType).map(([pitchType, points], i) => ({
    label: pitchType,
    data: points,
    backgroundColor: colorFor(pitchType, i),
    pointRadius: 6,
  }));

  if (chartInstance) chartInstance.destroy();

  chartInstance = new Chart(ctx, {
    type: "scatter",
    data: { datasets },
    options: {
      responsive: true,
      aspectRatio: 1,
      plugins: {
        title: { display: true, text: "Pitch Shapes by Type", font: { size: 16 } },
        legend: { position: "right", title: { display: true, text: "Pitch Type" } },
      },
      scales: {
        x: {
          min: -25,
          max: 25,
          title: { display: true, text: "Horizontal Break (inches)" },
          grid: {
            color: (ctx) => (ctx.tick.value === 0 ? "#888" : "#ddd"),
            lineWidth: (ctx) => (ctx.tick.value === 0 ? 2 : 1),
          },
        },
        y: {
          min: -25,
          max: 25,
          title: { display: true, text: "Vertical Break (inches)" },
          grid: {
            color: (ctx) => (ctx.tick.value === 0 ? "#888" : "#ddd"),
            lineWidth: (ctx) => (ctx.tick.value === 0 ? 2 : 1),
          },
        },
      },
    },
  });
}

function openTab(evt, tabName) {
  const tabcontent = document.getElementsByClassName("tab-content");
  for (const el of tabcontent) el.classList.remove("active");
  const tablinks = document.getElementsByClassName("tab-link");
  for (const el of tablinks) el.classList.remove("active");
  document.getElementById(tabName).classList.add("active");
  evt.currentTarget.classList.add("active");
}

document.addEventListener("DOMContentLoaded", () => {
  document.getElementById("analysis-form").addEventListener("submit", (e) => {
    e.preventDefault();
    renderDashboard();
  });
  renderDashboard();
});
