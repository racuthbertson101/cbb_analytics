"""Team profiles for the Compare page (IMPROVEMENT_PLAN Phase 4a.1): profiles/<season>.json.

One object per D-I team: record, four factors both ways with percentiles, shooting (3PA rate, 3P/2P/FT%, rim/mid/three mix when
shot locations exist), ball security and fouls, every rating system with ranks, résumé, last-10 form vs expectation,
consistency and upset profile, and plain rotation facts (no impact, depth or star-dependence scores until Phase 5).

build_profiles() is a pure function of the season's tables and an as-of date: every stat uses games strictly before `asof`
(tested). The export uses the day after the last game.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from pipeline.models.production import Predictor, load_prod
from pipeline.warehouse.paths import PARAMS, table_path

from .contract import OUT, write

V = 1
MIN_GAMES = 5        # DEFINITION: percentiles rank D-I teams with at least this many D-I games
UPSET_FAV = 0.70     # DEFINITION: an upset loss = losing with a pregame win probability of at least 70%
TOP = 50             # DEFINITION: "top 50" = final adjusted-efficiency rank


def _num(x, d=3):
    return None if x is None or not np.isfinite(x) else round(float(x), d)


def pct_rank(v: pd.Series, higher_good: bool, ref: pd.Series) -> pd.Series:
    r = np.sort(ref.dropna().values)
    p = np.searchsorted(r, v.values, side="right" if higher_good else "left") / max(len(r), 1)
    out = p if higher_good else 1 - p
    return pd.Series(np.where(v.isna(), np.nan, out), index=v.index)


def inches(h) -> float | None:
    try:
        f, i = str(h).replace('"', "").split("' ")
        return int(f) * 12 + int(i)
    except Exception:
        return None


def build_profiles(t: dict, asof: pd.Timestamp, fta_coef: float, win_prob) -> dict:
    """t: team_games, games, preds (game_id, pm, poss), ratings (team_id, adj_off, adj_def, adj_tempo), d1 (set), players,
    players_prev, rosters (optional), systems (optional dict), shot_mix (optional DataFrame). Uses games before `asof` only."""
    tg = t["team_games"]
    tg = tg[(tg.game_date < asof) & tg.both_d1 & tg.fga.notna() & (tg.game_type != "exhibition")].copy()
    g = t["games"]
    g = g[(g.game_date < asof) & g.completed & (g.game_type != "exhibition")].copy()
    tg["poss"] = tg.fga - tg.orb + tg.tov + fta_coef * tg.fta
    tg["opp_poss"] = tg.opp_fga - tg.opp_orb + tg.opp_tov + fta_coef * tg.opp_fta
    s = tg.groupby("team_id").agg(n=("game_id", "size"), **{c: (c, "sum") for c in [
        "poss", "opp_poss", "points", "opp_points", "fgm", "fga", "tpm", "tpa", "ftm", "fta", "orb", "drb", "tov", "stl", "pf",
        "opp_fgm", "opp_fga", "opp_tpm", "opp_tpa", "opp_fta", "opp_orb", "opp_drb", "opp_tov", "opp_stl"]})
    f = pd.DataFrame(index=s.index)
    f["efg"], f["efg_d"] = (s.fgm + 0.5 * s.tpm) / s.fga, (s.opp_fgm + 0.5 * s.opp_tpm) / s.opp_fga
    f["tov"], f["tov_d"] = s.tov / s.poss, s.opp_tov / s.opp_poss
    f["orb"], f["orb_d"] = s.orb / (s.orb + s.opp_drb), s.opp_orb / (s.opp_orb + s.drb)
    f["ftr"], f["ftr_d"] = s.fta / s.fga, s.opp_fta / s.opp_fga
    f["tpar"], f["tpar_d"] = s.tpa / s.fga, s.opp_tpa / s.opp_fga
    f["tp_pct"], f["two_pct"], f["ft_pct"] = s.tpm / s.tpa, (s.fgm - s.tpm) / (s.fga - s.tpa), s.ftm / s.fta
    f["stl"], f["pf"] = s.stl / s.opp_poss, s.pf / s.n
    f["pace"] = s.poss / s.n
    good = {"efg": True, "efg_d": False, "tov": False, "tov_d": True, "orb": True, "orb_d": False, "ftr": True, "ftr_d": False,
            "tpar": True, "tpar_d": False, "tp_pct": True, "two_pct": True, "ft_pct": True, "stl": True, "pf": False, "pace": True}
    ref = f[s.n >= MIN_GAMES]
    pc = pd.DataFrame({k: pct_rank(f[k], hg, ref[k]) for k, hg in good.items()})

    # records, résumé pieces, form, consistency
    R = t["ratings"].set_index("team_id")
    em = (R.adj_off - R.adj_def).sort_values(ascending=False)
    rank = pd.Series(np.arange(1, len(em) + 1), index=em.index)
    pr = t["preds"].set_index("game_id")
    g["pm"], g["poss_p"] = g.game_id.map(pr.pm), g.game_id.map(pr.poss)
    g["p"] = np.where(g.pm.notna(), win_prob(g.pm.fillna(0).values, g.poss_p.fillna(68).values), np.nan)
    rows = []
    for side, opp, sgn in (("home", "away", 1), ("away", "home", -1)):
        x = g[[f"{side}_id", f"{opp}_id", "game_id", "game_date", "home_score", "away_score", "pm", "p", "neutral_site", "conference_game", "game_type"]].copy()
        x.columns = ["team_id", "opp", "game_id", "game_date", "hs", "as_", "pm", "p", "neutral", "cg", "t"]
        x["margin"] = sgn * (x.hs - x.as_)
        x["pm"] = sgn * x.pm
        x["p"] = x.p if sgn == 1 else 1 - x.p
        x["site"] = np.where(x.neutral, "N", "H" if sgn == 1 else "A")
        rows.append(x)
    L = pd.concat(rows).sort_values(["team_id", "game_date", "game_id"])
    L["won"] = L.margin > 0
    L["d1opp"] = L.opp.isin(t["d1"])
    resid = (L.margin - L.pm).where(L.d1opp)
    rsd = resid.groupby(L.team_id).std()
    rsd_pc = pct_rank(rsd, False, rsd[rsd.index.isin(ref.index)])  # higher percentile = more consistent

    sysd = t.get("systems")
    sys_vals = {}
    if sysd:
        # a snapshot dated D is fit on games before D (site convention), so snapshots dated up to asof are pre-asof information
        before = [k for k, d in enumerate(sysd["dates"]) if pd.Timestamp(d) <= asof]
        sysd = sysd if before else None
    if sysd:
        i = before[-1]  # latest weekly snapshot at or before asof
        for k in ("adj", "cons", "elo", "bt", "pd", "mrank", "wab", "sor", "sos", "ncsos"):
            if k in sysd and sysd[k] is not None:
                vals = pd.Series(sysd[k][i], index=sysd["teams"], dtype=float)
                hi = k not in ("mrank", "sor")  # mean rank and SOR (chance a top-25 team matches) are better when lower
                rk = vals.rank(ascending=not hi, method="min")
                sys_vals[k] = (vals, rk)
        q = {k: pd.Series(sysd[k][i], index=sysd["teams"]) for k in ("q1w", "q1l", "q2w", "q2l", "q3w", "q3l", "q4w", "q4l") if k in sysd}
    players, prev, ro = t["players"], t.get("players_prev"), t.get("rosters")
    v2 = t.get("impacts_v2")
    v2net = v2.drop_duplicates(["team_id", "athlete_id"]).set_index(["team_id", "athlete_id"]).net if v2 is not None else None
    mix = t.get("shot_mix")
    out = {}
    for tid in sorted(t["d1"]):
        if tid not in f.index:
            continue
        lt = L[L.team_id == tid]
        d1g = lt[lt.d1opp]
        top = d1g[d1g.opp.map(rank) <= TOP]
        wins, losses = d1g[d1g.won], d1g[~d1g.won]
        best = wins.loc[wins.opp.map(em).idxmax()] if len(wins) and wins.opp.map(em).notna().any() else None
        worst = losses.loc[losses.opp.map(em).idxmin()] if len(losses) and losses.opp.map(em).notna().any() else None
        fav, dog = lt[lt.p >= UPSET_FAV], lt[lt.p <= 1 - UPSET_FAV]
        last = lt.tail(10)
        pl = players[players.team_id == tid].sort_values("min", ascending=False)
        rot = []
        rr = ro.set_index("athlete_id") if ro is not None and len(ro) else None
        for r in pl.head(9).itertuples():
            ri = rr.loc[r.athlete_id] if rr is not None and r.athlete_id in rr.index else None
            if isinstance(ri, pd.DataFrame):
                ri = ri.iloc[0]
            imp = None if v2net is None else v2net.get((tid, r.athlete_id))
            rot.append([r.athlete_id, r.name, None if ri is None else ri.experience_display_value, None if ri is None else ri.height,
                        _num(r.mpg, 1), _num(r.usg, 1), _num(r.ts, 3), _num(imp, 1)])
        tot_min = pl["min"].sum()
        # personnel (Phase 5c.3; context only per the pre-registered player test). DEFINITIONS: bench = players ranked 6th or
        # lower by minutes; usage = FGA + 0.44 FTA + TOV; star dependence = max over players of usage share x minutes share
        ms = pl["min"] / max(tot_min, 1e-9) * 5
        use = pl.fga + 0.44 * pl.fta + pl.tov
        us = use / max(use.sum(), 1e-9)
        bench = pl.iloc[5:]
        bnet = None
        if v2net is not None and len(bench):
            bv = pd.Series([v2net.get((tid, a)) for a in bench.athlete_id], index=bench.index, dtype=float)
            bw = ms.loc[bench.index]
            bnet = _num((bv * bw).sum() / bw[bv.notna()].sum(), 2) if bv.notna().any() else None
        personnel = {"bench_min_share": _num(ms.iloc[5:].sum() / 5, 3), "bench_impact": bnet,
                     "star_dependence": _num(float((us * ms / 5).max()), 3) if tot_min > 0 else None,
                     "usage_hhi": _num(float((us ** 2).sum()), 3) if tot_min > 0 else None}
        ret = None
        if prev is not None and tot_min > 0:
            back = set(prev[prev.team_id == tid].athlete_id)
            ret = _num(pl[pl.athlete_id.isin(back)]["min"].sum() / tot_min, 3)
        ht = ex = None
        if rr is not None and tot_min > 0:
            w = pl.set_index("athlete_id")["min"]
            hts = pd.Series({a: inches(rr.loc[a].height if not isinstance(rr.loc[a], pd.DataFrame) else rr.loc[a].iloc[0].height) for a in w.index if a in rr.index})
            exs = pd.Series({a: pd.to_numeric(rr.loc[a].experience_years if not isinstance(rr.loc[a], pd.DataFrame) else rr.loc[a].iloc[0].experience_years, errors="coerce") for a in w.index if a in rr.index})
            if hts.notna().sum():
                ht = _num((hts * w.reindex(hts.index)).sum() / w.reindex(hts.dropna().index).sum(), 1)
            if exs.notna().sum():
                ex = _num((exs * w.reindex(exs.index)).sum() / w.reindex(exs.dropna().index).sum(), 2)
        out[tid] = {
            "rec": [int(lt.won.sum()), int((~lt.won).sum()), int((lt.won & lt.cg & (lt.t == "regular")).sum()), int((~lt.won & lt.cg & (lt.t == "regular")).sum())],
            "n": int(s.loc[tid, "n"]),
            "ff": {k: [_num(f.loc[tid, k], 4), _num(pc.loc[tid, k], 3)] for k in good},
            "mix": None if mix is None or tid not in mix.index else {k: _num(mix.loc[tid, k], 3) for k in mix.columns},
            "sys": {k: [_num(v.get(tid), 4 if k == "sor" else 2), None if pd.isna(r.get(tid)) else int(r.get(tid))] for k, (v, r) in sys_vals.items()},
            "res": {"q": [int(q[k].get(tid, 0)) for k in ("q1w", "q1l", "q2w", "q2l", "q3w", "q3l", "q4w", "q4l")] if sysd else None,
                    "top50": [int(top.won.sum()), int((~top.won).sum())],
                    "best": None if best is None else [best.game_id, best.opp, int(best.margin)],
                    "worst": None if worst is None else [worst.game_id, worst.opp, int(worst.margin)]},
            "form": [[r.game_id, str(r.game_date.date()), r.opp, r.site, int(r.margin), _num(r.pm, 1)] for r in last.itertuples()],
            "cons": {"resid_sd": _num(rsd.get(tid), 2), "resid_sd_pc": _num(rsd_pc.get(tid), 3),
                     "upset_losses": [int((~fav.won).sum()), _num((1 - fav.p).sum(), 1), int(len(fav))],
                     "upset_wins": [int(dog.won.sum()), _num(dog.p.sum(), 1), int(len(dog))]},
            "rot": {"cols": ["id", "name", "cls", "ht", "mpg", "usg", "ts", "imp"], "players": rot, "ht_in": ht, "exp_years": ex, "returning_min_share": ret,
                    **personnel},
        }
    return out


def shot_mix(y: int, games: pd.DataFrame) -> pd.DataFrame | None:
    """rim / mid / three shares of attempts for each team and allowed by it, from the exported shot shards (when they exist)."""
    d = OUT / "shots" / str(y)
    if not (d / "league.json").exists():
        return None
    BIN, X0, Y0 = 3, -25, -6

    def zone(b):
        lat, dep = X0 + (b[0] + 0.5) * BIN, Y0 + (b[1] + 0.5) * BIN
        r = np.hypot(lat, dep)
        return "three" if r >= 22.2 else "rim" if r <= 6 else "mid"

    own, allowed = {}, {}
    gm = games.set_index("game_id")[["home_id", "away_id"]]
    for p in d.glob("*.json"):
        if p.stem == "league":
            continue
        sh = json.loads(p.read_text())
        acc = own.setdefault(p.stem, {"rim": 0, "mid": 0, "three": 0})
        for b in sh["bins"]:
            acc[zone(b)] += b[2]
        for gid, bins in (sh.get("games") or {}).items():
            if gid in gm.index:
                opp = gm.loc[gid].away_id if gm.loc[gid].home_id == p.stem else gm.loc[gid].home_id
                a2 = allowed.setdefault(opp, {"rim": 0, "mid": 0, "three": 0})
                for b in bins:
                    a2[zone(b)] += b[2]
    rows = {}
    for tid, a in own.items():
        tot, al = sum(a.values()), allowed.get(tid)
        at = sum(al.values()) if al else 0
        rows[tid] = {**{k: a[k] / tot for k in a}, **({f"{k}_d": al[k] / at for k in al} if at else {})}
    return pd.DataFrame(rows).T


def export_profiles(seasons=None):
    from pipeline.models.backtest import BT
    from pipeline.warehouse.paths import CURRENT_SEASON

    prod = load_prod()
    cal = Predictor.__new__(Predictor)
    cal.sig, cal.gx, cal.gy = prod["sigma_coef"], np.array(prod["calibration_grid_x"]), np.array(prod["calibration_grid_y"])
    fta = json.loads((PARAMS / "possessions.json").read_text())["fta_coef"]
    P = pd.read_parquet(BT / "adjeff_preds.parquet")
    R = pd.read_parquet(BT / "adjeff_ratings.parquet")
    for y in seasons or range(2010, CURRENT_SEASON + 1):
        if not table_path("team_games", y).exists():
            continue
        g = pd.read_parquet(table_path("games", y))
        Py = P[P.season == y]
        preds = pd.DataFrame({"game_id": Py.game_id.astype(str), "pm": Py.pred_a - Py.pred_b, "poss": Py.pred_poss})
        Ry = R[R.season == y]
        ratings = Ry[Ry.date == Ry.date.max()][["team_id", "adj_off", "adj_def", "adj_tempo"]]
        sysp = OUT / "systems" / f"{y}.json"
        t = {"team_games": pd.read_parquet(table_path("team_games", y)), "games": g, "preds": preds, "ratings": ratings,
             "d1": set(pd.read_parquet(table_path("team_seasons", y)).query("is_d1").team_id),
             "players": pd.read_parquet(table_path("player_seasons", y)) if table_path("player_seasons", y).exists() else pd.DataFrame(columns=["team_id", "athlete_id", "min", "name", "mpg", "usg", "ts", "fga", "fta", "tov"]),
             "players_prev": pd.read_parquet(table_path("player_seasons", y - 1)) if table_path("player_seasons", y - 1).exists() else None,
             "rosters": pd.read_parquet(table_path("rosters", y)) if table_path("rosters", y).exists() else None,
             "systems": json.loads(sysp.read_text()) if sysp.exists() else None, "shot_mix": shot_mix(y, g),
             "impacts_v2": pd.read_parquet(table_path("player_impacts_v2", y)) if table_path("player_impacts_v2", y).exists() else None}
        asof = g[g.completed].game_date.max() + pd.Timedelta(days=1)
        prof = build_profiles(t, asof, fta, cal._win_prob)
        write(f"profiles/{y}.json", {"v": V, "season": y, "asof": str(asof.date()), "teams": prof})
        print(f"profiles {y}: {len(prof)} teams", flush=True)


if __name__ == "__main__":
    export_profiles()
