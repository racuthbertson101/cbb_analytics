import pandas as pd
import pytest

from pipeline.warehouse.paths import table_path

pytestmark = pytest.mark.skipif(not table_path("player_seasons", 2026).exists(), reason="player tables not built")


def test_minutes_share_sums_to_five_per_team():
    a = pd.read_parquet(table_path("player_seasons", 2026))
    s = a.groupby("team_id").min_share.sum()
    assert ((s - 5).abs() < 1e-6).all()


def test_rate_ranges_plausible():
    a = pd.read_parquet(table_path("player_seasons", 2026))
    b = a[a["min"] > 600]
    assert 17 < b.usg.mean() < 24
    assert 0.5 < b.ts.mean() < 0.62
    assert b.ast_pct.between(0, 70).all() and b.blk_pct.between(0, 25).all()


def test_athlete_ids_are_clean_strings():
    a = pd.read_parquet(table_path("player_seasons", 2026))
    assert a.athlete_id.str.fullmatch(r"\d+").all()
