"""Build the warehouse tables from cached raw sportsdataverse files.

Idempotent: output depends only on raw inputs.
Tables: games, team_games, player_games, teams, team_seasons, rosters.
"""
from __future__ import annotations

import re
import sys

import numpy as np
import pandas as pd

from .paths import FIRST_SEASON, RAW, table_path

D1_MIN_GAMES = 10  # DEFINITION: fallback D-I test when standings are missing for a season

CONF_HEADLINE = re.compile(r"tournament|championship", re.I)
MTE_HEADLINE = re.compile(r"classic|challenge|invitational|showcase|tip-off|shootout|festival|series|battle", re.I)

TEAM_STAT_RENAME = {
    "team_score": "points", "opponent_team_score": "opp_points",
    "field_goals_made": "fgm", "field_goals_attempted": "fga",
    "three_point_field_goals_made": "tpm", "three_point_field_goals_attempted": "tpa",
    "free_throws_made": "ftm", "free_throws_attempted": "fta",
    "offensive_rebounds": "orb", "defensive_rebounds": "drb", "total_rebounds": "trb",
    "assists": "ast", "steals": "stl", "blocks": "blk", "turnovers": "tov", "fouls": "pf",
}
BOX = ["fgm", "fga", "tpm", "tpa", "ftm", "fta", "orb", "drb", "trb", "ast", "stl", "blk", "tov", "pf"]


def _idstr(s: pd.Series) -> pd.Series:
    """Integer-valued IDs as clean strings (raw files sometimes store them as floats)."""
    return pd.to_numeric(s, errors="coerce").astype("Int64").astype(str)


def _rd(kind, fname):
    p = RAW / kind / fname
    return pd.read_parquet(p) if p.exists() else None


def classify_game_type(s: pd.DataFrame) -> pd.Series:
    """DEFINITION (heuristic): game type from ESPN season_type, type abbreviation and event headline.

    Conference tournament games with no headline on a non-neutral site cannot be detected and stay 'regular'.
    """
    h = s.notes_headline.fillna("")
    date = pd.to_datetime(s.game_date)
    out = pd.Series("regular", index=s.index)
    same_conf = (s.home_conference_id == s.away_conference_id) & s.home_conference_id.notna()
    reg = s.season_type == 2
    ct = reg & same_conf & date.dt.month.isin([2, 3]) & (
        (h.str.contains(CONF_HEADLINE) & ~h.str.contains(MTE_HEADLINE))
        | (s.neutral_site.fillna(False).astype(bool) & (date.dt.month == 3)))
    out[ct] = "conf_tourney"
    p = s.season_type == 3
    out[p] = "other_post"
    out[p & h.str.contains(r"\bNIT\b", case=False)] = "nit"
    out[p & h.str.contains(r"championship|region|final four|first four", case=False)
        & ~h.str.contains(r"NIT|CBI|CIT|Crown", case=False)] = "ncaa"
    out[p & h.str.contains(r"Crown|CBI|CIT", case=False)] = "other_post"
    out[s.type_abbreviation.eq("EXH")] = "exhibition"
    return out


