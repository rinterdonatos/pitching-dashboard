# Pitch Shape Lab

Turns a TrackMan bullpen export into a scouting-style report: a Stuff+ grade for every pitch, its five
closest MLB comps, and how those comps actually performed.

**Live lab (pitcher dropdown, date range):** https://rinterdonatos.github.io/pitching-dashboard/

## What it does

- **MLB reference:** pulls a full season of pitch-level Statcast data from Baseball Savant (2025: 707K
  pitches, 829 pitchers) and builds one row per pitcher and pitch type. Every pitch is oriented to the
  pitcher's arm side, so lefties and righties compare directly.
- **Stuff+ (modeled on tjStuff+):** a gradient-boosted model trained on every 2025 MLB pitch predicts
  expected run value (the league-average value of each count and result, which removes batted-ball luck)
  from velocity, spin, induced vertical break, horizontal break, release height and side, extension, and
  separation from the pitcher's primary fastball. Pitch type, location and count are not inputs. Each pitch
  type is graded from its average traits and scaled so 100 = average MLB pitch and 10 points = one standard
  deviation. On pitchers held out of training it correlates r = 0.36 with expected run value per 100 pitches.
  The trees are exported to JSON and evaluated in the browser (matches scikit-learn to within 0.002).
- **Comps:** standardized distance on velocity, induced vertical break, horizontal break, spin, release
  height and extension within the same pitch family (movement weighted most), with each comp's Stuff+,
  whiff rate and run value per 100 pitches.
- **Site:** pick a pitcher and a date range; the arsenal table, Stuff+, movement profile against every MLB
  pitch, notes on separation off the fastball, and comps all recompute in the browser.

## Run it

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install pandas numpy scikit-learn pybaseball plotly
.venv\Scripts\python.exe fetch_statcast.py 2025        # ~10 min, writes data/
.venv\Scripts\python.exe lab.py build 2025             # reference arsenals + Stuff+ model
.venv\Scripts\python.exe site.py index.html "Name=a.csv;b.csv" "Other=c.csv"
```

Input is a standard TrackMan CSV (TaggedPitchType, RelSpeed, SpinRate, InducedVertBreak, HorzBreak,
RelHeight, RelSide, Extension).

Built by Reed Interdonato · Python, pandas, scikit-learn, Plotly · data: MLB Statcast via Baseball Savant
