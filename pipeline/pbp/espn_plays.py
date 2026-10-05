"""Live-season score timelines from ESPN game summaries (the nightly ingest already caches them), so win-probability
charts do not wait for the hoopR play-by-play release.

    update(season) -> merges every cached summary of a completed game into pbp_scores/<season>.parquet
"""
from __future__ import annotations

import json

import pandas as pd

from pipeline.ingest.espn import RAW
from pipeline.warehouse.paths import table_path

from .parse import scores_table


def plays_frame(summary: dict, game_id: str) -> pd.DataFrame:
    """ESPN `plays` in the hoopR column layout that parse.scores_table expects."""
    rows = [{"game_id": game_id, "sequence_number": int(p.get("sequenceNumber") or 0), "period_number": (p.get("period") or {}).get("number"),
             "clock_display_value": (p.get("clock") or {}).get("displayValue"), "home_score": p.get("homeScore"), "away_score": p.get("awayScore")}
            for p in (summary or {}).get("plays") or []]
    return pd.DataFrame(rows, columns=["game_id", "sequence_number", "period_number", "clock_display_value", "home_score", "away_score"])


def update(season: int) -> int:
    """Add (or replace) timelines for completed games of `season` whose ESPN summary is cached. Returns games written."""
    g = pd.read_parquet(table_path("games", season))
    done = g[g.completed & (g.game_type != "exhibition")].game_id.astype(str)
    frames = []
    for gid in done:
        f = RAW / "summary" / f"{gid}.json"
        if f.exists():
            p = plays_frame(json.loads(f.read_text(encoding="utf8")), gid)
            if len(p):
                frames.append(p)
    if not frames:
        return 0
    new = scores_table(pd.concat(frames, ignore_index=True))
    path = table_path("pbp_scores", season)
    old = pd.read_parquet(path) if path.exists() else new.iloc[:0]
    out = pd.concat([old[~old.game_id.isin(new.game_id)], new], ignore_index=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path, index=False)
    return int(new.game_id.nunique())
