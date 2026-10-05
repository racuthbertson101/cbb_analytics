"""In-game win probability (Phase 3b): bounded, anchored at tip, ends at the result, never trained on its own season."""
import json

import numpy as np
import pandas as pd
import pytest

from pipeline.export.gamedetail import flow, runs, series
from pipeline.models import ingame
from pipeline.warehouse.paths import PARAMS

PRM = PARAMS / "ingame.json"
pytestmark = pytest.mark.skipif(not PRM.exists(), reason="in-game model not fit")


def _coef():
    return json.loads(PRM.read_text())["production"]["2026"]


def _game(final_home, final_away, ot=False):
    t = np.array([0, 300, 900, 1500, 2100, 2390, 2400] + ([2650, 2700] if ot else []))
    h = np.array([0, 8, 20, 35, 50, 60, 60] + ([66, final_home] if ot else []))
    a = np.array([0, 6, 22, 33, 52, 60, 60] + ([64, final_away] if ot else []))
    if not ot:
        h[-1], a[-1] = final_home, final_away
    return pd.DataFrame({"elapsed": t, "home": h, "away": a})


@pytest.mark.parametrize("home_won,ot", [(True, False), (False, False), (True, True)])
def test_series_bounded_anchored_and_ends_at_result(home_won, ot):
    g = _game(70 if home_won else 58, 62 if home_won else 61, ot)
    if ot:
        g.loc[g.index[-1], ["home", "away"]] = [70, 66]
    s = series(g, _coef(), 0.64, home_won)
    assert np.all((s[:, 3] >= 0) & (s[:, 3] <= 1))
    assert s[0, 0] == 0 and s[0, 3] == pytest.approx(0.64)          # tip-off = calibrated pregame probability
    assert s[-1, 3] == (1.0 if home_won else 0.0)                    # series ends at the result


def test_tip_equals_pregame_for_any_p0():
    c = _coef()
    p0 = np.array([0.05, 0.3, 0.5, 0.8, 0.97])
    wp = ingame.predict(c, np.zeros(5), np.full(5, 2400), np.zeros(5), p0)
    assert np.allclose(wp, p0, atol=1e-9)


def test_leading_late_means_high_wp():
    c = _coef()
    assert ingame.predict(c, [10], [30], [0], [0.5])[0] > 0.97
    assert ingame.predict(c, [-10], [30], [0], [0.5])[0] < 0.03


def test_model_for_season_s_never_trained_on_s():
    p = json.loads(PRM.read_text())
    for s, c in {**p["production"], **p["by_season"]}.items():
        assert max(c["train_seasons"]) < int(s), (s, c["train_seasons"])


def test_runs_and_flow():
    h = np.array([0, 0, 2, 5, 7, 10, 10, 10])
    a = np.array([0, 2, 2, 2, 2, 2, 4, 6])
    t = np.arange(len(h)) * 60
    assert runs(h, a, t) == [[60, 300, "h", 10]]
    f = flow(h - a)
    assert f["lead_changes"] == 1 and f["ties"] == 1 and f["largest"] == {"h": 8, "a": 2}  # 2-2 after 0-2 is a tie
