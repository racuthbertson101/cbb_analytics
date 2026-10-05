"""In-game win probability (IMPROVEMENT_PLAN Phase 3b.2), fit walk-forward on play-by-play score states.

Model: logistic regression for "home team wins" on
    x1 = margin / sqrt(t + 1)            margin = home - away now; t = seconds left in regulation (or in the current OT period)
    x2 = logit(p0) * t / 2400            our calibrated walk-forward pregame probability, fading as the game runs down
    x3 = margin
    x4 = overtime flag
    x5 = margin / sqrt(t + 1) if t < 120 the last two minutes, where possession matters more than time
    x6 = t / 2400                        time trend (regulation share left)
(The plan's starting set was x1, pregame spread * t/2400, x3, x4; the pregame logit plus x5 and x6 were adopted after a
walk-forward comparison on 2022-2026: log loss 0.3778 -> 0.3770, worst calibration bin 6.3 -> 4.8 pp; DECISIONS.md.)
anchored to our calibrated pregame probability p0:
    WP = sigmoid( f(x) + w * (logit(p0) - f(tip)) ),  w = t / 2400 in regulation, 0 in overtime,
so WP equals p0 exactly at tip-off and the anchor fades out by the end of regulation.

Walk-forward: the model for season S is fit only on seasons before S (2016 is the first play-by-play season). Training uses
completed D-I games whose play-by-play final score equals the box score (incomplete feeds are dropped). Evidence, including
calibration by time remaining, goes to pipeline/params/ingame.json.

    python -m pipeline.models.ingame
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from pipeline.models.backtest import BT
from pipeline.pbp.parse import FIRST, OT, REG
from pipeline.warehouse.paths import PARAMS, table_path

FEATURES = ["x1", "x2", "x3", "x4", "x5", "x6"]
LATE = 120  # DEFINITION: "last two minutes" for x5
# DEFINITION: time-remaining buckets (seconds left) used to report calibration; "OT" = any overtime state
BUCKETS = [(1800, 2400, "40-30 min left"), (1200, 1800, "30-20"), (600, 1200, "20-10"), (300, 600, "10-5"), (120, 300, "5-2"), (0, 120, "under 2")]
EPS = 1e-6


def logit(p):
    p = np.clip(p, EPS, 1 - EPS)
    return np.log(p / (1 - p))


def sigmoid(z):
    return 1 / (1 + np.exp(-z))


def pregame() -> pd.DataFrame:
    """Walk-forward pregame margin and calibrated probability per game (home perspective; backtest `a` is the home team)."""
    O = pd.read_parquet(BT / "oos_preds.parquet", columns=["game_id", "season", "margin_pred", "p_final"])
    return O.rename(columns={"margin_pred": "pm", "p_final": "p0"}).assign(game_id=lambda d: d.game_id.astype(str))


def clock(elapsed: np.ndarray):
    """(t, ot): seconds left in regulation, or in the current overtime period, and the overtime flag."""
    e = np.asarray(elapsed, float)
    ot = e > REG
    t_ot = OT - ((e - REG) % OT)
    t_ot = np.where((e - REG) % OT == 0, 0, t_ot)  # exactly at the end of an OT period
    return np.where(ot, t_ot, np.maximum(REG - e, 0)), ot.astype(float)


def features(margin, t, ot, p0) -> np.ndarray:
    tr = np.where(ot > 0, 0, t) / REG
    z = margin / np.sqrt(t + 1)
    return np.column_stack([z, logit(p0) * tr, margin, ot, z * ((t < LATE) & (ot == 0)), tr])


def states(season: int, pre: pd.DataFrame | None = None) -> pd.DataFrame:
    """Score states of complete games with a walk-forward pregame prediction, with the final result."""
    s = pd.read_parquet(table_path("pbp_scores", season))
    g = pd.read_parquet(table_path("games", season))
    g = g[g.completed & g.both_d1 & (g.game_type != "exhibition")][["game_id", "home_score", "away_score"]]
    fin = s.groupby("game_id")[["home", "away"]].last()
    ok = g.set_index("game_id").join(fin, how="inner")
    ok = ok[(ok.home == ok.home_score) & (ok.away == ok.away_score)]
    pre = pregame() if pre is None else pre
    d = s[s.game_id.isin(ok.index)].merge(pre[["game_id", "pm", "p0"]], on="game_id")
    d["y"] = d.game_id.map((ok.home_score > ok.away_score).astype(float))
    d["margin"] = d.home - d.away
    d["t"], d["ot"] = clock(d.elapsed.values)
    last = ~d.game_id.duplicated(keep="last")
    d = d[~last | (d.t > 0)]  # the final whistle is the result, not a prediction
    X = features(d.margin.values, d.t.values, d.ot.values, d.p0.values)
    for i, c in enumerate(FEATURES):
        d[c] = X[:, i]
    d["season"] = season
    return d


def fit(d: pd.DataFrame) -> dict:
    m = LogisticRegression(C=1e6, max_iter=500).fit(d[FEATURES].values, d.y.values)
    return {"intercept": float(m.intercept_[0]), "coef": [float(c) for c in m.coef_[0]], "n_states": int(len(d)), "n_games": int(d.game_id.nunique()),
            "train_seasons": sorted(int(y) for y in d.season.unique())}


def predict(c: dict, margin, t, ot, p0) -> np.ndarray:
    """Anchored in-game home win probability."""
    b, w = np.array(c["coef"]), c["intercept"]
    p0 = np.asarray(p0, float)
    f = w + features(np.asarray(margin, float), np.asarray(t, float), np.asarray(ot, float), p0) @ b
    tip = w + features(np.zeros_like(p0), np.full(p0.shape, REG), np.zeros(p0.shape), p0) @ b
    a = np.where(np.asarray(ot) > 0, 0.0, np.asarray(t, float) / REG)
    return sigmoid(f + a * (logit(p0) - tip))


def calibration(p: np.ndarray, y: np.ndarray, t: np.ndarray, ot: np.ndarray) -> list[dict]:
    rows = []
    groups = [(f"{name}", (ot == 0) & (t > lo) & (t <= hi) if lo else (ot == 0) & (t <= hi)) for lo, hi, name in BUCKETS] + [("overtime", ot > 0)]
    for name, mask in groups:
        pp, yy = p[mask], y[mask]
        bins = np.minimum((pp * 10).astype(int), 9)
        ece = sum(abs(pp[bins == k].mean() - yy[bins == k].mean()) * (bins == k).sum() for k in range(10) if (bins == k).any()) / max(len(pp), 1)
        worst = max((abs(pp[bins == k].mean() - yy[bins == k].mean()) for k in range(10) if (bins == k).sum() >= 500), default=0.0)
        rows.append({"bucket": name, "n": int(mask.sum()), "mean_pred": round(float(pp.mean()), 4), "observed": round(float(yy.mean()), 4),
                     "ece": round(float(ece), 4), "worst_bin_gap": round(float(worst), 4)})
    return rows


def logloss(p, y):
    p = np.clip(p, EPS, 1 - EPS)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def walk_forward(last_season: int = 2026, export_seasons=(2025, 2026, 2027)) -> dict:
    pre = pregame()
    seasons = [y for y in range(FIRST, last_season + 1) if table_path("pbp_scores", y).exists()]
    data = {y: states(y, pre) for y in seasons}
    by_season, oos = {}, []
    for S in seasons[1:]:
        c = fit(pd.concat([data[y] for y in seasons if y < S]))
        d = data[S]
        p = predict(c, d.margin, d.t, d.ot, d.p0)
        base = LogisticRegression(C=1e6).fit(pd.concat([data[y] for y in seasons if y < S])[["x1"]].values,
                                              pd.concat([data[y] for y in seasons if y < S]).y.values)
        by_season[str(S)] = {**c, "log_loss": round(logloss(p, d.y.values), 4), "brier": round(float(np.mean((p - d.y.values) ** 2)), 4),
                             "log_loss_pregame_only": round(logloss(d.p0.values, d.y.values), 4),
                             "log_loss_margin_only": round(logloss(base.predict_proba(d[["x1"]].values)[:, 1], d.y.values), 4)}
        oos.append(pd.DataFrame({"p": p, "y": d.y.values, "t": d.t.values, "ot": d.ot.values}))
        print("ingame", S, by_season[str(S)]["log_loss"], flush=True)
    O = pd.concat(oos)
    production = {str(y): fit(pd.concat([data[s] for s in seasons if s < y])) for y in export_seasons}
    out = {
        "model": "logistic on [margin/sqrt(t+1), logit(pregame p)*t/2400, margin, OT flag, late-game margin/sqrt(t+1), t/2400], anchored to the calibrated pregame probability",
        "variant_comparison_2022_2026": {"plan_features": {"log_loss": 0.3778, "max_bucket_ece": 0.0207, "worst_bin_gap": 0.0631},
                                         "pregame_logit": {"log_loss": 0.3778, "max_bucket_ece": 0.0215, "worst_bin_gap": 0.0613},
                                         "adopted": {"log_loss": 0.3770, "max_bucket_ece": 0.0194, "worst_bin_gap": 0.0482}},
        "features": FEATURES, "first_season": FIRST, "test_seasons": [int(seasons[1]), int(seasons[-1])],
        "by_season": by_season, "production": production,
        "calibration_by_time_left": calibration(O.p.values, O.y.values, O.t.values, O.ot.values),
        "pooled": {"n_states": int(len(O)), "log_loss": round(logloss(O.p.values, O.y.values), 4)},
        "note": "Walk-forward: each season's model is fit on earlier seasons only. Calibration pools every test season out of sample.",
    }
    (PARAMS / "ingame.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    r = walk_forward()
    for row in r["calibration_by_time_left"]:
        print(row)
