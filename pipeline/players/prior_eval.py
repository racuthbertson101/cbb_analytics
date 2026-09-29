"""Does a roster-based (player impact) preseason prior beat the last-seasons-ratings-only prior? Walk-forward by season."""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from pipeline.warehouse.paths import PARAMS, table_path

from .impact import ImpactModel, load_ps, team_targets, within_season_r2

FIRST_TRAIN = 2010
ALPHAS = [1.0, 3.0, 10.0, 30.0, 100.0, 300.0]
KS = [0, 150, 400, 1600]
WINDOWS = [None, 4]  # training-row window in seasons (None = expanding)


def roster_features(S, model, k, cache, d1_teams, rosters_S=None):
    """Team-level features for season S from S-1 player impacts and the season-S roster (who is on the team)."""
    prev = cache[S - 1]
    imp = model.impacts(prev, k).set_index("athlete_id")
    cur = rosters_S if rosters_S is not None else cache[S][["team_id", "athlete_id"]]
    m = cur.merge(imp[["team_id", "min_share", "imp_o", "imp_d"]].rename(columns={"team_id": "prev_team"}), left_on="athlete_id", right_index=True, how="left")
    m["ret"] = m.prev_team == m.team_id
    m["inn"] = m.prev_team.notna() & ~m.ret
    rows = {}
    for flag, tag in (("ret", "ret"), ("inn", "in")):
        d = m[m[flag]]
        g = d.assign(co=d.min_share * d.imp_o, cd=d.min_share * d.imp_d, sh=d.min_share / 5).groupby("team_id")[["co", "cd", "sh"]].sum()
        g.columns = [f"{tag}_o", f"{tag}_d", f"{tag}_share"]
        rows[tag] = g
    F = pd.concat(rows.values(), axis=1).reindex(list(d1_teams)).fillna(0.0)
    return F


def lag_frame(T, tg):
    """Final adj ratings of season T, T-1, T-2 by team."""
    def g(y):
        t = tg[tg.season == y].set_index("team_id")
        return t[["adj_off", "adj_def"]]
    cur, l1, l2 = g(T), g(T - 1), g(T - 2)
    df = cur.join(l1, rsuffix="_1", how="left").join(l2, rsuffix="_2", how="left")
    df.columns = ["o", "d", "o1", "d1", "o2", "d2"]
    return df


def build_rows(S, model, k, cache, tg, d1s):
    df = lag_frame(S, tg)
    df = df[df.o1.notna()].copy()
    df["o2"] = df.o2.fillna(df.o1)
    df["d2"] = df.d2.fillna(df.d1)
    F = roster_features(S, model, k, cache, df.index)
    df = df.join(F)
    df["S"] = S
    return df


def fit_predict(train, test, cols_o, cols_d):
    out = {}
    for tgt, cols in (("o", cols_o), ("d", cols_d)):
        Xtr = np.c_[np.ones(len(train)), train[cols].values]
        b = np.linalg.lstsq(Xtr, train[tgt].values, rcond=None)[0]
        pred = np.c_[np.ones(len(test)), test[cols].values] @ b
        out[tgt] = float(np.sqrt(((pred - test[tgt].values) ** 2).mean()))
        out[tgt + "_coef"] = b.tolist()
    return out


