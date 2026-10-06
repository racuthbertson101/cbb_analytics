"""Regularized adjusted plus-minus from lineup stints (IMPROVEMENT_PLAN Phase 5a.2).

For every valid stint in a covered game, two rows (one per team on offense):
    points per 100 possessions = mu + sum(offense of the 5 attackers) + sum(defense of the 5 defenders) + home * site
weighted by the stint's possessions; ridge on the player terms (mu and home unpenalized). Player defense is reported with the
sign flipped (positive = fewer points allowed); net = offense + defense, in points per 100 possessions vs an average player.

The ridge strength is chosen walk-forward inside each season: fit on games before the 70th-percentile date, score the
possession-weighted squared error on the later stints. Evidence and next-season / split-half correlations go to
pipeline/params/rapm.json; ratings to data/backtest/rapm_<season>.parquet.

    python -m pipeline.players.rapm
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.sparse.linalg import LinearOperator, cg

from pipeline.models.backtest import BT
from pipeline.pbp.stints import OUT as STINTS
from pipeline.warehouse.paths import PARAMS, table_path

LAMBDAS = [250, 500, 1000, 2000, 4000, 8000]
SPLIT_Q = 0.70          # DEFINITION: walk-forward split for the ridge strength (first 70% of game dates -> rest)
MIN_POSS_CORR = 500     # DEFINITION: possessions required in both samples for correlation reporting


def rows(S: pd.DataFrame) -> pd.DataFrame:
    S = S[S.valid & S.game_covered]
    site = np.where(S.neutral, 0.0, 1.0)
    h = pd.DataFrame({"game_id": S.game_id, "off": S.home5, "def": S.away5, "pts": S.home_pts, "poss": S.home_poss, "site": site})
    a = pd.DataFrame({"game_id": S.game_id, "off": S.away5, "def": S.home5, "pts": S.away_pts, "poss": S.away_poss, "site": -site})
    r = pd.concat([h, a], ignore_index=True)
    r = r[r.poss > 0]
    r["y"] = 100 * r.pts / r.poss
    return r.reset_index(drop=True)


def design(r: pd.DataFrame, players: list[str]):
    ix = {p: i for i, p in enumerate(players)}
    n, P = len(r), len(players)
    ri, ci = [], []
    for k, (o, d) in enumerate(zip(r["off"], r["def"])):
        for p in o:
            ri.append(k), ci.append(ix[p])
        for p in d:
            ri.append(k), ci.append(P + ix[p])
    X = sparse.csr_matrix((np.ones(len(ri)), (ri, ci)), shape=(n, 2 * P))
    return sparse.hstack([X, sparse.csr_matrix(r.site.values.reshape(-1, 1))]).tocsr()


def fit(r: pd.DataFrame, lam: float, players: list[str] | None = None, prior_off: dict | None = None, prior_def: dict | None = None) -> dict:
    """With prior_off/prior_def (player -> per-100 value, defense positive = good), the ridge shrinks toward the prior
    instead of toward zero: solve for the deviation from the prior (Phase 5b)."""
    players = players or sorted({p for L in r["off"] for p in L} | {p for L in r["def"] for p in L})
    X, w = design(r, players), r.poss.values
    b0 = np.zeros(2 * len(players) + 1)
    if prior_off is not None:
        b0[:len(players)] = [prior_off.get(p, 0.0) for p in players]
        b0[len(players):2 * len(players)] = [-prior_def.get(p, 0.0) for p in players]  # model defense sign: + = allows more
    mu = float(np.average(r.y - X @ b0, weights=w))
    W = sparse.diags(w)
    pen = np.r_[np.full(2 * len(players), lam), 1e-6]  # home term unpenalized
    A = (X.T @ W @ X + sparse.diags(pen)).tocsr()
    # symmetric positive definite: conjugate gradient with a Jacobi preconditioner (a direct solve took >10 min)
    dinv = 1 / A.diagonal()
    b, info = cg(A, X.T @ (w * (r.y.values - mu - X @ b0)), M=LinearOperator(A.shape, lambda v: dinv * v), rtol=1e-8, maxiter=5000)
    if info:
        raise RuntimeError(f"RAPM solver did not converge (info={info})")
    b = b + b0
    P = len(players)
    return {"players": players, "off": b[:P], "def": -b[P:2 * P], "home": float(b[-1]), "mu": mu}


def predict(m: dict, r: pd.DataFrame) -> np.ndarray:
    o = dict(zip(m["players"], m["off"]))
    d = dict(zip(m["players"], m["def"]))
    return m["mu"] + np.array([sum(o.get(p, 0) for p in a) - sum(d.get(p, 0) for p in b) for a, b in zip(r["off"], r["def"])]) + m["home"] * r.site.values


def choose_lambda(r: pd.DataFrame, dates: pd.Series) -> tuple[float, dict]:
    d = r.game_id.map(dates)
    cut = d.drop_duplicates().quantile(SPLIT_Q)  # over the covered games' own dates (2024-25 coverage is late-season only)
    tr, te = r[d < cut], r[d >= cut]
    err = {}
    for lam in LAMBDAS:
        m = fit(tr, lam)
        err[lam] = float(np.average((te.y.values - predict(m, te)) ** 2, weights=te.poss.values))
    return min(err, key=err.get), {str(k): round(v, 2) for k, v in err.items()}


def table(m: dict, r: pd.DataFrame, y: int) -> pd.DataFrame:
    poss = pd.concat([r[["off", "poss"]].explode("off").rename(columns={"off": "p"}), r[["def", "poss"]].explode("def").rename(columns={"def": "p"})]).groupby("p").poss.sum()
    t = pd.DataFrame({"athlete_id": m["players"], "off": m["off"], "def": m["def"]})
    t["net"] = t.off + t["def"]
    t["poss"] = t.athlete_id.map(poss).fillna(0)
    ps = pd.read_parquet(table_path("player_seasons", y))
    main = ps.sort_values("min", ascending=False).drop_duplicates("athlete_id").set_index("athlete_id")
    t["team_id"], t["name"], t["min"] = t.athlete_id.map(main.team_id), t.athlete_id.map(main.name), t.athlete_id.map(main["min"])
    t["season"] = y
    return t


def corr(a: pd.DataFrame, b: pd.DataFrame) -> dict:
    j = a.merge(b, on="athlete_id", suffixes=("_a", "_b"))
    j = j[(j.poss_a >= MIN_POSS_CORR) & (j.poss_b >= MIN_POSS_CORR)]
    return {"n": int(len(j)), **{k: round(float(np.corrcoef(j[k + "_a"], j[k + "_b"])[0, 1]), 3) for k in ("net", "off", "def")}}


def run(seasons=(2025, 2026)) -> dict:
    out = {"model": "ridge RAPM on lineup stints, offense and defense per player plus a home term, possession-weighted",
           "lambda_grid": LAMBDAS, "seasons": {}}
    tabs = {}
    for y in seasons:
        p = STINTS / f"stints_{y}.parquet"
        if not p.exists():
            continue
        S = pd.read_parquet(p)
        r = rows(S)
        dates = pd.read_parquet(table_path("games", y)).set_index("game_id").game_date
        lam, err = choose_lambda(r, dates)
        m = fit(r, lam)
        t = table(m, r, y)
        tabs[y] = t
        t.to_parquet(BT / f"rapm_{y}.parquet", index=False)
        # split-half stability: odd vs even games (by id) with the same lambda
        ids = sorted(r.game_id.unique())
        half = {g: i % 2 for i, g in enumerate(ids)}
        h0, h1 = r[r.game_id.map(half) == 0], r[r.game_id.map(half) == 1]
        sh = corr(table(fit(h0, lam), h0, y), table(fit(h1, lam), h1, y))
        q = t[t.poss >= 1000]
        out["seasons"][str(y)] = {"lambda": lam, "holdout_mse_by_lambda": err, "rows": int(len(r)), "games": int(r.game_id.nunique()),
                                  "players": int(len(t)), "home_per100": round(m["home"], 2), "split_half_corr": sh,
                                  "sd_net_1000poss": round(float(q.net.std()), 2)}
        print("rapm", y, out["seasons"][str(y)], flush=True)
    ys = sorted(tabs)
    if len(ys) >= 2:
        out["next_season_corr"] = {f"{a}->{b}": corr(tabs[a], tabs[b]) for a, b in zip(ys, ys[1:])}
    (PARAMS / "rapm.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    print(json.dumps(run().get("next_season_corr"), indent=1))
