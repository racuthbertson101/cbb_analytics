"""Player impact v2 (IMPROVEMENT_PLAN Phase 5b.1): play-by-play RAPM with a box-score prior, team-consistent.

1. Box prior (BPM-style): player-level ridge of RAPM offense and defense on standardized box rates, position and role terms,
   weighted by RAPM possessions. Fit on the RAPM seasons (2024-25 partial, 2025-26). Grouped cross-validation by team picks the
   penalty and reports out-of-fold correlation.
2. Seasons with lineup data: RAPM refit with the box prior as its prior mean (ridge on the deviation from the prior), so a
   player with few possessions stays near his box prior. Seasons without lineup data: the box prior alone.
3. Team consistency: each team's minutes-share-weighted sum of player offense (defense) is shifted to equal its adjusted
   offense (defense) relative to the league, with the shift shared equally by its players.
Smell tests (assertions, stored with the evidence in pipeline/params/players_v2.json): position mean impacts within +/-2
points per 100, SD of impact between 2 and 4, and no player under 15 mpg in the top 25 (players with 500+ minutes).

    python -m pipeline.players.impact_v2
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from pipeline.models.backtest import BT
from pipeline.pbp.stints import OUT as STINTS
from pipeline.warehouse.paths import PARAMS, table_path

from . import rapm
from .impact import FEATS, load_ps

POS = ["G", "F", "C"]
PRIOR_POS = False  # attempt 2 (DECISIONS.md): position dummies in the prior pushed centers past the smell test
ROLE = ["mpg", "start_share"]
ALPHAS = [1.0, 3.0, 10.0, 30.0, 100.0, 300.0, 1000.0]
SMELL_MIN = 500          # DEFINITION: players with at least this many minutes enter the smell tests
SMELL = {"position_mean_abs_max": 2.0, "sd_min": 2.0, "sd_max": 4.0, "top25_min_mpg": 15.0}  # from IMPROVEMENT_PLAN 5b
RAPM_SEASONS = (2025, 2026)


def features(ps: pd.DataFrame, mu: pd.Series | None = None, sd: pd.Series | None = None):
    X = ps[FEATS].copy()
    big = ps["min"] >= 100
    mu = X[big].mean() if mu is None else mu
    sd = X[big].std() if sd is None else sd
    Z = ((X - mu) / sd).fillna(0.0).clip(-4, 4)
    pos = ps.position.fillna("").str[0]
    for p in POS if PRIOR_POS else []:
        Z["pos_" + p] = (pos == p).astype(float)
    Z["mpg"] = (ps.mpg - 20) / 10
    Z["start_share"] = (ps.starts / ps.gp.clip(lower=1)).fillna(0)
    return Z, mu, sd


def fit_prior(seasons=RAPM_SEASONS) -> dict:
    """Box prior: offense and defense ridge fits on RAPM, penalty by grouped (team) cross-validation."""
    frames = []
    for y in seasons:
        p = BT / f"rapm_{y}.parquet"
        if not p.exists():
            continue
        r = pd.read_parquet(p)[["athlete_id", "off", "def", "poss"]]
        ps = load_ps(y).sort_values("min", ascending=False).drop_duplicates("athlete_id")
        frames.append(ps.merge(r, on="athlete_id").assign(season=y))
    D = pd.concat(frames, ignore_index=True)
    D = D[D.poss >= 100]
    Z, mu, sd = features(D)
    cols = list(Z.columns)
    X, w = Z.values, D.poss.values
    groups = D.team_id.astype(str) + D.season.astype(str)
    folds = pd.Series(pd.factorize(groups)[0] % 5, index=D.index).values
    out = {"features": cols, "feature_mean": mu.to_dict(), "feature_std": sd.to_dict(), "n_players": int(len(D))}
    for tag in ("off", "def"):
        y = D[tag].values
        cv = {}
        for a in ALPHAS:
            pred = np.zeros(len(y))
            for f in range(5):
                tr, te = folds != f, folds == f
                pred[te] = _ridge(X[tr], y[tr], w[tr], a)(X[te])
            cv[a] = float(np.corrcoef(pred, y)[0, 1])  # out-of-fold correlation, unweighted
        best = max(cv, key=cv.get)
        f = _ridge(X, y, w, best)
        out[tag] = {"alpha": best, "cv_corr_by_alpha": {str(k): round(v, 4) for k, v in cv.items()}, "cv_corr": round(cv[best], 4),
                    "intercept": f.b0, "coef": dict(zip(cols, map(float, f.b)))}
    return out


class _ridge:
    def __init__(self, X, y, w, a):
        xm = np.average(X, axis=0, weights=w)
        self.ym = float(np.average(y, weights=w))
        Xc = X - xm
        A = Xc.T @ (Xc * w[:, None]) + a * np.eye(X.shape[1])
        self.b = np.linalg.solve(A, Xc.T @ (w * (y - self.ym)))
        self.b0 = float(self.ym - xm @ self.b)

    def __call__(self, X):
        return self.b0 + X @ self.b


def prior_impacts(ps: pd.DataFrame, P: dict) -> pd.DataFrame:
    Z, _, _ = features(ps, pd.Series(P["feature_mean"]), pd.Series(P["feature_std"]))
    Z = Z[P["features"]].values
    out = ps[["team_id", "athlete_id", "min", "min_share", "mpg", "position"]].copy()
    for tag in ("off", "def"):
        out["prior_" + tag] = P[tag]["intercept"] + Z @ np.array([P[tag]["coef"][c] for c in P["features"]])
    return out


def team_adjust(imp: pd.DataFrame, team: pd.DataFrame) -> pd.DataFrame:
    """Shift each team's players so sum(min_share * offense) = adjusted offense relative to the league (same for defense)."""
    t = team.set_index("team_id")
    out = imp.copy()
    # attempt 3 (DECISIONS.md): the team's gap is shared in proportion to minutes share (shift_i = gap * s_i / sum s^2), so the
    # players on the floor carry it; an equal split per player moved low-minute guards most and widened position gaps
    s2 = (out.min_share ** 2).groupby(out.team_id).sum()
    for tag, target in (("off", t.rel_off), ("def", t.rel_def)):
        cur = (out.min_share * out[tag]).groupby(out.team_id).sum()
        gap = (target.reindex(cur.index) - cur).fillna(0.0)
        out[tag] = out[tag] + out.min_share * out.team_id.map(gap / s2).fillna(0.0)
    out["net"] = out["off"] + out["def"]
    return out


