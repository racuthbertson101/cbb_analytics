"""Accuracy exports: live prediction-log scoreboard and walk-forward backtest summaries."""
from __future__ import annotations

import numpy as np
import pandas as pd

from pipeline.models.backtest import BT
from pipeline.models.evaluate import bucket_table, metrics, reliability
from pipeline.predictions import log
from pipeline.warehouse.paths import table_path

from .contract import write


def live_summary():
    L = log.read()
    problems = log.check()
    if L.empty:
        write("accuracy/live.json", {"n_logged": 0, "n_resolved": 0, "verified": not problems, "problems": problems,
                                     "message": "No live predictions logged yet. The log starts when the season opens and is append-only."})
        return
    seasons = sorted({int(str(d)[:4]) + (1 if int(str(d)[5:7]) >= 9 else 0) for d in L.game_date})
    G = pd.concat([pd.read_parquet(table_path("games", y)) for y in seasons if table_path("games", y).exists()])
    S = log.scored(L, G)  # last prediction made before tip-off, per game
    # per-game badge for the Game page: the scored prediction's time, hash prefix and values
    S["season"] = [int(str(d)[:4]) + (1 if int(str(d)[5:7]) >= 9 else 0) for d in S.game_date.astype(str)]
    for y, grp in S.groupby("season"):
        write(f"accuracy/logged/{y}.json", {"v": 1, "cols": ["made_at", "hash", "p", "pm", "days_before"],
                                            "games": {r.game_id: [r.made_at, r.row_hash[:12], round(float(r.p), 4), round(float(r.pm), 2), int(r.days_before)]
                                                      for r in grp.itertuples()}})
    m = S.merge(G[["game_id", "completed", "home_score", "away_score"]], on="game_id", how="left")
    done = m[m.completed.fillna(False).astype(bool)]
    out = {"n_logged": int(len(L)), "n_games": int(L.game_id.nunique()), "n_resolved": int(len(done)), "verified": not problems, "problems": problems,
           "first_logged": str(L.made_at.min()), "last_logged": str(L.made_at.max()),
           "scoring": "last prediction made before tip-off", "logged_seasons": sorted(int(x) for x in S.season.unique())}
    if len(done):
        y = (done.home_score > done.away_score).astype(float).values
        p = done.p.astype(float).values
        mm = metrics(p, y, done.pm.astype(float).values, (done.home_score - done.away_score).astype(float).values)
        rel, ece = reliability(p, y)
        done = done.assign(day=done.game_date.astype(str))
        daily = done.groupby("day").apply(lambda d: {"day": d.name, "n": len(d), "correct": int(((d.p > 0.5) == (d.home_score > d.away_score)).sum())}, include_groups=False).tolist()
        days = done.days_before.value_counts().sort_index()
        out.update({"metrics": mm, "reliability": rel, "ece": ece, "buckets": bucket_table(p, y), "daily": daily,
                    "days_before": [{"days": int(k), "n": int(v)} for k, v in days.items()]})
    write("accuracy/live.json", out)


def backtest_summary():
    O = pd.read_parquet(BT / "oos_preds.parquet")
    per = {}
    for s, g in O.groupby("season"):
        per[str(s)] = metrics(g.p_final.values, g.y.values, g.margin_pred.values, g.margin.values)
    last = O[O.season >= O.season.max() - 2]
    rel, ece = reliability(last.p_final.values, last.y.values)
    recent = O[(O.season == O.season.max()) & (O.game_type == "regular")].sort_values("date", ascending=False).head(60)
    write("accuracy/backtest.json", {"per_season": per, "reliability_last3": rel, "ece_last3": ece, "buckets_last3": bucket_table(last.p_final.values, last.y.values),
                                     "last3_seasons": [int(O.season.max() - 2), int(O.season.max())]})
    write("accuracy/recent.json", {"rows": [{"d": str(r.date.date()), "a": r.b, "h": r.a, "pm": round(float(r.margin_pred), 1), "p": round(float(r.p_final), 3), "m": int(r.margin), "n": bool(r.site == 0)} for r in recent.itertuples()]})


if __name__ == "__main__":
    live_summary()
    backtest_summary()
