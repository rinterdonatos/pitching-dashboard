"""Build the interactive Pitch Shape Lab page: switch between pitchers and filter by date range.

    .venv\\Scripts\\python.exe site.py out.html "Name=a.csv;b.csv" "Other Name=c.csv" [--img-base URL]

Each pitch is scored by the whiff model here in Python; the page then re-averages whatever
pitches fall in the chosen date range, so the arsenal table, Whiff+, chart, notes and MLB comps
all update in the browser with no server.
"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import lab
from report import COLORS, FAMILY_TINT, name_first_last

COMP_FEATS = ["velo", "ivb", "hb", "spin", "rel_z", "ext"]


def r(v, d=1):
    return None if pd.isna(v) else round(float(v), d)


def load_pitcher(name: str, paths: list[str], model) -> dict:
    frames = []
    for p in paths:
        f = lab.load_trackman(p)
        frames.append(f)
    df = pd.concat(frames, ignore_index=True)
    df["pitcher"] = 0
    df = lab.add_fastball_deltas(df.drop(columns=["d_velo", "d_ivb", "d_hb"]))
    df["group_code"] = df["group"].map(lab.GROUP_CODE)
    df["arm_angle"] = np.nan
    df["xwhiff"] = 100 * model.predict_proba(df[lab.FEATURES])[:, 1]
    df["date"] = pd.to_datetime(df["date"], format="mixed").dt.strftime("%Y-%m-%d")
    return {"hand": "RHP" if df["throws"].iloc[0] == "R" else "LHP",
            "pitches": [{"d": x.date, "t": x.pitch_type, "v": r(x.velo), "s": r(x.spin, 0),
                         "ivb": r(x.ivb), "hb": r(x.hb), "rz": r(x.rel_z, 2), "ext": r(x.ext, 2),
                         "x": r(x.xwhiff, 2)} for x in df.itertuples()]}


def build(out: str, pitchers: dict[str, list[str]], year: int = 2025, img_base: str = "") -> Path:
    ref = pd.read_csv(lab.DATA / f"reference_{year}.csv")
    model = pickle.loads((lab.DATA / f"whiff_model_{year}.pkl").read_bytes())
    meta = json.loads((lab.DATA / f"meta_{year}.json").read_text())

    data = {name: load_pitcher(name, paths, model) for name, paths in pitchers.items()}
    refrows = [[int(x.pitcher), name_first_last(x.player_name), x.pitch_type, x.pitch_name, x.group,
                x.throws, r(x.velo), r(x.ivb), r(x.hb), r(x.spin, 0), r(x.rel_z, 2), r(x.ext, 2),
                r(x.whiff_pct), r(x.rv100, 2), r(x.xwhiff, 2)] for x in ref.itertuples()]
    fam = {g: {"sd": {c: float(f[c].std()) for c in COMP_FEATS}, "xmean": float(f["xwhiff"].mean()),
               "xs": sorted(round(float(v), 2) for v in f["xwhiff"])}
           for g, f in ref.groupby("group")}
    types = {t: {"dv": float(f["d_velo"].mean()), "di": float(f["d_ivb"].mean()),
                 "dh": float(f["d_hb"].mean()), "velo": float(f["velo"].mean()),
                 "ivbs": sorted(round(float(v), 1) for v in f["ivb"])}
             for t, f in ref.groupby("pitch_type")}
    payload = {"pitchers": data, "ref": refrows, "fam": fam, "types": types, "names": lab.NAMES,
               "group": lab.GROUP, "colors": COLORS, "tint": FAMILY_TINT, "meta": meta}

    page = (PAGE.replace("__DATA__", json.dumps(payload, separators=(",", ":")))
                .replace("__IMG__", img_base)
                .replace("__YEAR__", str(meta["year"]))
                .replace("__ALLP__", f"{meta['pitches']:,}")
                .replace("__PITCHERS__", f"{meta['pitchers']:,}")
                .replace("__SWINGS__", f"{meta['swings']:,}")
                .replace("__AUC__", str(meta["holdout_auc"])))
    path = Path(out)
    path.write_text(page, encoding="utf-8")
    return path


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pitch Shape Lab</title>
<meta name="description" content="Compare amateur pitch shapes to every MLB arsenal: comps, whiff model and movement profile.">
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
.tabs { display:flex; gap:6px; flex-wrap:wrap }
.tabs button { border:1px solid var(--line); background:#f7f9fb; color:var(--ink); border-radius:999px; padding:7px 14px; font:inherit; font-weight:600; cursor:pointer }
.tabs button.on { background:var(--navy); color:#fff; border-color:var(--navy) }
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
    <p>Bullpen data compared against every MLB arsenal from the __YEAR__ season: closest comps, a whiff model, and your movement profile.</p>
  </div>
</header>

<main class="wrap">
  <div class="controls">
    <div class="tabs" id="tabs"></div>
    <div class="dates">From <input type="date" id="from"> to <input type="date" id="to">
      <button id="all" type="button">All dates</button></div>
  </div>

  <div id="body">
    <div class="tiles">
      <div class="tile"><div class="l">Pitches</div><div class="v" id="tN"></div></div>
      <div class="tile"><div class="l">Top velo</div><div class="v" id="tVelo"></div></div>
      <div class="tile"><div class="l">Best bat-misser</div><div class="v" id="tBest" style="font-size:19px"></div></div>
      <div class="tile"><div class="l">Its Whiff+</div><div class="v" id="tPlus"></div></div>
    </div>

    <h2>Arsenal</h2>
    <div class="card"><table id="arsenal"></table>
      <p class="method">xWhiff = predicted swing-and-miss rate from shape, release and separation off the fastball.
      Whiff+ = 100 × xWhiff / MLB average for that pitch family (100 is league average, 120 is 20% better).</p></div>

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
    <p><b>Whiff model.</b> Gradient-boosted classifier trained on __SWINGS__ MLB swings to predict a miss from velocity, spin, movement, release point, extension, arm angle and separation from the pitcher's primary fastball. Validated on pitchers held out of training (ROC AUC __AUC__). Every bullpen pitch is scored individually, so date filtering re-averages exact model outputs. Location and count are left out on purpose, so the score reflects the pitch itself ("stuff").</p>
  </div>
</main>
<footer>Built by Reed Interdonato · Python, pandas, scikit-learn, Plotly · data: MLB Statcast / Baseball Savant ·
  <a href="https://github.com/rinterdonatos/pitching-dashboard/tree/main/pitch-shape-lab">code</a> ·
  <a href="v1/">original v1 dashboard</a></footer>

<script>
const D = __DATA__;
const [I_ID, I_NAME, I_TYPE, I_PNAME, I_GROUP, I_HAND, I_VELO, I_IVB, I_HB, I_SPIN, I_RZ, I_EXT, I_WHIFF, I_RV, I_X] = [...Array(15).keys()];
const FEATS = [["velo", I_VELO, 1.0], ["ivb", I_IVB, 1.5], ["hb", I_HB, 1.5], ["spin", I_SPIN, 0.5], ["rel_z", I_RZ, 0.75], ["ext", I_EXT, 0.5]];
const PKEY = {velo: "v", ivb: "ivb", hb: "hb", spin: "s", rel_z: "rz", ext: "ext"};
const $ = s => document.querySelector(s);
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);
const f = (v, d = 1) => v == null || isNaN(v) ? "–" : Number(v).toFixed(d);
const mean = a => { const b = a.filter(v => v != null && !isNaN(v)); return b.length ? b.reduce((x, y) => x + y, 0) / b.length : null; };
const names = Object.keys(D.pitchers);
let who = names[0];

function plusColor(p) {  // red below 100, grey at 100, green above
  const t = Math.max(-1, Math.min(1, (p - 100) / 25));
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
      ext: mean(ps.map(p => p.ext)), x: mean(ps.map(p => p.x))};
    if (fbM) { a.dv = a.velo - fbM.v; a.di = a.ivb - fbM.ivb; a.dh = a.hb - fbM.hb; }
    const fam = D.fam[a.group];
    a.plus = 100 * a.x / fam.xmean;
    a.pct = 100 * fam.xs.filter(v => v < a.x).length / fam.xs.length;
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
  const best = ars.reduce((x, y) => (y.plus > x.plus ? y : x));
  out.push(`<b>Best bat-misser:</b> the ${best.name.toLowerCase()} projects a ${f(best.x, 0)}% whiff rate, ${f(best.plus, 0)} Whiff+ (better than ${f(best.pct, 0)}% of MLB ${best.group} pitches).`);
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
  const best = ars.reduce((x, y) => (y.plus > x.plus ? y : x));
  $("#tN").textContent = pitches.length;
  $("#tVelo").textContent = `${f(Math.max(...pitches.map(p => p.v)))} mph`;
  $("#tBest").textContent = best.name;
  $("#tPlus").textContent = f(best.plus, 0);
  $("#arsenal").innerHTML = `<tr><th>Pitch</th><th>#</th><th>Velo</th><th>Max</th><th>Spin</th><th>IVB</th><th>HB (arm +)</th><th>Ext</th><th>xWhiff</th><th>Whiff+</th></tr>` +
    ars.map(a => `<tr><td><span class="dot" style="background:${D.colors[a.t] || "#555"}"></span>${esc(a.name)}</td><td>${a.n}</td>
      <td>${f(a.velo)}</td><td>${f(a.vmax)}</td><td>${f(a.spin, 0)}</td><td>${f(a.ivb)}</td><td>${f(a.hb)}</td><td>${f(a.ext)}</td>
      <td>${f(a.x)}%</td><td><span class="plus" style="background:${plusColor(a.plus)}">${f(a.plus, 0)}</span></td></tr>`).join("");
  $("#notes").innerHTML = notes(ars).map(s => `<li>${s}</li>`).join("");
  $("#comps").innerHTML = ars.map(a => `<div class="card"><h3><span class="dot" style="background:${D.colors[a.t] || "#555"}"></span>${esc(a.name)}
      <small>${f(a.velo)} mph · IVB ${f(a.ivb)} · HB ${f(a.hb)}</small></h3>
      <table><tr><th>MLB pitcher</th><th>Pitch</th><th></th><th>MPH</th><th>IVB</th><th>HB</th><th>Whiff%</th><th>RV/100</th><th>Match</th></tr>
      ${comps(a).map(({r, sim}) => `<tr><td><a href="https://baseballsavant.mlb.com/savant-player/${r[I_ID]}" target="_blank" rel="noopener">${esc(r[I_NAME])}</a></td>
        <td>${esc(r[I_PNAME])}</td><td>${r[I_HAND]}HP</td><td>${f(r[I_VELO])}</td><td>${f(r[I_IVB])}</td><td>${f(r[I_HB])}</td>
        <td>${f(r[I_WHIFF])}%</td><td>${f(r[I_RV], 2)}</td><td><b>${f(sim, 0)}</b></td></tr>`).join("")}</table></div>`).join("");
  chart(pitches, ars);
}

function pick(name) {
  who = name;
  document.querySelectorAll("#tabs button").forEach(b => b.classList.toggle("on", b.dataset.name === name));
  const [lo, hi] = dateBounds();
  for (const el of [$("#from"), $("#to")]) { el.min = lo; el.max = hi; }
  $("#from").value = lo; $("#to").value = hi;
  render();
}

$("#tabs").innerHTML = names.map(n => `<button type="button" data-name="${esc(n)}">${esc(n)} <span style="opacity:.6;font-weight:400">${D.pitchers[n].hand}</span></button>`).join("");
document.querySelectorAll("#tabs button").forEach(b => b.onclick = () => pick(b.dataset.name));
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
