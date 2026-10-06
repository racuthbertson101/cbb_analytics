"""Lineup stints from play-by-play substitutions (IMPROVEMENT_PLAN Phase 5a.1). Local only.

    python -m pipeline.pbp.stints 2026 [2025]

A stint is a stretch of game time with the same ten players. Starting lineups come from the box score (starter flag); each
batch of substitutions at one clock time closes the current stint. Per stint and side: points (score deltas) and
possessions estimated from the stint's own events (FGA - ORB + TOV + c*FTA). Stints where either side does not have exactly
five players are marked invalid (missing or extra substitution events) and are excluded from RAPM.

COVERAGE: substitution events exist in the hoopR/ESPN play-by-play only from 2024-25 on (26% of 2024-25 games, every
2025-26 game; none before). See DECISIONS.md / KNOWN_ISSUES.md.
Output: data/pbp/stints_<season>.parquet and coverage printed.
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from pipeline.warehouse.paths import PARAMS, ROOT, table_path

from .parse import OT, clock_seconds, elapsed

OUT = ROOT / "data" / "pbp"
COLS = ["game_id", "sequence_number", "period_number", "clock_display_value", "type_text", "text", "team_id", "athlete_id_1",
        "home_score", "away_score", "home_team_id", "away_team_id"]
FGA = {"JumpShot", "LayUpShot", "DunkShot", "TipShot", "Shot"}
GOOD_TIME = 0.90  # DEFINITION: a game counts as covered when valid 5-v-5 stints span at least 90% of its game time


def load_events(y: int) -> pd.DataFrame:
    d = pd.read_parquet(ROOT / "data" / "raw" / "sdv" / "pbp" / f"play_by_play_{y}.parquet", columns=COLS)
    d = d.dropna(subset=["period_number"]).copy()
    d["rem"] = clock_seconds(d.clock_display_value).groupby(d.game_id).ffill().fillna(0).clip(lower=0)
    quarters = ((d.period_number >= 3) & (d.rem > OT)).groupby(d.game_id).transform("any")
    d["t"] = elapsed(d.period_number, d.rem, quarters)
    d["kind"] = np.select(
        [d.type_text.eq("Substitution") & d.text.str.contains("subbing in", na=False), d.type_text.eq("Substitution"),
         d.type_text.isin(FGA), d.type_text.eq("MadeFreeThrow"), d.type_text.str.contains("Turnover", na=False), d.type_text.eq("Offensive Rebound")],
        ["in", "out", "fga", "fta", "tov", "orb"], "other")
    for c in ("game_id", "team_id", "athlete_id_1", "home_team_id", "away_team_id"):
        d[c] = pd.to_numeric(d[c], errors="coerce").map(lambda x: str(int(x)) if x == x else "")  # "" = missing
    return d.sort_values(["game_id", "t", "sequence_number"], kind="stable")


def game_stints(ev: pd.DataFrame, starters: dict[str, set], home: str, away: str, fta_coef: float) -> list[dict]:
    on = {home: set(starters.get(home, ())), away: set(starters.get(away, ()))}
    out, start, s0 = [], 0, (0, 0)
    acc = {home: dict(fga=0, fta=0, tov=0, orb=0), away: dict(fga=0, fta=0, tov=0, orb=0)}
    last = (0, 0)

    def close(t_end, score):
        nonlocal start, s0
        if t_end > start:
            ph = acc[home]["fga"] - acc[home]["orb"] + acc[home]["tov"] + fta_coef * acc[home]["fta"]
            pa = acc[away]["fga"] - acc[away]["orb"] + acc[away]["tov"] + fta_coef * acc[away]["fta"]
            out.append({"start": start, "end": t_end, "home5": tuple(sorted(on[home])), "away5": tuple(sorted(on[away])),
                        "valid": len(on[home]) == 5 and len(on[away]) == 5,
                        "home_pts": score[0] - s0[0], "away_pts": score[1] - s0[1], "home_poss": ph, "away_poss": pa})
        start, s0 = t_end, score
        for k in acc:
            acc[k] = dict(fga=0, fta=0, tov=0, orb=0)

    rows = ev[["t", "kind", "team_id", "athlete_id_1", "home_score", "away_score"]].itertuples(index=False)
    pending_t = None
    for t, kind, team, ath, hs, as_ in rows:
        score = (int(hs), int(as_)) if hs == hs and as_ == as_ else last
        if kind in ("in", "out"):
            if pending_t != t:  # first substitution of a batch at this clock time: close the stint before it
                close(t, last)
                pending_t = t
            if team in on and ath:
                (on[team].add if kind == "in" else on[team].discard)(ath)
            continue
        pending_t = None
        if team in acc and kind in acc[team]:
            acc[team][kind] += 1
        last = score
    close(int(ev.t.max()) if len(ev) else 0, last)
    return out


def season_stints(y: int) -> tuple[pd.DataFrame, dict]:
    fta = json.loads((PARAMS / "possessions.json").read_text())["fta_coef"]
    ev = load_events(y)
    pg = pd.read_parquet(table_path("player_games", y))
    st = pg[pg.starter].groupby(["game_id", "team_id"]).athlete_id.apply(set)
    g = pd.read_parquet(table_path("games", y)).set_index("game_id")
    rows = []
    for gid, e in ev.groupby("game_id", sort=False):
        if gid not in g.index or not e.kind.isin(["in", "out"]).any():
            continue
        h, a = g.loc[gid, "home_id"], g.loc[gid, "away_id"]
        starters = {tid: st.get((gid, tid), set()) for tid in (h, a)}
        for s in game_stints(e, starters, h, a, fta):
            rows.append({"game_id": gid, "home_id": h, "away_id": a, "neutral": bool(g.loc[gid, "neutral_site"]), **s})
    S = pd.DataFrame(rows)
    S["secs"] = S.end - S.start
    tot = S.groupby("game_id").secs.sum()
    ok = S[S.valid].groupby("game_id").secs.sum().reindex(tot.index).fillna(0) / tot
    covered = set(ok[ok >= GOOD_TIME].index)
    S["game_covered"] = S.game_id.isin(covered)
    # possessions check vs the box estimate (both teams averaged), covered games only
    tg = pd.read_parquet(table_path("team_games", y))
    box = (tg.fga - tg.orb + tg.tov + fta * tg.fta).groupby(tg.game_id).mean()
    sp = S[S.game_covered].groupby("game_id")[["home_poss", "away_poss"]].sum().mean(axis=1)
    rel = (sp / box.reindex(sp.index) - 1).abs()
    d1 = g[g.completed & g.both_d1 & (g.game_type != "exhibition")].index
    rep = {"season": y, "d1_games": int(len(d1)), "games_with_subs": int(S.game_id.nunique()),
           "games_covered": int(len(covered & set(d1))), "covered_share_of_d1": round(len(covered & set(d1)) / max(len(d1), 1), 4),
           "valid_time_share": round(float(S[S.valid].secs.sum() / S.secs.sum()), 4),
           "poss_within_3pct": round(float((rel <= 0.03).mean()), 4), "poss_median_rel_err": round(float(rel.median()), 4)}
    OUT.mkdir(parents=True, exist_ok=True)
    S.assign(home5=S.home5.map(list), away5=S.away5.map(list)).to_parquet(OUT / f"stints_{y}.parquet", index=False)
    return S, rep


if __name__ == "__main__":
    for y in [int(a) for a in sys.argv[1:]] or [2025, 2026]:
        print(season_stints(y)[1], flush=True)
