"""Resume metrics at weekly snapshots: wins above bubble, strength of record, quadrant records, SOS variants.

DEFINITIONS (not fitted; also listed on the Methodology page):
  * Our own predictive rating (adjusted efficiency margin rank) stands in for NET everywhere below.
  * Bubble team = the team ranked BUBBLE_RANK in adjusted efficiency margin at the snapshot date.
  * Wins above bubble (WAB) = actual wins - sum over D-I games of P(bubble team wins that game, same site).
  * Strength of record (SOR) = probability that an average top-SOR_TOP team (mean rating of the top SOR_TOP) wins at least as many
    of these games as the team did; smaller = more impressive.
  * Quadrants use NCAA site-adjusted rank cutoffs applied to opponent rank in our rating (QUAD table).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from pipeline.warehouse.paths import PARAMS

from .backtest import BT
from .bt import snap_days
from .data import load_games

BUBBLE_RANK = 45  # DEFINITION
SOR_TOP = 25  # DEFINITION
# DEFINITION: NCAA quadrant cutoffs (opponent rank upper bounds) by site: (home, neutral, away)
QUAD = {1: (30, 50, 75), 2: (75, 100, 135), 3: (160, 200, 240)}


def quad_of(rank, site):
    """site: +1 home, 0 neutral, -1 away (from the team's view)."""
    j = 0 if site > 0 else 1 if site == 0 else 2
    for q in (1, 2, 3):
        if rank <= QUAD[q][j]:
            return q
    return 4


def poisson_binom_ge(ps: np.ndarray, w: int) -> float:
    dist = np.zeros(len(ps) + 1)
    dist[0] = 1.0
    for p in ps:
        dist[1:] = dist[1:] * (1 - p) + dist[:-1] * p
        dist[0] *= 1 - p
    return float(dist[w:].sum())


def win_prob(margin, poss, prod):
    s = np.maximum(prod["sigma_coef"][0] + prod["sigma_coef"][1] * (poss - 68.0), 3.0)
    from scipy.stats import norm
    return np.interp(norm.cdf(margin / s), prod["calibration_grid_x"], prod["calibration_grid_y"])


def compute(seasons=range(2010, 2027)):
    prod = json.loads((PARAMS / "adjeff.json").read_text())
    G = load_games()
    R = pd.read_parquet(BT / "adjeff_ratings.parquet")
    out = []
    for y in seasons:
        Gy = G[G.season == y].sort_values(["date", "game_id"])
        Ry = R[R.season == y]
        days = np.unique(Gy.date.values)
        for D in snap_days(days):
            r = Ry[Ry.date == pd.Timestamp(D)].set_index("team_id")
            if r.empty:
                continue
            marg = r.adj_off - r.adj_def
            rank = marg.rank(ascending=False, method="first").astype(int)
            order = marg.sort_values(ascending=False).index
            bub, top = r.loc[order[BUBBLE_RANK - 1]], r.loc[order[:SOR_TOP]].mean(numeric_only=True)
            mu, hca = r.mu.iloc[0], r.hca.iloc[0]
            g = Gy[Gy.date < pd.Timestamp(D)]
            g = g[g.a.isin(r.index) & g.b.isin(r.index)]
            # long form: one row per team-game
            rows = []
            for side, me, opp, s in (("h", g.a, g.b, g.site), ("a", g.b, g.a, -g.site)):
                rows.append(pd.DataFrame({"team": me.values, "opp": opp.values, "site": s.values,
                                          "win": ((g.margin > 0) if side == "h" else (g.margin < 0)).values, "cg": g.conference_game.values}))
            L = pd.concat(rows, ignore_index=True)
            oo, od, ot = r.adj_off[L.opp].values, r.adj_def[L.opp].values, r.adj_tempo[L.opp].values
            for tag, v in (("bub", bub), ("top", top)):
                ea = v.adj_off + od - mu + hca * L.site.values
                eb = oo + v.adj_def - mu - hca * L.site.values
                poss = (v.adj_tempo + ot) / 2
                L["p_" + tag] = win_prob((ea - eb) * poss / 100, poss, prod)
            L["oppm"] = marg[L.opp].values
            L["rk"] = rank[L.opp].values
            L["q"] = [quad_of(a, b) for a, b in zip(L.rk.values, L.site.values)]
            for t, d in L.groupby("team"):
                w = int(d.win.sum())
                rec = {"season": y, "day": pd.Timestamp(D), "team_id": t, "w": w, "l": int(len(d) - w), "wab": w - d.p_bub.sum(),
                       "sor": poisson_binom_ge(d.p_top.values, w) if len(d) else np.nan, "sos": d.oppm.mean(),
                       "ncsos": d.oppm[~d.cg].mean() if (~d.cg).any() else np.nan, "rank": int(rank[t])}
                for q in (1, 2, 3, 4):
                    dq = d[d.q == q]
                    rec[f"q{q}w"], rec[f"q{q}l"] = int(dq.win.sum()), int((~dq.win).sum())
                out.append(rec)
        print("resume", y, flush=True)
    df = pd.DataFrame(out)
    df.to_parquet(BT / "resume.parquet")
    return df


if __name__ == "__main__":
    df = compute()
    print(df.shape)
    d = df[(df.season == 2026) & (df.day == df[df.season == 2026].day.max())].sort_values("wab", ascending=False).head(6)
    print(d[["team_id", "w", "l", "wab", "sor", "q1w", "q1l", "sos", "rank"]].round(3))
