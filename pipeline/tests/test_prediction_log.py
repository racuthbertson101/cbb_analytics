import json
import shutil

import pandas as pd

from pipeline.predictions import log


def _rows(ids, p=0.6):
    return pd.DataFrame({"game_id": ids, "game_date": "2027-01-05", "home_id": "1", "away_id": "2", "neutral": False, "pm": 3.0, "ph": 70.0,
                         "pa": 67.0, "p": p, "model_version": "t"})


def test_every_night_logged_and_chain_verifies(tmp_path):
    assert log.append(_rows(["a", "b"]), "2027-01-03T07:30:00+00:00", tmp_path) == 2
    assert log.append(_rows(["a", "b", "c"], p=0.7), "2027-01-04T07:30:00+00:00", tmp_path) == 3  # a new night re-logs every game
    assert log.append(_rows(["a"], p=0.9), "2027-01-04T09:00:00+00:00", tmp_path) == 0  # same-day re-run: skipped
    df = log.read(tmp_path)
    assert len(df) == 5 and log.verify(tmp_path)
    assert (tmp_path / "log" / "2027" / "01-03.csv").exists() and (tmp_path / "log" / "2027" / "01-04.csv").exists()
    assert json.loads((tmp_path / "HEAD.json").read_text())["rows"] == 5


def test_tampered_row_fails(tmp_path):
    log.append(_rows(["a", "b"]), "2027-01-03T07:30:00+00:00", tmp_path)
    f = tmp_path / "log" / "2027" / "01-03.csv"
    f.write_text(f.read_text().replace("0.6,", "0.99,", 1))
    assert not log.verify(tmp_path) and "edited" in log.check(tmp_path)[0]


def test_missing_or_shortened_log_fails(tmp_path):
    log.append(_rows(["a"]), "2027-01-03T07:30:00+00:00", tmp_path)
    log.append(_rows(["b"]), "2027-01-04T07:30:00+00:00", tmp_path)
    (tmp_path / "log" / "2027" / "01-04.csv").unlink()  # a lost night
    assert not log.verify(tmp_path) and "shorter" not in log.check(tmp_path)[0] and "deleted" in log.check(tmp_path)[0]
    shutil.rmtree(tmp_path / "log")  # the whole log gone, HEAD still committed
    assert not log.verify(tmp_path)


def test_rows_without_head_fail(tmp_path):
    log.append(_rows(["a"]), "2027-01-03T07:30:00+00:00", tmp_path)
    (tmp_path / "HEAD.json").unlink()
    assert not log.verify(tmp_path)


def test_append_refuses_broken_log(tmp_path):
    log.append(_rows(["a"]), "2027-01-03T07:30:00+00:00", tmp_path)
    (tmp_path / "HEAD.json").write_text(json.dumps({"rows": 9, "last_hash": "x"}))
    try:
        log.append(_rows(["b"]), "2027-01-04T07:30:00+00:00", tmp_path)
        raise AssertionError("append should refuse")
    except RuntimeError:
        pass


def test_scores_last_prediction_before_tipoff(tmp_path):
    log.append(_rows(["a", "b"], p=0.6), "2027-01-03T07:30:00+00:00", tmp_path)
    log.append(_rows(["a", "b"], p=0.7), "2027-01-04T07:30:00+00:00", tmp_path)
    log.append(_rows(["a", "b"], p=0.8), "2027-01-05T07:30:00+00:00", tmp_path)
    games = pd.DataFrame({"game_id": ["a", "b"], "game_date": pd.to_datetime(["2027-01-05", "2027-01-05"]),
                          "game_datetime": pd.to_datetime(["2027-01-06T00:00", "2027-01-05T06:00"])})  # b tipped before the 3rd run
    s = log.scored(log.read(tmp_path), games).set_index("game_id")
    assert s.loc["a", "p"] == 0.8 and s.loc["a", "days_before"] == 0
    assert s.loc["b", "p"] == 0.7 and s.loc["b", "days_before"] == 1


def test_no_win_probability_band_in_log_schema():
    """AUDIT M-1: outcome quantiles pushed through the CDF are not an interval on the probability; it must not be logged."""
    assert not {"plo", "phi", "win_prob_lo", "win_prob_hi"} & set(log.FIELDS)


def test_schema_bump_keeps_old_hashes(tmp_path):
    """Phase 5c.2: rows logged before p_est_lo/p_est_hi existed still verify after new rows carry them."""
    log.append(_rows(["a", "b"]), "2027-01-03T07:30:00+00:00", tmp_path)          # schema 2 rows
    old_head = json.loads((tmp_path / "HEAD.json").read_text())["last_hash"]
    new = _rows(["a", "b"]).assign(p_est_lo=[0.51, 0.55], p_est_hi=[0.68, 0.71])
    log.append(new, "2027-01-04T07:30:00+00:00", tmp_path)                         # schema 3 rows
    assert log.verify(tmp_path)
    df = log.read(tmp_path)
    assert df.p_est_lo.isna().sum() == 2 and df.p_est_lo.notna().sum() == 2
    first = log.read(tmp_path).iloc[:2]
    assert first.row_hash.iloc[-1] == old_head                                      # old rows' hashes unchanged
    f = tmp_path / "log" / "2027" / "01-04.csv"
    f.write_text(f.read_text().replace("0.55,", "0.95,", 1))                        # tampering with a new field is caught
    assert not log.verify(tmp_path)
