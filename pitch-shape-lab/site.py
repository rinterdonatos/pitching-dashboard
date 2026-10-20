"""Build the interactive Pitch Shape Lab page: switch between pitchers and filter by date range.

    .venv\\Scripts\\python.exe site.py out.html "Name=a.csv;b.csv" "Other Name=c.csv" [--img-base URL]

The page re-averages whatever
pitches fall in the chosen date range and grades the averages with Stuff+, so the table, chart, notes and comps
all update in the browser with no server.
"""
import json
import sys
from pathlib import Path

import pandas as pd

import lab
from report import COLORS, FAMILY_TINT, name_first_last

COMP_FEATS = ["velo", "ivb", "hb", "spin", "rel_z", "ext"]


def r(v, d=1):
    return None if pd.isna(v) else round(float(v), d)


def load_pitcher(name: str, paths: list[str]) -> dict:
    frames = []
    for p in paths:
        f = lab.load_trackman(p)
        frames.append(f)
    df = pd.concat(frames, ignore_index=True)
    df["pitcher"] = 0
    df = lab.add_fastball_deltas(df.drop(columns=["d_velo", "d_ivb", "d_hb"]))
    df["date"] = pd.to_datetime(df["date"], format="mixed").dt.strftime("%Y-%m-%d")
    return {"hand": "RHP" if df["throws"].iloc[0] == "R" else "LHP",
            "pitches": [{"d": x.date, "t": x.pitch_type, "v": r(x.velo), "s": r(x.spin, 0),
                         "ivb": r(x.ivb), "hb": r(x.hb), "rz": r(x.rel_z, 2), "rx": r(x.rel_x, 2),
                         "ext": r(x.ext, 2)} for x in df.itertuples()]}


