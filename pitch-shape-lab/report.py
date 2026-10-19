"""Turn a TrackMan CSV into an interactive Pitch Shape Lab report.

    .venv\\Scripts\\python.exe report.py <trackman.csv> [out.html] [--year 2025]
"""
import html
import json
import pickle
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

import lab

COLORS = {"FF": "#d64545", "SI": "#e8833a", "FC": "#8c5a3c", "SL": "#e0b400", "ST": "#c9a227",
          "SV": "#7aa83b", "CU": "#3a7bd5", "KC": "#2f5fb3", "CS": "#5b8def",
          "CH": "#2e9e6b", "FS": "#159a9c", "FO": "#0f7c7e", "SC": "#6b9e2e"}
FAMILY_TINT = {"fastball": "#d64545", "cutter": "#8c5a3c", "breaking": "#c9a227", "offspeed": "#2e9e6b"}


def name_first_last(n: str) -> str:
    return " ".join(reversed([p.strip() for p in n.split(",", 1)])) if "," in n else n


def fmt(v, d=1):
    return "–" if pd.isna(v) else f"{v:.{d}f}"


def movement_chart(pitches, a, ref):
    fig = go.Figure()
    for fam, tint in FAMILY_TINT.items():
        r = ref[ref["group"] == fam]
        fig.add_trace(go.Scatter(
            x=r["hb"], y=r["ivb"], mode="markers", name=f"MLB {fam}", legendgroup="mlb",
            marker=dict(size=5, color=tint, opacity=0.13), hoverinfo="text",
            text=[f"{name_first_last(p)} · {t}<br>{v:.1f} mph · IVB {i:.1f} · HB {h:.1f}"
                  for p, t, v, i, h in zip(r["player_name"], r["pitch_name"], r["velo"], r["ivb"], r["hb"])]))
    for pt, g in pitches.groupby("pitch_type"):
        fig.add_trace(go.Scatter(
            x=g["hb"], y=g["ivb"], mode="markers", name=lab.NAMES.get(pt, pt),
            marker=dict(size=9, color=COLORS.get(pt, "#555"), line=dict(width=1, color="white")),
            hovertemplate="%{x:.1f} in HB · %{y:.1f} in IVB<extra>" + lab.NAMES.get(pt, pt) + "</extra>"))
    for _, r in a.iterrows():
        fig.add_annotation(x=r["hb"], y=r["ivb"], text=f"<b>{r['pitch_type']}</b>", showarrow=False,
                           yshift=16, font=dict(size=12, color=COLORS.get(r["pitch_type"], "#333")))
    fig.update_layout(
        height=600, margin=dict(l=60, r=20, t=10, b=50), template="plotly_white",
        xaxis=dict(title="Horizontal break (in)  ←  glove side · arm side  →", range=[-25, 25],
                   zeroline=True, zerolinecolor="#999"),
        yaxis=dict(title="Induced vertical break (in)", range=[-25, 25], zeroline=True,
                   zerolinecolor="#999"),
        legend=dict(orientation="h", y=-0.15), font=dict(family="Inter, Segoe UI, sans-serif"))
    return fig


def insights(a: pd.DataFrame, ref: pd.DataFrame) -> list[str]:
    out = []
    best = a.loc[a["whiff_plus"].idxmax()]
    out.append(f"<b>Best bat-misser:</b> your {best['pitch_name'].lower()} projects a {best['xwhiff']:.0f}% "
               f"whiff rate, {best['whiff_plus']:.0f} Whiff+ (better than {best['pctile']:.0f}% of MLB "
               f"{best['group']} pitches).")
    for _, r in a.iterrows():
        if r["group"] == "fastball" or pd.isna(r["d_velo"]):
            continue
        same = ref[ref["pitch_type"] == r["pitch_type"]]
        if same.empty:
            continue
        mv, mi, mh = same["d_velo"].mean(), same["d_ivb"].mean(), same["d_hb"].mean()
        out.append(
            f"<b>{r['pitch_name']}:</b> {abs(r['d_velo']):.1f} mph off your fastball (MLB avg {abs(mv):.1f}), "
            f"{abs(r['d_ivb']):.1f} in of vertical separation (MLB avg {abs(mi):.1f}) and "
            f"{abs(r['d_hb']):.1f} in horizontal (MLB avg {abs(mh):.1f}).")
    fb = a[a["group"] == "fastball"]
    if len(fb):
        f = fb.iloc[0]
        same = ref[ref["pitch_type"] == f["pitch_type"]]
        ivb_pct = 100 * (same["ivb"] < f["ivb"]).mean()
        out.append(f"<b>Fastball shape:</b> {f['ivb']:.1f} in of IVB is higher than {ivb_pct:.0f}% of MLB "
                   f"{f['pitch_name'].lower()}s, at {f['velo']:.1f} mph (MLB avg {same['velo'].mean():.1f}).")
    return out


