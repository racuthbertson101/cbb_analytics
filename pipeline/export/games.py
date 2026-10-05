"""Game-level shards for the Game, Team and Player pages (contract v1 addendum, IMPROVEMENT_PLAN Phase 3a).

    teamlogs/<season>/<team>.json    every game's team box for both sides, 2010+ (D-I teams)
    playerlogs/<season>/<team>.json  every player's game lines, 2017+ (D-I teams), with pre-game expectations

Format: {"v": 2, "season", "team", "cols": [...], "rows" | "logs": ...}; integers where the stat is a count, floats 1 decimal.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.warehouse.paths import table_path

from .contract import write

TLOG_FIRST = 2010   # DEFINITION: first season with team logs (same as the rest of the site's history)
PLOG_FIRST = 2017   # DEFINITION: first season with player logs (size budget, IMPROVEMENT_PLAN 4.2)
MIN_PRIOR_MINUTES = 30  # DEFINITION: below this many earlier minutes a player has no pre-game rate (expectation left empty)
V = 2

BOX = ["fgm", "fga", "tpm", "tpa", "ftm", "fta", "orb", "drb", "ast", "stl", "blk", "tov", "pf"]
EXTRA = {"points_in_paint": "pip", "fast_break_points": "fbp", "turnover_points": "top", "largest_lead": "ll"}
TCOLS = ["game", "d", "opp", "site", "t", "pts", "opp_pts"] + BOX + list(EXTRA.values()) + ["o_" + c for c in BOX + list(EXTRA.values())]
# the first 19 player-log columns keep their v1 positions (the Player page indexes them)
PCOLS = ["game", "d", "opp", "site", "margin", "min", "pts", "reb", "ast", "stl", "blk", "tov", "pf", "fgm", "fga", "tpm", "tpa", "ftm",
         "fta", "st", "orb", "drb", "ts", "os", "xpts", "xreb"]


def _i(x):
    return None if pd.isna(x) else int(x)


def expected_lines(pg: pd.DataFrame) -> pd.DataFrame:
    """Pre-game expectation for each player-game: season-to-date points and rebounds per minute from games on EARLIER dates
    (never the game itself or the same day) times the minutes actually played. Empty below MIN_PRIOR_MINUTES earlier minutes.

    pg: one season's player-games with athlete_id, team_id, game_date, minutes, points, trb.
    """
    d = pg[["athlete_id", "team_id", "game_date", "minutes", "points", "trb"]].copy()
    day = d.groupby(["athlete_id", "team_id", "game_date"], as_index=False)[["minutes", "points", "trb"]].sum()
    day = day.sort_values(["athlete_id", "team_id", "game_date"])
    g = day.groupby(["athlete_id", "team_id"])
    for c in ("minutes", "points", "trb"):
        day["prior_" + c] = g[c].cumsum() - day[c]  # totals over strictly earlier dates
    out = d.merge(day[["athlete_id", "team_id", "game_date", "prior_minutes", "prior_points", "prior_trb"]],
                  on=["athlete_id", "team_id", "game_date"], how="left")
    ok = out.prior_minutes >= MIN_PRIOR_MINUTES
    out["xpts"] = np.where(ok, out.prior_points / out.prior_minutes.where(ok) * out.minutes, np.nan)
    out["xreb"] = np.where(ok, out.prior_trb / out.prior_minutes.where(ok) * out.minutes, np.nan)
    return out[["xpts", "xreb"]].set_axis(pg.index)


def team_logs(y: int) -> int:
    tg = pd.read_parquet(table_path("team_games", y))
    if tg.empty:
        return 0
    d1 = set(pd.read_parquet(table_path("team_seasons", y)).query("is_d1").team_id)
    g = pd.read_parquet(table_path("games", y))[["game_id", "home_id"]]
    ex = tg[["game_id", "team_id"] + list(EXTRA)].rename(columns={"team_id": "opp_id", **{k: "o_" + v for k, v in EXTRA.items()}})
    t = tg[tg.team_id.isin(d1) & (tg.game_type != "exhibition")].merge(g, on="game_id").merge(ex, on=["game_id", "opp_id"], how="left")
    t["site"] = np.where(t.neutral_site, "N", np.where(t.team_id == t.home_id, "H", "A"))
    t = t.rename(columns={**EXTRA, **{"opp_" + c: "o_" + c for c in BOX}})
    n = 0
    for tid, grp in t.groupby("team_id"):
        rows = []
        for r in grp.sort_values("game_date").itertuples(index=False):
            r = r._asdict()
            rows.append([r["game_id"], str(r["game_date"].date()), r["opp_id"], r["site"], r["game_type"], _i(r["points"]), _i(r["opp_points"])]
                        + [_i(r[c]) for c in BOX + list(EXTRA.values())] + [_i(r["o_" + c]) for c in BOX + list(EXTRA.values())])
        write(f"teamlogs/{y}/{tid}.json", {"v": V, "season": y, "team": tid, "cols": TCOLS, "rows": rows})
        n += 1
    return n


def player_logs(y: int) -> int:
    pg = pd.read_parquet(table_path("player_games", y))
    if pg.empty:
        return 0
    d1 = set(pd.read_parquet(table_path("team_seasons", y)).query("is_d1").team_id)
    g = pd.read_parquet(table_path("games", y))[["game_id", "game_date", "home_id", "away_id", "neutral_site", "home_score", "away_score", "game_type"]]
    pg = pg[~pg.did_not_play & (pg.minutes > 0)].drop(columns=["game_date"]).merge(g, on="game_id")
    pg = pg[pg.game_type != "exhibition"]
    pg[["xpts", "xreb"]] = expected_lines(pg)
    pg = pg[pg.team_id.isin(d1)]
    home = pg.team_id == pg.home_id
    pg["opp"] = np.where(home, pg.away_id, pg.home_id)
    pg["site"] = np.where(pg.neutral_site, "N", np.where(home, "H", "A"))
    pg["ts"] = np.where(home, pg.home_score, pg.away_score)
    pg["os"] = np.where(home, pg.away_score, pg.home_score)
    n = 0
    for tid, grp in pg.groupby("team_id"):
        logs, names = {}, {}
        for r in grp.sort_values(["game_date", "game_id"]).itertuples():
            names[r.athlete_id] = r.name
            logs.setdefault(r.athlete_id, []).append([
                r.game_id, str(r.game_date.date()), r.opp, r.site, _i(r.ts - r.os), _i(r.minutes), _i(r.points), _i(r.trb), _i(r.ast),
                _i(r.stl), _i(r.blk), _i(r.tov), _i(r.pf), _i(r.fgm), _i(r.fga), _i(r.tpm), _i(r.tpa), _i(r.ftm), _i(r.fta),
                int(bool(r.starter)), _i(r.orb), _i(r.drb), _i(r.ts), _i(r.os),
                None if np.isnan(r.xpts) else round(float(r.xpts), 1), None if np.isnan(r.xreb) else round(float(r.xreb), 1)])
        write(f"playerlogs/{y}/{tid}.json", {"v": V, "season": y, "team": tid, "cols": PCOLS, "names": names, "logs": logs})
        n += 1
    return n


def export_logs(seasons=None):
    from pipeline.warehouse.paths import CURRENT_SEASON

    seasons = seasons or range(TLOG_FIRST, CURRENT_SEASON + 1)
    for y in seasons:
        if not table_path("team_games", y).exists():
            continue
        nt = team_logs(y)
        np_ = player_logs(y) if y >= PLOG_FIRST and table_path("player_games", y).exists() else 0
        print(f"logs {y}: {nt} team, {np_} player shards", flush=True)


if __name__ == "__main__":
    export_logs()
