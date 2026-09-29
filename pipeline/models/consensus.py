"""Consensus rating: non-negative least squares blend of systems' predicted margins, weights learned on held-out seasons.

Systems with per-game walk-forward margin predictions: adjusted efficiency (adjeff), margin-aware Elo, Bradley-Terry (logit -> margin
by regression), previous-season rating. The player-driven system has no per-game walk-forward predictions (it needs the
season's own minutes) so it enters the mean-rank ranking only.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy.optimize import nnls
from scipy.stats import norm

from pipeline.warehouse.paths import PARAMS

from .backtest import BT
from .evaluate import logloss, sigma_of, sigma_model

SYS = ["adjeff", "elo", "bt", "prev"]


def load_frame() -> pd.DataFrame:
    P = pd.read_parquet(BT / "adjeff_preds.parquet")
    P["adjeff"] = P.pred_a - P.pred_b
    P["margin"] = P.pts_a - P.pts_b
    P = P.merge(pd.read_parquet(BT / "elo_preds.parquet")[["game_id", "elo_margin"]], on="game_id", how="left")
    P = P.merge(pd.read_parquet(BT / "bt_preds.parquet")[["game_id", "bt_logit"]], on="game_id", how="left")
    P = P.rename(columns={"elo_margin": "elo", "prev_margin": "prev"})
    return P[P.season >= 2012].dropna(subset=["adjeff", "elo", "bt_logit", "prev"]).copy()


def main():
    P = load_frame()
    tests = list(range(2015, 2027))
    rows, w_by = [], {}
    for S in tests:
        tr, te = P[P.season < S].copy(), P[P.season == S].copy()
        c = float((tr.bt_logit * tr.margin).sum() / (tr.bt_logit ** 2).sum())  # BT logit -> margin scale
        for d in (tr, te):
            d["bt"] = c * d.bt_logit
        A = tr[SYS].values
        w, _ = nnls(A, tr.margin.values)
        te["cons"] = te[SYS].values @ w
        tr["cons"] = tr[SYS].values @ w
        b = sigma_model(tr.assign(margin_pred=tr.cons, pred_poss=tr.pred_poss), True)
        te["p_cons"] = norm.cdf(te.cons / sigma_of(b, te.pred_poss))
        b1 = sigma_model(tr.assign(margin_pred=tr.adjeff), True)
        te["p_adj"] = norm.cdf(te.adjeff / sigma_of(b1, te.pred_poss))
        rows.append(te)
        w_by[S] = {"weights": dict(zip(SYS, map(float, w))), "bt_margin_scale": c}
    T = pd.concat(rows)
    y = (T.margin > 0).astype(float).values
    rep = {"test_seasons": [tests[0], tests[-1]], "weights_by_season": w_by}
    for k in SYS + ["cons"]:
        e = T[k] - T.margin
        rep[k] = {"mae": float(e.abs().mean()), "rmse": float(np.sqrt((e ** 2).mean()))}
    rep["cons"]["log_loss"] = logloss(T.p_cons.values, y)
    rep["adjeff"]["log_loss"] = logloss(T.p_adj.values, y)
    # production weights: all seasons
    c = float((P.bt_logit * P.margin).sum() / (P.bt_logit ** 2).sum())
    P["bt"] = c * P.bt_logit
    w, _ = nnls(P[SYS].values, P.margin.values)
    rep["production"] = {"weights": dict(zip(SYS, map(float, w))), "bt_margin_scale": c}
    (PARAMS / "consensus.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps({k: rep[k] for k in ("adjeff", "elo", "bt", "prev", "cons", "production")}, indent=1))
    return rep


if __name__ == "__main__":
    main()