def build_season(y: int, d1_prev: set | None = None):
    s = _rd("schedules", f"mbb_schedule_{y}.parquet")
    s = s.drop_duplicates("game_id", keep="last").copy()
    for c in ["home_conference_id", "away_conference_id", "neutral_site", "tournament_id", "notes_headline",
              "type_abbreviation", "conference_competition", "home_current_rank", "away_current_rank",
              "team_box", "player_box", "PBP", "venue_full_name", "attendance"]:
        if c not in s:
            s[c] = np.nan
    s["game_id"] = s.game_id.astype(str)
    completed = s.status_type_completed.fillna(False).astype(bool) & s.home_score.notna() & s.away_score.notna()
    games = pd.DataFrame({
        "game_id": s.game_id, "season": y,
        "game_date": pd.to_datetime(s.game_date).astype("datetime64[ns]"),
        "game_datetime": pd.to_datetime(s.game_date_time, utc=True, errors="coerce").dt.tz_localize(None),
        "home_id": s.home_id.astype(str), "away_id": s.away_id.astype(str),
        "home_score": s.home_score, "away_score": s.away_score,
        "completed": completed, "status": s.status_type_description,
        "neutral_site": s.neutral_site.fillna(False).astype(bool),
        "neutral_known": y >= FIRST_SEASON,
        "conference_game": s.conference_competition.fillna(False).astype(bool),
        "season_type": s.season_type, "tournament_id": s.tournament_id,
        "notes": s.notes_headline,
        "home_conf_id": s.home_conference_id, "away_conf_id": s.away_conference_id,
        "home_rank": s.home_current_rank, "away_rank": s.away_current_rank,
        "venue": s.venue_full_name, "attendance": s.attendance,
    })
    games["game_type"] = classify_game_type(s.assign(game_date=games.game_date)).values
    games["home_seed"] = np.nan  # seed fields reserved for the tournament module
    games["away_seed"] = np.nan
    games["has_team_box"] = s.team_box.fillna(False).astype(bool).values
    games["has_player_box"] = s.player_box.fillna(False).astype(bool).values
    games["has_pbp"] = s.PBP.fillna(False).astype(bool).values

    # teams (latest naming, logos, colors)
    teams = []
    for side in ("home", "away"):
        t = s[[f"{side}_id", f"{side}_location", f"{side}_name", f"{side}_abbreviation", f"{side}_display_name",
               f"{side}_short_display_name", f"{side}_color", f"{side}_alternate_color", f"{side}_logo"]].copy()
        t.columns = ["team_id", "location", "name", "abbreviation", "display_name", "short_name", "color", "alt_color", "logo"]
        teams.append(t)
    teams = pd.concat(teams).drop_duplicates("team_id", keep="last")
    teams["team_id"] = teams.team_id.astype(str)
    teams["season"] = y

    # conference by season from standings; D-I set
    st = _rd("standings", f"standings_{y}.parquet")
    conf = None
    if st is not None:
        conf = st[["group_id", "group_name", "team_id"]].drop_duplicates("team_id")
        conf = conf[~conf.group_name.str.contains("Crown", na=False)].copy()
        conf["team_id"] = conf.team_id.astype(str)
    sc = pd.concat([
        pd.DataFrame({"team_id": games.home_id, "conf_id": games.home_conf_id}),
        pd.DataFrame({"team_id": games.away_id, "conf_id": games.away_conf_id})])
    ng = sc.groupby("team_id").size().rename("n_games")
    mode_conf = sc.dropna(subset=["conf_id"]).groupby("team_id").conf_id.agg(lambda x: x.mode().iloc[0]).rename("sched_conf_id")
    ts = pd.concat([ng, mode_conf], axis=1).reset_index().rename(columns={"index": "team_id"})
    ts["season"] = y
    if conf is not None:
        ts = ts.merge(conf.rename(columns={"group_id": "conf_id", "group_name": "conference"}), on="team_id", how="left")
        ts["is_d1"] = ts.conference.notna()
    else:
        ts["conf_id"] = np.nan
        ts["conference"] = None
        ts["is_d1"] = ts.team_id.isin(d1_prev) if d1_prev is not None else ts.n_games >= D1_MIN_GAMES
    ts["conf_id"] = pd.to_numeric(ts.conf_id, errors="coerce").fillna(ts.sched_conf_id)
    d1 = set(ts.team_id[ts.is_d1])
    games["home_d1"] = games.home_id.isin(d1)
    games["away_d1"] = games.away_id.isin(d1)
    games["both_d1"] = games.home_d1 & games.away_d1
    g = games.set_index("game_id")

    # team_games from team box
    tg = pd.DataFrame()
    tb = _rd("team_box", f"team_box_{y}.parquet")
    if tb is not None:
        tb = tb.drop_duplicates(["game_id", "team_id"]).copy()
        for c in ["game_id", "team_id", "opponent_team_id"]:
            tb[c] = tb[c].astype(str)
        for c in list(TEAM_STAT_RENAME) + ["points_in_paint", "fast_break_points", "turnover_points", "largest_lead"]:
            if c not in tb:
                tb[c] = np.nan
        tg = tb[["game_id", "team_id", "opponent_team_id", "team_home_away"] + list(TEAM_STAT_RENAME)
                + ["points_in_paint", "fast_break_points", "turnover_points", "largest_lead"]].rename(
            columns={"opponent_team_id": "opp_id", "team_home_away": "home_away", **TEAM_STAT_RENAME})
        tg["season"] = y
        tg = tg[tg.game_id.isin(g.index[g.completed])].copy()
        tg["game_date"] = tg.game_id.map(g.game_date)
        tg["neutral_site"] = tg.game_id.map(g.neutral_site)
        tg["game_type"] = tg.game_id.map(g.game_type)
        tg["both_d1"] = tg.game_id.map(g.both_d1)
        opp = tg[["game_id", "team_id"] + BOX].rename(columns={"team_id": "opp_id", **{c: "opp_" + c for c in BOX}})
        tg = tg.merge(opp, on=["game_id", "opp_id"], how="left")

    # player_games
    pg = pd.DataFrame()
    pb = _rd("player_box", f"player_box_{y}.parquet")
    if pb is not None:
        pb = pb.dropna(subset=["athlete_id"]).drop_duplicates(["game_id", "team_id", "athlete_id"]).copy()
        for c in ["game_id", "team_id", "athlete_id"]:
            pb[c] = _idstr(pb[c])
        pg = pb[["game_id", "team_id", "athlete_id", "athlete_display_name", "minutes", "points", "field_goals_made",
                 "field_goals_attempted", "three_point_field_goals_made", "three_point_field_goals_attempted",
                 "free_throws_made", "free_throws_attempted", "offensive_rebounds", "defensive_rebounds", "rebounds",
                 "assists", "steals", "blocks", "turnovers", "fouls", "starter", "did_not_play",
                 "athlete_position_abbreviation", "athlete_jersey"]].rename(columns={
            "athlete_display_name": "name", "field_goals_made": "fgm", "field_goals_attempted": "fga",
            "three_point_field_goals_made": "tpm", "three_point_field_goals_attempted": "tpa",
            "free_throws_made": "ftm", "free_throws_attempted": "fta", "offensive_rebounds": "orb",
            "defensive_rebounds": "drb", "rebounds": "trb", "assists": "ast", "steals": "stl", "blocks": "blk",
            "turnovers": "tov", "fouls": "pf", "athlete_position_abbreviation": "position", "athlete_jersey": "jersey"})
        pg["season"] = y
        pg = pg[pg.game_id.isin(g.index[g.completed])].copy()
        pg["game_date"] = pg.game_id.map(g.game_date)
        pg["did_not_play"] = pg.did_not_play.fillna(False).astype(bool)
        pg["starter"] = pg.starter.fillna(False).astype(bool)

    ro = _rd("rosters", f"rosters_{y}.parquet")
    if ro is not None:
        ro = ro.dropna(subset=["athlete_id"]).assign(team_id=_idstr(ro.team_id), athlete_id=_idstr(ro.athlete_id))
        ro = ro[["season", "team_id", "athlete_id", "full_name", "jersey", "position_abbreviation", "height", "weight",
                 "experience_years", "experience_display_value", "date_of_birth", "headshot_href"]
                ].drop_duplicates(["team_id", "athlete_id"])
    tables = dict(games=games, team_games=tg, player_games=pg, teams=teams, team_seasons=ts,
                  rosters=ro if ro is not None else pd.DataFrame())
    return tables, d1


def write(table: str, season: int, df: pd.DataFrame) -> int:
    p = table_path(table, season)
    p.parent.mkdir(parents=True, exist_ok=True)
    if df is None or len(df) == 0:
        return 0
    df = df.sort_values(list(df.columns[:2])).reset_index(drop=True)
    df.to_parquet(p, index=False)
    return len(df)


def build(seasons=None):
    seasons = seasons or range(FIRST_SEASON, 2028)
    d1_prev, counts = None, {}
    for y in seasons:
        if not (RAW / "schedules" / f"mbb_schedule_{y}.parquet").exists():
            continue
        t, d1_prev = build_season(y, d1_prev)
        counts[y] = {k: write(k, y, v) for k, v in t.items()}
        print(y, counts[y], flush=True)
    return counts


if __name__ == "__main__":
    build([int(a) for a in sys.argv[1:]] or None)
