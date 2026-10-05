"""Compare-page shards (IMPROVEMENT_PLAN Phase 4a.2, 4a.4).

    teamhistory/<team>.json   every game since 2008 (head-to-head across seasons): [game, d, opp, site, pts, opp_pts, pm]
    analogs.json              calibration view: for a predicted favorite margin and possessions, what happened in past games
                              with a predicted margin within 1.5 and possessions within 3 (walk-forward predictions, 2012+)
    analog_games.json         lazily loaded: per game, the 8 four-factor matchup gaps, for "closest past games" on Compare
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from pipeline.models.backtest import BT
from pipeline.warehouse.paths import FIRST_SEASON, table_path

from .contract import OUT, write

V = 1
WIN_M, WIN_P = 1.5, 3.0      # DEFINITION: analog window (predicted margin +/- 1.5, predicted possessions +/- 3)
GRID_M = np.arange(0, 30.5, 0.5)
GRID_P = np.arange(58, 81, 1.0)
MIN_ANALOGS = 30             # DEFINITION: cells with fewer past games are left empty
ANALOG_FIRST = 2015          # DEFINITION: first season in analog_games.json (size)


def export_teamhistory(last_season: int):
    P = pd.read_parquet(BT / "adjeff_preds.parquet")
    pm = pd.Series((P.pred_a - P.pred_b).values, index=P.game_id.astype(str))
    rows = []
    d1_any = set()
    for y in range(FIRST_SEASON, last_season + 1):
        if not table_path("games", y).exists():
            continue
        d1_any |= set(pd.read_parquet(table_path("team_seasons", y)).query("is_d1").team_id)
        g = pd.read_parquet(table_path("games", y))
        g = g[g.completed & (g.game_type != "exhibition")]
        for side, opp, sgn in (("home", "away", 1), ("away", "home", -1)):
            rows.append(pd.DataFrame({"team": g[f"{side}_id"], "game": g.game_id.astype(str), "d": g.game_date.dt.strftime("%Y-%m-%d"),
                                      "opp": g[f"{opp}_id"], "site": np.where(g.neutral_site, "N", "H" if sgn == 1 else "A"),
                                      "pts": g[f"{side}_score"].astype(int), "opp_pts": g[f"{opp}_score"].astype(int),
                                      "pm": (sgn * g.game_id.astype(str).map(pm)).round(1)}))
    H = pd.concat(rows).sort_values(["team", "d"])
    n = 0
    for tid, grp in H[H.team.isin(d1_any)].groupby("team"):
        write(f"teamhistory/{tid}.json", {"v": V, "team": tid, "cols": ["game", "d", "opp", "site", "pts", "opp_pts", "pm"],
                                          "rows": [[r.game, r.d, r.opp, r.site, r.pts, r.opp_pts, None if pd.isna(r.pm) else float(r.pm)] for r in grp.itertuples()]})
        n += 1
    print(f"teamhistory: {n} teams", flush=True)


def export_analogs():
    O = pd.read_parquet(BT / "oos_preds.parquet")
    fav = np.sign(O.margin_pred).replace(0, 1)
    m, p, res = np.abs(O.margin_pred.values), O.pred_poss.values, (fav * O.margin).values  # favorite's view
    cells = []
    for gm in GRID_M:
        mm = np.abs(m - gm) <= WIN_M
        for gp in GRID_P:
            sel = mm & (np.abs(p - gp) <= WIN_P)
            k = int(sel.sum())
            if k < MIN_ANALOGS:
                cells.append(None)
                continue
            r = res[sel]
            cells.append([k, round(float((r > 0).mean()), 3), *[int(np.round(np.quantile(r, q))) for q in (0.1, 0.5, 0.9)]])
    write("analogs.json", {"v": V, "window": {"margin": WIN_M, "poss": WIN_P}, "seasons": [int(O.season.min()), int(O.season.max())],
                           "grid_margin": GRID_M.tolist(), "grid_poss": GRID_P.tolist(), "cols": ["n", "fav_win", "q10", "q50", "q90"],
                           "cells": cells, "note": "favorite's perspective; walk-forward predictions; a calibration view, not a new prediction"})
    print(f"analogs: {sum(c is not None for c in cells)} of {len(cells)} cells", flush=True)


def export_analog_games(last_season: int):
    """Per game (2015+): ids, predicted margin, result and the 8 four-factor matchup gaps (home offense minus away defense
    allowed, and away offense minus home defense allowed, for eFG, TOV, ORB, FT rate), from end-of-season profiles."""
    P = pd.read_parquet(BT / "adjeff_preds.parquet")
    rows = []
    for y in range(ANALOG_FIRST, last_season + 1):
        pf = OUT / "profiles" / f"{y}.json"
        if not pf.exists():
            continue
        prof = json.loads(pf.read_text())["teams"]
        ff = {t: {k: v[0] for k, v in d["ff"].items()} for t, d in prof.items()}
        Py = P[P.season == y]
        g = pd.read_parquet(table_path("games", y))[["game_id", "home_id", "away_id"]]
        Py = Py.assign(game_id=Py.game_id.astype(str)).merge(g, on="game_id")
        for r in Py[Py.a == Py.home_id].itertuples():
            h, a = ff.get(r.home_id), ff.get(r.away_id)
            if not h or not a or any(v is None for v in list(h.values()) + list(a.values())):
                continue
            gaps = [h["efg"] - a["efg_d"], h["tov"] - a["tov_d"], h["orb"] - a["orb_d"], h["ftr"] - a["ftr_d"],
                    a["efg"] - h["efg_d"], a["tov"] - h["tov_d"], a["orb"] - h["orb_d"], a["ftr"] - h["ftr_d"]]
            rows.append([r.game_id, y, r.home_id, r.away_id, round(float(r.pred_a - r.pred_b), 1), int(r.pts_a - r.pts_b)] + [round(x, 3) for x in gaps])
    write("analog_games.json", {"v": V, "cols": ["game", "season", "h", "a", "pm", "margin", "efg_h", "tov_h", "orb_h", "ftr_h", "efg_a", "tov_a", "orb_a", "ftr_a"],
                                "rows": rows})
    print(f"analog games: {len(rows)}", flush=True)


def export_compare_extras(last_season: int):
    export_teamhistory(last_season)
    export_analogs()
    export_analog_games(last_season)


if __name__ == "__main__":
    from pipeline.warehouse.paths import CURRENT_SEASON

    export_compare_extras(CURRENT_SEASON)
