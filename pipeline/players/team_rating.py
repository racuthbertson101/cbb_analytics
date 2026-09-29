"""Player-driven team rating: bottom-up from roster minutes shares and fitted player impact (in the spirit of EvanMiya).

team margin rating = sum_p share_p * impact_p  (+ unfilled minutes * replacement impact), share_p = minutes share (sums to 5).
Season-end version uses the season's own minutes; the preseason version projects next season from returning/incoming players'
previous-season impact and minutes share.

DEFINITION: replacement impact = minutes-weighted mean impact of players in the bottom half of their team's minutes (bench).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.warehouse.paths import table_path


def replacement(pi: pd.DataFrame) -> float:
    med = pi.groupby("team_id")["min"].transform("median")
    b = pi[pi["min"] < med]
    return float(np.average(b.imp, weights=b["min"]))


def season_final(y: int) -> pd.DataFrame:
    pi = pd.read_parquet(table_path("player_impacts", y))
    g = pi.assign(o=pi.min_share * pi.imp_o, d=pi.min_share * pi.imp_d).groupby("team_id")[["o", "d"]].sum()
    g["pd_margin"] = g.o + g.d
    return g.rename(columns={"o": "pd_off", "d": "pd_def"})


def preseason(next_season: int, roster: pd.DataFrame) -> pd.DataFrame:
    """roster: DataFrame(team_id, athlete_id) for next season. Uses impacts/shares from next_season-1."""
    pi = pd.read_parquet(table_path("player_impacts", next_season - 1)).set_index("athlete_id")
    rep = replacement(pi.reset_index())
    m = roster.merge(pi[["min_share", "imp_o", "imp_d", "imp"]], left_on="athlete_id", right_index=True, how="left")
    m = m.dropna(subset=["min_share"])
    tot = m.groupby("team_id").min_share.sum()
    scale = np.minimum(1.0, 5.0 / tot)  # if returning shares exceed 5, scale down
    m["sh"] = m.min_share * m.team_id.map(scale)
    g = m.assign(o=m.sh * m.imp_o, d=m.sh * m.imp_d).groupby("team_id")[["o", "d", "sh"]].sum()
    g["unfilled"] = 5.0 - g.sh
    g["pd_margin"] = g.o + g.d + g.unfilled * rep
    return g.rename(columns={"o": "pd_off", "d": "pd_def"})
