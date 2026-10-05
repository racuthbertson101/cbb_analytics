"""Warehouse validation tests (run after `python -m pipeline.warehouse.build`)."""
import pandas as pd
import pytest

from pipeline.warehouse.paths import FIRST_SEASON, WH, table_path

SEASONS = [y for y in range(FIRST_SEASON, 2027) if table_path("games", y).exists()]
ALL_SEASONS = [y for y in range(FIRST_SEASON, 2031) if table_path("team_seasons", y).exists()]  # incl. the upcoming season
pytestmark = pytest.mark.skipif(not SEASONS, reason="warehouse not built")


def load(table, y):
    return pd.read_parquet(table_path(table, y))


@pytest.mark.parametrize("y", SEASONS)
def test_no_duplicate_games(y):
    g = load("games", y)
    assert g.game_id.is_unique
    tg = load("team_games", y)
    assert not tg.duplicated(["game_id", "team_id"]).any()


@pytest.mark.parametrize("y", SEASONS)
def test_both_teams_present(y):
    g = load("games", y)
    tg = load("team_games", y)
    d1 = g[g.completed & g.both_d1]
    n = tg.groupby("game_id").size()
    has_both = d1.game_id.map(n).fillna(0).eq(2)
    assert has_both.mean() >= 0.98, f"{y}: only {has_both.mean():.3f} D-I games have both team boxes"
    assert (n <= 2).all()


@pytest.mark.parametrize("y", SEASONS)
def test_team_points_match_player_points(y):
    tg = load("team_games", y)
    pg = load("player_games", y)
    s = pg.groupby(["game_id", "team_id"]).points.sum().rename("pp").reset_index()
    m = tg.merge(s, on=["game_id", "team_id"])
    ok = (m.points - m.pp).abs() <= 2
    assert ok.mean() >= 0.97, f"{y}: {ok.mean():.3f} within tolerance"


@pytest.mark.parametrize("y", SEASONS)
def test_possessions_plausible(y):
    tg = load("team_games", y)
    d = tg[tg.both_d1 & tg.fga.notna()]
    poss = d.fga - d.orb + d.tov + 0.475 * d.fta
    assert 55 < poss.mean() < 80
    assert (poss.between(35, 120)).mean() > 0.99


@pytest.mark.parametrize("y", ALL_SEASONS)
def test_d1_team_count(y):
    ts = load("team_seasons", y)
    assert 335 <= ts.is_d1.sum() <= 370
    if y >= 2026:
        assert 355 <= ts.is_d1.sum() <= 370


@pytest.mark.parametrize("y", ALL_SEASONS)
def test_d1_teams_have_conference(y):
    ts = load("team_seasons", y)
    d1 = ts[ts.is_d1]
    assert d1.conference.notna().all() and d1.conf_id.notna().all()
    if y >= 2026:  # earlier standings split some leagues into divisions ("SEC - West")
        assert 30 <= d1.conference.nunique() <= 33


def test_upcoming_membership_fallback_without_espn(tmp_path, monkeypatch):
    """With no ESPN membership file: last season's D-I set, schedule conferences, then the overrides file."""
    from pipeline.warehouse import build

    if not table_path("team_seasons", 2026).exists() or not table_path("games", 2027).exists():
        pytest.skip("warehouse not built")
    monkeypatch.setattr(build, "ESPN_RAW", tmp_path)
    g = load("games", 2027)
    sc = pd.concat([pd.DataFrame({"team_id": g.home_id, "c": g.home_conf_id}), pd.DataFrame({"team_id": g.away_id, "c": g.away_conf_id})])
    sched = sc.dropna().groupby("team_id").c.agg(lambda x: x.mode().iloc[0])
    m = build.upcoming_membership(2027, None, sched).set_index("team_id")
    assert 355 <= len(m) <= 370 and m.conference.notna().all()
    assert "2697" in m.index and "2598" not in m.index  # West Florida in, Saint Francis (PA) out
    assert m.loc["2250", "conference"] == "Pac-12 Conference"  # Gonzaga's move, read from the 2027 schedule


@pytest.mark.parametrize("y", SEASONS)
def test_dates_sane(y):
    g = load("games", y)
    lo, hi = pd.Timestamp(y - 1, 10, 25), pd.Timestamp(y, 4, 20)
    assert g.game_date.between(lo, hi).mean() > 0.995, f"{y} dates out of window"


@pytest.mark.parametrize("y", SEASONS)
def test_scores_and_flags(y):
    g = load("games", y)
    c = g[g.completed]
    assert (c.home_score >= 0).all() and (c.away_score >= 0).all()
    assert (c.home_score != c.away_score).all()  # no ties in basketball
    assert g.game_type.isin(["regular", "conf_tourney", "ncaa", "nit", "other_post", "exhibition"]).all()
    assert g.neutral_site.dtype == bool


def test_ncaa_tournament_size():
    # Source gaps: 2009 (58), 2010 (55), 2013 (55) have missing NCAA games in ESPN data; see KNOWN_ISSUES.md
    for y in SEASONS:
        if y in (2020,):
            continue
        g = load("games", y)
        n = int((g.game_type == "ncaa").sum())
        assert 50 <= n <= 70, f"{y}: {n} NCAA tournament games"


def test_team_ids_stable_across_seasons():
    a, b = load("team_seasons", 2025), load("team_seasons", 2026)
    common = set(a[a.is_d1].team_id) & set(b[b.is_d1].team_id)
    assert len(common) > 320