def season_impacts(y: int, P: dict, lam: float | None = None) -> pd.DataFrame:
    ps = load_ps(y)
    base = prior_impacts(ps, P)
    st = STINTS / f"stints_{y}.parquet"
    src = "box prior"
    if y in RAPM_SEASONS and st.exists():
        r = rapm.rows(pd.read_parquet(st))
        pri = base.sort_values("min", ascending=False).drop_duplicates("athlete_id").set_index("athlete_id")
        m = rapm.fit(r, lam or 2000.0, prior_off=pri.prior_off.to_dict(), prior_def=pri.prior_def.to_dict())
        o, d = dict(zip(m["players"], m["off"])), dict(zip(m["players"], m["def"]))
        base["off"] = [o.get(a, po) for a, po in zip(base.athlete_id, base.prior_off)]
        base["def"] = [d.get(a, pd_) for a, pd_ in zip(base.athlete_id, base.prior_def)]
        src = "RAPM with box prior"
    else:
        base["off"], base["def"] = base.prior_off, base.prior_def
    R = pd.read_parquet(BT / "adjeff_ratings.parquet")
    R = R[(R.season == y)]
    R = R[R.date == R.date.max()]
    team = pd.DataFrame({"team_id": R.team_id, "rel_off": R.adj_off - R.mu, "rel_def": R.mu - R.adj_def})
    out = team_adjust(base, team)
    out["source"] = src
    out["season"] = y
    return out


def smell(imp: pd.DataFrame) -> dict:
    q = imp[imp["min"] >= SMELL_MIN]
    pos = q.position.fillna("").str[0]
    pm = {p: round(float(q.net[pos == p].mean()), 2) for p in POS if (pos == p).any()}
    sdv = float(q.net.std())
    top = q.sort_values("net", ascending=False).head(25)
    res = {"n": int(len(q)), "position_means": pm, "sd": round(sdv, 2), "top25_min_mpg": round(float(top.mpg.min()), 1),
           "top10": top.head(10)[["athlete_id", "net"]].round(2).values.tolist()}
    res["pass_position"] = all(abs(v) <= SMELL["position_mean_abs_max"] for v in pm.values())
    res["pass_sd"] = SMELL["sd_min"] <= sdv <= SMELL["sd_max"]
    res["pass_top25"] = res["top25_min_mpg"] >= SMELL["top25_min_mpg"]
    res["pass"] = res["pass_position"] and res["pass_sd"] and res["pass_top25"]
    return res


