"""Parse hoopR/ESPN play-by-play into a compact score-change table (local only; play-by-play is never published).

    python -m pipeline.pbp.parse [2016 2017 ...]

Output: warehouse table pbp_scores/<season>.parquet (published with the warehouse; raw play-by-play is not): one row per scoring change per game (plus the opening tip and the final row) with
game_id, elapsed (seconds since tip; regulation 2400 s, each OT 300 s; quarter-format feeds handled), period, home, away.
Also prints coverage against the warehouse box scores: share of completed D-I games with play-by-play, and the share whose
final play-by-play score equals the box score.
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from pipeline.ingest import download
from pipeline.warehouse.paths import table_path

FIRST, REG, HALF, OT = 2016, 2400, 1200, 300  # DEFINITION: first play-by-play season used; game clock lengths in seconds
# The game clock as displayed ("MM:SS", or "SS.s" in the last minute in some seasons) is the only clock field that is right in every
# season: older files compute *_seconds_remaining for four quarters (period 1 runs to 3000 s), which is wrong for men's halves.
COLS = ["game_id", "sequence_number", "period_number", "clock_display_value", "home_score", "away_score"]


def clock_seconds(c: pd.Series) -> pd.Series:
    c = c.astype(str)
    mm = c.str.extract(r"^(\d+):(\d+(?:\.\d+)?)$").astype(float)
    ss = pd.to_numeric(c.where(~c.str.contains(":")), errors="coerce")
    return (mm[0] * 60 + mm[1]).fillna(ss)


def elapsed(period: pd.Series, rem: pd.Series, quarters: pd.Series | None = None) -> pd.Series:
    """Seconds since tip from the period and the seconds left in it. Some feeds record a game in four 10-minute quarters
    (`quarters` True): then periods 1-4 are regulation and overtime starts at period 5."""
    p = period.astype(int)
    q = np.zeros(len(p), bool) if quarters is None else np.asarray(quarters, bool)
    halves = np.where(p <= 2, (p - 1) * HALF + (HALF - rem), REG + (p - 3) * OT + (OT - rem))
    qtrs = np.where(p <= 4, (p - 1) * (REG // 4) + (REG // 4 - rem), REG + (p - 5) * OT + (OT - rem))
    return np.where(q, qtrs, halves)


def scores_table(raw: pd.DataFrame) -> pd.DataFrame:
    d = raw.dropna(subset=["period_number", "home_score", "away_score"]).copy()
    d = d.sort_values(["game_id", "sequence_number"])
    rem = clock_seconds(d.clock_display_value)
    d["rem"] = rem.groupby(d.game_id).ffill().fillna(0).clip(lower=0)
    # quarter format: a third period with more than an overtime's worth of clock left
    quarters = ((d.period_number >= 3) & (d.rem > OT)).groupby(d.game_id).transform("any")
    d["elapsed"] = elapsed(d.period_number, d.rem, quarters)
    # sequence numbers are not chronological: late corrections are appended after "End Game"; order by game time first
    # within one clock time, sequence numbers can still be out of order; scores never decrease, so total points breaks ties
    d["_tot"] = d.home_score + d.away_score
    d = d.sort_values(["game_id", "elapsed", "_tot", "sequence_number"], kind="stable")
    d["home"], d["away"] = d.home_score.astype(int), d.away_score.astype(int)
    g = d.groupby("game_id")
    change = (d.home != g.home.shift()) | (d.away != g.away.shift())
    first, last = ~d.game_id.duplicated(), ~d.game_id.duplicated(keep="last")
    out = d[change | first | last][["game_id", "elapsed", "period_number", "home", "away"]].rename(columns={"period_number": "period"})
    out["elapsed"] = out.elapsed.round().astype(int)
    out["period"] = out.period.astype(int)
    out["game_id"] = out.game_id.astype(str)
    return out.drop_duplicates(["game_id", "elapsed", "home", "away"]).reset_index(drop=True)


def parse_season(y: int) -> dict:
    p = download.fetch("pbp", y)
    if p is None:
        return {"season": y, "pbp": False}
    s = scores_table(pd.read_parquet(p, columns=COLS))
    out = table_path("pbp_scores", y)
    out.parent.mkdir(parents=True, exist_ok=True)
    s.to_parquet(out, index=False)
    g = pd.read_parquet(table_path("games", y))
    g = g[g.completed & g.both_d1 & (g.game_type != "exhibition")]
    fin = s.groupby("game_id").last()
    m = g.set_index("game_id").join(fin[["home", "away"]], how="left")
    have = m.home.notna()
    match = (m.home == m.home_score) & (m.away == m.away_score)
    return {"season": y, "d1_games": int(len(m)), "with_pbp": round(float(have.mean()), 4),
            "final_matches_box": round(float(match[have].mean()), 4), "score_rows": int(len(s))}


if __name__ == "__main__":
    for y in [int(a) for a in sys.argv[1:]] or range(FIRST, 2028):
        print(parse_season(y), flush=True)
