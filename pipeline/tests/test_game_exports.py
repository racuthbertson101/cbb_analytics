"""Game-level exports (Phase 3a): pre-game expectations use only earlier games (leakage test, AUDIT/plan 3a.4)."""
import numpy as np
import pandas as pd

from pipeline.export.games import MIN_PRIOR_MINUTES, expected_lines


def _games():
    d = pd.to_datetime(["2026-11-05", "2026-11-08", "2026-11-12", "2026-11-12", "2026-11-15"])
    return pd.DataFrame({"athlete_id": ["p1", "p1", "p1", "p2", "p1"], "team_id": "t", "game_date": d[[0, 1, 2, 2, 4]],
                         "minutes": [20.0, 20.0, 30.0, 25.0, 10.0], "points": [10.0, 14.0, 9.0, 8.0, 2.0], "trb": [4.0, 2.0, 6.0, 3.0, 1.0]})


def test_expectation_is_prior_rate_times_minutes():
    x = expected_lines(_games())
    assert np.isnan(x.xpts[0])                              # no earlier games
    assert np.isnan(x.xpts[1])                              # 20 earlier minutes < MIN_PRIOR_MINUTES
    assert MIN_PRIOR_MINUTES <= 40
    assert np.isclose(x.xpts[2], 24 / 40 * 30)               # (10 + 14) points in 40 earlier minutes, times 30 played
    assert np.isclose(x.xpts[4], 33 / 70 * 10)


def test_no_leakage_from_the_game_or_later_games():
    base = expected_lines(_games())
    g = _games()
    g.loc[2, ["points", "trb"]] = [99.0, 99.0]               # change the game itself
    g.loc[4, ["points", "minutes"]] = [50.0, 40.0]           # and a later game
    x = expected_lines(g)
    assert np.isclose(x.xpts[2], base.xpts[2]) and np.isclose(x.xreb[2], base.xreb[2])
    assert np.isclose(x.xpts[1], base.xpts[1], equal_nan=True)


def test_same_day_games_do_not_see_each_other():
    g = pd.concat([_games(), pd.DataFrame({"athlete_id": ["p1"], "team_id": "t", "game_date": pd.to_datetime(["2026-11-12"]),
                                           "minutes": [5.0], "points": [40.0], "trb": [0.0]})], ignore_index=True)
    x = expected_lines(g)
    assert np.isclose(x.xpts[2], 24 / 40 * 30)  # the second game that day is not "earlier"
