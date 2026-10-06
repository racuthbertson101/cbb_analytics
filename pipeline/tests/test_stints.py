"""Stints (Phase 5a.1): five players per side, stint time adds up to the game length."""
import pandas as pd
import pytest

from pipeline.pbp.stints import OUT, game_stints


def _ev(rows):
    return pd.DataFrame(rows, columns=["t", "kind", "team_id", "athlete_id_1", "home_score", "away_score"])


def test_substitution_batch_closes_stint_and_counts():
    H, A = "1", "2"
    starters = {H: {"h1", "h2", "h3", "h4", "h5"}, A: {"a1", "a2", "a3", "a4", "a5"}}
    ev = _ev([
        (10, "fga", H, "h1", 2, 0), (30, "fga", A, "a1", 2, 3), (40, "tov", H, "h2", 2, 3),
        (600, "out", H, "h1", 2, 3), (600, "in", H, "h6", 2, 3),            # one substitution batch at 600 s
        (700, "fga", H, "h6", 4, 3), (2400, "other", "", "", 4, 3),
    ])
    s = game_stints(ev, starters, H, A, 0.4856)
    assert len(s) == 2 and all(x["valid"] for x in s)
    assert s[0]["end"] == 600 and s[1]["start"] == 600 and s[1]["end"] == 2400
    assert "h6" in s[1]["home5"] and "h1" not in s[1]["home5"]
    assert (s[0]["home_pts"], s[0]["away_pts"], s[1]["home_pts"]) == (2, 3, 2)
    assert s[0]["home_poss"] == 2 and s[0]["away_poss"] == 1           # FGA + TOV for home, one FGA for away


def test_missing_substitution_marks_stint_invalid():
    H, A = "1", "2"
    starters = {H: {"h1", "h2", "h3", "h4", "h5"}, A: {"a1", "a2", "a3", "a4", "a5"}}
    ev = _ev([(100, "in", H, "h6", 0, 0), (2400, "other", "", "", 0, 0)])  # an "in" without its "out": six players
    s = game_stints(ev, starters, H, A, 0.4856)
    assert s[-1]["valid"] is False


@pytest.mark.skipif(not (OUT / "stints_2026.parquet").exists(), reason="stints not built")
def test_real_stints_five_a_side_and_game_length():
    S = pd.read_parquet(OUT / "stints_2026.parquet")
    v = S[S.valid]
    assert v.home5.map(len).eq(5).all() and v.away5.map(len).eq(5).all()
    c = S[S.game_covered]
    secs = c.groupby("game_id").secs.sum()
    length = c.groupby("game_id").end.max()
    expected = 2400 + ((length - 2400).clip(lower=0) / 300).round() * 300   # regulation plus whole overtimes
    assert ((secs - expected).abs() / expected <= 0.01).mean() >= 0.99
