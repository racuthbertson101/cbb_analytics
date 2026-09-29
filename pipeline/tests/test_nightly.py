from datetime import date

from pipeline.nightly import in_full_window, season_of


def test_season_of():
    assert season_of(date(2026, 9, 28)) == 2027 and season_of(date(2027, 3, 1)) == 2027 and season_of(date(2026, 4, 6)) == 2026


def test_full_run_window_november_to_mid_april():
    assert in_full_window(date(2026, 11, 1)) and in_full_window(date(2027, 1, 15)) and in_full_window(date(2027, 4, 15))
    assert not in_full_window(date(2027, 4, 16)) and not in_full_window(date(2026, 10, 31)) and not in_full_window(date(2026, 7, 4))