def run(seasons=range(2010, 2027)) -> dict:
    P = fit_prior()
    lam = json.loads((PARAMS / "rapm.json").read_text())["seasons"]
    out = {"prior": P, "smell_tests": {}, "smell_thresholds": SMELL, "smell_min_minutes": SMELL_MIN}
    for y in seasons:
        if not table_path("player_seasons", y).exists():
            continue
        imp = season_impacts(y, P, lam.get(str(y), {}).get("lambda"))
        table_path("player_impacts_v2", y).parent.mkdir(parents=True, exist_ok=True)
        imp.to_parquet(table_path("player_impacts_v2", y), index=False)
        if y in RAPM_SEASONS or y == max(seasons):
            out["smell_tests"][str(y)] = {**smell(imp), "source": imp.source.iloc[0]}
        print("impact v2", y, imp.source.iloc[0], flush=True)
    (PARAMS / "players_v2.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "top10"} for k, v in r["smell_tests"].items()}, indent=1))
    print("prior cv corr: off", r["prior"]["off"]["cv_corr"], "def", r["prior"]["def"]["cv_corr"])


class StoredV2:
    """Adapter with the ImpactModel.impacts() interface, serving stored v2 impacts (for pipeline.players.prior_eval)."""

    def impacts(self, ps: pd.DataFrame, k: float = 0) -> pd.DataFrame:
        y = int(ps.season.iloc[0]) if "season" in ps else None
        v = pd.read_parquet(table_path("player_impacts_v2", y))
        out = ps[["team_id", "athlete_id", "min", "min_share"]].merge(v[["team_id", "athlete_id", "off", "def"]], on=["team_id", "athlete_id"], how="left")
        out["imp_o"], out["imp_d"] = out.off.fillna(0.0), out["def"].fillna(0.0)
        out["imp"] = out.imp_o + out.imp_d
        return out.drop(columns=["off", "def"])


def roster_cv(tests=range(2013, 2025)) -> dict:
    """Phase 5b.2: next-season team rating error of the roster prior with v2 impacts vs v1 (same rows, same fits).
    Rule (DECISIONS.md, written before running): adopt v2 only if pooled RMSE improves for offense and defense and each
    improves in at least 7 of 12 seasons."""
    from .impact import team_targets
    from .prior_eval import build_rows, fit_predict

    cache = {y: load_ps(y).assign(season=y) for y in range(2010, 2027) if table_path("player_seasons", y).exists()}
    tg = team_targets()
    d1s = {y: set(pd.read_parquet(table_path("team_seasons", y)).query("is_d1").team_id) for y in cache}
    base_o, base_d = ["o1", "o2"], ["d1", "d2"]
    full_o, full_d = base_o + ["ret_o", "in_o", "ret_share", "in_share"], base_d + ["ret_d", "in_d", "ret_share", "in_share"]
    m = StoredV2()
    v1 = json.loads((PARAMS / "players_prior_eval.json").read_text())
    v1csv = pd.read_csv(PARAMS / "players_prior_eval.csv")
    rows = []
    for S in tests:
        tr = [T for T in range(2012, S) if T - 1 in cache]
        train = pd.concat([build_rows(T, m, 0, cache, tg, d1s) for T in tr])
        test = build_rows(S, m, 0, cache, tg, d1s)
        f = fit_predict(train, test, full_o, full_d)
        b = fit_predict(train, test, base_o, base_d)
        k, w = v1["chosen_k_by_season"][str(S)], v1["chosen_window_by_season"][str(S)]
        r1 = v1csv[(v1csv.S == S) & (v1csv.k == k) & (v1csv.win == w)].iloc[0]
        rows.append({"S": S, "base_o": b["o"], "base_d": b["d"], "v2_o": f["o"], "v2_d": f["d"], "v1_o": float(r1.full_o), "v1_d": float(r1.full_d)})
        print("roster cv", S, {k_: round(v_, 3) for k_, v_ in rows[-1].items() if k_ != "S"}, flush=True)
    R = pd.DataFrame(rows)
    rm = lambda c: float(np.sqrt((R[c] ** 2).mean()))  # noqa: E731
    res = {"seasons": [int(R.S.min()), int(R.S.max())], **{f"rmse_{c}": round(rm(c), 4) for c in ("base_o", "base_d", "v1_o", "v1_d", "v2_o", "v2_d")},
           "v2_better_seasons_o": int((R.v2_o < R.v1_o).sum()), "v2_better_seasons_d": int((R.v2_d < R.v1_d).sum()), "n_seasons": int(len(R)),
           "by_season": R.round(4).to_dict("records")}
    res["adopt_v2_in_prior"] = bool(rm("v2_o") < rm("v1_o") and rm("v2_d") < rm("v1_d") and res["v2_better_seasons_o"] >= 7 and res["v2_better_seasons_d"] >= 7)
    p = json.loads((PARAMS / "players_v2.json").read_text())
    p["roster_prior_cv"] = res
    (PARAMS / "players_v2.json").write_text(json.dumps(p, indent=1))
    return res
