"""Margin-aware Elo, fit by maximum likelihood (Gaussian margin errors) on training seasons.

Rating is in points of margin vs an average D-I team. Expected margin = r_a - r_b + hca*site.
Update: r_a += K*(m - expected), r_b -= K*(m - expected), with the observed margin capped at +-cap.
Season carryover: r <- carry * r at each new season. (K, hca, carry, cap) are estimated; sigma is the residual sd.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import norm

from pipeline.warehouse.paths import PARAMS

from .registry import register


def run(G: pd.DataFrame, K: float, hca: float, carry: float, cap: float, snapshots=None):
    """G sorted by date (columns season,a,b,site,margin). Returns per-game pregame expected margin.
    snapshots: optional set of (season, date) after which to record all ratings (weekly snapshots)."""
    r: dict = {}
    n = len(G)
    exp = np.zeros(n)
    seasons, a, b, site, m = G.season.values, G.a.values, G.b.values, G.site.values, G.margin.values
    dates = G.date.values
    snaps = []
    cur = None
    for i in range(n):
        if seasons[i] != cur:
            if cur is not None and snapshots is not None:
                snaps.append((cur, "final", dict(r)))
            cur = seasons[i]
            for t in r:
                r[t] *= carry
        if snapshots is not None and i > 0 and dates[i] != dates[i - 1] and seasons[i] == seasons[i - 1] and (dates[i], seasons[i]) in snapshots:
            snaps.append((seasons[i], dates[i], dict(r)))
        ra, rb = r.get(a[i], 0.0), r.get(b[i], 0.0)
        e = ra - rb + hca * site[i]
        exp[i] = e
        err = max(-cap, min(cap, m[i])) - e
        r[a[i]] = ra + K * err
        r[b[i]] = rb - K * err
    if snapshots is not None:
        snaps.append((cur, "final", dict(r)))
    return exp, snaps


def loss(theta, G, mask):
    K, hca, carry, cap = theta
    if not (0.001 < K < 0.5 and 0 < carry < 1.2 and 5 < cap < 80 and 0 < hca < 10):
        return 1e12
    exp, _ = run(G, K, hca, carry, cap)
    e = (G.margin.values - exp)[mask]
    return float((e ** 2).mean())


def fit_params(G: pd.DataFrame, train_max_season: int, x0=(0.05, 3.5, 0.8, 30.0)) -> dict:
    mask = (G.season.values <= train_max_season) & (G.season.values >= 2010)
    res = minimize(lambda th: loss(th, G[G.season <= train_max_season].reset_index(drop=True), mask[G.season.values <= train_max_season]),
                   x0, method="Nelder-Mead", options={"xatol": 1e-3, "fatol": 1e-4, "maxiter": 70})
    K, hca, carry, cap = res.x
    return {"K": float(K), "hca": float(hca), "carry": float(carry), "cap": float(cap), "mse": float(res.fun), "train_max_season": train_max_season}


def walk_forward(G: pd.DataFrame, test_seasons) -> pd.DataFrame:
    out, fits = [], {}
    x0 = (0.05, 3.5, 0.8, 30.0)
    for S in test_seasons:
        p = fit_params(G, S - 1, x0)
        x0 = (p["K"], p["hca"], p["carry"], p["cap"])
        fits[S] = p
        exp, _ = run(G[G.season <= S].reset_index(drop=True), p["K"], p["hca"], p["carry"], p["cap"])
        g = G[G.season <= S].reset_index(drop=True)
        m = g.season.values == S
        out.append(pd.DataFrame({"game_id": g.game_id.values[m], "elo_margin": exp[m], "season": S}))
        print("elo", S, {k: round(v, 3) for k, v in p.items()}, flush=True)
    (PARAMS / "elo_mle.json").write_text(json.dumps(fits, indent=1))
    return pd.concat(out)


@register("elo")
class EloSystem:
    name = "Elo (margin-aware, MLE)"

    @staticmethod
    def fit(games_before_date: pd.DataFrame, params: dict):
        exp, snaps = run(games_before_date, params["K"], params["hca"], params["carry"], params["cap"], snapshots=set())
        return snaps[-1][2]


if __name__ == "__main__":
    from pipeline.models.backtest import BT
    from pipeline.models.data import load_games
    G = load_games()
    walk_forward(G, range(2012, 2027)).to_parquet(BT / "elo_preds.parquet")
