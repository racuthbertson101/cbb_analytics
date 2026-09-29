"""Replay the whole nightly path as if today were DATE (a past date), using a truncated copy of the data.

    python -m pipeline.replay 2026-02-15 [--nsim 3000] [--no-build]

Copies data/warehouse and data/backtest to data/replay/, removes results on/after DATE (future games stay scheduled, exactly like a real
morning), then runs pipeline.nightly against those copies with ESPN re-ingesting DATE-3 .. DATE+7 (results on/after DATE are masked).
Exports overwrite web/public/data; run `make site` afterwards to restore the normal site.
"""
from __future__ import annotations

import argparse
import os
import shutil
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
        d = pd.read_parquet(p)
        d[~d.game_id.isin(drop)].to_parquet(p, index=False)
    return len(drop)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date")
    ap.add_argument("--nsim", type=int, default=3000)
    ap.add_argument("--no-build", action="store_true")
    a = ap.parse_args()
    d = pd.Timestamp(a.date)
    season = d.year + 1 if d.month >= 9 else d.year
    rep = ROOT / "data" / "replay"
    if rep.exists():
        shutil.rmtree(rep)
    shutil.copytree(ROOT / "data" / "warehouse", rep / "warehouse")
    shutil.copytree(ROOT / "data" / "backtest", rep / "backtest")
    n = truncate(rep / "warehouse", season, d)
    print(f"replay {a.date}: truncated {n} games of season {season}")
    env = dict(os.environ, CBB_WAREHOUSE=str(rep / "warehouse"), CBB_ARTIFACTS=str(rep / "backtest"), CBB_PREDICTION_LOG=str(rep / "log.parquet"))
    cmd = [sys.executable, "-m", "pipeline.nightly", "--today", a.date, "--nsim", str(a.nsim), "--force"] + (["--no-build"] if a.no_build else [])
    subprocess.run(cmd, cwd=ROOT, env=env, check=True)


if __name__ == "__main__":
    main()
