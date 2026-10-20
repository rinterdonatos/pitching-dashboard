"""Pitch Shape Lab: MLB reference arsenals, a whiff model, and shape comps.

    .venv\\Scripts\\python.exe lab.py build 2025     # once per season: reference + model

Conventions (everything is from the pitcher's point of view, so lefties and righties compare):
  ivb    induced vertical break, inches (+ = rise)
  hb     horizontal break, inches, + = arm side (run), - = glove side (sweep/cut)
  rel_z  release height, ft;  rel_x  release side, ft (+ = arm side);  ext  extension, ft
"""
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupShuffleSplit

DATA = Path(__file__).parent / "data"

# Statcast pitch codes -> the three families comps are drawn from.
GROUP = {"FF": "fastball", "SI": "fastball", "FC": "cutter", "SL": "breaking", "ST": "breaking",
         "SV": "breaking", "CU": "breaking", "KC": "breaking", "CS": "breaking",
         "CH": "offspeed", "FS": "offspeed", "FO": "offspeed", "SC": "offspeed"}
NAMES = {"FF": "4-Seam Fastball", "SI": "Sinker", "FC": "Cutter", "SL": "Slider", "ST": "Sweeper",
         "SV": "Slurve", "CU": "Curveball", "KC": "Knuckle Curve", "CS": "Slow Curve",
         "CH": "Changeup", "FS": "Splitter", "FO": "Forkball", "SC": "Screwball"}
# TrackMan tags -> Statcast codes.
TRACKMAN = {"fastball": "FF", "four-seam": "FF", "fourseamfastball": "FF", "4-seam": "FF",
            "sinker": "SI", "twoseamfastball": "SI", "two-seam": "SI", "cutter": "FC",
            "slider": "SL", "sweeper": "ST", "curveball": "CU", "knucklecurve": "KC",
            "changeup": "CH", "splitter": "FS", "forkball": "FO", "screwball": "SC"}

SHAPE = ["velo", "spin", "ivb", "hb", "rel_z", "rel_x", "ext"]
FEATURES = SHAPE + ["arm_angle", "d_velo", "d_ivb", "d_hb", "group_code"]
GROUP_CODE = {"fastball": 0, "cutter": 1, "breaking": 2, "offspeed": 3}
SWINGS = {"swinging_strike", "swinging_strike_blocked", "foul", "foul_tip", "hit_into_play"}
WHIFFS = {"swinging_strike", "swinging_strike_blocked"}


def normalize_statcast(df: pd.DataFrame) -> pd.DataFrame:
    """Pitch-level Statcast -> pitcher's-view shape columns."""
    df = df[df["pitch_type"].isin(GROUP)].copy()
    arm = np.where(df["p_throws"] == "R", -1.0, 1.0)  # Statcast x is catcher's view
    out = pd.DataFrame({
        "pitcher": df["pitcher"], "player_name": df["player_name"], "throws": df["p_throws"],
        "pitch_type": df["pitch_type"],
        "velo": df["release_speed"], "spin": df["release_spin_rate"],
        "ivb": df["pfx_z"] * 12, "hb": df["pfx_x"] * 12 * arm,
        "rel_z": df["release_pos_z"], "rel_x": df["release_pos_x"] * arm,
        "ext": df["release_extension"],
        "arm_angle": df["arm_angle"] if "arm_angle" in df else np.nan,
        "description": df["description"], "run_value": -df["delta_run_exp"],
    })
    out["group"] = out["pitch_type"].map(GROUP)
    return out.dropna(subset=["velo", "ivb", "hb"])


def add_fastball_deltas(df: pd.DataFrame, key: str = "pitcher") -> pd.DataFrame:
    """How each pitch differs from the same pitcher's primary fastball (most-thrown FF/SI)."""
    fb = df[df["group"] == "fastball"]
    if fb.empty:
        prim = df.groupby(key)[["velo", "ivb", "hb"]].transform("max")
        return df.assign(d_velo=df["velo"] - prim["velo"], d_ivb=np.nan, d_hb=np.nan)
    counts = fb.groupby([key, "pitch_type"]).size().rename("n").reset_index()
    primary = counts.sort_values("n").drop_duplicates(key, keep="last")[[key, "pitch_type"]]
    means = fb.merge(primary, on=[key, "pitch_type"]).groupby(key)[["velo", "ivb", "hb"]].mean()
    m = df[[key]].join(means, on=key)
    return df.assign(d_velo=df["velo"] - m["velo"].values, d_ivb=df["ivb"] - m["ivb"].values,
                     d_hb=df["hb"] - m["hb"].values)


