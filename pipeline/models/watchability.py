"""Game watchability: five components scaled to 0-100 by historical percentiles, combined with judgment-call weights
(config/watchability.yaml). Uses only pregame information (ratings fit on earlier games, predicted margin, last-season player impact)."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import yaml

from pipeline.warehouse.paths import PARAMS, ROOT, table_path

from .backtest import BT
from .resume import BUBBLE_RANK

CFG = ROOT / "config" / "watchability.yaml"


def load_cfg():
    return yaml.safe_load(CFG.read_text(encoding="utf8"))


def rating_context(season: int, R: pd.DataFrame):
    """dict date -> DataFrame(index team) with margin and rank, from pregame ratings."""
    Ry = R[R.season == season]
    out = {}
    for d, g in Ry.groupby("date"):
        g = g.set_index("team_id")
        m = g.adj_off - g.adj_def
        out[d] = pd.DataFrame({"em": m, "rank": m.rank(ascending=False, method="first")})
    return out


def star_table(season: int) -> dict:
    """Best player impact per team from the previous season for players on the team's current-season roster (pregame proxy)."""
    prev = table_path("player_impacts", season - 1)
    cur = table_path("player_games", season)
    ro = table_path("rosters", season)
    if not prev.exists():
        return {}
    pi = pd.read_parquet(prev)
    pi = pi[pi["min"] >= 300].set_index("athlete_id")
    if ro.exists():
        r = pd.read_parquet(ro)[["team_id", "athlete_id"]]
    elif cur.exists():
        r = pd.read_parquet(cur)[["team_id", "athlete_id"]].drop_duplicates()
    else:
        return {}
    m = r.merge(pi[["imp"]], left_on="athlete_id", right_index=True)
    return m.groupby("team_id").imp.max().to_dict()


def components_for_games(g: pd.DataFrame, ctx: dict, star: dict, title_p: dict | None = None) -> pd.DataFrame:
    """g: DataFrame(game_id, d(date Timestamp), h, a, pm, pp). Returns raw component values."""
    rows = []
    for r in g.itertuples():
        c = ctx.get(r.d)
        if c is None or r.h not in c.index or r.a not in c.index or pd.isna(r.pm):
            rows.append((r.game_id, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan))
            continue
        eh, ea = c.em[r.h], c.em[r.a]
        rh, ra = c["rank"][r.h], c["rank"][r.a]
        quality = (eh + ea) / 2
        comp = -abs(r.pm)
        star_v = max(star.get(r.h, np.nan), star.get(r.a, np.nan)) if star else np.nan
        # ranking proximity: both teams good (mean rank small) and close in rank
        rank_prox = -(np.log((rh + ra) / 2) + 0.5 * abs(np.log(rh) - np.log(ra)))
        bubble = -(abs(rh - BUBBLE_RANK) + abs(ra - BUBBLE_RANK)) / 2
        title = np.nan
        if title_p is not None:
            title = title_p.get((r.h, r.a), np.nan)
        rows.append((r.game_id, quality, comp, r.pp, star_v, rank_prox, bubble, title))
    return pd.DataFrame(rows, columns=["game_id", "quality", "competitiveness", "tempo", "star_power", "rank_prox", "bubble", "title"])


def build_distributions(seasons=range(2010, 2027)) -> dict:
    """Historical quantile tables (101 points) for every raw component."""
    R = pd.read_parquet(BT / "adjeff_ratings.parquet")
    P = pd.read_parquet(BT / "adjeff_preds.parquet")
    allc = []
    for y in seasons:
        g = P[P.season == y]
        g = pd.DataFrame({"game_id": g.game_id, "d": g.date, "h": g.a, "a": g.b, "pm": g.pred_a - g.pred_b, "pp": g.pred_poss})
        allc.append(components_for_games(g, rating_context(y, R), star_table(y)))
    A = pd.concat(allc)
    qs = np.linspace(0, 1, 101)
    dist = {c: A[c].dropna().quantile(qs).round(4).tolist() for c in ("quality", "competitiveness", "tempo", "star_power", "rank_prox", "bubble")}
    (PARAMS / "watchability.json").write_text(json.dumps({"distributions": dist, "n_games": int(len(A)), "seasons": [min(seasons), max(seasons)],
                                                          "note": "component values are converted to 0-100 by percentile in these historical distributions"}, indent=1))
    return dist


def pctl(v, table):
    if v is None or pd.isna(v):
        return np.nan
    return float(np.interp(v, table, np.linspace(0, 100, len(table))))


def score(raw: pd.DataFrame, dist: dict, cfg: dict | None = None) -> pd.DataFrame:
    cfg = cfg or load_cfg()
    w, sw = cfg["weights"], cfg["stakes_weights"]
    out = raw[["game_id"]].copy()
    for c in ("quality", "competitiveness", "tempo", "star_power", "rank_prox", "bubble"):
        out[c] = [pctl(v, dist[c]) for v in raw[c]]
    out["title"] = raw.title.clip(0, 1) * 100 if "title" in raw else np.nan  # title contender share already on 0-1 scale
    # stakes = weighted average of available sub-components
    st = pd.DataFrame({"rank_proximity": out.rank_prox, "title_leverage": out.title, "bubble_proximity": out.bubble})
    sww = pd.Series(sw)
    ok = st.notna()
    stakes = (st.fillna(0) * sww).sum(axis=1) / (ok * sww).sum(axis=1).replace(0, np.nan)
    out["stakes"] = stakes
    comp = out[["quality", "competitiveness", "tempo", "star_power", "stakes"]]
    ww = pd.Series(w)
    okc = comp.notna()
    total = (comp.fillna(0) * ww).sum(axis=1) / (okc * ww).sum(axis=1).replace(0, np.nan)
    out["score"] = 1 + 9 * total / 100
    return out
