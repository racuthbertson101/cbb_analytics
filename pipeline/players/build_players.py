"""Fit the final impact model, write player_impacts tables and params/players.json (coefficients + validation evidence)."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from pipeline.warehouse.paths import PARAMS, table_path

from .impact import ImpactModel, load_ps, team_targets, within_season_r2

ALPHAS = [1.0, 3.0, 10.0, 30.0, 100.0, 300.0]


def main():
    seasons = [y for y in range(2010, 2027) if table_path("player_seasons", y).exists()]
    cache = {y: load_ps(y) for y in seasons}
    tg = team_targets()
    # alpha by leave-one-season-out on within-season team fit (all seasons)
    cv = {}
    for a in ALPHAS:
        errs = []
        for hold in seasons:
            m = ImpactModel(a).fit([y for y in seasons if y != hold], tg, cache)
            r2 = within_season_r2(m, cache, tg, [hold])
            errs.append((1 - r2["o"], 1 - r2["d"]))
        cv[a] = float(np.mean(errs))
    alpha = min(cv, key=cv.get)
    model = ImpactModel(alpha).fit(seasons, tg, cache)
    r2 = within_season_r2(model, cache, tg, seasons)
    ev = json.loads((PARAMS / "players_prior_eval.json").read_text())
    R = pd.read_csv(PARAMS / "players_prior_eval.csv")
    pooled = R.groupby("k").apply(lambda x: (x.full_o ** 2 + x.full_d ** 2).mean(), include_groups=False)
    k = int(pooled.idxmin())
    for y in seasons:
        imp = model.impacts(cache[y], k)
        ps = cache[y].merge(imp[["athlete_id", "team_id", "imp_o", "imp_d", "imp"]], on=["athlete_id", "team_id"])
        p = table_path("player_impacts", y)
        p.parent.mkdir(parents=True, exist_ok=True)
        ps.to_parquet(p, index=False)
    params = {"model": model.to_json(), "alpha_cv_error": {str(a): v for a, v in cv.items()}, "alpha": alpha, "shrink_k_minutes": k,
              "shrink_k_evidence": "k minimizing pooled walk-forward next-season RMSE (players_prior_eval.csv)",
              "within_season_r2_offense": r2["o"], "within_season_r2_defense": r2["d"],
              "prior_evaluation": {kk: ev[kk] for kk in ("rmse_o_base", "rmse_o_full", "rmse_d_base", "rmse_d_full", "seasons_o_improved", "seasons_d_improved", "adopt")},
              "decision": "Roster-based preseason prior NOT adopted: did not improve next-season team ratings in at least 9 of 14 walk-forward test seasons (SPEC 7: adopt only if cross validation says it helps)."
              if not ev["adopt"] else "Roster-based preseason prior adopted.",
              "features_offense": list(model.coef["o"][1].index), "features_defense": list(model.coef["d"][1].index)}
    (PARAMS / "players.json").write_text(json.dumps(params, indent=1))
    print(json.dumps({k_: v for k_, v in params.items() if k_ not in ("model",)}, indent=1))
    top = pd.read_parquet(table_path("player_impacts", 2026)).query("min > 600").sort_values("imp", ascending=False).head(8)
    print(top[["name", "team_id", "min", "imp_o", "imp_d", "imp"]].round(2).to_string())


if __name__ == "__main__":
    main()
