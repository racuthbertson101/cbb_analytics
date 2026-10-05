"""Incremental ESPN ingest (public JSON endpoints, as used by hoopR): scoreboard per date + game summary (box score).

Polite: identifying UA, <=4 concurrent requests, small sleep, retries with backoff, everything cached on disk.
Idempotent: game rows are keyed by game_id; re-ingesting a date replaces that game's rows and changes nothing else.
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from pipeline.warehouse.build import BOX, TEAM_STAT_RENAME, classify_game_type, force_neutral
from pipeline.warehouse.paths import ROOT, table_path

BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"
RAW = ROOT / "data" / "raw" / "espn"
UA = {"User-Agent": "Mozilla/5.0"}  # plain browser-style UA; ESPN 403s both unusual agents and a full Chrome string sent by python-requests
MAX_WORKERS = 4
RECHECK_DAYS = 3  # re-fetch the last N days each run to pick up stat corrections


def _get(url: str, params: dict, cache: Path, force: bool = False):
    if cache.exists() and not force:
        return json.loads(cache.read_text(encoding="utf8"))
    for attempt in range(5):
        try:
            time.sleep(0.15)
            r = requests.get(url, params=params, headers=UA, timeout=40)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            d = r.json()
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(d), encoding="utf8")
            return d
        except Exception:
            time.sleep(2 ** attempt)
    raise RuntimeError(f"ESPN request failed after retries: {url} {params}")


def scoreboard(day: date, force=False):
    return _get(f"{BASE}/scoreboard", {"dates": day.strftime("%Y%m%d"), "groups": "50", "limit": "400"}, RAW / "scoreboard" / f"{day:%Y%m%d}.json", force)


def summary(event_id: str, force=False):
    return _get(f"{BASE}/summary", {"event": event_id}, RAW / "summary" / f"{event_id}.json", force)


def _et_date(iso: str) -> pd.Timestamp:
    return pd.Timestamp(iso).tz_convert("America/New_York").tz_localize(None).normalize()


def parse_scoreboard(d: dict) -> pd.DataFrame:
    rows = []
    for e in (d or {}).get("events", []):
        c = e["competitions"][0]
        comp = {x["homeAway"]: x for x in c["competitors"]}
        if "home" not in comp or "away" not in comp:
            continue
        st = e["status"]["type"]
        done = bool(st.get("completed"))
        notes = c.get("notes") or []
        rank = lambda x: (x.get("curatedRank") or {}).get("current")  # noqa: E731
        rows.append({
            "game_id": str(e["id"]), "season": e.get("season", {}).get("year"), "season_type": e.get("season", {}).get("type"),
            "game_date": _et_date(e["date"]), "game_datetime": pd.Timestamp(e["date"]).tz_convert("UTC").tz_localize(None),
            "home_id": str(comp["home"]["team"]["id"]), "away_id": str(comp["away"]["team"]["id"]),
            "home_score": float(comp["home"]["score"]) if done and comp["home"].get("score") not in (None, "") else np.nan,
            "away_score": float(comp["away"]["score"]) if done and comp["away"].get("score") not in (None, "") else np.nan,
            "completed": done and comp["home"].get("score") not in (None, ""), "status": st.get("description"),
            "neutral_site": bool(c.get("neutralSite")), "conference_game": bool(c.get("conferenceCompetition")),
            "tournament_id": (e.get("tournamentId") or c.get("tournamentId")), "notes_headline": notes[0].get("headline") if notes else None,
            "type_abbreviation": (c.get("type") or {}).get("abbreviation"), "home_rank": rank(comp["home"]), "away_rank": rank(comp["away"]),
            "venue": (c.get("venue") or {}).get("fullName"), "attendance": c.get("attendance"),
            "home_team": comp["home"]["team"], "away_team": comp["away"]["team"],
        })
    return pd.DataFrame(rows)


def _split(v: str):
    a, b = v.split("-")
    return float(a), float(b)


def parse_summary(d: dict, game_id: str, game_row: dict):
    """Returns (team_rows, player_rows) in warehouse column conventions."""
    trows, prows = [], []
    if not d or "boxscore" not in d:
        return trows, prows
    teams = {}
    for t in d["boxscore"].get("teams", []):
        s = {x["name"]: x["displayValue"] for x in t["statistics"]}
        fgm, fga = _split(s["fieldGoalsMade-fieldGoalsAttempted"])
        tpm, tpa = _split(s["threePointFieldGoalsMade-threePointFieldGoalsAttempted"])
        ftm, fta = _split(s["freeThrowsMade-freeThrowsAttempted"])
        f = lambda k: float(s.get(k, "nan") or "nan")  # noqa: E731
        teams[str(t["team"]["id"])] = {
            "fgm": fgm, "fga": fga, "tpm": tpm, "tpa": tpa, "ftm": ftm, "fta": fta, "orb": f("offensiveRebounds"), "drb": f("defensiveRebounds"),
            "trb": f("totalRebounds"), "ast": f("assists"), "stl": f("steals"), "blk": f("blocks"), "tov": f("turnovers"), "pf": f("fouls"),
            "points_in_paint": f("pointsInPaint"), "fast_break_points": f("fastBreakPoints"), "turnover_points": f("turnoverPoints"), "largest_lead": f("largestLead")}
    ids = list(teams)
    if len(ids) != 2:
        return [], []
    scores = {game_row["home_id"]: game_row["home_score"], game_row["away_id"]: game_row["away_score"]}
    for tid in ids:
        opp = ids[1] if tid == ids[0] else ids[0]
        r = {"game_id": game_id, "team_id": tid, "opp_id": opp, "home_away": "home" if tid == game_row["home_id"] else "away",
             "points": scores.get(tid), "opp_points": scores.get(opp), **teams[tid]}
        r.update({"opp_" + k: teams[opp][k] for k in BOX})
        trows.append(r)
    for p in d["boxscore"].get("players", []):
        tid = str(p["team"]["id"])
        for grp in p.get("statistics", []):
            keys = grp["keys"]
            for a in grp.get("athletes", []):
                st = dict(zip(keys, a.get("stats", [])))
                dnp = bool(a.get("didNotPlay")) or not st or st.get("minutes") in (None, "", "--")
                def num(k):  # noqa: E306
                    try:
                        return float(st.get(k))
                    except (TypeError, ValueError):
                        return np.nan
                def pair(k):  # noqa: E306
                    try:
                        return _split(st[k])
                    except Exception:
                        return (np.nan, np.nan)
                fgm, fga = pair("fieldGoalsMade-fieldGoalsAttempted")
                tpm, tpa = pair("threePointFieldGoalsMade-threePointFieldGoalsAttempted")
                ftm, fta = pair("freeThrowsMade-freeThrowsAttempted")
                ath = a["athlete"]
                prows.append({"game_id": game_id, "team_id": tid, "athlete_id": str(ath["id"]), "name": ath.get("displayName"), "minutes": num("minutes"),
                              "points": num("points"), "fgm": fgm, "fga": fga, "tpm": tpm, "tpa": tpa, "ftm": ftm, "fta": fta, "orb": num("offensiveRebounds"),
                              "drb": num("defensiveRebounds"), "trb": num("rebounds"), "ast": num("assists"), "stl": num("steals"), "blk": num("blocks"),
                              "tov": num("turnovers"), "pf": num("fouls"), "starter": bool(a.get("starter")), "did_not_play": dnp,
                              "position": (ath.get("position") or {}).get("abbreviation"), "jersey": ath.get("jersey")})
    return trows, prows


def ingest_days(season: int, days: list[date], force_recent: bool = True, workers: int = MAX_WORKERS, now: date | None = None, cutoff: date | None = None) -> dict:
    """Fetch scoreboards for the given days and summaries for completed games; merge into the warehouse tables for `season`."""
    today = now or date.today()
    boards = []
    with ThreadPoolExecutor(workers) as ex:
        res = list(ex.map(lambda d: scoreboard(d, force=force_recent and (today - d).days <= RECHECK_DAYS and d <= today), days))
    for d in res:
        b = parse_scoreboard(d)
        if len(b):
            boards.append(b)
    if not boards:
        return {"games": 0, "completed": 0}
    B = pd.concat(boards).drop_duplicates("game_id", keep="last")
    B = B[B.season == season].copy()
    if cutoff is not None:  # replay guard: games on/after the cutoff are treated as not yet played
        late = B.game_date >= pd.Timestamp(cutoff)
        B.loc[late, ["completed", "home_score", "away_score"]] = [False, np.nan, np.nan]
    done = B[B.completed]
    with ThreadPoolExecutor(workers) as ex:
        sums = list(ex.map(lambda gid: summary(gid, force=False), done.game_id))
    trows, prows = [], []
    gmap = B.set_index("game_id").to_dict("index")
    for gid, s in zip(done.game_id, sums):
        t, p = parse_summary(s, gid, gmap[gid])
        trows += t
        prows += p
    return merge_into_warehouse(season, B, pd.DataFrame(trows), pd.DataFrame(prows))


def _align(df: pd.DataFrame, template: pd.DataFrame) -> pd.DataFrame:
    """Coerce new rows to the dtypes of the existing table so concatenation and parquet writes stay consistent."""
    out = df[[c for c in template.columns if c in df.columns]].copy()
    for c in out.columns:
        dt = template[c].dtype
        if pd.api.types.is_numeric_dtype(dt) and not pd.api.types.is_bool_dtype(dt):
            out[c] = pd.to_numeric(out[c], errors="coerce").astype(dt) if not pd.api.types.is_integer_dtype(dt) else pd.to_numeric(out[c], errors="coerce")
        elif pd.api.types.is_bool_dtype(dt):
            out[c] = out[c].fillna(False).astype(bool)
    return out


def merge_into_warehouse(season: int, B: pd.DataFrame, T: pd.DataFrame, P: pd.DataFrame) -> dict:
    games = pd.read_parquet(table_path("games", season))
    ts = pd.read_parquet(table_path("team_seasons", season))
    d1 = set(ts.team_id[ts.is_d1])
    conf = dict(zip(ts.team_id, ts.conf_id))
    new = pd.DataFrame({
        "game_id": B.game_id.values, "season": season, "game_date": B.game_date.values, "game_datetime": B.game_datetime.values,
        "home_id": B.home_id.values, "away_id": B.away_id.values, "home_score": B.home_score.values, "away_score": B.away_score.values,
        "completed": B.completed.values, "status": B.status.values, "neutral_site": B.neutral_site.values, "neutral_known": True,
        "conference_game": B.conference_game.values, "season_type": B.season_type.values, "tournament_id": pd.to_numeric(B.tournament_id, errors="coerce").values,
        "notes": B.notes_headline.values, "home_conf_id": B.home_id.map(conf).values, "away_conf_id": B.away_id.map(conf).values,
        "home_rank": B.home_rank.values, "away_rank": B.away_rank.values, "venue": B.venue.values, "attendance": B.attendance.values})
    cls = pd.DataFrame({"notes_headline": B.notes_headline.values, "season_type": B.season_type.values, "type_abbreviation": B.type_abbreviation.values,
                        "home_conference_id": new.home_conf_id.values, "away_conference_id": new.away_conf_id.values, "neutral_site": B.neutral_site.values,
                        "game_date": B.game_date.values, "tournament_id": new.tournament_id.values}, index=new.index)
    new["game_type"] = classify_game_type(cls).values
    new["neutral_site"] = force_neutral(new.game_type, new.notes, new.neutral_site)
    new["home_seed"] = np.nan
    new["away_seed"] = np.nan
    new["has_team_box"] = new.game_id.isin(T.game_id.unique() if len(T) else [])
    new["has_player_box"] = new.game_id.isin(P.game_id.unique() if len(P) else [])
    new["has_pbp"] = False
    new["home_d1"] = new.home_id.isin(d1)
    new["away_d1"] = new.away_id.isin(d1)
    new["both_d1"] = new.home_d1 & new.away_d1
    new = new[games.columns.intersection(new.columns)]
    for c in games.columns:  # align dtypes to the existing table
        if c in new.columns:
            try:
                new[c] = new[c].astype(games[c].dtype)
            except Exception:
                pass
    old_ids = set(games.game_id)
    n_new = int((~new.game_id.isin(old_ids)).sum())
    merged = pd.concat([games[~games.game_id.isin(new.game_id)], new], ignore_index=True).sort_values(["game_date", "game_id"]).reset_index(drop=True)
    merged.to_parquet(table_path("games", season), index=False)
    g = merged.set_index("game_id")
    if len(T):
        tg = pd.read_parquet(table_path("team_games", season))
        T = T.assign(season=season, game_date=T.game_id.map(g.game_date), neutral_site=T.game_id.map(g.neutral_site), game_type=T.game_id.map(g.game_type), both_d1=T.game_id.map(g.both_d1))
        tg = pd.concat([tg[~tg.game_id.isin(T.game_id)], _align(T, tg)], ignore_index=True)
        tg.sort_values(["game_id", "team_id"]).reset_index(drop=True).to_parquet(table_path("team_games", season), index=False)
    if len(P):
        pg = pd.read_parquet(table_path("player_games", season))
        P = P.assign(season=season, game_date=P.game_id.map(g.game_date))
        pg = pd.concat([pg[~pg.game_id.isin(P.game_id)], _align(P, pg)], ignore_index=True)
        pg.sort_values(["game_id", "team_id", "athlete_id"]).reset_index(drop=True).to_parquet(table_path("player_games", season), index=False)
    return {"games": int(len(new)), "new_games": n_new, "completed": int(new.completed.sum()), "team_rows": int(len(T)), "player_rows": int(len(P))}


def last_completed_date(season: int) -> pd.Timestamp | None:
    g = pd.read_parquet(table_path("games", season))
    c = g[g.completed]
    return c.game_date.max() if len(c) else None


def daterange(a: date, b: date):
    return [a + timedelta(days=i) for i in range((b - a).days + 1)]


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--start")
    ap.add_argument("--end")
    a = ap.parse_args()
    days = daterange(date.fromisoformat(a.start), date.fromisoformat(a.end))
    print(ingest_days(a.season, days))
