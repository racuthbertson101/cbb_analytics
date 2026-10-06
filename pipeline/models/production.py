"""Production use of the adjusted-efficiency system: fit as of a date, calibrated predictions with intervals.

Implements the shared rating-system interface:
    fit(games_before_date, params) -> ratings
    predict(team_a, team_b, site, date) -> {margin, total, score_a, score_b, win_prob_a, interval}
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy.stats import norm

from pipeline.warehouse.paths import PARAMS

from . import adjeff
from .engine import Context, base_params, build_prior, finals_no_prior
from .registry import register


def load_prod() -> dict:
    return json.loads((PARAMS / "adjeff.json").read_text())


def day_number(date) -> int:
    return int((pd.Timestamp(date).normalize() - pd.Timestamp("1970-01-01")).days)


class Predictor:
    """Wraps fitted ratings with the spread model, Platt/isotonic calibration and residual-quantile intervals.

The 80% interval is an OUTCOME interval on the margin (80% of results land in it). There is deliberately no interval on
the win probability: pushing outcome quantiles through the CDF gives ~10%-90% for every game (AUDIT M-1). An estimate
interval from rating uncertainty is planned (IMPROVEMENT_PLAN Phase 5).
"""

    def __init__(self, ratings: adjeff.Ratings, prod: dict):
        self.r, self.prod = ratings, prod
        self.sig = prod["sigma_coef"]
        self.gx, self.gy = np.array(prod["calibration_grid_x"]), np.array(prod["calibration_grid_y"])
        self.q = prod["margin_residual_quantiles"]
        self.sq = prod["score_residual_quantiles"]

    def _win_prob(self, margin, poss):
        s = np.maximum(self.sig[0] + self.sig[1] * (poss - 68.0), 3.0)
        p = norm.cdf(margin / s)
        return np.interp(p, self.gx, self.gy)

    def predict_arrays(self, ia, ib, site) -> pd.DataFrame:
        sa, sb, poss = self.r.predict_arrays(ia, ib, site)
        m = sa - sb
        return pd.DataFrame({"margin": m, "total": sa + sb, "score_a": sa, "score_b": sb, "poss": poss,
                             "win_prob_a": self._win_prob(m, poss),
                             "margin_lo": m + self.q["0.1"], "margin_hi": m + self.q["0.9"]})

    def predict(self, team_a, team_b, site=1.0, date=None) -> dict:
        i, j = self.r.tix[team_a], self.r.tix[team_b]
        d = self.predict_arrays(np.array([i]), np.array([j]), np.array([float(site)])).iloc[0]
        return {"margin": d.margin, "total": d.total, "score_a": d.score_a, "score_b": d.score_b, "win_prob_a": d.win_prob_a,
                "interval": {"level": 0.8, "margin": [d.margin_lo, d.margin_hi],
                             "score_a": [d.score_a + self.sq["0.1"], d.score_a + self.sq["0.9"]],
                             "score_b": [d.score_b + self.sq["0.1"], d.score_b + self.sq["0.9"]]}}


def ratings_asof(ctx: Context, season: int, asof, prod: dict | None = None) -> adjeff.Ratings:
    """Fit season ratings using only games strictly before `asof` (prior from earlier seasons' finals)."""
    prod = prod or load_prod()
    cfg = prod["config"]
    if season - 1 not in ctx.sd:
        raise ValueError("need previous season in context")
    fin = finals_no_prior(_sub_ctx(ctx, [y for y in ctx.seasons if y < season]), cfg)
    prior = build_prior(ctx, fin, season, prod["prior_coefs_current"])
    sd = ctx.sd[season]
    day = day_number(asof)
    n = int(np.searchsorted(sd.date, day, side="left"))
    p = base_params(cfg)
    p.update(prior)
    from .rating_sd import OUT as SD_PARAMS, sd_params

    if SD_PARAMS.exists():
        p.update(sd_params())
    return adjeff.fit(sd, n, day, p)


def _sub_ctx(ctx, seasons):
    c = object.__new__(Context)
    c.G, c.seasons, c.sd = ctx.G, list(seasons), {y: ctx.sd[y] for y in seasons}
    return c


@register("adjeff")
class AdjEffSystem:
    name = "Adjusted efficiency (ridge)"

    @staticmethod
    def fit(games_before_date: pd.DataFrame, params: dict | None = None, season: int | None = None, asof=None):
        """games_before_date: modeling frame (see pipeline.models.data.load_games) for all history before `asof`."""
        prod = params or load_prod()
        season = season or int(games_before_date.season.max())
        seasons = sorted(set(games_before_date.season) | {season})
        ctx = Context(seasons=[y for y in seasons if y >= 2008], G=games_before_date, last_season=season)
        r = ratings_asof(ctx, season, asof if asof is not None else games_before_date.date.max() + pd.Timedelta(days=1), prod)
        return Predictor(r, prod)
