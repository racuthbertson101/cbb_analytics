"""Shot chart shards (Phase 9 stretch): binned shot locations per team and player, plus a league baseline.

Shots (ESPN x/y from the sportsdataverse release, free throws excluded) are converted to hoop-relative feet: lateral in [-25, 25],
depth = distance from the hoop toward mid-court (baseline side negative), then binned into BIN x BIN ft cells.
Shard: shots/<season>/<team>.json = {bins:[[bx,by,attempts,makes]...], players:{pid:[...]}} and shots/<season>/league.json.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.ingest import download
from pipeline.warehouse.paths import CURRENT_SEASON, table_path

from .contract import write

BIN = 3.0
SHOT_SEASONS = 1  # latest season only: the 2025 shots file covers only ~1/4 as many shots as 2026 (source gap, KNOWN_ISSUES)
MIN_PLAYER_SHOTS = 25


def prep(season: int) -> pd.DataFrame | None:
    p = download.fetch("shots", season)
    if p is None:
        return None
    d = pd.read_parquet(p, columns=["game_id", "team_id", "athlete_id_1", "type_text", "scoring_play", "score_value", "coordinate_x", "coordinate_y"])
    d = d[~d.type_text.astype(str).str.contains("FreeThrow", na=False)]
    d = d[d.coordinate_x.between(-47, 47) & d.coordinate_y.between(-25, 25)].copy()
    d["lat"] = d.coordinate_y.astype(float)
    d["depth"] = 41.75 - d.coordinate_x.abs()
    d["bx"] = np.floor((d.lat + 25) / BIN).astype(int)
    d["by"] = np.floor((d.depth + 6) / BIN).astype(int)
    d["made"] = d.scoring_play.fillna(False).astype(int)
    d["team_id"] = pd.to_numeric(d.team_id, errors="coerce").astype("Int64").astype(str)
    d["pid"] = pd.to_numeric(d.athlete_id_1, errors="coerce").astype("Int64").astype(str)
    return d


def bins(df: pd.DataFrame):
    g = df.groupby(["bx", "by"]).made.agg(["size", "sum"]).reset_index()
    return [[int(r.bx), int(r.by), int(r["size"]), int(r["sum"])] for _, r in g.iterrows()]


def export_shots(last_season=CURRENT_SEASON):
    for y in range(last_season - SHOT_SEASONS + 1, last_season + 1):
        d = prep(y)
        if d is None:
            continue
        ts = pd.read_parquet(table_path("team_seasons", y))
        d1 = set(ts[ts.is_d1].team_id)
        d = d[d.team_id.isin(d1)]
        write(f"shots/{y}/league.json", {"bin": BIN, "origin": [-25, -6], "bins": bins(d), "n": int(len(d))})
        for tid, g in d.groupby("team_id"):
            players = {}
            for pid, gp in g.groupby("pid"):
                if pid != "<NA>" and len(gp) >= MIN_PLAYER_SHOTS:
                    players[pid] = bins(gp)
            write(f"shots/{y}/{tid}.json", {"n": int(len(g)), "bins": bins(g), "players": players})
        print("shots", y, len(d), flush=True)


if __name__ == "__main__":
    export_shots()
