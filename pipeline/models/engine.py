"""Walk-forward engine for the adjusted-efficiency system: season finals, fitted preseason priors, blockwise backtests.

Leakage rule: every fit at day D uses only games with date < D; every prediction for a game on day D uses a fit at day <= D.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.warehouse.paths import FIRST_SEASON, table_path

from . import adjeff
from .adjeff import SeasonData
from .data import load_games

LAST_SEASON = 2026


def _load_roster_feats() -> dict:
    """Roster-prior features (pipeline.players.roster_prior), {S: {feats, window, k}}; empty if not built."""
    import pickle

    from .backtest import BT
    p = BT / "roster_feats.pkl"
    return pickle.load(open(p, "rb")) if p.exists() else {}


class Context:
    def __init__(self, seasons=None, G=None, last_season=LAST_SEASON):
        self.G = G if G is not None else load_games()
        self.roster = _load_roster_feats()
        self.seasons = list(seasons or range(FIRST_SEASON, last_season + 1))
        self.sd: dict[int, SeasonData] = {}
        for y in self.seasons:
            ts = pd.read_parquet(table_path("team_seasons", y))
            uni = set(ts.team_id[ts.is_d1])
            self.sd[y] = SeasonData.from_frame(self.G, y, uni)


def base_params(cfg: dict) -> dict:
    return {k: cfg[k] for k in ("lam", "lam_t", "halflife", "halflife_t", "cap", "lam_h", "skip_eff") if k in cfg}


def season_final(ctx: Context, y: int, cfg: dict, prior: dict | None = None) -> adjeff.Ratings:
    sd = ctx.sd[y]
    p = base_params(cfg)
    if prior:
        p.update(prior)
    return adjeff.fit(sd, len(sd.date), int(sd.date[-1]) + 1, p)


def finals_no_prior(ctx: Context, cfg: dict) -> dict[int, adjeff.Ratings]:
    return {y: season_final(ctx, y, cfg) for y in ctx.seasons}


def _lagged(finals: dict, y: int, lag: int, teams, attr: str):
    r = finals.get(y - lag)
    out = np.full(len(teams), np.nan)
    if r is None:
        return out
    v = getattr(r, attr)
    for i, t in enumerate(teams):
        j = r.tix.get(t)
        if j is not None and r.n_games[j] > 0:
            out[i] = v[j]
    return out


def prior_coefs(ctx: Context, finals: dict, S: int) -> dict:
    """Preseason prior regression: final rating in T on final rating in T-1 and T-2, estimated on seasons T < S only."""
    coefs = {}
    for attr in ("o", "d", "t"):
        X, Y = [], []
        for T in ctx.seasons:
            if T >= S or T - 1 not in finals:
                continue
            teams = finals[T].teams
            y = _lagged(finals, T, 0, teams, attr)
            x1 = _lagged(finals, T, 1, teams, attr)
            x2 = _lagged(finals, T, 2, teams, attr)
            x2 = np.where(np.isnan(x2), x1, x2)
            m = ~np.isnan(y) & ~np.isnan(x1)
            X.append(np.c_[x1[m], x2[m]])
            Y.append(y[m])
        if not X:
            coefs[attr] = (0.0, 0.0)
            continue
        X, Y = np.vstack(X), np.concatenate(Y)
        b = np.linalg.lstsq(X, Y, rcond=None)[0]
        coefs[attr] = (float(b[0]), float(b[1]))
    ro = _roster_coefs(ctx, finals, S)
    if ro:
        coefs["roster"] = ro
    return coefs


def _roster_coefs(ctx: Context, finals: dict, S: int) -> dict | None:
    """Regression of final ratings on [1, last, two-ago, returning/incoming impact and minutes shares] (rows T < S, optional window)."""
    R = getattr(ctx, "roster", {}).get(S)
    if not R:
        return None
    Ts = [T for T in ctx.seasons if T < S and T - 1 in finals and T in R["feats"]]
    if R["window"]:
        Ts = Ts[-R["window"]:]
    if len(Ts) < 1:
        return None
    out = {}
    for attr in ("o", "d"):
        cols = [f"ret_{attr}", f"in_{attr}", "ret_share", "in_share"]
        X, Y = [], []
        for T in Ts:
            teams = finals[T].teams
            y = _lagged(finals, T, 0, teams, attr)
            x1 = _lagged(finals, T, 1, teams, attr)
            x2 = _lagged(finals, T, 2, teams, attr)
            x2 = np.where(np.isnan(x2), x1, x2)
            F = R["feats"][T].reindex(teams).fillna(0.0)[cols].values
            m = ~np.isnan(y) & ~np.isnan(x1)
            X.append(np.c_[np.ones(m.sum()), x1[m], x2[m], F[m]])
            Y.append(y[m])
        b = np.linalg.lstsq(np.vstack(X), np.concatenate(Y), rcond=None)[0]
        out[attr] = {"cols": ["intercept", "last", "two_ago"] + cols, "beta": [float(v) for v in b], "n_rows": int(sum(len(y) for y in Y)), "window": R["window"], "k": R["k"]}
    return out


def build_prior(ctx: Context, finals: dict, S: int, coefs: dict) -> dict:
    """Prior vectors for season S teams from last two seasons' final ratings and the fitted coefficients."""
    teams = ctx.sd[S].teams if S in ctx.sd else None
    out = {}
    for attr, key in (("o", "prior_o"), ("d", "prior_d"), ("t", "prior_t")):
        k1, k2 = coefs[attr]
        x1 = _lagged(finals, S, 1, teams, attr)
        x2 = _lagged(finals, S, 2, teams, attr)
        x2 = np.where(np.isnan(x2), x1, x2)
        v = k1 * x1 + k2 * x2
        ro = coefs.get("roster")
        R = getattr(ctx, "roster", {}).get(S)
        if ro and R and S in R["feats"] and attr in ro:
            cols = [f"ret_{attr}", f"in_{attr}", "ret_share", "in_share"]
            F = R["feats"][S].reindex(teams).fillna(0.0)[cols].values
            b = np.array(ro[attr]["beta"])
            v = b[0] + b[1] * x1 + b[2] * x2 + F @ b[3:]
        out[key] = np.where(np.isnan(v), 0.0, v)
    prev = finals.get(S - 1)
    if prev is not None:
        out["prior_mu"], out["prior_hca"], out["prior_mu_t"] = prev.mu, prev.hca, prev.mu_t
    return out


