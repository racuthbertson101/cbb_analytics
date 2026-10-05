"""Profiles (Phase 4a.1): everything as of a date comes from games strictly before it (leakage test)."""
import json

import numpy as np
import pandas as pd
import pytest

from pipeline.export.profiles import build_profiles
from pipeline.warehouse.paths import table_path

pytestmark = pytest.mark.skipif(not table_path("team_games", 2026).exists(), reason="warehouse not built")
ASOF = pd.Timestamp("2026-01-20")


def _tables():
    g = pd.read_parquet(table_path("games", 2026))
    tg = pd.read_parquet(table_path("team_games", 2026))
    preds = pd.DataFrame({"game_id": g.game_id, "pm": 2.0, "poss": 68.0})
    ratings = pd.DataFrame({"team_id": sorted(set(g.home_id)), "adj_off": 105.0, "adj_def": 105.0, "adj_tempo": 68.0})
    ratings["adj_off"] += np.arange(len(ratings)) % 17  # any fixed as-of ratings (input, not derived from games)
    return {"team_games": tg, "games": g, "preds": preds, "ratings": ratings,
            "d1": set(pd.read_parquet(table_path("team_seasons", 2026)).query("is_d1").team_id),
            "players": pd.DataFrame(columns=["team_id", "athlete_id", "min", "name", "mpg", "usg", "ts"])}


def _prob(m, poss):
    return 1 / (1 + np.exp(-m / 7))


def test_games_on_or_after_asof_do_not_change_profiles():
    base = build_profiles(_tables(), ASOF, 0.4856, _prob)
    t = _tables()
    late_g = t["games"].game_date >= ASOF
    t["games"].loc[late_g, ["home_score", "away_score"]] = [0.0, 150.0]     # rewrite every later result
    late_t = t["team_games"].game_date >= ASOF
    t["team_games"].loc[late_t, ["fga", "fgm", "tov", "orb", "points"]] = [200.0, 1.0, 90.0, 0.0, 2.0]
    after = build_profiles(t, ASOF, 0.4856, _prob)
    assert json.dumps(base, sort_keys=True) == json.dumps(after, sort_keys=True)


def test_games_before_asof_do_change_profiles():
    base = build_profiles(_tables(), ASOF, 0.4856, _prob)
    t = _tables()
    early = t["team_games"].game_date < ASOF
    t["team_games"].loc[early, "fgm"] = t["team_games"].loc[early, "fgm"] + 1
    assert json.dumps(base, sort_keys=True) != json.dumps(build_profiles(t, ASOF, 0.4856, _prob), sort_keys=True)
