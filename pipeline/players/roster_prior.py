"""Roster-based preseason prior features (adopted after walk-forward cross validation, see params/players_prior_eval.json).

For each target season S, features for every team-season T <= S are computed with the impact model trained on seasons < S (so nothing
about season S results enters S's features): returning and incoming-transfer impact contributions and minutes shares, from the
previous season's player impacts and the season's roster (players who appear for the team; the rosters table for the upcoming season).
Saved to data/backtest/roster_feats.pkl as {S: {"feats": {T: DataFrame}, "window": int, "k": float}}.
"""
from __future__ import annotations

import json
import pickle

import pandas as pd

from pipeline.models.backtest import BT
from pipeline.warehouse.paths import PARAMS, table_path

from .impact import ImpactModel, load_ps, team_targets
from .prior_eval import roster_features

FEAT_COLS = ["ret_o", "ret_d", "in_o", "in_d", "ret_share", "in_share"]


def build(upcoming: int = 2027):
    cache = {y: load_ps(y) for y in range(2010, upcoming) if table_path("player_impacts", y).exists()}
    tg = team_targets()
    ev = json.loads((PARAMS / "players_prior_eval.json").read_text())
    R = pd.read_csv(PARAMS / "players_prior_eval.csv")
    alpha_by_s = R.groupby("S").alpha.first().to_dict()
    d1 = {y: list(pd.read_parquet(table_path("team_seasons", y)).query("is_d1").team_id) for y in range(2010, upcoming + 1) if table_path("team_seasons", y).exists()}
    out = {}
    targets = [int(s) for s in ev["chosen_k_by_season"]] + [upcoming]
    for S in targets:
        if S == upcoming:
            pj = json.loads((PARAMS / "players.json").read_text())
            model, k, win = ImpactModel.from_json(pj["model"]), float(pj["shrink_k_minutes"]), int(ev["chosen_window_by_season"].get("2026", 0))
            ro = table_path("rosters", S)
            roster = pd.read_parquet(ro)[["team_id", "athlete_id"]].drop_duplicates() if ro.exists() else None
        else:
            k, win = float(ev["chosen_k_by_season"][str(S)]), int(ev["chosen_window_by_season"][str(S)])
            model = ImpactModel(alpha_by_s[S]).fit([y for y in cache if y < S], tg, cache)
            roster = None
        feats = {}
        for T in range(2012, S + 1):
            if T - 1 not in cache:
                continue
            feats[T] = roster_features(T, model, k, cache, d1[T], roster if T == S and roster is not None else None)[FEAT_COLS]
        out[S] = {"feats": feats, "window": win, "k": k}
        print("roster feats", S, len(feats), flush=True)
    pickle.dump(out, open(BT / "roster_feats.pkl", "wb"))


if __name__ == "__main__":
    build()
