"""Data contract v1: write JSON shards for the site into web/public/data/ (see docs/DATA_CONTRACT.md)."""
from __future__ import annotations

import json
import math
import sys

import numpy as np
import pandas as pd

from pipeline.models.backtest import BT
from pipeline.models.data import load_games
from pipeline.models.engine import Context
from pipeline.models.production import Predictor, load_prod, ratings_asof
from pipeline.warehouse.paths import ROOT, table_path

OUT = ROOT / "web" / "public" / "data"
CONTRACT_VERSION = 1
FIRST_EXPORT = 2010


def clean(o):
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not math.isfinite(o) else round(float(o), 4)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if o is pd.NaT:
        return None
    return o


def write(rel: str, obj):
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(clean(obj), separators=(",", ":"), allow_nan=False), encoding="utf8")


def r1(a):
    return [None if not np.isfinite(x) else round(float(x), 1) for x in a]


def export_all(asof_default: str | None = None):
    prod = load_prod()
    G = load_games()
    ctx = Context(G=G, last_season=2027)  # 2027 has no completed games; used for the preseason prior
    seasons = [y for y in range(FIRST_EXPORT, 2028) if table_path("games", y).exists()]
    R = pd.read_parquet(BT / "adjeff_ratings.parquet")
    P = pd.read_parquet(BT / "adjeff_preds.parquet")

    # ---------- teams ----------
    ts_all, tm_all = [], []
    for y in seasons:
        ts_all.append(pd.read_parquet(table_path("team_seasons", y)))
        tm_all.append(pd.read_parquet(table_path("teams", y)))
    TS = pd.concat(ts_all)
    TM = pd.concat(tm_all).drop_duplicates("team_id", keep="last").set_index("team_id")
    d1_ids = set(TS[TS.is_d1].team_id)
    conf_by = {y: dict(zip(t.team_id, t.conference)) for y, t in TS.groupby("season")}
    teams = []
    for tid in sorted(d1_ids):
        r = TM.loc[tid]
        teams.append({"id": tid, "name": r.display_name, "short": r.short_name, "abbr": r.abbreviation, "loc": r.location,
                      "color": r.color, "alt": r.alt_color, "logo": r.logo,
                      "conf": {str(y): conf_by[y].get(tid) for y in seasons if conf_by[y].get(tid)}})
    write("teams.json", {"version": CONTRACT_VERSION, "teams": teams})
    names = TM[["display_name", "short_name", "logo", "color"]].to_dict("index")

    # ---------- per season ----------
    cal = Predictor.__new__(Predictor)
    cal.sig, cal.gx, cal.gy = prod["sigma_coef"], np.array(prod["calibration_grid_x"]), np.array(prod["calibration_grid_y"])
    last_dates = {}
    for y in seasons:
        g = pd.read_parquet(table_path("games", y))
        g = g[g.game_type != "exhibition"].copy()
        comp = g[g.completed]
        last_dates[y] = str(comp.game_date.max().date()) if len(comp) else None
        # predictions
        pred = pd.DataFrame(columns=["game_id", "pm", "pp", "p"])
        q10, q90 = prod["margin_residual_quantiles"]["0.1"], prod["margin_residual_quantiles"]["0.9"]
        if y <= 2026:
            p = P[P.season == y].copy()
            p["pm"] = p.pred_a - p.pred_b
            p["pp"] = p.pred_poss
            p["p"] = cal._win_prob(p.pm.values, p.pp.values)
            p["lo"] = cal._win_prob(p.pm.values + q10, p.pp.values)
            p["hi"] = cal._win_prob(p.pm.values + q90, p.pp.values)
            p["ph"], p["pa"] = p.pred_a, p.pred_b
            pred = p[["game_id", "pm", "pp", "p", "lo", "hi", "ph", "pa"]]
        else:
            r = ratings_asof(ctx, 2027, pd.Timestamp("2026-10-01"), prod)
            pr = Predictor(r, prod)
            up = g[~g.completed & g.home_id.isin(r.tix) & g.away_id.isin(r.tix)]
            ia, ib = up.home_id.map(r.tix).values, up.away_id.map(r.tix).values
            site = np.where(up.neutral_site, 0.0, 1.0)
            d = pr.predict_arrays(ia, ib, site)
            pred = pd.DataFrame({"game_id": up.game_id.values, "pm": d.margin.values, "pp": d.poss.values, "p": d.win_prob_a.values,
                                 "ph": d.score_a.values, "pa": d.score_b.values})
            pred["lo"], pred["hi"] = d.win_prob_lo.values, d.win_prob_hi.values
        g = g.merge(pred, on="game_id", how="left")
        rows = []
        for r in g.sort_values(["game_date", "game_id"]).itertuples():
            rows.append({"id": r.game_id, "d": str(r.game_date.date()), "a": r.away_id, "h": r.home_id,
                         "as": r.away_score if r.completed else None, "hs": r.home_score if r.completed else None,
                         "n": bool(r.neutral_site), "t": r.game_type, "cg": bool(r.conference_game),
                         "ok": bool(r.completed), "pm": r.pm, "pp": r.pp, "p": r.p, "plo": r.lo, "phi": r.hi, "ph": r.ph, "pa": r.pa,
                         "ar": None if pd.isna(r.away_rank) or r.away_rank > 25 else int(r.away_rank),
                         "hr": None if pd.isna(r.home_rank) or r.home_rank > 25 else int(r.home_rank),
                         "d1": bool(r.both_d1), "note": r.notes if isinstance(r.notes, str) else None})
        write(f"games/{y}.json", {"season": y, "games": rows})

        # ratings by date
        if y <= 2026:
            Ry = R[R.season == y]
            dates = sorted(Ry.date.unique())
            teams_y = sorted(Ry.team_id.unique())
            ti = {t: i for i, t in enumerate(teams_y)}
            mats = {k: np.full((len(dates), len(teams_y)), np.nan) for k in ("adj_off", "adj_def", "adj_tempo", "n_games")}
            di = {d: i for i, d in enumerate(dates)}
            ii = Ry.date.map(di).values
            jj = Ry.team_id.map(ti).values
            for k in mats:
                mats[k][ii, jj] = Ry[k].values
            write(f"ratings/{y}.json", {"season": y, "dates": [str(pd.Timestamp(d).date()) for d in dates], "teams": teams_y,
                                        "off": [r1(x) for x in mats["adj_off"]], "def": [r1(x) for x in mats["adj_def"]],
                                        "tempo": [r1(x) for x in mats["adj_tempo"]], "gp": [[None if np.isnan(v) else int(v) for v in x] for x in mats["n_games"]]})
            fin = Ry[Ry.date == dates[-1]].set_index("team_id")
            # rankings table (final state) with record, SOS, luck
            d1g = comp[comp.both_d1].copy()
            d1g["pw"] = np.nan
            pp_ = pred.set_index("game_id").p
            d1g["pw"] = d1g.game_id.map(pp_)
            rec = {}
            for r in comp.itertuples():
                for tid, opp, won in ((r.home_id, r.away_id, r.home_score > r.away_score), (r.away_id, r.home_id, r.away_score > r.home_score)):
                    x = rec.setdefault(tid, {"w": 0, "l": 0, "cw": 0, "cl": 0, "opp": [], "exp": 0.0, "pn": 0})
                    x["w" if won else "l"] += 1
                    if r.conference_game and r.game_type in ("regular",):
                        x["cw" if won else "cl"] += 1
            for r in d1g.itertuples():
                if not np.isnan(r.pw):
                    rec[r.home_id]["exp"] += r.pw
                    rec[r.away_id]["exp"] += 1 - r.pw
                    rec[r.home_id]["pn"] += 1
                    rec[r.away_id]["pn"] += 1
                if r.home_id in fin.index and r.away_id in fin.index:
                    rec[r.home_id]["opp"].append((fin.loc[r.away_id, "adj_off"] - fin.loc[r.away_id, "adj_def"]))
                    rec[r.away_id]["opp"].append((fin.loc[r.home_id, "adj_off"] - fin.loc[r.home_id, "adj_def"]))
            tab = []
            for tid in fin.index:
                if tid not in d1_ids or tid not in rec:
                    continue
                x = rec[tid]
                if x["w"] + x["l"] == 0:
                    continue
                tab.append({"id": tid, "conf": conf_by[y].get(tid), "w": x["w"], "l": x["l"], "cw": x["cw"], "cl": x["cl"],
                            "off": fin.loc[tid, "adj_off"], "def": fin.loc[tid, "adj_def"], "tempo": fin.loc[tid, "adj_tempo"],
                            "sos": float(np.mean(x["opp"])) if x["opp"] else None,
                            "luck": (x["w"] - x["exp"] if x["pn"] else None)})
            tab = pd.DataFrame(tab)
            tab["margin"] = tab["off"] - tab["def"]
            write(f"rankings/{y}.json", {"season": y, "asof": str(pd.Timestamp(dates[-1]).date()),
                                          "rows": tab.round(3).to_dict("records")})
            # four factors / team stats
            tg = pd.read_parquet(table_path("team_games", y))
            tg = tg[tg.both_d1 & tg.fga.notna() & tg.opp_fga.notna() & (tg.game_type != "exhibition")]
            c = json.loads((ROOT / 'pipeline' / 'params' / 'possessions.json').read_text())['fta_coef']
            tg = tg.assign(poss=(tg.fga - tg.orb + tg.tov + c * tg.fta + tg.opp_fga - tg.opp_orb + tg.opp_tov + c * tg.opp_fta) / 2)
            agg = tg.groupby("team_id").sum(numeric_only=True)
            st = pd.DataFrame({
                "efg": (agg.fgm + 0.5 * agg.tpm) / agg.fga, "tov": agg.tov / agg.poss, "orb": agg.orb / (agg.orb + agg.opp_drb),
                "ftr": agg.fta / agg.fga, "efg_d": (agg.opp_fgm + 0.5 * agg.opp_tpm) / agg.opp_fga, "tov_d": agg.opp_tov / agg.poss,
                "orb_d": agg.opp_orb / (agg.opp_orb + agg.drb), "ftr_d": agg.opp_fta / agg.opp_fga,
                "three_rate": agg.tpa / agg.fga, "ft_pct": agg.ftm / agg.fta, "two_pct": (agg.fgm - agg.tpm) / (agg.fga - agg.tpa),
                "three_pct": agg.tpm / agg.tpa, "poss_pg": agg.poss / tg.groupby("team_id").size()})
            write(f"teamstats/{y}.json", {"season": y, "rows": {k: {c_: v for c_, v in row.items()} for k, row in st.round(4).to_dict("index").items()}})
        else:
            r = ratings_asof(ctx, 2027, pd.Timestamp("2026-10-01"), prod)
            t = r.table()
            write("ratings/2027_preseason.json", {"season": 2027, "teams": t.team_id.tolist(), "off": r1(t.adj_off), "def": r1(t.adj_def),
                                                  "tempo": r1(t.adj_tempo)})

    cur = max(y for y in seasons if y <= 2026)
    write("meta.json", {"version": CONTRACT_VERSION, "sport": "mbb", "current_season": cur, "upcoming_season": 2027,
                        "seasons": [y for y in seasons if y <= 2026], "last_game_date": last_dates[cur],
                        "default_asof": last_dates[cur], "current_last_date": str(pd.read_parquet(table_path("games", cur)).game_date.max().date()), "season_first_date": str(pd.read_parquet(table_path("games", cur)).game_date.min().date()), "generated": pd.Timestamp.now("UTC").isoformat()})
    write("tournament.json", {"status": "coming_soon", "brackets": []})
    # methodology inputs
    for name in ("adjeff.json", "backtest.json", "possessions.json", "players.json", "players_prior_eval.json"):
        src = ROOT / "pipeline" / "params" / name
        if src.exists():
            d = json.loads(src.read_text())
            if name == "players.json":
                d.pop("model", None) if False else None
            if name == "adjeff.json":
                for k in ("calibration_grid_x", "calibration_grid_y", "season_cfgs", "prior_coefs_by_season"):
                    d.pop(k, None)
            write(f"params/{name}", d)
    md = ROOT / "pipeline" / "params" / "BACKTEST.md"
    if md.exists():
        write("params/backtest_md.json", {"md": md.read_text(encoding="utf8")})
    print("exported", len(seasons), "seasons")


if __name__ == "__main__":
    export_all()
