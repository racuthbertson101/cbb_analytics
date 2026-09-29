"""Evaluate the walk-forward backtest: margin errors, calibrated win probability, baselines, reliability, reports."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from pipeline.warehouse.paths import PARAMS

from .backtest import BT, FIRST_TEST, combined_cfg
from .data import load_games
from .elo import elo_predictions

EPS = 1e-6
BUCKETS = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0001]


def sigma_model(train: pd.DataFrame, use_tempo: bool) -> tuple:
    """E|resid| = sigma*sqrt(2/pi); optionally linear in predicted possessions."""
    r = (train.margin_pred - train.margin).abs().values
    if use_tempo:
        X = np.c_[np.ones(len(train)), train.pred_poss.values - 68.0]
        b = np.linalg.lstsq(X, r, rcond=None)[0]
    else:
        b = np.array([r.mean(), 0.0])
    return tuple(b * np.sqrt(np.pi / 2))


def sigma_of(b, pred_poss):
    return np.maximum(b[0] + b[1] * (pred_poss - 68.0), 3.0)


def logloss(p, y):
    p = np.clip(p, EPS, 1 - EPS)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def fit_calibrator(kind, p_raw, y):
    if kind == "raw":
        return lambda p: p
    if kind == "platt":
        z = np.log(np.clip(p_raw, EPS, 1 - EPS) / (1 - np.clip(p_raw, EPS, 1 - EPS)))
        m = LogisticRegression(C=1e6).fit(z[:, None], y)
        return lambda p: m.predict_proba(np.log(np.clip(p, EPS, 1 - EPS) / (1 - np.clip(p, EPS, 1 - EPS)))[:, None])[:, 1]
    iso = IsotonicRegression(y_min=0.005, y_max=0.995, out_of_bounds="clip").fit(p_raw, y)
    return iso.predict


def metrics(p, y, margin_pred=None, margin=None) -> dict:
    p = np.clip(p, EPS, 1 - EPS)
    out = {"n": int(len(y)), "log_loss": logloss(p, y), "brier": float(((p - y) ** 2).mean()),
           "accuracy": float(((p > 0.5) == (y > 0.5)).mean())}
    if margin_pred is not None:
        e = margin_pred - margin
        out["mae"], out["rmse"] = float(np.abs(e).mean()), float(np.sqrt((e ** 2).mean()))
    return out


def reliability(p, y, bins=10):
    df = pd.DataFrame({"p": p, "y": y})
    df["bin"] = np.minimum((df.p * bins).astype(int), bins - 1)
    g = df.groupby("bin").agg(mean_pred=("p", "mean"), obs=("y", "mean"), n=("y", "size")).reset_index()
    ece = float((g.n * (g.mean_pred - g.obs).abs()).sum() / g.n.sum())
    return g.round(4).to_dict("records"), ece


def bucket_table(p, y):
    conf = np.maximum(p, 1 - p)
    correct = ((p > 0.5) == (y > 0.5))
    rows = []
    for lo, hi in zip(BUCKETS[:-1], BUCKETS[1:]):
        m = (conf >= lo) & (conf < hi)
        if m.sum():
            rows.append({"bucket": f"{lo:.2f}-{min(hi, 1):.2f}", "n": int(m.sum()), "mean_conf": float(conf[m].mean()),
                         "accuracy": float(correct[m].mean())})
    return rows


def main():
    P = pd.read_parquet(BT / "adjeff_preds.parquet")
    P["margin_pred"] = P.pred_a - P.pred_b
    P["margin"] = P.pts_a - P.pts_b
    P["y"] = (P.margin > 0).astype(float)
    G = load_games()
    seasons_test = list(range(FIRST_TEST, 2027))

    # Elo baseline
    E = elo_predictions(G, seasons_test)
    P = P.merge(E[["game_id", "elo_diff", "elo_cfg"]], on="game_id", how="left")

    out_rows, oos = [], []
    cal_choice = {}
    for S in seasons_test:
        tr, te = P[P.season < S], P[P.season == S].copy()
        # spread model: compare constant vs tempo-dependent sigma out of sample (log loss of normal win prob)
        bc, bt = sigma_model(tr, False), sigma_model(tr, True)
        te["p_const"] = norm.cdf(te.margin_pred / sigma_of(bc, te.pred_poss))
        te["p_tempo"] = norm.cdf(te.margin_pred / sigma_of(bt, te.pred_poss))
        oos.append(te.assign(bc0=bc[0], bt0=bt[0], bt1=bt[1]))
    O = pd.concat(oos)
    ll_const = logloss(O.p_const.values, O.y.values)
    ll_tempo = logloss(O.p_tempo.values, O.y.values)
    use_tempo = ll_tempo < ll_const - 1e-5
    pcol = "p_tempo" if use_tempo else "p_const"

    # calibration candidates (fit on seasons < S, evaluated on S)
    cands = {}
    for kind in ("raw", "platt", "isotonic"):
        ps = []
        for S in seasons_test:
            tr_ = P[P.season < S]
            b = sigma_model(tr_, use_tempo)
            p_tr = norm.cdf(tr_.margin_pred / sigma_of(b, tr_.pred_poss))
            cal = fit_calibrator(kind, p_tr, tr_.y.values)
            te = O[O.season == S]
            ps.append(pd.Series(cal(te[pcol].values), index=te.index))
        cands[kind] = pd.concat(ps)
    cal_ll = {k: logloss(v.values, O.loc[v.index, "y"].values) for k, v in cands.items()}
    best_cal = min(cal_ll, key=cal_ll.get)
    O["p_final"] = cands[best_cal]

    # baselines (walk-forward)
    def home_baseline():
        ps, mp = [], []
        for S in seasons_test:
            tr_, te = P[P.season < S], O[O.season == S]
            h = tr_[tr_.site > 0]
            ph = h.y.mean()
            mh = h.margin.mean()
            ps.append(pd.Series(np.where(te.site > 0, ph, 0.5), index=te.index))
            mp.append(pd.Series(np.where(te.site > 0, mh, 0.0), index=te.index))
        return pd.concat(ps), pd.concat(mp)

    ph, mh = home_baseline()
    O["p_home"], O["m_home"] = ph, mh
    # accuracy for 'home team wins' as a pure pick (neutral: pick 'a' arbitrary -> excluded from accuracy comparison)
    # previous-season rating only
    pv = []
    for S in seasons_test:
        tr_ = P[(P.season < S) & P.prev_margin.notna()]
        te = O[O.season == S]
        s = np.sqrt(((tr_.prev_margin - tr_.margin) ** 2).mean())
        pv.append(pd.Series(norm.cdf(te.prev_margin.fillna(0) / s), index=te.index))
    O["p_prev"] = pd.concat(pv)
    # Elo: margin via linear map of diff + site (fit on seasons < S), win prob from elo logistic
    ep, em = [], []
    for S in seasons_test:
        tr_ = P[(P.season < S) & P.elo_diff.notna()]
        te = O[O.season == S]
        X = np.c_[tr_.elo_diff, tr_.site, np.ones(len(tr_))]
        b = np.linalg.lstsq(X, tr_.margin.values, rcond=None)[0]
        em.append(pd.Series(np.c_[te.elo_diff, te.site, np.ones(len(te))] @ b, index=te.index))
        hca = float(te.elo_cfg.iloc[0].split(",")[1])
        ep.append(pd.Series(1 / (1 + 10 ** (-(te.elo_diff + hca * te.site) / 400)), index=te.index))
    O["p_elo"], O["m_elo"] = pd.concat(ep), pd.concat(em)

    systems = {
        "adjeff (calibrated)": (O.p_final, O.margin_pred),
        "adjeff (raw normal)": (O[pcol], O.margin_pred),
        "home team wins": (O.p_home, O.m_home),
        "previous-season rating only": (O.p_prev, O.prev_margin.fillna(0)),
        "simple Elo": (O.p_elo, O.m_elo),
    }
    report = {"test_seasons": [FIRST_TEST, 2026], "sigma_const_ll": ll_const, "sigma_tempo_ll": ll_tempo,
              "sigma_uses_tempo": bool(use_tempo), "calibration_candidates_ll": cal_ll, "calibration_chosen": best_cal,
              "systems": {}, "by_season": {}}
    for name, (p, mp) in systems.items():
        m = metrics(p.values, O.y.values, mp.values, O.margin.values)
        # accuracy of picking the team favored; for home-baseline picks home on non-neutral only
        if name == "home team wins":
            nn = O.site > 0
            m["accuracy"] = float((O.y[nn] == 1).mean())
            m["accuracy_note"] = "non-neutral games only (always pick home)"
        report["systems"][name] = m
    # per-season table for calibrated model and baselines
    for S in seasons_test:
        s = O[O.season == S]
        report["by_season"][str(S)] = {
            "adjeff": metrics(s.p_final.values, s.y.values, s.margin_pred.values, s.margin.values),
            "home": metrics(s.p_home.values, s.y.values, s.m_home.values, s.margin.values),
            "prev": metrics(s.p_prev.values, s.y.values, s.prev_margin.fillna(0).values, s.margin.values),
            "elo": metrics(s.p_elo.values, s.y.values, s.m_elo.values, s.margin.values)}
    rel, ece = reliability(O.p_final.values, O.y.values)
    report["reliability"], report["ece"] = rel, ece
    rel_raw, ece_raw = reliability(O[pcol].values, O.y.values)
    report["reliability_uncalibrated"], report["ece_uncalibrated"] = rel_raw, ece_raw
    report["buckets"] = bucket_table(O.p_final.values, O.y.values)
    beats = {k: bool(v["log_loss"] > report["systems"]["adjeff (calibrated)"]["log_loss"]) for k, v in report["systems"].items() if k != "adjeff (calibrated)"}
    report["beats_baselines_logloss"] = beats
    report["seasons_beating_home"] = int(sum(v["adjeff"]["log_loss"] < v["home"]["log_loss"] for v in report["by_season"].values()))
    tourn = O[O.game_type == "ncaa"]
    report["ncaa_tournament"] = metrics(tourn.p_final.values, tourn.y.values, tourn.margin_pred.values, tourn.margin.values)
    report["bias_margin"] = float((O.margin_pred - O.margin).mean())
    PARAMS.mkdir(parents=True, exist_ok=True)
    (PARAMS / "backtest.json").write_text(json.dumps(report, indent=1))
    O[["game_id", "season", "date", "a", "b", "site", "margin_pred", "margin", "pred_poss", "p_final", "y", "game_type"]].to_parquet(BT / "oos_preds.parquet")

    # production parameters: everything estimated on all seasons through 2026
    prod_cfg = combined_cfg(2027)
    meta = json.loads((BT / "meta.json").read_text())
    b_all = sigma_model(P, use_tempo)
    p_all = norm.cdf(P.margin_pred / sigma_of(b_all, P.pred_poss))
    cal = fit_calibrator(best_cal, p_all, P.y.values)
    grid = np.linspace(0.001, 0.999, 999)
    resid = (P.margin - P.margin_pred)
    qs = {str(q): float(resid.quantile(q)) for q in (0.05, 0.10, 0.25, 0.75, 0.90, 0.95)}
    a_res = pd.concat([(P.pts_a - P.pred_a), (P.pts_b - P.pred_b)])
    sq = {str(q): float(a_res.quantile(q)) for q in (0.05, 0.10, 0.25, 0.75, 0.90, 0.95)}
    from .engine import Context, finals_no_prior, prior_coefs
    ctx_all = Context()
    cur_coefs = prior_coefs(ctx_all, finals_no_prior(ctx_all, prod_cfg), 2027)
    prod = {"config": prod_cfg, "prior_coefs_current": cur_coefs, "sigma_coef": list(map(float, b_all)), "sigma_uses_tempo": bool(use_tempo),
            "calibration": best_cal, "calibration_grid_x": grid.tolist(), "calibration_grid_y": np.asarray(cal(grid)).round(5).tolist(),
            "margin_residual_quantiles": qs, "score_residual_quantiles": sq,
            "season_cfgs": {k: v["cfg"] for k, v in meta.items()}, "prior_coefs_by_season": {k: v["prior_coefs"] for k, v in meta.items()},
            "evidence": "see backtest.json (walk-forward, test seasons 2012-2026)"}
    (PARAMS / "adjeff.json").write_text(json.dumps(prod, indent=1))
    write_md(report, prod)
    print(json.dumps({k: report[k] for k in ("sigma_uses_tempo", "calibration_chosen", "calibration_candidates_ll", "ece", "ece_uncalibrated", "seasons_beating_home", "ncaa_tournament")}, indent=1))
    for k, v in report["systems"].items():
        print(k, {a: round(b, 4) for a, b in v.items() if isinstance(b, float)})
    return report


def write_md(rep, prod):
    L = ["# Adjusted-efficiency backtest", "",
         f"Walk-forward over test seasons {rep['test_seasons'][0]}-{rep['test_seasons'][1]}. Each game is predicted from ratings fit on games strictly before its date; hyperparameters for season S are chosen on seasons < S; the spread model and calibrator for season S are fit on predictions of seasons < S.", "",
         "## Systems (pooled over all test games)", "", "| System | MAE | RMSE | Log loss | Brier | Accuracy |", "|---|---|---|---|---|---|"]
    for k, v in rep["systems"].items():
        L.append(f"| {k} | {v.get('mae', float('nan')):.3f} | {v.get('rmse', float('nan')):.3f} | {v['log_loss']:.4f} | {v['brier']:.4f} | {v['accuracy']:.3f} |")
    L += ["", f"Spread model uses tempo: **{rep['sigma_uses_tempo']}** (log loss const {rep['sigma_const_ll']:.4f} vs tempo-dependent {rep['sigma_tempo_ll']:.4f}).",
          f"Calibrator chosen: **{rep['calibration_chosen']}** (walk-forward log loss by candidate: " + ", ".join(f"{k} {v:.4f}" for k, v in rep["calibration_candidates_ll"].items()) + ").",
          f"Expected calibration error: {rep['ece']:.4f} (uncalibrated {rep['ece_uncalibrated']:.4f}). Bias (pred - actual margin): {rep['bias_margin']:.3f}.",
          f"Seasons where adjeff beats home-team-wins log loss: {rep['seasons_beating_home']} of {len(rep['by_season'])}.", "",
          "## Reliability (calibrated)", "", "| Bin | Mean predicted | Observed | N |", "|---|---|---|---|"]
    for r in rep["reliability"]:
        L.append(f"| {r['bin']} | {r['mean_pred']:.3f} | {r['obs']:.3f} | {r['n']} |")
    L += ["", "## Accuracy by confidence bucket", "", "| Bucket | N | Mean confidence | Accuracy |", "|---|---|---|---|"]
    for r in rep["buckets"]:
        L.append(f"| {r['bucket']} | {r['n']} | {r['mean_conf']:.3f} | {r['accuracy']:.3f} |")
    L += ["", "## By season (adjeff calibrated)", "", "| Season | MAE | RMSE | Log loss | Accuracy | Home-wins log loss |", "|---|---|---|---|---|---|"]
    for s, v in rep["by_season"].items():
        a = v["adjeff"]
        L.append(f"| {s} | {a['mae']:.2f} | {a['rmse']:.2f} | {a['log_loss']:.4f} | {a['accuracy']:.3f} | {v['home']['log_loss']:.4f} |")
    t = rep["ncaa_tournament"]
    L += ["", f"NCAA tournament games: n={t['n']}, MAE {t['mae']:.2f}, log loss {t['log_loss']:.4f}, accuracy {t['accuracy']:.3f}.", "",
          "## Production parameters", "", f"Config: `{json.dumps(prod['config'])}`"]
    (PARAMS / "BACKTEST.md").write_text("\n".join(L), encoding="utf8")


if __name__ == "__main__":
    main()
