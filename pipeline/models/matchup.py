"""Team-level matchup test (IMPROVEMENT_PLAN Phase 4a.3), pre-registered in pipeline/params/matchup_eval.json.

Do style matchups (pace, three-point volume, offensive rebounding, turnovers, free throws, rest) explain the walk-forward
margin residual? Every input is season-to-date from games on EARLIER dates; the adjustment for season S is a ridge fit on
seasons before S; baseline and candidate probabilities go through the same production spread + calibration mapping.

    python -m pipeline.models.matchup
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sklearn.linear_model import RidgeCV

from pipeline.models.backtest import BT
from pipeline.models.production import Predictor, load_prod
from pipeline.warehouse.paths import PARAMS, table_path

FEATURES = ["tempo_clash", "three_point", "offensive_rebounding", "turnovers", "free_throws", "rest"]
FIRST_DATA, TEST = 2010, (2012, 2026)
MIN_GAMES = 3      # pre-registered: fewer earlier D-I games -> feature 0 (league average)
REST_CAP = 7       # pre-registered: days of rest capped
EPS = 1e-6


def team_dates(y: int, fta_coef: float) -> pd.DataFrame:
    """Season-to-date rates for every team on every game date of season y, from games on earlier dates only."""
    tg = pd.read_parquet(table_path("team_games", y))
    tg = tg[tg.both_d1 & tg.fga.notna() & tg.opp_fga.notna() & (tg.game_type != "exhibition")].copy()
    tg["poss"] = tg.fga - tg.orb + tg.tov + fta_coef * tg.fta
    tg["opp_poss"] = tg.opp_fga - tg.opp_orb + tg.opp_tov + fta_coef * tg.opp_fta
    tg["g"] = 1
    cols = ["g", "poss", "opp_poss", "fga", "tpa", "orb", "drb", "tov", "fta", "opp_fga", "opp_tpa", "opp_orb", "opp_drb", "opp_tov", "opp_fta"]
    day = tg.groupby(["team_id", "game_date"])[cols].sum().reset_index().sort_values(["team_id", "game_date"])
    cum = day.groupby("team_id")[cols].cumsum()
    day[cols] = cum.values
    dates = pd.DataFrame({"game_date": np.sort(pd.read_parquet(table_path("games", y)).game_date.unique())})
    grid = dates.merge(pd.DataFrame({"team_id": day.team_id.unique()}), how="cross").sort_values("game_date")
    # last cumulative row strictly before each date (allow_exact_matches=False: same-day games are not "earlier")
    st = pd.merge_asof(grid, day.sort_values("game_date"), on="game_date", by="team_id", allow_exact_matches=False)
    st = st.fillna({c: 0 for c in cols})
    with np.errstate(divide="ignore", invalid="ignore"):
        st["pace"] = st.poss / st.g
        st["tpar"], st["tpar_allowed"] = st.tpa / st.fga, st.opp_tpa / st.opp_fga
        st["orbp"], st["orbp_allowed"] = st.orb / (st.orb + st.opp_drb), st.opp_orb / (st.opp_orb + st.drb)
        st["tovp"], st["tovp_forced"] = st.tov / st.poss, st.opp_tov / st.opp_poss
        st["ftr"], st["ftr_allowed"] = st.fta / st.fga, st.opp_fta / st.opp_fga
    rates = ["pace", "tpar", "tpar_allowed", "orbp", "orbp_allowed", "tovp", "tovp_forced", "ftr", "ftr_allowed"]
    ok = st.g >= MIN_GAMES
    for c in rates:  # z against the league on that date (teams with enough games), 0 below MIN_GAMES
        v = st[c].where(ok)
        m, s = v.groupby(st.game_date).transform("mean"), v.groupby(st.game_date).transform("std")
        st["z_" + c] = ((v - m) / s.replace(0, np.nan)).fillna(0.0)
    st["pace_c"] = (st.pace.where(ok) - st.pace.where(ok).groupby(st.game_date).transform("mean")).fillna(0.0)
    return st[["team_id", "game_date", "g", "pace_c"] + ["z_" + c for c in rates]]


def rest_days(y: int) -> pd.DataFrame:
    g = pd.read_parquet(table_path("games", y))
    g = g[g.completed][["game_id", "game_date", "home_id", "away_id"]]
    long = pd.concat([g.rename(columns={"home_id": "team_id"})[["game_id", "game_date", "team_id"]],
                      g.rename(columns={"away_id": "team_id"})[["game_id", "game_date", "team_id"]]]).sort_values(["team_id", "game_date"])
    long["rest"] = long.groupby("team_id").game_date.diff().dt.days.fillna(REST_CAP).clip(upper=REST_CAP)
    return long[["game_id", "team_id", "rest"]]


def features(y: int, fta_coef: float) -> pd.DataFrame:
    """Pre-game features for every walk-forward-predicted game of season y, oriented home minus away."""
    P = pd.read_parquet(BT / "adjeff_preds.parquet")
    P = P[P.season == y].copy()
    g = pd.read_parquet(table_path("games", y))[["game_id", "home_id", "away_id", "game_date"]]
    P = P.merge(g, on="game_id")
    P = P[P.a == P.home_id]  # backtest side a is the home (or listed-home) team
    st = team_dates(y, fta_coef)
    h = P.merge(st.add_prefix("h_"), left_on=["home_id", "game_date"], right_on=["h_team_id", "h_game_date"], how="left")
    d = h.merge(st.add_prefix("a_"), left_on=["away_id", "game_date"], right_on=["a_team_id", "a_game_date"], how="left")
    d = d.fillna({c: 0.0 for c in d.columns if c.startswith(("h_z_", "a_z_", "h_pace", "a_pace"))})
    r = rest_days(y)
    d = d.merge(r.rename(columns={"team_id": "home_id", "rest": "h_rest"}), on=["game_id", "home_id"], how="left")
    d = d.merge(r.rename(columns={"team_id": "away_id", "rest": "a_rest"}), on=["game_id", "away_id"], how="left")
    X = pd.DataFrame({
        "tempo_clash": d.h_pace_c - d.a_pace_c,
        "three_point": d.h_z_tpar * d.a_z_tpar_allowed - d.a_z_tpar * d.h_z_tpar_allowed,
        "offensive_rebounding": d.h_z_orbp * d.a_z_orbp_allowed - d.a_z_orbp * d.h_z_orbp_allowed,
        "turnovers": d.h_z_tovp * d.a_z_tovp_forced - d.a_z_tovp * d.h_z_tovp_forced,
        "free_throws": d.h_z_ftr * d.a_z_ftr_allowed - d.a_z_ftr * d.h_z_ftr_allowed,
        "rest": d.h_rest.fillna(REST_CAP) - d.a_rest.fillna(REST_CAP),
    })
    X["season"], X["game_id"] = y, d.game_id.values
    X["pm"] = (d.pred_a - d.pred_b).values
    X["poss"] = d.pred_poss.values
    X["margin"] = (d.pts_a - d.pts_b).values
    X["resid"] = X.margin - X.pm
    return X.reset_index(drop=True)


def logloss(p, y):
    p = np.clip(p, EPS, 1 - EPS)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def evaluate(D: pd.DataFrame, feats: list[str], g) -> dict:
    per, pooled_b, pooled_c, ys = {}, [], [], []
    for S in range(TEST[0], TEST[1] + 1):
        tr, te = D[D.season < S], D[D.season == S]
        m = RidgeCV(alphas=np.logspace(-1, 5, 13)).fit(tr[feats].values, tr.resid.values)
        y = (te.margin > 0).astype(float).values
        pb, pc = g(te.pm.values, te.poss.values), g(te.pm.values + m.predict(te[feats].values), te.poss.values)
        per[str(S)] = {"baseline": round(logloss(pb, y), 5), "candidate": round(logloss(pc, y), 5), "alpha": float(m.alpha_),
                       "coef": [round(float(c), 4) for c in m.coef_]}
        pooled_b.append(pb), pooled_c.append(pc), ys.append(y)
    yy = np.concatenate(ys)
    lb, lc = logloss(np.concatenate(pooled_b), yy), logloss(np.concatenate(pooled_c), yy)
    return {"features": feats, "pooled_baseline": round(lb, 5), "pooled_candidate": round(lc, 5), "improvement": round(lb - lc, 5),
            "seasons_improved": sum(v["candidate"] < v["baseline"] for v in per.values()), "by_season": per}


def run() -> dict:
    prm = json.loads((PARAMS / "matchup_eval.json").read_text())
    rule = prm["adoption_rule"]
    prod = load_prod()
    cal = Predictor.__new__(Predictor)
    cal.sig, cal.gx, cal.gy = prod["sigma_coef"], np.array(prod["calibration_grid_x"]), np.array(prod["calibration_grid_y"])
    fta = json.loads((PARAMS / "possessions.json").read_text())["fta_coef"]
    D = pd.concat([features(y, fta) for y in range(FIRST_DATA, TEST[1] + 1)], ignore_index=True)
    D = D[np.isfinite(D[FEATURES]).all(axis=1) & D.resid.notna() & (D.margin != 0)]
    passes = lambda r: r["improvement"] >= rule["pooled_log_loss_improvement_at_least"] and r["seasons_improved"] >= rule["seasons_improved_at_least"]  # noqa: E731
    results = {f: evaluate(D, [f], cal._win_prob) for f in FEATURES}
    results["joint"] = evaluate(D, FEATURES, cal._win_prob)
    for r in results.values():
        r["passes"] = bool(passes(r))
        print(r["features"], r["improvement"], r["seasons_improved"], r["passes"], flush=True)
    adopted = [f for f in FEATURES if results[f]["passes"]]
    prm["results"] = {"n_games": int(len(D)), "per_feature": {k: {kk: v for kk, v in r.items() if kk != "by_season"} for k, r in results.items()},
                      "by_season": {k: r["by_season"] for k, r in results.items()}}
    prm["decision"] = {"adopted": adopted, "status": "adopted" if adopted else "context only",
                       "note": "A feature enters the prediction only if it passes the rule alone; none did." if not adopted else "Adopted features enter the prediction through this file."}
    prm["status"] = "evaluated"
    prm["evaluated"] = pd.Timestamp.now().strftime("%Y-%m-%d")
    (PARAMS / "matchup_eval.json").write_text(json.dumps(prm, indent=1))
    return prm


if __name__ == "__main__":
    r = run()
    print(r["decision"])
