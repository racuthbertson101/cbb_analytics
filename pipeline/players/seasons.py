"""Player season lines with per-40 and advanced rates computed with team totals (ratio-of-sums over player-games)."""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from pipeline.warehouse.paths import FIRST_SEASON, WH, table_path

COUNT = ["min", "pts", "fgm", "fga", "tpm", "tpa", "ftm", "fta", "orb", "drb", "trb", "ast", "stl", "blk", "tov", "pf"]


def player_games_enriched(y: int) -> pd.DataFrame:
    pg = pd.read_parquet(table_path("player_games", y))
    tg = pd.read_parquet(table_path("team_games", y))
    g = pd.read_parquet(table_path("games", y))[["game_id", "both_d1", "game_type"]]
    pg = pg[~pg.did_not_play & pg.minutes.notna() & (pg.minutes > 0)].rename(columns={"minutes": "min", "points": "pts"})
    tmin = pg.groupby(["game_id", "team_id"])["min"].sum().rename("t_min")
    keep = ["game_id", "team_id", "fgm", "fga", "tpm", "tpa", "ftm", "fta", "orb", "drb", "trb", "ast", "tov", "blk", "stl",
            "opp_fgm", "opp_fga", "opp_tpa", "opp_fta", "opp_orb", "opp_drb", "opp_tov"]
    tg = tg[keep].copy()
    tg.columns = ["game_id", "team_id"] + ["t_" + c for c in keep[2:]]
    m = pg.merge(tmin, on=["game_id", "team_id"]).merge(tg, on=["game_id", "team_id"]).merge(g, on="game_id")
    return m[m.game_type != "exhibition"]


def build_season(y: int) -> pd.DataFrame:
    m = player_games_enriched(y)
    m["gp"] = 1
    m["starts"] = m.starter.astype(int)
    m["poss_tm"] = m.t_fga - m.t_orb + m.t_tov + 0.486 * m.t_fta  # team possessions used only inside rate denominators
    m["opp_poss"] = m.t_opp_fga - m.t_opp_orb + m.t_opp_tov + 0.486 * m.t_opp_fta
    fs = m["min"] / (m.t_min / 5)  # fraction of the game played (0..1)
    # numerators / denominators per player-game, summed over the season
    m["n_usg"] = (m.fga + 0.44 * m.fta + m.tov) * (m.t_min / 5)
    m["d_usg"] = m["min"] * (m.t_fga + 0.44 * m.t_fta + m.t_tov)
    m["n_ast"] = m.ast
    m["d_ast"] = (m["min"] / (m.t_min / 5)) * m.t_fgm - m.fgm
    m["n_orb"] = m.orb * (m.t_min / 5)
    m["d_orb"] = m["min"] * (m.t_orb + m.t_opp_drb)
    m["n_drb"] = m.drb * (m.t_min / 5)
    m["d_drb"] = m["min"] * (m.t_drb + m.t_opp_orb)
    m["n_stl"] = m.stl * (m.t_min / 5)
    m["d_stl"] = m["min"] * m.opp_poss
    m["n_blk"] = m.blk * (m.t_min / 5)
    m["d_blk"] = m["min"] * (m.t_opp_fga - m.t_opp_tpa)
    m["poss_on"] = fs * m.poss_tm  # possessions while on the floor (approx)
    m["min_share_num"] = m["min"]
    m["team_min_5"] = m.t_min / 5
    sumcols = COUNT + ["gp", "starts", "n_usg", "d_usg", "n_ast", "d_ast", "n_orb", "d_orb", "n_drb", "d_drb", "n_stl", "d_stl",
                       "n_blk", "d_blk", "poss_on", "team_min_5"]
    a = m.groupby(["team_id", "athlete_id"], as_index=False)[sumcols].sum()
    names = m.sort_values("game_date").groupby("athlete_id").agg(name=("name", "last"), position=("position", "last"))
    a = a.merge(names, on="athlete_id")
    # minutes share of team total across the season: player minutes / team-minutes-per-slot
    tm5 = m.groupby("team_id").apply(lambda d: d.drop_duplicates("game_id").team_min_5.sum(), include_groups=False).rename("tm5")
    a = a.merge(tm5, on="team_id")
    a["min_share"] = a["min"] / a.tm5
    a["mpg"] = a["min"] / a.gp
    r = pd.DataFrame(index=a.index)
    a["usg"] = 100 * a.n_usg / a.d_usg.replace(0, np.nan)
    a["ast_pct"] = 100 * a.n_ast / a.d_ast.where(a.d_ast > 0)
    a["orb_pct"] = 100 * a.n_orb / a.d_orb.replace(0, np.nan)
    a["drb_pct"] = 100 * a.n_drb / a.d_drb.replace(0, np.nan)
    a["stl_pct"] = 100 * a.n_stl / a.d_stl.replace(0, np.nan)
    a["blk_pct"] = 100 * a.n_blk / a.d_blk.replace(0, np.nan)
    a["ts"] = a.pts / (2 * (a.fga + 0.44 * a.fta)).replace(0, np.nan)
    a["efg"] = (a.fgm + 0.5 * a.tpm) / a.fga.replace(0, np.nan)
    a["tov_pct"] = 100 * a.tov / (a.fga + 0.44 * a.fta + a.tov).replace(0, np.nan)
    a["ftr"] = a.fta / a.fga.replace(0, np.nan)
    a["tpar"] = a.tpa / a.fga.replace(0, np.nan)
    a["ft_pct"] = a.ftm / a.fta.replace(0, np.nan)
    a["tp_pct"] = a.tpm / a.tpa.replace(0, np.nan)
    a["two_pct"] = (a.fgm - a.tpm) / (a.fga - a.tpa).replace(0, np.nan)
    for c in ["pts", "fga", "fta", "tpa", "orb", "drb", "trb", "ast", "stl", "blk", "tov", "pf"]:
        a[c + "_40"] = 40 * a[c] / a["min"]
    for c in ["pts", "fga", "tov", "ast", "trb", "stl", "blk"]:
        a[c + "_100"] = 100 * a[c] / a.poss_on.replace(0, np.nan)
    a["season"] = y
    return a.drop(columns=[c for c in a.columns if c.startswith(("n_", "d_"))] + ["team_min_5"])


def build_all(seasons=None):
    out = {}
    for y in seasons or range(FIRST_SEASON, 2027):
        if not table_path("player_games", y).exists():
            continue
        a = build_season(y)
        p = table_path("player_seasons", y)
        p.parent.mkdir(parents=True, exist_ok=True)
        a.to_parquet(p, index=False)
        out[y] = len(a)
        print(y, len(a), flush=True)
    return out


if __name__ == "__main__":
    build_all([int(x) for x in sys.argv[1:]] or None)