def build(out: str, pitchers: dict[str, list[str]], year: int = 2025, img_base: str = "") -> Path:
    ref = pd.read_csv(lab.DATA / f"reference_{year}.csv")
    stuff = json.loads((lab.DATA / f"stuff_model_{year}.json").read_text())
    meta = json.loads((lab.DATA / f"meta_{year}.json").read_text())

    data = {name: load_pitcher(name, paths) for name, paths in pitchers.items()}
    refrows = [[int(x.pitcher), name_first_last(x.player_name), x.pitch_type, x.pitch_name, x.group,
                x.throws, r(x.velo), r(x.ivb), r(x.hb), r(x.spin, 0), r(x.rel_z, 2), r(x.ext, 2),
                r(x.whiff_pct), r(x.rv100, 2), r(x.stuff_plus, 1)] for x in ref.itertuples()]
    fam = {g: {"sd": {c: float(f[c].std()) for c in COMP_FEATS}} for g, f in ref.groupby("group")}
    types = {t: {"dv": float(f["d_velo"].mean()), "di": float(f["d_ivb"].mean()),
                 "dh": float(f["d_hb"].mean()), "velo": float(f["velo"].mean()),
                 "ivbs": sorted(round(float(v), 1) for v in f["ivb"])}
             for t, f in ref.groupby("pitch_type")}
    payload = {"pitchers": data, "ref": refrows, "fam": fam, "types": types, "names": lab.NAMES,
               "group": lab.GROUP, "colors": COLORS, "tint": FAMILY_TINT, "meta": meta, "stuff": stuff, "trackman": lab.TRACKMAN}

    page = (PAGE.replace("__DATA__", json.dumps(payload, separators=(",", ":")))
                .replace("__IMG__", img_base)
                .replace("__YEAR__", str(meta["year"]))
                .replace("__ALLP__", f"{meta['pitches']:,}")
                .replace("__PITCHERS__", f"{meta['pitchers']:,}")
                .replace("__R__", str(meta["stuff_holdout_r"]))
                .replace("__RA__", str(meta["stuff_holdout_r_actual"])))
    path = Path(out)
    path.write_text(page, encoding="utf-8")
    return path


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pitch Shape Lab</title>
<meta name="description" content="Compare amateur pitch shapes to every MLB arsenal: Stuff+, MLB comps and movement profile.">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
:root { --ink:#14202b; --ink2:#5b6873; --bg:#f4f6f8; --card:#fff; --line:#e3e8ec; --navy:#13294b; }
* { box-sizing:border-box }
body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 Inter,"Segoe UI",system-ui,sans-serif }
.wrap { max-width:1120px; margin:0 auto; padding:0 16px }
header.hero { position:relative; overflow:hidden; background:radial-gradient(1200px 400px at 50% 120%,#24578f,transparent),linear-gradient(135deg,#0f2240,#1c4271);
  color:#fff; min-height:250px; display:flex; align-items:center }
.hero .wrap { position:relative; z-index:2; text-align:center; padding:34px 16px 54px }
.hero .kicker { letter-spacing:.18em; text-transform:uppercase; font-size:12px; opacity:.75 }
.hero h1 { margin:6px 0 6px; font-size:40px; letter-spacing:-.01em }
.hero p { margin:0 auto; max-width:560px; opacity:.85 }
.hero img { position:absolute; bottom:0; height:230px; z-index:1; filter:drop-shadow(0 10px 18px rgba(0,0,0,.35)) }
.hero img.left { left:max(12px, calc(50% - 600px)) }
.hero img.right { right:max(12px, calc(50% - 600px)) }
.controls { position:relative; z-index:3; margin:-30px auto 18px; background:var(--card); border-radius:14px; padding:12px 14px;
  box-shadow:0 6px 22px rgba(16,30,45,.12); display:flex; flex-wrap:wrap; gap:12px 18px; align-items:center }
.who { display:flex; gap:8px; align-items:center; color:var(--ink2); font-size:14px }
.who select { font:inherit; font-weight:600; color:var(--ink); padding:7px 34px 7px 12px; border:1px solid var(--line); border-radius:10px;
  background:#f7f9fb url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%2314202b' stroke-width='1.6' fill='none'/%3E%3C/svg%3E") no-repeat right 12px center;
  appearance:none; cursor:pointer; min-width:220px }
.upload { font-weight:600; color:#1f5fa8; border:1px dashed #9db6d6; border-radius:10px; padding:7px 12px; cursor:pointer; background:#f5f9ff; font-size:14px }
.upload:hover { background:#eaf2ff }
.upmsg { font-size:13px; color:var(--ink2) } .upmsg.err { color:#b03a2e }
.dates { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin-left:auto; color:var(--ink2); font-size:14px }
.dates input { font:inherit; padding:5px 8px; border:1px solid var(--line); border-radius:8px; color:var(--ink) }
.dates button { font:inherit; border:0; background:none; color:#1f5fa8; cursor:pointer; padding:4px 6px }
.tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; margin-bottom:6px }
.tile { background:var(--card); border-radius:12px; padding:14px 16px; box-shadow:0 2px 10px rgba(16,30,45,.06) }
.tile .l { font-size:12px; color:var(--ink2); text-transform:uppercase; letter-spacing:.06em }
.tile .v { font-size:24px; font-weight:700 }
.card { background:var(--card); border-radius:12px; padding:18px; margin-bottom:16px; box-shadow:0 2px 10px rgba(16,30,45,.06); overflow-x:auto }
h2 { font-size:18px; margin:24px 0 10px } h3 { margin:0 0 10px; font-size:16px }
h3 small { color:var(--ink2); font-weight:400; margin-left:8px }
table { width:100%; border-collapse:collapse; font-size:14px }
th { text-align:left; color:var(--ink2); font-weight:600; border-bottom:2px solid var(--line); padding:7px 8px; white-space:nowrap }
td { border-bottom:1px solid var(--line); padding:7px 8px; white-space:nowrap }
a { color:#1f5fa8; text-decoration:none } a:hover { text-decoration:underline }
.dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:7px; vertical-align:middle }
.plus { display:inline-block; min-width:44px; text-align:center; font-weight:700; border-radius:6px; padding:1px 6px; color:#fff }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(520px,1fr)); gap:16px }
.grid table { font-size:13px } .grid td, .grid th { padding:6px }
ul.notes li { margin:6px 0 }
.method { color:var(--ink2); font-size:13px }
.empty { color:var(--ink2); padding:30px; text-align:center }
footer { color:var(--ink2); font-size:12px; text-align:center; padding:24px 16px 40px }
footer a { color:var(--ink2); text-decoration:underline }
@media (max-width:760px) { .hero img { height:120px; opacity:.55 } .hero h1 { font-size:30px } .grid { grid-template-columns:1fr } .dates { margin-left:0 } }
</style></head>
<body>
<header class="hero">
  <img class="left" src="__IMG__67665cdf-22fb-4154-b3b7-014d9c2b75cc.png" alt="">
  <img class="right" src="__IMG__mikolas.png" alt="">
  <div class="wrap">
    <div class="kicker">Pitch Shape Lab</div>
    <h1>How does your arsenal stack up?</h1>
    <p>Bullpen data compared against every MLB arsenal from the __YEAR__ season: Stuff+, closest MLB comps, and your movement profile.</p>
  </div>
</header>

<main class="wrap">
  <div class="controls">
    <label class="who">Pitcher <select id="who"></select></label>
    <label class="upload" title="Your file is read in your browser and never uploaded anywhere">
      <input type="file" id="file" accept=".csv,text/csv" hidden>Upload TrackMan CSV</label>
    <span id="upmsg" class="upmsg"></span>
    <div class="dates">From <input type="date" id="from"> to <input type="date" id="to">
      <button id="all" type="button">All dates</button></div>
  </div>

  <div id="body">
    <div class="tiles">
      <div class="tile"><div class="l">Pitches</div><div class="v" id="tN"></div></div>
      <div class="tile"><div class="l">Top velo</div><div class="v" id="tVelo"></div></div>
      <div class="tile"><div class="l">Best pitch</div><div class="v" id="tBest" style="font-size:19px"></div></div>
      <div class="tile"><div class="l">Its Stuff+</div><div class="v" id="tPlus"></div></div>
    </div>

    <h2>Arsenal</h2>
    <div class="card"><table id="arsenal"></table>
      <p class="method">Stuff+ grades each pitch from its average velocity, movement, spin, release and separation off the fastball.
      100 = average MLB pitch; every 10 points is one standard deviation (110 is good, 120+ is elite).</p></div>

    <h2>Movement profile</h2>
    <div class="card"><div id="chart" style="height:600px"></div>
      <p class="method">Faint dots: every MLB pitcher's average pitch shape in __YEAR__, oriented to the pitcher's arm side so lefties and righties compare directly.</p></div>

    <h2>What stands out</h2>
    <div class="card"><ul class="notes" id="notes"></ul></div>

    <h2>Closest MLB comps</h2>
    <div class="grid" id="comps"></div>
  </div>
  <div class="card empty" id="none" hidden>No pitches in this date range.</div>

  <h2>Method</h2>
  <div class="card method">
    <p><b>Data.</b> __ALLP__ regular-season pitches from __PITCHERS__ MLB pitchers (__YEAR__ Statcast via Baseball Savant), aggregated to one row per pitcher and pitch type (min. 100 pitches).</p>
    <p><b>Comps.</b> Standardized distance on velocity, induced vertical break, horizontal break, spin, release height and extension within the same pitch family; movement weighted most. Missing measurements (e.g. no release data) are left out of the distance.</p>
    <p><b>Stuff+.</b> Modeled on tjStuff+: a gradient-boosted model trained on every __YEAR__ MLB pitch predicts expected run value (the league-average value of each count and result, so batted-ball luck is removed) from velocity, spin, induced vertical break, horizontal break, release height and side, extension, and separation from the pitcher's primary fastball. Pitch type, location and count are not inputs. Each pitch type is scored from its <i>average</i> traits over the selected dates, MLB arsenals the same way, then scaled so 100 is the average MLB pitch and 10 points is one standard deviation. On pitchers held out of training, Stuff+ correlates r = __R__ with expected run value per 100 pitches (r = __RA__ with raw run value). Traits a bullpen file doesn't record are filled with the MLB average for that pitch family. The model runs in your browser, so changing dates re-grades your averages instantly.</p>
  </div>
</main>
<footer>Built by Reed Interdonato · Python, pandas, scikit-learn, Plotly · data: MLB Statcast / Baseball Savant ·
  <a href="https://github.com/rinterdonatos/pitching-dashboard/tree/main/pitch-shape-lab">code</a> ·
  <a href="v1/">original v1 dashboard</a></footer>

<script>
const D = __DATA__;
const [I_ID, I_NAME, I_TYPE, I_PNAME, I_GROUP, I_HAND, I_VELO, I_IVB, I_HB, I_SPIN, I_RZ, I_EXT, I_WHIFF, I_RV, I_STUFF] = [...Array(15).keys()];
const FEATS = [["velo", I_VELO, 1.0], ["ivb", I_IVB, 1.5], ["hb", I_HB, 1.5], ["spin", I_SPIN, 0.5], ["rel_z", I_RZ, 0.75], ["ext", I_EXT, 0.5]];
const PKEY = {velo: "v", ivb: "ivb", hb: "hb", spin: "s", rel_z: "rz", ext: "ext"};
const $ = s => document.querySelector(s);
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);
const f = (v, d = 1) => v == null || isNaN(v) ? "–" : Number(v).toFixed(d);
const mean = a => { const b = a.filter(v => v != null && !isNaN(v)); return b.length ? b.reduce((x, y) => x + y, 0) / b.length : null; };
const names = Object.keys(D.pitchers);
let who = names[0];

function stuffPlus(a) {  // evaluate the exported gradient-boosted trees on this pitch's averages
  const S = D.stuff, fm = S.fam_means[a.group];
  const x = S.features.map(k => (a[k] == null || isNaN(a[k])) ? fm[k] : a[k]);
  let raw = S.base;
  for (const t of S.trees) {
    let i = 0;
    while (!t[i][5]) { const [feat, thr, l, r] = t[i]; i = x[feat] <= thr ? l : r; }
    raw += t[i][4];
  }
  return 100 + 10 * (raw - S.mu) / S.sd;
}

function plusColor(p) {  // red below 100, grey at 100, green above
  const t = Math.max(-1, Math.min(1, (p - 100) / 20));
  const mix = (a, b, k) => a.map((x, i) => Math.round(x + (b[i] - x) * k));
  const c = t < 0 ? mix([138, 150, 163], [192, 57, 43], -t) : mix([138, 150, 163], [46, 125, 79], t);
  return `rgb(${c.join(",")})`;
}

function arsenal(pitches) {
  const by = {};
  pitches.forEach(p => (by[p.t] = by[p.t] || []).push(p));
  const fbTypes = Object.keys(by).filter(t => D.group[t] === "fastball").sort((a, b) => by[b].length - by[a].length);
  const fb = fbTypes.length ? by[fbTypes[0]] : null;
  const fbM = fb ? {v: mean(fb.map(p => p.v)), ivb: mean(fb.map(p => p.ivb)), hb: mean(fb.map(p => p.hb))} : null;
  return Object.entries(by).map(([t, ps]) => {
    const a = {t, n: ps.length, name: D.names[t] || t, group: D.group[t],
      velo: mean(ps.map(p => p.v)), vmax: Math.max(...ps.map(p => p.v)), spin: mean(ps.map(p => p.s)),
      ivb: mean(ps.map(p => p.ivb)), hb: mean(ps.map(p => p.hb)), rel_z: mean(ps.map(p => p.rz)),
      rel_x: mean(ps.map(p => p.rx)), ext: mean(ps.map(p => p.ext))};
    if (fbM) { a.dv = a.velo - fbM.v; a.di = a.ivb - fbM.ivb; a.dh = a.hb - fbM.hb; }
    a.d_velo = a.dv; a.d_ivb = a.di; a.d_hb = a.dh;
    a.stuff = stuffPlus(a);
    return a;
  }).sort((a, b) => b.n - a.n);
}

function comps(a, k = 5) {
  const fam = D.fam[a.group];
  return D.ref.filter(r => r[I_GROUP] === a.group).map(r => {
    let s = 0;
    for (const [name, idx, w] of FEATS) {
      const mine = a[name], theirs = r[idx];
      if (mine == null || theirs == null || isNaN(mine)) continue;
      s += w * ((theirs - mine) / fam.sd[name]) ** 2;
    }
    const dist = Math.sqrt(s);
    return {r, dist, sim: 100 * Math.exp(-dist / 2)};
  }).sort((x, y) => x.dist - y.dist).slice(0, k);
}

function notes(ars) {
  const out = [];
  const best = ars.reduce((x, y) => (y.stuff > x.stuff ? y : x));
  const better = 100 * D.ref.filter(r => r[I_STUFF] < best.stuff).length / D.ref.length;
  out.push(`<b>Best pitch:</b> the ${best.name.toLowerCase()} grades out at ${f(best.stuff, 0)} Stuff+, better than ${f(better, 0)}% of MLB pitches.`);
  ars.forEach(a => {
    const T = D.types[a.t];
    if (a.group === "fastball" || a.dv == null || !T) return;
    out.push(`<b>${esc(a.name)}:</b> ${f(Math.abs(a.dv))} mph off the fastball (MLB avg ${f(Math.abs(T.dv))}), ${f(Math.abs(a.di))} in of vertical separation (MLB avg ${f(Math.abs(T.di))}) and ${f(Math.abs(a.dh))} in horizontal (MLB avg ${f(Math.abs(T.dh))}).`);
  });
  const fb = ars.find(a => a.group === "fastball");
  if (fb && D.types[fb.t]) {
    const T = D.types[fb.t], pct = 100 * T.ivbs.filter(v => v < fb.ivb).length / T.ivbs.length;
    out.push(`<b>Fastball shape:</b> ${f(fb.ivb)} in of IVB is more than ${f(pct, 0)}% of MLB ${fb.name.toLowerCase()}s, at ${f(fb.velo)} mph (MLB avg ${f(T.velo)}).`);
  }
  return out;
}

let bgTraces = null;
function background() {
  if (bgTraces) return bgTraces;
  bgTraces = Object.entries(D.tint).map(([fam, tint]) => {
    const rows = D.ref.filter(r => r[I_GROUP] === fam);
    return {x: rows.map(r => r[I_HB]), y: rows.map(r => r[I_IVB]), mode: "markers", type: "scattergl",
      name: `MLB ${fam}`, legendgroup: "mlb", marker: {size: 5, color: tint, opacity: 0.13}, hoverinfo: "text",
      text: rows.map(r => `${r[I_NAME]} · ${r[I_PNAME]}<br>${f(r[I_VELO])} mph · IVB ${f(r[I_IVB])} · HB ${f(r[I_HB])}`)};
  });
  return bgTraces;
}

function chart(pitches, ars) {
  const mine = Object.entries(pitches.reduce((m, p) => ((m[p.t] = m[p.t] || []).push(p), m), {})).map(([t, ps]) => ({
    x: ps.map(p => p.hb), y: ps.map(p => p.ivb), mode: "markers", type: "scatter", name: D.names[t] || t,
    marker: {size: 9, color: D.colors[t] || "#555", line: {width: 1, color: "white"}},
    hovertemplate: `%{x:.1f} in HB · %{y:.1f} in IVB<extra>${D.names[t] || t}</extra>`}));
  const ann = ars.map(a => ({x: a.hb, y: a.ivb, text: `<b>${a.t}</b>`, showarrow: false, yshift: 16,
    font: {size: 12, color: D.colors[a.t] || "#333"}}));
  Plotly.react("chart", [...background(), ...mine], {
    margin: {l: 60, r: 20, t: 10, b: 50}, template: "plotly_white", annotations: ann,
    xaxis: {title: {text: "Horizontal break (in)  ←  glove side · arm side  →"}, range: [-25, 25], zeroline: true, zerolinecolor: "#999"},
    yaxis: {title: {text: "Induced vertical break (in)"}, range: [-25, 25], zeroline: true, zerolinecolor: "#999"},
    legend: {orientation: "h", y: -0.15}, font: {family: "Inter, Segoe UI, sans-serif"}
  }, {displayModeBar: false, responsive: true});
}

function dateBounds() {
  const ds = D.pitchers[who].pitches.map(p => p.d).sort();
  return [ds[0], ds[ds.length - 1]];
}

function render() {
  const P = D.pitchers[who];
  const from = $("#from").value, to = $("#to").value;
  const pitches = P.pitches.filter(p => (!from || p.d >= from) && (!to || p.d <= to));
  $("#body").hidden = !pitches.length; $("#none").hidden = !!pitches.length;
  if (!pitches.length) return;
  const ars = arsenal(pitches);
  const best = ars.reduce((x, y) => (y.stuff > x.stuff ? y : x));
  $("#tN").textContent = pitches.length;
  $("#tVelo").textContent = `${f(Math.max(...pitches.map(p => p.v)))} mph`;
  $("#tBest").textContent = best.name;
  $("#tPlus").textContent = f(best.stuff, 0);
  $("#arsenal").innerHTML = `<tr><th>Pitch</th><th>#</th><th>Velo</th><th>Max</th><th>Spin</th><th>IVB</th><th>HB</th><th>Ext</th><th>Stuff+</th></tr>` +
    ars.map(a => `<tr><td><span class="dot" style="background:${D.colors[a.t] || "#555"}"></span>${esc(a.name)}</td><td>${a.n}</td>
      <td>${f(a.velo)}</td><td>${f(a.vmax)}</td><td>${f(a.spin, 0)}</td><td>${f(a.ivb)}</td><td>${f(a.hb)}</td><td>${f(a.ext)}</td>
      <td><span class="plus" style="background:${plusColor(a.stuff)}">${f(a.stuff, 0)}</span></td></tr>`).join("");
  $("#notes").innerHTML = notes(ars).map(s => `<li>${s}</li>`).join("");
  $("#comps").innerHTML = ars.map(a => `<div class="card"><h3><span class="dot" style="background:${D.colors[a.t] || "#555"}"></span>${esc(a.name)}
      <small>${f(a.velo)} mph · IVB ${f(a.ivb)} · HB ${f(a.hb)}</small></h3>
      <table><tr><th>MLB pitcher</th><th>Pitch</th><th></th><th>MPH</th><th>IVB</th><th>HB</th><th>Stuff+</th><th>Whiff%</th><th>RV/100</th><th>Match</th></tr>
      ${comps(a).map(({r, sim}) => `<tr><td><a href="https://baseballsavant.mlb.com/savant-player/${r[I_ID]}" target="_blank" rel="noopener">${esc(r[I_NAME])}</a></td>
        <td>${esc(r[I_PNAME])}</td><td>${r[I_HAND]}HP</td><td>${f(r[I_VELO])}</td><td>${f(r[I_IVB])}</td><td>${f(r[I_HB])}</td>
        <td>${f(r[I_STUFF], 0)}</td><td>${f(r[I_WHIFF])}%</td><td>${f(r[I_RV], 2)}</td><td><b>${f(sim, 0)}</b></td></tr>`).join("")}</table></div>`).join("");
  chart(pitches, ars);
}

function pick(name) {
  who = name;
  $("#who").value = name;
  const [lo, hi] = dateBounds();
  for (const el of [$("#from"), $("#to")]) { el.min = lo; el.max = hi; }
  $("#from").value = lo; $("#to").value = hi;
  render();
}

function fillWho() {
  $("#who").innerHTML = Object.keys(D.pitchers).map(n => `<option value="${esc(n)}">${esc(n)} (${D.pitchers[n].hand})</option>`).join("");
}
fillWho();

// ---- upload: parse a TrackMan CSV entirely in the browser ----
function parseCSV(text) {
  const rows = []; let row = [], cell = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"' && text[i + 1] === '"') { cell += '"'; i++; } else if (c === '"') q = false; else cell += c; }
    else if (c === '"') q = true;
    else if (c === ",") { row.push(cell); cell = ""; }
    else if (c === "\n" || c === "\r") { if (c === "\r" && text[i + 1] === "\n") i++; row.push(cell); rows.push(row); row = []; cell = ""; }
    else cell += c;
  }
  if (cell !== "" || row.length) { row.push(cell); rows.push(row); }
  return rows.filter(r => r.some(v => v.trim() !== ""));
}

function isoDate(v) {
  if (!v) return null;
  let m = String(v).trim().match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
  if (m) return `${m[1]}-${m[2].padStart(2, "0")}-${m[3].padStart(2, "0")}`;
  m = String(v).trim().match(/^(\d{1,2})\/(\d{1,2})\/(\d{2,4})/);
  if (m) return `${m[3].length === 2 ? "20" + m[3] : m[3]}-${m[1].padStart(2, "0")}-${m[2].padStart(2, "0")}`;
  const d = new Date(v); return isNaN(d) ? null : d.toISOString().slice(0, 10);
}

function loadTrackman(text, fileName) {
  const rows = parseCSV(text);
  if (rows.length < 2) throw new Error("That file has no pitch rows.");
  const head = rows[0].map(h => h.trim().toLowerCase().replace(/^\ufeff/, ""));
  const col = (...names) => names.map(n => head.indexOf(n)).find(i => i >= 0);
  const C = {who: col("pitcher"), hand: col("pitcherthrows"), date: col("date"),
    type: col("taggedpitchtype", "autopitchtype", "pitchtype"), v: col("relspeed", "velocity"),
    s: col("spinrate"), ivb: col("inducedvertbreak", "verticalbreak"), hb: col("horzbreak", "horizontalbreak"),
    rz: col("relheight"), rx: col("relside"), ext: col("extension")};
  if ([C.type, C.v, C.ivb, C.hb].some(i => i == null))
    throw new Error("Couldn't find the pitch type, velocity and break columns (TaggedPitchType, RelSpeed, InducedVertBreak, HorzBreak).");
  const num = (r, i) => { if (i == null) return null; const x = parseFloat(r[i]); return isNaN(x) ? null : x; };
  let pitches = rows.slice(1).map(r => ({
    d: isoDate(C.date != null ? r[C.date] : null) || new Date().toISOString().slice(0, 10),
    t: D.trackman[String(r[C.type] || "").toLowerCase().replace(/\s+/g, "")],
    v: num(r, C.v), s: num(r, C.s), ivb: num(r, C.ivb), hb: num(r, C.hb),
    rz: num(r, C.rz), rx: num(r, C.rx), ext: num(r, C.ext)}))
    .filter(p => p.t && p.v != null && p.ivb != null && p.hb != null);
  if (!pitches.length) throw new Error("No pitches with a recognized pitch type, velocity and break.");
  // Exports differ in sign conventions: orient so the fastball runs to the arm side (+).
  const fb = pitches.filter(p => D.group[p.t] === "fastball");
  if (fb.length && mean(fb.map(p => p.hb)) < 0) pitches.forEach(p => p.hb = -p.hb);
  if (mean(pitches.map(p => p.rx)) < 0) pitches.forEach(p => { if (p.rx != null) p.rx = -p.rx; });
  const first = rows[1];
  let name = C.who != null ? String(first[C.who] || "").trim() : "";
  if (name.includes(",")) name = name.split(",").map(x => x.trim()).reverse().join(" ");
  name = name || fileName.replace(/\.[^.]+$/, "");
  const throws = C.hand != null ? String(first[C.hand] || "R").trim()[0].toUpperCase() : "R";
  return {name, hand: throws === "L" ? "LHP" : "RHP", pitches};
}

$("#file").onchange = async e => {
  const file = e.target.files[0]; if (!file) return;
  const msg = $("#upmsg"); msg.className = "upmsg";
  try {
    const p = loadTrackman(await file.text(), file.name);
    let name = `${p.name} (uploaded)`, k = 2;
    while (D.pitchers[name]) name = `${p.name} (uploaded ${k++})`;
    D.pitchers[name] = {hand: p.hand, pitches: p.pitches};
    fillWho(); pick(name);
    msg.textContent = `Loaded ${p.pitches.length} pitches. Your file stays in your browser.`;
  } catch (err) {
    msg.className = "upmsg err"; msg.textContent = err.message;
  }
  e.target.value = "";
};
$("#who").onchange = e => pick(e.target.value);
$("#from").onchange = render; $("#to").onchange = render;
$("#all").onclick = () => { const [lo, hi] = dateBounds(); $("#from").value = lo; $("#to").value = hi; render(); };
pick(who);
</script>
</body></html>
"""

if __name__ == "__main__":
    argv = sys.argv[1:]
    img = ""
    if "--img-base" in argv:
        i = argv.index("--img-base")
        img = argv[i + 1]
        del argv[i:i + 2]
    if len(argv) < 2:
        print(__doc__)
        sys.exit(1)
    pitchers = {}
    for spec in argv[1:]:
        name, _, paths = spec.partition("=")
        pitchers[name] = paths.split(";")
    print(f"wrote {build(argv[0], pitchers, img_base=img)}")
