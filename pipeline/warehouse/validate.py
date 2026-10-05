"""Nightly validation of one season's warehouse tables. Returns a list of failure strings (empty = ok)."""
from __future__ import annotations

import pandas as pd

from .paths import table_path


# DEFINITIONS (AUDIT R-4): ceilings on missing values in completed D-I games, and the player-sum agreement required.
NULL_CEILING = 0.01          # share of completed D-I team-games allowed to miss each core box stat
PLAYER_SUM_LIVE = 0.99       # live season: share of team-games whose player points sum within 2 of the team total
PLAYER_SUM_HISTORY = 0.95    # older seasons (2008-2013 box scores are known to be incomplete, KNOWN_ISSUES)
CORE_TEAM_STATS = ["fga", "fta", "orb", "drb", "tov"]


def validate(season: int, live: bool = False) -> list[str]:
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
    ok = ((m.points - m.pp).abs() <= 2).mean() if len(m) else 1.0
    need = PLAYER_SUM_LIVE if live else PLAYER_SUM_HISTORY
    if ok < need:
        bad.append(f"team points match player points in only {ok:.3f} of team-games (need {need})")
    core = tg[tg.both_d1.fillna(False).astype(bool)]
    for c in CORE_TEAM_STATS:
        share = core[c].isna().mean() if len(core) else 0.0
        if share > NULL_CEILING:
            bad.append(f"{c} missing in {share:.3f} of completed D-I team-games (ceiling {NULL_CEILING})")
    played = pg[~pg.did_not_play.fillna(False).astype(bool)] if "did_not_play" in pg else pg
    if len(played) and played.minutes.isna().mean() > NULL_CEILING:
        bad.append(f"player minutes missing in {played.minutes.isna().mean():.3f} of player-games (ceiling {NULL_CEILING})")
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
