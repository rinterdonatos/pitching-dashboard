"""Download a season of pitch-level Statcast data from Baseball Savant (via pybaseball).

    .venv\\Scripts\\python.exe fetch_statcast.py 2025

Writes data/statcast_<year>.csv.gz with just the columns the lab uses.
"""
import sys
from pathlib import Path

import pandas as pd
from pybaseball import cache, statcast

COLS = ["game_date", "game_type", "pitcher", "player_name", "p_throws", "pitch_type", "pitch_name",
        "release_speed", "release_spin_rate", "pfx_x", "pfx_z", "release_pos_x", "release_pos_z",
        "release_extension", "arm_angle", "description", "delta_run_exp", "balls", "strikes"]

SEASONS = {2025: ("2025-03-27", "2025-09-28"), 2024: ("2024-03-28", "2024-09-30")}


def main(year: int) -> None:
    start, end = SEASONS[year]
    cache.enable()
    df = statcast(start_dt=start, end_dt=end, parallel=True)
    df = df[df["game_type"] == "R"]
    keep = [c for c in COLS if c in df.columns]
    out = Path("data")
    out.mkdir(exist_ok=True)
    path = out / f"statcast_{year}.csv.gz"
    df[keep].to_csv(path, index=False)
    print(f"{len(df):,} pitches -> {path}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2025)
