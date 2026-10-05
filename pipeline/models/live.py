"""Refit the live season with the stored production params (no hyperparameter search) and patch the model artifacts.

Artifacts (data/backtest/*.parquet) hold pregame ratings/predictions for every past season; each night only the current season
is recomputed here. Everything for date D uses only games before D (same engine as the backtest).
"""
from __future__ import annotations

import json
import pickle

import numpy as np
import pandas as pd

from pipeline.warehouse.paths import PARAMS, table_path

from . import adjeff
from .backtest import BT
from .engine import Context, base_params, block_predict, build_prior, finals_no_prior
from .production import load_prod

EPOCH = pd.Timestamp("1970-01-01")


def fit_season(season: int, G: pd.DataFrame | None = None, asof=None):
    """Pregame predictions and dated rating snapshots for every game date of the season so far.

    With no completed games yet (opening morning) the rating IS the preseason prior: one snapshot dated `asof`, no predictions.
    """
    prod = load_prod()
    cfg = prod["config"]
    ctx = Context(G=G, last_season=season)
    prior_seasons = [y for y in ctx.seasons if y < season]
    sub = object.__new__(Context)
    sub.G, sub.seasons, sub.sd = ctx.G, prior_seasons, {y: ctx.sd[y] for y in prior_seasons}
    fin = finals_no_prior(sub, cfg)
    prior = build_prior(ctx, fin, season, prod["prior_coefs_current"])
    sd = ctx.sd[season]
    rat = []
    if len(sd.date) == 0:
        from .production import day_number

        p = base_params(cfg)
        p.update(prior)
        day = day_number(pd.Timestamp(asof) if asof is not None else pd.Timestamp.today().normalize())
        r = adjeff.fit(sd, 0, day, p)
        t = r.table()
        t["date"], t["hca"], t["mu"], t["season"] = EPOCH + pd.Timedelta(days=day), r.hca, r.mu, season
        return pd.DataFrame(columns=["game_id", "season", "date"]), t

    def hook(r, D, sd_, lo, hi):
        t = r.table()
        t["date"] = EPOCH + pd.Timedelta(days=D)
        t["hca"] = r.hca
        t["mu"] = r.mu
        rat.append(t)

    pr = block_predict(sd, cfg, prior, 1, hook)
    p = base_params(cfg)
    p.update(prior)
    last = int(sd.date[-1]) + 1
    hook(adjeff.fit(sd, len(sd.date), last, p), last, sd, 0, 0)
    f = sd.frame[["game_id", "a", "b", "site", "pts_a", "pts_b", "poss", "game_type", "neutral_site"]]
    pr = pr.merge(f, on="game_id")
    pr["season"] = season
    pr["date"] = EPOCH + pd.to_timedelta(pr.date, unit="D")
    pr["prev_margin"] = np.nan
    R = pd.concat(rat, ignore_index=True)
    R["season"] = season
    return pr, R


def patch_artifacts(season: int, G: pd.DataFrame | None = None, asof=None):
    pr, R = fit_season(season, G, asof)
    P0 = pd.read_parquet(BT / "adjeff_preds.parquet")
    R0 = pd.read_parquet(BT / "adjeff_ratings.parquet")
    P1 = pd.concat([P0[P0.season != season], pr[[c for c in P0.columns if c in pr.columns]]], ignore_index=True)
    R1 = pd.concat([R0[R0.season != season], R[[c for c in R0.columns if c in R.columns]]], ignore_index=True)
    P1.to_parquet(BT / "adjeff_preds.parquet")
    R1.to_parquet(BT / "adjeff_ratings.parquet")
    return len(pr), len(R)


def refresh_bt(season: int, G: pd.DataFrame | None = None):
    """Recompute Bradley-Terry weekly snapshots for one season with the production config; update bt_snaps.pkl."""
    from .bt import Season, season_run
    from .data import load_games
    G = G if G is not None else load_games()
    cfgj = json.loads((PARAMS / "bt.json").read_text())["production_config"]
    lam, k = cfgj["lambda"], cfgj["prior_k"]
    snaps = pickle.load(open(BT / "bt_snaps.pkl", "rb"))
    uni = set(pd.read_parquet(table_path("team_seasons", season)).query("is_d1").team_id)
    S = Season(G, season, uni)
    prev = None
    if season - 1 in snaps:
        pv = snaps[season - 1]
        prev = (pv["snaps"][-1][1], pv["teams"])
    logit, sn = season_run(S, lam, k, prev)
    snaps[season] = {"cfg": (lam, k), "teams": S.teams, "snaps": sn}
    pickle.dump(snaps, open(BT / "bt_snaps.pkl", "wb"))
    return len(sn)


def refresh_resume(season: int):
    from .resume import compute
    compute([season])
