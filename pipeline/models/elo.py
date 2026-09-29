"""Simple Elo (win/loss) used as a baseline in Phase 2. The full margin-aware maximum-likelihood Elo is a Phase 5 system.

Elo scale (400) is a definition; K, home advantage and season carryover are chosen by walk-forward log loss.
"""
from __future__ import annotations

import itertools

import numpy as np
import pandas as pd


def run_elo(G: pd.DataFrame, K: float, hca: float, carry: float) -> pd.DataFrame:
    """G sorted by date. Returns per-game pre-game rating difference (a - b, incl. no site) using only prior games."""
    r: dict[str, float] = {}
    out = np.zeros(len(G))
    seasons = G.season.values
    a, b, site = G.a.values, G.b.values, G.site.values
    win = (G.pts_a.values > G.pts_b.values).astype(float)
    cur = None
    for i in range(len(G)):
        if seasons[i] != cur:
            cur = seasons[i]
            for t in r:
                r[t] = 1500 + carry * (r[t] - 1500)
        ra, rb = r.get(a[i], 1500.0), r.get(b[i], 1500.0)
        diff = ra - rb
        out[i] = diff
        p = 1 / (1 + 10 ** (-(diff + hca * site[i]) / 400))
        d = K * (win[i] - p)
        r[a[i]] = ra + d
        r[b[i]] = rb - d
    return out


GRID = list(itertools.product([10, 20, 35], [40, 70, 100], [0.6, 0.75, 0.9]))  # K, hca, carry


def grid_logloss(G: pd.DataFrame) -> pd.DataFrame:
    """Per-season log loss for each config (each run is sequential over all history, so no leakage)."""
    rows = []
    win = (G.pts_a.values > G.pts_b.values).astype(float)
    for K, hca, carry in GRID:
        diff = run_elo(G, K, hca, carry)
        p = np.clip(1 / (1 + 10 ** (-(diff + hca * G.site.values) / 400)), 1e-6, 1 - 1e-6)
        ll = -(win * np.log(p) + (1 - win) * np.log(1 - p))
        d = pd.DataFrame({"season": G.season.values, "ll": ll}).groupby("season").ll.agg(["sum", "count"]).reset_index()
        d["cfg"] = f"{K},{hca},{carry}"
        rows.append(d)
    return pd.concat(rows)


def elo_predictions(G: pd.DataFrame, seasons_test) -> pd.DataFrame:
    """Walk-forward Elo: config for test season S chosen on log loss of seasons < S (from FIRST season onward)."""
    res = grid_logloss(G)
    out = []
    cache = {}
    for S in seasons_test:
        tr = res[res.season < S]
        best = tr.groupby("cfg").apply(lambda x: x["sum"].sum() / x["count"].sum(), include_groups=False).idxmin()
        K, hca, carry = map(float, best.split(","))
        if best not in cache:
            cache[best] = run_elo(G, K, hca, carry)
        m = G.season.values == S
        out.append(pd.DataFrame({"game_id": G.game_id.values[m], "elo_diff": cache[best][m], "elo_cfg": best, "season": S}))
    return pd.concat(out)
