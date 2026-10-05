"""Conference exports: conferences/<season>.json (stats and rankings) and standings/<season>.json (simulation snapshots)."""
from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from pipeline.models.backtest import BT
from pipeline.sims.conference import CFG_DIR, load_cfg, run_season, slug
from pipeline.warehouse.paths import CURRENT_SEASON, PARAMS, table_path

from .contract import OUT, r1, write

FIRST = 2010


def conference_stats(seasons):
    P = pd.read_parquet(BT / "adjeff_preds.parquet")
    P["pm"] = P.pred_a - P.pred_b
    prod = json.loads((PARAMS / "adjeff.json").read_text())
    from pipeline.models.production import Predictor
    cal = Predictor.__new__(Predictor)
    cal.sig, cal.gx, cal.gy = prod["sigma_coef"], np.array(prod["calibration_grid_x"]), np.array(prod["calibration_grid_y"])
    P["p"] = cal._win_prob(P.pm.values, P.pred_poss.values)
    R = pd.read_parquet(BT / "adjeff_ratings.parquet")
    idx = []
    for y in seasons:
        ts = pd.read_parquet(table_path("team_seasons", y))
        ts = ts[ts.is_d1 & ts.conference.notna()]
        conf = dict(zip(ts.team_id, ts.conference))
        Ry = R[R.season == y]
        fin = Ry[Ry.date == Ry.date.max()].set_index("team_id")
        fin = fin[fin.index.isin(conf)]
        fin = fin.assign(conf=fin.index.map(conf), em=fin.adj_off - fin.adj_def)
        g = pd.read_parquet(table_path("games", y))
        g = g[g.completed & g.both_d1 & ~g.conference_game & (g.game_type == "regular")].copy()
        g["hc"], g["ac"] = g.home_id.map(conf), g.away_id.map(conf)
        g = g[g.hc.notna() & g.ac.notna() & (g.hc != g.ac)].merge(P[P.season == y][["game_id", "p"]], on="game_id", how="left")
        rows = []
        for c, grp in fin.groupby("conf"):
            gh, ga = g[g.hc == c], g[g.ac == c]
            w = int((gh.home_score > gh.away_score).sum() + (ga.away_score > ga.home_score).sum())
            n = len(gh) + len(ga)
            exp = float(gh.p.sum() + (1 - ga.p).sum())
            top = grp.em.sort_values(ascending=False)
            rows.append({"id": slug(c), "name": c, "n": int(len(grp)), "em": grp.em.mean(), "off": grp.adj_off.mean(), "def": grp.adj_def.mean(),
                         "tempo": grp.adj_tempo.mean(), "top_em": top.iloc[0], "median_em": grp.em.median(), "top4_em": top.head(4).mean(),
                         "nc_w": w, "nc_l": n - w, "nc_exp_w": exp, "nc_over": w - exp if n else None, "teams": list(top.index[:3])})
        df = pd.DataFrame(rows)
        df["rank"] = df.em.rank(ascending=False, method="min").astype(int)
        write(f"conferences/{y}.json", {"season": y, "rows": df.round(3).to_dict("records")})
        idx.append(y)
    print("conference stats", idx[0], "-", idx[-1])


def _sim_one(args):
    season, asof, conf, nsim, seed = args
    out = run_season(season, asof, nsim=nsim, seed=seed, only=[conf])
    return conf, out[conf]


def sim_standings(season, asof, nsim=20000, workers=8, keep_only=False):
    ts = pd.read_parquet(table_path("team_seasons", season))
    confs = sorted(ts[ts.is_d1 & ts.conference.notna()].conference.unique())
    with ProcessPoolExecutor(workers) as ex:
        results = list(ex.map(_sim_one, [(season, asof, c, nsim, i) for i, c in enumerate(confs)]))
    snap = {"asof": asof, "nsim": nsim, "conferences": {}}
    for conf, o in results:
        res = o["res"]
        rows = []
        for i, t in enumerate(o["teams"]):
            rows.append({"id": t, "exp_w": res["exp_wins"][i], "cw": res["cur_w"][i], "cg": res["cur_g"][i], "exp_finish": res["exp_finish"][i],
                         "finish": [round(float(x), 4) for x in res["finish"][i]], "p_title": res["p_title"][i], "p_share": res["p_title_share"][i],
                         "p_qual": res["p_qualify"][i], "p_bye": {k: float(v[i]) for k, v in res["p_bye"].items()}, "best": int(res["best"][i]), "worst": int(res["worst"][i])})
        snap["conferences"][slug(conf)] = {"name": conf, "config": o["cfg"], "n_remaining": o["n_remaining"], "rows": rows}
    p = OUT / "standings" / f"{season}.json"
    prev = json.loads(p.read_text()) if p.exists() else {"season": season, "snapshots": []}
    prev["snapshots"] = ([] if keep_only else [s for s in prev["snapshots"] if s["asof"] != asof]) + [snap]
    prev["snapshots"].sort(key=lambda s: s["asof"])
    write(f"standings/{season}.json", prev)
    return snap


def tiebreak_index():
    """One row per conference page: every tiebreaker config, plus every conference name in the data without its own config
    (renamed or defunct leagues such as the Pac-12 or the United Athletic Conference), which use an alias or the fallback rules."""
    import yaml

    keys = ("conference", "status", "rules", "qualifiers", "bye_seed_lines", "source_url", "notes", "researched")
    rows = []
    for p in sorted(CFG_DIR.glob("*.yaml")):
        d = yaml.safe_load(p.read_text(encoding="utf8"))
        rows.append({"id": slug(d["conference"]), **{k: d.get(k) for k in keys}})
    have = {r["id"] for r in rows}
    names = set()
    for y in range(FIRST, CURRENT_SEASON + 2):
        if table_path("team_seasons", y).exists():
            ts = pd.read_parquet(table_path("team_seasons", y), columns=["conference", "is_d1"])
            names |= set(ts.conference[ts.is_d1].dropna())
    for name in sorted(names):
        if slug(name) in have:
            continue
        d = load_cfg(name)
        note = f"Uses the {d['conference']} rules (renamed league)." if d["conference"] != "_fallback" else "No researched rules: generic fallback."
        rows.append({"id": slug(name), **{k: d.get(k) for k in keys}, "conference": name, "status": "fallback", "notes": note})
    write("tiebreakers.json", {"rows": rows})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--sim", nargs="*", default=None, help="season:asof pairs, e.g. 2026:2026-02-15")
    ap.add_argument("--nsim", type=int, default=20000)
    a = ap.parse_args()
    tiebreak_index()
    if a.stats:
        conference_stats(list(range(FIRST, CURRENT_SEASON + 1)))
    for s in a.sim or []:
        y, d = s.split(":")
        sim_standings(int(y), d, a.nsim)
