"""Box-score impact rating v1 (fitted): regress team adjusted offense/defense on minutes-weighted player rate features.

team_rating = a + sum_p (min_share_p / 5) * (beta . z_p)   (min_share sums to 5 per team)
impact_p    = beta . z_p / 5   -> contribution to team rating per unit of min_share, i.e. per 100 possessions on the floor
Shrinkage for low minutes: impact * min / (min + k), k chosen by walk-forward validation.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from pipeline.models.backtest import BT
from pipeline.warehouse.paths import PARAMS, table_path

OFF = ["usg", "ts", "ast_pct", "tov_pct", "orb_pct", "ftr", "tpar", "usg_ts"]
DEF = ["stl_pct", "blk_pct", "drb_pct", "pf_40", "orb_pct", "tov_pct"]
FEATS = sorted(set(OFF) | set(DEF))
MIN_STD = 100  # players below this many minutes are ignored when computing feature means/stds (a numerical choice, not a rating input)


def load_ps(y: int) -> pd.DataFrame:
    a = pd.read_parquet(table_path("player_seasons", y))
    a["usg_ts"] = (a.usg / 20) * (a.ts - 0.55) * 20
    return a


def team_targets() -> pd.DataFrame:
    """End-of-season adjusted ratings used as regression targets. Frozen in impact_targets.parquet (created from the lag-only-prior
    model) so the impact model does not depend on ratings that themselves use the roster prior (no feedback loop)."""
    p = BT / "impact_targets.parquet"
    if p.exists():
        return pd.read_parquet(p)
    R = pd.read_parquet(BT / "adjeff_ratings.parquet")
    last = R.groupby("season").date.transform("max")
    R = R[R.date == last]
    F = R[["season", "team_id", "adj_off", "adj_def", "adj_tempo"]]
    F.to_parquet(p)
    return F


class ImpactModel:
    def __init__(self, alpha=50.0):
        self.alpha = alpha

    def _z(self, ps):
        Z = (ps[FEATS] - self.mu) / self.sd
        return Z.fillna(0.0)

    def _team_X(self, ps, feats):
        Z = self._z(ps)[feats].values * (ps.min_share.values[:, None] / 5)
        X = pd.DataFrame(Z, columns=feats)
        X["team_id"] = ps.team_id.values
        return X.groupby("team_id").sum()

    def fit(self, seasons, targets: pd.DataFrame, cache: dict):
        ps_all = pd.concat([cache[y] for y in seasons])
        big = ps_all[ps_all["min"] >= MIN_STD]
        w = big["min"]
        self.mu = big[FEATS].apply(lambda c: np.average(c.dropna(), weights=w[c.notna()]))
        self.sd = big[FEATS].apply(lambda c: np.sqrt(np.average((c.dropna() - self.mu[c.name]) ** 2, weights=w[c.notna()])))
        self.coef = {}
        for tag, feats, col, sign in (("o", OFF, "adj_off", 1.0), ("d", DEF, "adj_def", -1.0)):
            Xs, ys = [], []
            for y in seasons:
                X = self._team_X(cache[y], feats)
                t = targets[targets.season == y].set_index("team_id")[col]
                j = X.index.intersection(t.index)
                Xs.append(X.loc[j])
                ys.append(t.loc[j])
            X, yv = pd.concat(Xs), pd.concat(ys)
            xm, ym = X.mean(), yv.mean()
            Xc, yc = X - xm, yv - ym
            beta = np.linalg.solve(Xc.T.values @ Xc.values + self.alpha * np.eye(len(feats)), Xc.T.values @ yc.values)
            self.coef[tag] = (feats, pd.Series(beta, index=feats), sign)
        return self

    def impacts(self, ps: pd.DataFrame, k: float) -> pd.DataFrame:
        Z = self._z(ps)
        out = ps[["team_id", "athlete_id", "min", "min_share"]].copy()
        for tag in ("o", "d"):
            feats, beta, sign = self.coef[tag]
            # center on the minutes-weighted mean player (z = 0 by construction of standardization)
            out["imp_" + tag] = sign * (Z[feats].values @ beta.values) / 5
        shrink = out["min"] / (out["min"] + k)
        out["imp_o"] *= shrink
        out["imp_d"] *= shrink
        out["imp"] = out.imp_o + out.imp_d
        return out

    def to_json(self):
        return {"alpha": self.alpha, "feature_mean": self.mu.to_dict(), "feature_std": self.sd.to_dict(),
                "offense_coef": self.coef["o"][1].to_dict(), "defense_coef": self.coef["d"][1].to_dict()}

    @classmethod
    def from_json(cls, d):
        m = cls(d["alpha"])
        m.mu, m.sd = pd.Series(d["feature_mean"]), pd.Series(d["feature_std"])
        o, dd = pd.Series(d["offense_coef"]), pd.Series(d["defense_coef"])
        m.coef = {"o": (list(o.index), o, 1.0), "d": (list(dd.index), dd, -1.0)}
        return m


def within_season_r2(model, cache, targets, seasons):
    res = {}
    for tag, col in (("o", "adj_off"), ("d", "adj_def")):
        feats, beta, _ = model.coef[tag]
        ys, ps_ = [], []
        for y in seasons:
            X = model._team_X(cache[y], feats)
            t = targets[targets.season == y].set_index("team_id")[col]
            j = X.index.intersection(t.index)
            ys.append(t.loc[j] - t.loc[j].mean())
            ps_.append(pd.Series(X.loc[j].values @ beta.values, index=j))
        yv, pv = pd.concat(ys), pd.concat(ps_)
        res[tag] = float(np.corrcoef(yv.values, pv.values)[0, 1] ** 2)
    return res
