"""Replay the whole nightly path as if today were DATE (a past date), using a truncated copy of the data.

    python -m pipeline.replay 2026-02-15 [--nsim 3000] [--no-build]

Copies the warehouse, model artifacts and prediction log to data/rehearsal/, removes results on/after DATE (future games stay
scheduled, exactly like a real morning), then runs pipeline.nightly against those copies with ESPN re-ingesting DATE-3 .. DATE+7
(results on/after DATE are masked). Exports overwrite web/public/data; `make site` restores the normal site.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def truncate(wh: Path, season: int, cut: pd.Timestamp):
    g = pd.read_parquet(wh / "mbb" / "games" / f"{season}.parquet")
    late = g.game_date >= cut
    drop = set(g[late].game_id)
    g.loc[late, ["completed", "home_score", "away_score"]] = [False, float("nan"), float("nan")]
    g.loc[late, ["has_team_box", "has_player_box"]] = False
    g.to_parquet(wh / "mbb" / "games" / f"{season}.parquet", index=False)
    for t in ("team_games", "player_games"):
        p = wh / "mbb" / t / f"{season}.parquet"
        if not p.exists():  # the upcoming season has no box tables yet
            continue
        d = pd.read_parquet(p)
        d[~d.game_id.isin(drop)].to_parquet(p, index=False)
    return len(drop)


def main():
    """A fresh rehearsal of one date: same as `python -m pipeline.nightly --rehearsal --rehearsal-reset --today DATE --force`."""
    ap = argparse.ArgumentParser()
    ap.add_argument("date")
    ap.add_argument("--nsim", type=int, default=3000)
    ap.add_argument("--no-build", action="store_true")
    a = ap.parse_args()
    cmd = [sys.executable, "-m", "pipeline.nightly", "--today", a.date, "--nsim", str(a.nsim), "--force", "--rehearsal", "--rehearsal-reset"]
    subprocess.run(cmd + (["--no-build"] if a.no_build else []), cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
