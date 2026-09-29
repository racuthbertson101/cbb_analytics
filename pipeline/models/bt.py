"""Results-only Bradley-Terry: ridge logistic regression on win/loss (margin ignored) with a home-court term.

P(a beats b) = sigmoid(s_a - s_b + h*site). Ridge shrinks strengths toward k * last season's final strength (k, lambda by walk-forward).
Fits are refit weekly (every 7th game date); games in a week are predicted from the fit at the week's start.
"""
from __future__ import annotations

import itertools
import json

import numpy as np
import pandas as pd

from pipeline.warehouse.paths import PARAMS, table_path

from .backtest import BT
from .data import load_games
from .registry import register

LAMS = [1.0, 3.0, 10.0]
KS = [0.0, 0.5, 0.75]


def irls(ia, ib, site, y, N, lam, prior, iters=8):
    n = len(y)
    X = np.zeros((n, N + 1))
    r = np.arange(n)
    X[r, ia] += 1.0
    X[r, ib] -= 1.0
    X[:, N] = site
    b = np.concatenate([prior, [0.3]])
    pen = np.concatenate([np.full(N, lam), [1e-3]])
    b0 = np.concatenate([prior, [0.0]])
    for _ in range(iters):
        z = X @ b
        p = 1 / (1 + np.exp(-z))
        W = np.clip(p * (1 - p), 1e-6, None)
        g = X.T @ (y - p) - pen * (b - b0)
        H = (X * W[:, None]).T @ X + np.diag(pen)
        step = np.linalg.solve(H, g)
        b = b + step
        if np.abs(step).max() < 1e-5:
            break
    return b[:N], b[N]


class Season:
    def __init__(self, G: pd.DataFrame, y: int, universe):
        g = G[G.season == y].sort_values(["date", "game_id"]).reset_index(drop=True)
        self.teams = np.array(sorted(universe))
        self.tix = {t: i for i, t in enumerate(self.teams)}
        g = g[g.a.isin(self.tix) & g.b.isin(self.tix)].reset_index(drop=True)
        self.g = g
        self.ia, self.ib = g.a.map(self.tix).values, g.b.map(self.tix).values
        self.site = g.site.values
        self.y = (g.margin.values > 0).astype(float)
        self.date = g.date.values
        self.days = np.unique(self.date)


def snap_days(days):
    """DEFINITION: weekly snapshots = every 7th distinct game date, plus the day after the last game (final)."""
    return list(days[::7]) + [days[-1] + np.timedelta64(1, "D")]


def prior_from(prev_b, prev_teams, teams, k):
    p = np.zeros(len(teams))
    if prev_b is None:
        return p
    d = dict(zip(prev_teams, prev_b))
    for i, t in enumerate(teams):
        p[i] = k * d.get(t, 0.0)
    return p


def season_run(S: Season, lam, k, prev):
    """Returns (per-game pregame logit diff, snapshots list[(day, strengths, h)]) using weekly refits."""
    prior = prior_from(prev[0], prev[1], S.teams, k) if prev else np.zeros(len(S.teams))
    sd = snap_days(S.days)
    logit = np.zeros(len(S.g))
    snaps = []
    for i, D in enumerate(sd):
        n = int(np.searchsorted(S.date, D, side="left"))
        b, h = irls(S.ia[:n], S.ib[:n], S.site[:n], S.y[:n], len(S.teams), lam, prior)
        snaps.append((D, b, h))
        if i < len(sd) - 1:
            hi = int(np.searchsorted(S.date, sd[i + 1], side="left"))
            logit[n:hi] = b[S.ia[n:hi]] - b[S.ib[n:hi]] + h * S.site[n:hi]
    return logit, snaps


def all_runs(seasons=range(2008, 2027)):
    G = load_games()
    uni = {y: set(pd.read_parquet(table_path("team_seasons", y)).query("is_d1").team_id) for y in seasons}
    SS = {y: Season(G, y, uni[y]) for y in seasons}
    out = {}
    for lam, k in itertools.product(LAMS, KS):
        prev, res = None, {}
        for y in seasons:
            logit, snaps = season_run(SS[y], lam, k, prev)
            res[y] = (logit, snaps)
            prev = (snaps[-1][1], SS[y].teams)
        out[(lam, k)] = res
        print("bt", lam, k, flush=True)
    return SS, out


def main():
    seasons = list(range(2008, 2027))
    SS, out = all_runs(seasons)
    ll = {}
    for cfg, res in out.items():
        for y in seasons:
            if y < 2010:
                continue
            p = np.clip(1 / (1 + np.exp(-res[y][0])), 1e-6, 1 - 1e-6)
            yy = SS[y].y
            ll[(cfg, y)] = (-(yy * np.log(p) + (1 - yy) * np.log(1 - p))).sum(), len(yy)
    chosen, rows, snapsel = {}, [], {}
    for S in range(2012, 2027):
        best, be = None, 1e9
        for cfg in out:
            e = sum(ll[(cfg, y)][0] for y in range(2010, S)) / sum(ll[(cfg, y)][1] for y in range(2010, S))
            if e < be:
                best, be = cfg, e
        chosen[S] = best
        logit = out[best][S][0]
        g = SS[S].g
        rows.append(pd.DataFrame({"game_id": g.game_id.values, "bt_logit": logit, "season": S}))
        snapsel[S] = out[best][S][1]
    P = pd.concat(rows)
    P.to_parquet(BT / "bt_preds.parquet")
    # display snapshots use the walk-forward-selected config for 2012+ and the config chosen for 2012 before that
    final_cfg = chosen[2026]
    (PARAMS / "bt.json").write_text(json.dumps({"chosen_by_season": {str(k): list(v) for k, v in chosen.items()}, "production_config": {"lambda": final_cfg[0], "prior_k": final_cfg[1]},
                                                "selection": "walk-forward: log loss on seasons before the test season", "grid": {"lambda": LAMS, "prior_k": KS},
                                                "refit": "weekly (every 7th game date)"}, indent=1))
    # snapshots for export
    snaps = {}
    for y in seasons:
        cfg = chosen.get(y, chosen[2012])
        snaps[y] = {"cfg": cfg, "teams": SS[y].teams, "snaps": out[cfg][y][1]}
    return P, snaps


@register("bt")
class BradleyTerry:
    name = "Bradley-Terry (results only)"

    @staticmethod
    def fit(games_before_date: pd.DataFrame, params: dict):
        raise NotImplementedError("use pipeline.models.bt.season_run for weekly fits")


if __name__ == "__main__":
    import pickle
    P, snaps = main()
    pickle.dump(snaps, open(BT / "bt_snaps.pkl", "wb"))
    print(P.shape)