def build_report(csv_path: str, out_path: str, year: int = 2025) -> Path:
    ref = pd.read_csv(lab.DATA / f"reference_{year}.csv")
    model = pickle.loads((lab.DATA / f"whiff_model_{year}.pkl").read_bytes())
    meta = json.loads((lab.DATA / f"meta_{year}.json").read_text())

    pitches = lab.load_trackman(csv_path)
    a = lab.score(lab.arsenal(pitches), ref, model)
    who = name_first_last(str(pitches["pitcher_name"].iloc[0]))
    hand = "RHP" if pitches["throws"].iloc[0] == "R" else "LHP"
    date = str(pitches["date"].iloc[0])

    fig = movement_chart(pitches, a, ref)
    chart = fig.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False})

    rows = "".join(f"""<tr><td><span class="dot" style="background:{COLORS.get(r.pitch_type, '#555')}"></span>
        {html.escape(r.pitch_name)}</td><td>{r.n}</td><td>{fmt(r.velo)}</td><td>{fmt(r.velo_max)}</td>
        <td>{fmt(r.spin, 0)}</td><td>{fmt(r.ivb)}</td><td>{fmt(r.hb)}</td><td>{fmt(r.ext)}</td>
        <td>{fmt(r.xwhiff)}%</td><td><span class="plus" style="--p:{min(max(r.whiff_plus, 50), 150)}">
        {r.whiff_plus:.0f}</span></td></tr>""" for r in a.itertuples())

    comp_blocks = []
    for _, r in a.iterrows():
        c = lab.comps(r, ref)
        items = "".join(f"""<tr><td><a href="https://baseballsavant.mlb.com/savant-player/{int(m.pitcher)}"
            target="_blank" rel="noopener">{html.escape(name_first_last(m.player_name))}</a></td>
            <td>{html.escape(m.pitch_name)}</td><td>{m.throws}HP</td><td>{fmt(m.velo)}</td><td>{fmt(m.ivb)}</td>
            <td>{fmt(m.hb)}</td><td>{fmt(m.whiff_pct)}%</td><td>{fmt(m.rv100, 2)}</td>
            <td><b>{m.similarity:.0f}</b></td></tr>""" for m in c.itertuples())
        comp_blocks.append(f"""<div class="card"><h3><span class="dot" style="background:
            {COLORS.get(r['pitch_type'], '#555')}"></span>{html.escape(r['pitch_name'])}
            <small>{fmt(r['velo'])} mph · IVB {fmt(r['ivb'])} · HB {fmt(r['hb'])}</small></h3>
            <table><tr><th>MLB pitcher</th><th>Pitch</th><th></th><th>MPH</th><th>IVB</th><th>HB</th>
            <th>Whiff%</th><th>RV/100</th><th>Match</th></tr>{items}</table></div>""")

    notes = "".join(f"<li>{s}</li>" for s in insights(a, ref))
    page = TEMPLATE.format(
        who=html.escape(who), hand=hand, date=html.escape(date), n=len(pitches), types=len(a),
        top_velo=fmt(pitches["velo"].max()), best=html.escape(a.loc[a["whiff_plus"].idxmax(), "pitch_name"]),
        best_plus=f"{a['whiff_plus'].max():.0f}", rows=rows, chart=chart, notes=notes,
        comps="".join(comp_blocks), year=meta["year"], pitchers=f"{meta['pitchers']:,}",
        swings=f"{meta['swings']:,}", auc=meta["holdout_auc"], allp=f"{meta['pitches']:,}")
    out = Path(out_path)
    out.write_text(page, encoding="utf-8")
    return out


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pitch Shape Lab – {who}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
:root {{ --ink:#14202b; --ink2:#5b6873; --bg:#f4f6f8; --card:#fff; --line:#e3e8ec; --navy:#13294b; --accent:#d64545; }}
* {{ box-sizing:border-box }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 Inter,"Segoe UI",system-ui,sans-serif }}
header {{ background:linear-gradient(135deg,#13294b,#1f4a7a); color:#fff; padding:36px 16px 28px }}
.wrap {{ max-width:1100px; margin:0 auto; padding:0 16px }}
header .kicker {{ letter-spacing:.14em; text-transform:uppercase; font-size:12px; opacity:.75 }}
header h1 {{ margin:6px 0 4px; font-size:32px }}
header p {{ margin:0; opacity:.85 }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:12px; margin:-18px auto 18px }}
.tile {{ background:var(--card); border-radius:12px; padding:14px 16px; box-shadow:0 2px 10px rgba(16,30,45,.08) }}
.tile .l {{ font-size:12px; color:var(--ink2); text-transform:uppercase; letter-spacing:.06em }}
.tile .v {{ font-size:26px; font-weight:700 }}
.card {{ background:var(--card); border-radius:12px; padding:18px; margin-bottom:16px; box-shadow:0 2px 10px rgba(16,30,45,.06); overflow-x:auto }}
h2 {{ font-size:18px; margin:26px 0 10px }} h3 {{ margin:0 0 10px; font-size:16px }}
h3 small {{ color:var(--ink2); font-weight:400; margin-left:8px }}
table {{ width:100%; border-collapse:collapse; font-size:14px }}
th {{ text-align:left; color:var(--ink2); font-weight:600; border-bottom:2px solid var(--line); padding:7px 8px; white-space:nowrap }}
td {{ border-bottom:1px solid var(--line); padding:7px 8px; white-space:nowrap }}
a {{ color:#1f5fa8; text-decoration:none }} a:hover {{ text-decoration:underline }}
.dot {{ display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:7px; vertical-align:middle }}
.plus {{ display:inline-block; min-width:44px; text-align:center; font-weight:700; border-radius:6px; padding:1px 6px;
  color:#fff; background:color-mix(in srgb, #2e7d4f calc((var(--p) - 100) * 2%), color-mix(in srgb, #c0392b calc((100 - var(--p)) * 2%), #8a96a3)) }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(520px,1fr)); gap:16px }}
.grid table {{ font-size:13px }} .grid td, .grid th {{ padding:6px 6px }}
ul.notes li {{ margin:6px 0 }}
.method {{ color:var(--ink2); font-size:13px }}
footer {{ color:var(--ink2); font-size:12px; text-align:center; padding:24px 16px 40px }}
@media (max-width:600px) {{ .grid {{ grid-template-columns:1fr }} header h1 {{ font-size:24px }} }}
</style></head>
<body>
<header><div class="wrap">
  <div class="kicker">Pitch Shape Lab</div>
  <h1>{who} <span style="opacity:.6;font-weight:400">· {hand}</span></h1>
  <p>Bullpen {date} · {n} pitches · compared against every MLB arsenal from the {year} season</p>
</div></header>
<main class="wrap">
  <div class="tiles">
    <div class="tile"><div class="l">Top velo</div><div class="v">{top_velo} mph</div></div>
    <div class="tile"><div class="l">Pitch types</div><div class="v">{types}</div></div>
    <div class="tile"><div class="l">Best bat-misser</div><div class="v" style="font-size:20px">{best}</div></div>
    <div class="tile"><div class="l">Its Whiff+</div><div class="v">{best_plus}</div></div>
  </div>

  <h2>Arsenal</h2>
  <div class="card"><table>
    <tr><th>Pitch</th><th>#</th><th>Velo</th><th>Max</th><th>Spin</th><th>IVB</th><th>HB (arm +)</th><th>Ext</th><th>xWhiff</th><th>Whiff+</th></tr>
    {rows}</table>
    <p class="method">xWhiff = predicted swing-and-miss rate from shape, release and separation off your fastball.
    Whiff+ = 100 × xWhiff / MLB average for that pitch family (100 is league average, 120 is 20% better).</p></div>

  <h2>Movement profile</h2>
  <div class="card">{chart}
    <p class="method">Faint dots: every MLB pitcher's average pitch shape in {year}, oriented to the pitcher's arm side so lefties and righties compare directly.</p></div>

  <h2>What stands out</h2>
  <div class="card"><ul class="notes">{notes}</ul></div>

  <h2>Closest MLB comps</h2>
  <div class="grid">{comps}</div>

  <h2>Method</h2>
  <div class="card method">
    <p><b>Data.</b> {allp} regular-season pitches from {pitchers} MLB pitchers ({year} Statcast via Baseball Savant), aggregated to one row per pitcher and pitch type (min. 100 pitches).</p>
    <p><b>Comps.</b> Standardized distance on velocity, induced vertical break, horizontal break, spin, release height and extension within the same pitch family; movement weighted most.</p>
    <p><b>Whiff model.</b> Gradient-boosted classifier trained on {swings} MLB swings to predict a miss from velocity, spin, movement, release point, extension, arm angle and separation from the pitcher's primary fastball. Validated on pitchers held out of training (ROC AUC {auc}). Location and count are left out on purpose, so the score reflects the pitch itself ("stuff"), not how it was located.</p>
  </div>
</main>
<footer>Built by Reed Interdonato · Python, pandas, scikit-learn, Plotly · data: MLB Statcast / Baseball Savant</footer>
</body></html>
"""

if __name__ == "__main__":
    argv = sys.argv[1:]
    year = 2025
    if "--year" in argv:
        i = argv.index("--year")
        year = int(argv[i + 1])
        del argv[i:i + 2]
    args = argv
    if not args:
        print(__doc__)
        sys.exit(1)
    out = build_report(args[0], args[1] if len(args) > 1 else "report.html", year)
    print(f"wrote {out}")