def main():
    seasons = list(range(FIRST_TRAIN - 1, 2027))
    cache = {y: load_ps(y) for y in range(2010, 2027) if table_path("player_seasons", y).exists()}
    tg = team_targets()
    d1s = {y: set(pd.read_parquet(table_path("team_seasons", y)).query("is_d1").team_id) for y in cache}
    tests = list(range(2013, 2027))
    base_o, base_d = ["o1", "o2"], ["d1", "d2"]
    full_o = base_o + ["ret_o", "in_o", "ret_share", "in_share"]
    full_d = base_d + ["ret_d", "in_d", "ret_share", "in_share"]
    results, chosen = [], {}
    # inner tuning of alpha by leave-one-season-out within-season fit on training seasons
    for S in tests:
        tr_seasons = [y for y in cache if y < S]
        best_a, best_e = None, 1e9
        for a in ALPHAS:
            errs = []
            for hold in tr_seasons[-6:]:  # last 6 training seasons held out in turn
                m = ImpactModel(a).fit([y for y in tr_seasons if y != hold], tg, cache)
                r2 = within_season_r2(m, cache, tg, [hold])
                errs.append(1 - (r2["o"] + r2["d"]) / 2)
            if np.mean(errs) < best_e:
                best_a, best_e = a, float(np.mean(errs))
        model = ImpactModel(best_a).fit(tr_seasons, tg, cache)
        r2_in = within_season_r2(model, cache, tg, tr_seasons)
        for k, win in [(k, w) for k in KS for w in WINDOWS]:
            rows_from = [T for T in tr_seasons if T - 1 in cache and T >= 2012]
            if win:
                rows_from = rows_from[-win:]
            train = pd.concat([build_rows(T, model, k, cache, tg, d1s) for T in rows_from])
            test = build_rows(S, model, k, cache, tg, d1s)
            b = fit_predict(train, test, base_o, base_d)
            f = fit_predict(train, test, full_o, full_d)
            results.append({"S": S, "k": k, "win": win or 0, "alpha": best_a, "base_o": b["o"], "base_d": b["d"], "full_o": f["o"], "full_d": f["d"], "n": len(test), "r2_in_o": r2_in["o"], "r2_in_d": r2_in["d"]})
        print(S, best_a, flush=True)
    R = pd.DataFrame(results)
    R.to_csv(PARAMS / "players_prior_eval.csv", index=False)
    # walk-forward choice of k: for S, pooled improvement on seasons < S (from 2015)
    sel = []
    for S in tests:
        past = R[(R.S < S)]
        if past.empty:
            kk, ww = 400, 0
        else:
            kk, ww = past.groupby(["k", "win"]).apply(lambda x: (x.full_o ** 2 + x.full_d ** 2).mean(), include_groups=False).idxmin()
        r = R[(R.S == S) & (R.k == kk) & (R.win == ww)].iloc[0]
        sel.append({"S": S, "k": kk, "win": ww, "base_o": r.base_o, "full_o": r.full_o, "base_d": r.base_d, "full_d": r.full_d, "alpha": r.alpha})
    sel = pd.DataFrame(sel)
    summ = {"seasons": tests, "rmse_o_base": float(np.sqrt((sel.base_o ** 2).mean())), "rmse_o_full": float(np.sqrt((sel.full_o ** 2).mean())),
            "rmse_d_base": float(np.sqrt((sel.base_d ** 2).mean())), "rmse_d_full": float(np.sqrt((sel.full_d ** 2).mean())),
            "seasons_o_improved": int((sel.full_o < sel.base_o).sum()), "seasons_d_improved": int((sel.full_d < sel.base_d).sum()),
            "chosen_k_by_season": dict(zip(sel.S.astype(str), sel.k)), "chosen_window_by_season": dict(zip(sel.S.astype(str), sel.win)), "alpha_by_season": dict(zip(sel.S.astype(str), sel.alpha)),
            "pooled_by_k_win": {f"k={a},win={b}": {"o": float(np.sqrt((x.full_o ** 2).mean())), "d": float(np.sqrt((x.full_d ** 2).mean()))} for (a, b), x in R.groupby(["k", "win"])}}
    summ["adopt"] = bool(summ["rmse_o_full"] < summ["rmse_o_base"] and summ["rmse_d_full"] < summ["rmse_d_base"]
                         and summ["seasons_o_improved"] >= 9 and summ["seasons_d_improved"] >= 9)
    (PARAMS / "players_prior_eval.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps({k: v for k, v in summ.items() if k not in ("alpha_by_season",)}, indent=1))


if __name__ == "__main__":
    main()