def build(year: int) -> None:
    raw = pd.read_csv(DATA / f"statcast_{year}.csv.gz", low_memory=False)
    df = add_fastball_deltas(normalize_statcast(raw))
    df["group_code"] = df["group"].map(GROUP_CODE)

    # --- whiff model: P(miss | swing) from shape + release + separation from the fastball ---
    sw = df[df["description"].isin(SWINGS)].copy()
    sw["whiff"] = sw["description"].isin(WHIFFS).astype(int)
    split = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=7)
    tr, te = next(split.split(sw, groups=sw["pitcher"]))  # test on pitchers never seen
    model = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05, max_leaf_nodes=48,
                                           categorical_features=[FEATURES.index("group_code")],
                                           random_state=7)
    model.fit(sw.iloc[tr][FEATURES], sw.iloc[tr]["whiff"])
    auc = roc_auc_score(sw.iloc[te]["whiff"], model.predict_proba(sw.iloc[te][FEATURES])[:, 1])
    model.fit(sw[FEATURES], sw["whiff"])  # final model on everything

    # --- reference arsenal: one row per pitcher x pitch type ---
    df["swing"] = df["description"].isin(SWINGS)
    df["whiff"] = df["description"].isin(WHIFFS)
    g = df.groupby(["pitcher", "pitch_type"])
    ref = g.agg(player_name=("player_name", "first"), throws=("throws", "first"),
                group=("group", "first"), n=("velo", "size"),
                **{c: (c, "mean") for c in SHAPE + ["arm_angle", "d_velo", "d_ivb", "d_hb"]},
                swings=("swing", "sum"), whiffs=("whiff", "sum"),
                run_value=("run_value", "sum")).reset_index()
    ref = ref[ref["n"] >= 100]
    ref["whiff_pct"] = 100 * ref["whiffs"] / ref["swings"].clip(lower=1)
    ref["rv100"] = 100 * ref["run_value"] / ref["n"]
    ref["group_code"] = ref["group"].map(GROUP_CODE)
    ref["xwhiff"] = 100 * model.predict_proba(ref[FEATURES])[:, 1]
    ref["pitch_name"] = ref["pitch_type"].map(NAMES)

    DATA.mkdir(exist_ok=True)
    ref.to_csv(DATA / f"reference_{year}.csv", index=False)
    with open(DATA / f"whiff_model_{year}.pkl", "wb") as f:
        pickle.dump(model, f)
    meta = {"year": year, "pitches": int(len(df)), "swings": int(len(sw)), "holdout_auc": round(auc, 3),
            "pitchers": int(df["pitcher"].nunique()), "arsenal_rows": int(len(ref)),
            "league_whiff_by_group": ref.groupby("group").apply(
                lambda x: round(100 * x["whiffs"].sum() / x["swings"].sum(), 1)).to_dict()}
    (DATA / f"meta_{year}.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta, indent=1))


# ---------------------------------------------------------------- your pitches

def load_trackman(path: str) -> pd.DataFrame:
    """A TrackMan (or similar) CSV -> pitcher's-view shape columns, one row per pitch."""
    t = pd.read_csv(path)
    col = {c.lower(): c for c in t.columns}
    pick = lambda *names: next((t[col[n]] for n in names if n in col), np.nan)
    throws = str(pick("pitcherthrows").iloc[0] if "pitcherthrows" in col else "Right")[0].upper()
    tag = pick("taggedpitchtype", "autopitchtype", "pitchtype").astype(str)
    df = pd.DataFrame({
        "pitcher_name": pick("pitcher"), "date": pick("date"),
        "pitch_type": tag.str.lower().str.replace(" ", "").map(TRACKMAN),
        "velo": pick("relspeed", "velocity"), "spin": pick("spinrate"),
        "ivb": pick("inducedvertbreak", "verticalbreak"), "hb": pick("horzbreak", "horizontalbreak"),
        "rel_z": pick("relheight"), "rel_x": pick("relside"), "ext": pick("extension"),
        "result": pick("pitchcall"),
    })
    df["throws"] = throws
    df = df.dropna(subset=["pitch_type", "velo", "ivb", "hb"])
    df["group"] = df["pitch_type"].map(GROUP)
    # Exports differ in sign conventions; orient so the fastball runs to the arm side (+)
    # and the release point sits on the arm side (+).
    fb = df[df["group"] == "fastball"]
    if len(fb) and fb["hb"].mean() < 0:
        df["hb"] = -df["hb"]
    if df["rel_x"].notna().any() and df["rel_x"].mean() < 0:
        df["rel_x"] = -df["rel_x"]
    df["pitcher"] = 0
    return add_fastball_deltas(df)


def arsenal(pitches: pd.DataFrame) -> pd.DataFrame:
    a = pitches.groupby("pitch_type").agg(
        n=("velo", "size"), velo_max=("velo", "max"),
        **{c: (c, "mean") for c in SHAPE + ["d_velo", "d_ivb", "d_hb"]}).reset_index()
    a["group"] = a["pitch_type"].map(GROUP)
    a["group_code"] = a["group"].map(GROUP_CODE)
    a["pitch_name"] = a["pitch_type"].map(NAMES)
    a["arm_angle"] = np.nan  # TrackMan bullpens don't report it; the model handles missing
    return a.sort_values("n", ascending=False)


def score(a: pd.DataFrame, ref: pd.DataFrame, model) -> pd.DataFrame:
    """Predicted whiff% per pitch and its percentile among MLB pitches of the same family."""
    a = a.copy()
    a["xwhiff"] = 100 * model.predict_proba(a[FEATURES])[:, 1]
    plus, pct = [], []
    for _, r in a.iterrows():
        fam = ref[ref["group"] == r["group"]]
        plus.append(100 * r["xwhiff"] / fam["xwhiff"].mean())
        pct.append(100 * (fam["xwhiff"] < r["xwhiff"]).mean())
    a["whiff_plus"], a["pctile"] = plus, pct
    return a


def comps(pitch: pd.Series, ref: pd.DataFrame, k: int = 5) -> pd.DataFrame:
    """Closest MLB pitches in the same family, by standardized shape + release distance."""
    fam = ref[ref["group"] == pitch["group"]].copy()
    feats = ["velo", "ivb", "hb", "spin", "rel_z", "ext"]
    weights = np.array([1.0, 1.5, 1.5, 0.5, 0.75, 0.5])  # movement matters most for shape
    sd = fam[feats].std()
    mine = pd.to_numeric(pitch[feats], errors="coerce").astype(float)
    diff = ((fam[feats].astype(float) - mine) / sd).fillna(0).to_numpy(dtype=float)
    fam["distance"] = np.sqrt((weights * diff ** 2).sum(axis=1))
    fam["similarity"] = 100 * np.exp(-fam["distance"] / 2)
    return fam.nsmallest(k, "distance")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "build":
        build(int(sys.argv[2]) if len(sys.argv) > 2 else 2025)
    else:
        print(__doc__)
