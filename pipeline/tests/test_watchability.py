import numpy as np
import pandas as pd
import pytest

from pipeline.models import watchability as W
from pipeline.warehouse.paths import PARAMS

pytestmark = pytest.mark.skipif(not (PARAMS / "watchability.json").exists(), reason="distributions not built")


def test_weights_sum_and_score_range():
    cfg = W.load_cfg()
    assert abs(sum(cfg["weights"].values()) - 1) < 1e-9 and abs(sum(cfg["stakes_weights"].values()) - 1) < 1e-9


def test_scores_monotone_in_quality_and_closeness():
    import json
    dist = json.loads((PARAMS / "watchability.json").read_text())["distributions"]
    base = dict(game_id="x", quality=0.0, competitiveness=-6.0, tempo=69.0, star_power=10.0, rank_prox=-5.5, bubble=-130.0, title=np.nan)
    hi = dict(base, game_id="hi", quality=30.0, competitiveness=-1.0)
    lo = dict(base, game_id="lo", quality=-20.0, competitiveness=-25.0)
    s = W.score(pd.DataFrame([hi, lo]), dist).set_index("game_id").score
    assert 1 <= s.lo < s.hi <= 10
