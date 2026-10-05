import pandas as pd

from pipeline.predictions import log


def _rows(ids, p=0.6):
    return pd.DataFrame({"game_id": ids, "game_date": "2027-01-05", "home_id": "1", "away_id": "2", "neutral": False, "pm": 3.0, "ph": 70.0,
                         "pa": 67.0, "p": p, "model_version": "t"})


def test_append_only_and_tamper_detection(tmp_path):
    path = tmp_path / "log.parquet"
    assert log.append(_rows(["a", "b"]), "2027-01-04T07:30Z", path) == 2
    assert log.append(_rows(["b", "c"], p=0.9), "2027-01-05T07:30Z", path) == 1  # 'b' already logged: never overwritten
    df = pd.read_parquet(path)
    assert list(df.game_id) == ["a", "b", "c"] and df.loc[df.game_id == "b", "p"].iloc[0] == 0.6
    assert log.verify(path)
    df.loc[0, "p"] = 0.99  # tamper with history
    df.to_parquet(path, index=False)
    assert not log.verify(path)


def test_no_win_probability_band_in_log_schema():
    """AUDIT M-1: outcome quantiles pushed through the CDF are not an interval on the probability; it must not be logged."""
    from pipeline.predictions.log import FIELDS

    assert not {"plo", "phi", "win_prob_lo", "win_prob_hi"} & set(FIELDS)
