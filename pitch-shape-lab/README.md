# Pitch Shape Lab

Turns a TrackMan bullpen export into a scouting-style report: the five closest MLB comps for every
pitch, how those comps actually performed, and a model-based "stuff" score.

**Live sample report (my bullpen):** https://rinterdonatos.github.io/pitching-dashboard/pitch-shape-lab/

## What it does

- **MLB reference:** pulls a full season of pitch-level Statcast data from Baseball Savant (2025: 707K
  pitches, 829 pitchers) and builds one row per pitcher and pitch type. Every pitch is oriented to the
  pitcher's arm side, so lefties and righties compare directly.
- **Comps:** standardized distance on velocity, induced vertical break, horizontal break, spin, release
  height and extension within the same pitch family (movement weighted most). Each comp shows its real
  whiff rate and run value per 100 pitches.
- **Whiff model:** a gradient-boosted classifier trained on 336K MLB swings predicts a miss from velocity,
  spin, movement, release point, extension, arm angle and separation from the pitcher's primary fastball.
  Validated on pitchers held out of training (ROC AUC 0.64). Location and count are excluded on purpose,
  so the score reflects the pitch itself.
- **Report:** an interactive HTML page (Plotly) with the arsenal table, xWhiff and Whiff+ (100 = MLB
  average for the pitch family), the movement profile against every MLB pitch, and auto-written notes on
  separation off the fastball.

## Run it

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install pandas numpy scikit-learn pybaseball plotly
.venv\Scripts\python.exe fetch_statcast.py 2025     # ~10 min, writes data/
.venv\Scripts\python.exe lab.py build 2025          # reference arsenals + whiff model
.venv\Scripts\python.exe report.py my_bullpen.csv report.html
```

Input is a standard TrackMan CSV (TaggedPitchType, RelSpeed, SpinRate, InducedVertBreak, HorzBreak,
RelHeight, RelSide, Extension).

Built by Reed Interdonato · Python, pandas, scikit-learn, Plotly · data: MLB Statcast via Baseball Savant