def block_predict(sd: SeasonData, cfg: dict, prior: dict, step: int, ratings_hook=None) -> pd.DataFrame:
    """Walk through the season in blocks of `step` days (1 = every game day). Fit before each block, predict its games."""
    p = base_params(cfg)
    p.update(prior)
    days = np.unique(sd.date)
    start = days[0]
    out = []
    D = start
    last = days[-1]
    while D <= last:
        lo = np.searchsorted(sd.date, D, side="left")
        hi = np.searchsorted(sd.date, D + step, side="left")
        if hi > lo:
            r = adjeff.fit(sd, lo, int(D), p)
            sl = slice(lo, hi)
            sa, sb, poss = r.predict_arrays(sd.ia[sl], sd.ib[sl], sd.site[sl])
            out.append(pd.DataFrame({"game_id": sd.game_id[sl], "date": sd.date[sl], "pred_a": sa, "pred_b": sb,
                                     "pred_poss": poss, "n_prior": lo}))
            if ratings_hook:
                ratings_hook(r, int(D), sd, lo, hi)
        D += step
    return pd.concat(out, ignore_index=True)


def season_eval(ctx: Context, S: int, cfg: dict, finals: dict, step: int = 7) -> dict:
    """Blockwise walk-forward for one season using only information from seasons < S for the prior."""
    coefs = prior_coefs(ctx, finals, S)
    prior = build_prior(ctx, finals, S, coefs)
    sd = ctx.sd[S]
    pr = block_predict(sd, cfg, prior, step)
    f = sd.frame.set_index("game_id")
    m = pr.merge(f[["pts_a", "pts_b", "poss"]], left_on="game_id", right_index=True)
    err = (m.pred_a - m.pred_b) - (m.pts_a - m.pts_b)
    perr = m.pred_poss - m.poss
    return {"season": S, "n": len(m), "sse": float((err ** 2).sum()), "sae": float(err.abs().sum()),
            "sse_poss": float((perr ** 2).sum()), "coefs": coefs}
