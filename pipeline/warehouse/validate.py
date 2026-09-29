"""Nightly validation of one season's warehouse tables. Returns a list of failure strings (empty = ok)."""
from __future__ import annotations

import pandas as pd

from .paths import table_path


def validate(season: int) -> list[str]:
    bad = []
    g = pd.read_parquet(table_path("games", season))
    tg = pd.read_parquet(table_path("team_games", season))
    pg = pd.read_parquet(table_path("player_games", season))
    if not g.game_id.is_unique:
        bad.append("duplicate game ids")
    if tg.duplicated(["game_id", "team_id"]).any():
        bad.append("duplicate team-game rows")
    n = tg.groupby("game_id").size()
    if (n > 2).any():
        bad.append("game with more than two team rows")
    d1 = g[g.completed & g.both_d1]
    both = d1.game_id.map(n).fillna(0).eq(2)
    if len(d1) and both.mean() < 0.97:
        bad.append(f"only {both.mean():.3f} of completed D-I games have both team boxes")
    s = pg.groupby(["game_id", "team_id"]).points.sum().rename("pp").reset_index()
    m = tg.merge(s, on=["game_id", "team_id"])
    if len(m) and ((m.points - m.pp).abs() <= 2).mean() < 0.95:
        bad.append("team points do not match player points")
    d = tg[tg.both_d1 & tg.fga.notna()]
    poss = d.fga - d.orb + d.tov + 0.486 * d.fta
    if len(d) and not (55 < poss.mean() < 80):
        bad.append("implausible possessions")
    c = g[g.completed]
    if len(c) and ((c.home_score == c.away_score) | (c.home_score < 0) | (c.away_score < 0)).any():
        bad.append("tied or negative scores")
    if not g.game_date.between(pd.Timestamp(season - 1, 9, 1), pd.Timestamp(season, 5, 1)).all():
        bad.append("game dates outside the season window")
    return bad
