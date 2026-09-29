"""Export player shards (contract v1 addendum): players/<season>.json, playerlogs/<season>/<team>.json, playercareer/<bucket>.json."""
from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.warehouse.paths import table_path

from .contract import OUT, write

COLS = ["id", "name", "tid", "pos", "gp", "gs", "mpg", "share", "ppg", "rpg", "apg", "pts40", "trb40", "ast40", "stl40", "blk40", "tov40",
        "usg", "ts", "efg", "ast_pct", "orb_pct", "drb_pct", "stl_pct", "blk_pct", "tov_pct", "ftr", "tpar", "ft_pct", "tp_pct", "two_pct",
        "imp_o", "imp_d", "imp", "min", "ht", "cls", "wt"]
PCT_STATS = {"usg": True, "ts": True, "ast_pct": True, "orb_pct": True, "drb_pct": True, "stl_pct": True, "blk_pct": True,
             "tov_pct": False, "ftr": True, "efg": True, "imp": True, "imp_o": True, "imp_d": True, "pts40": True}
REF_MIN = 300  # DEFINITION: percentiles are ranks among D-I players with at least this many minutes that season
LOG_SEASONS = 3  # game logs exported for the most recent seasons only (size budget)
MIN_EXPORT = 50


def pct_ranks(s: pd.Series, ref: pd.Series, higher=True) -> np.ndarray:
    r = np.sort(ref.dropna().values)
    v = s.values.astype(float)
    p = np.searchsorted(r, v, side="right") / max(len(r), 1)
    p = np.where(np.isnan(v), np.nan, p)
    return p if higher else 1 - p


def export_players(seasons=None, last_season=2026):
    seasons = seasons or [y for y in range(2010, last_season + 1) if table_path("player_impacts", y).exists()]
    career = {}
    for y in seasons:
        pi = pd.read_parquet(table_path("player_impacts", y))
        d1 = set(pd.read_parquet(table_path("team_seasons", y)).query("is_d1").team_id)
        pi = pi[pi.team_id.isin(d1) & (pi["min"] >= MIN_EXPORT)].copy()
        pi["mpg"] = pi["min"] / pi.gp
        pi["ppg"], pi["rpg"], pi["apg"] = pi.pts / pi.gp, pi.trb / pi.gp, pi.ast / pi.gp
        pi["share"] = pi.min_share
        for a, b in (("pts40", "pts_40"), ("trb40", "trb_40"), ("ast40", "ast_40"), ("stl40", "stl_40"), ("blk40", "blk_40"), ("tov40", "tov_40")):
            pi[a] = pi[b]
        pi["id"], pi["tid"], pi["pos"], pi["gs"] = pi.athlete_id, pi.team_id, pi.position, pi.starts
        ro = table_path("rosters", y)
        pi["ht"], pi["cls"], pi["wt"] = None, None, None
        if ro.exists():
            r = pd.read_parquet(ro).set_index(["team_id", "athlete_id"])
            j = pd.MultiIndex.from_arrays([pi.team_id, pi.athlete_id])
            rr = r.reindex(j)
            pi["ht"] = rr.height.values
            pi["cls"] = rr.experience_display_value.values
            pi["wt"] = rr.weight.values
        ref = pi[pi["min"] >= REF_MIN]
        pc = {k: pct_ranks(pi[k], ref[k], hb) for k, hb in PCT_STATS.items()}
        rows = []
        for i, r in enumerate(pi[COLS].itertuples(index=False)):
            row = list(r) + [None if np.isnan(pc[k][i]) or r.min < REF_MIN else round(float(pc[k][i]), 3) for k in PCT_STATS]
            rows.append(row)
        cols = COLS + ["pc_" + k for k in PCT_STATS]
        write(f"players/{y}.json", {"season": y, "ref_min": REF_MIN, "cols": cols, "rows": rows})
        for r in pi.itertuples():
            career.setdefault(int(r.athlete_id) % 100, {}).setdefault(r.athlete_id, []).append(
                [y, r.team_id, int(r.gp), round(r.mpg, 1), round(r.ppg, 1), round(r.rpg, 1), round(r.apg, 1),
                 None if pd.isna(r.ts) else round(r.ts, 3), None if pd.isna(r.usg) else round(r.usg, 1), round(r.imp, 2)])
        # game logs for recent seasons
        if y > last_season - LOG_SEASONS:
            pg = pd.read_parquet(table_path("player_games", y))
            g = pd.read_parquet(table_path("games", y))[["game_id", "game_date", "home_id", "away_id", "neutral_site", "home_score", "away_score"]]
            pg = pg[~pg.did_not_play & (pg.minutes > 0) & pg.team_id.isin(d1)].drop(columns=["game_date"]).merge(g, on="game_id")
            pg["opp"] = np.where(pg.team_id == pg.home_id, pg.away_id, pg.home_id)
            pg["site"] = np.where(pg.neutral_site, "N", np.where(pg.team_id == pg.home_id, "H", "A"))
            pg["res"] = np.where(pg.team_id == pg.home_id, pg.home_score - pg.away_score, pg.away_score - pg.home_score)
            for tid, grp in pg.groupby("team_id"):
                logs = {}
                for r in grp.sort_values("game_date").itertuples():
                    logs.setdefault(r.athlete_id, []).append([r.game_id, str(r.game_date.date()), r.opp, r.site, int(r.res), int(r.minutes), int(r.points),
                                                              int(r.trb), int(r.ast), int(r.stl), int(r.blk), int(r.tov), int(r.pf), int(r.fgm), int(r.fga),
                                                              int(r.tpm), int(r.tpa), int(r.ftm), int(r.fta)])
                write(f"playerlogs/{y}/{tid}.json", {"season": y, "team": tid, "cols": ["game", "d", "opp", "site", "margin", "min", "pts", "reb", "ast", "stl", "blk", "tov", "pf", "fgm", "fga", "tpm", "tpa", "ftm", "fta"], "logs": logs})
        print("players", y, len(rows), flush=True)
    for b, d in career.items():
        write(f"playercareer/{b}.json", d)


if __name__ == "__main__":
    export_players()
