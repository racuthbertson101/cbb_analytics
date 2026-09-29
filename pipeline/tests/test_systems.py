import numpy as np
import pandas as pd
import pytest

from pipeline.models import elo_mle
from pipeline.models.resume import poisson_binom_ge, quad_of
from pipeline.warehouse.paths import table_path


def test_poisson_binomial():
    assert abs(poisson_binom_ge(np.array([0.5, 0.5]), 1) - 0.75) < 1e-12
    assert abs(poisson_binom_ge(np.array([0.9] * 3), 0) - 1.0) < 1e-12
    assert abs(poisson_binom_ge(np.array([1.0, 1.0]), 2) - 1.0) < 1e-12


def test_quadrants():
    assert quad_of(10, +1) == 1 and quad_of(31, +1) == 2 and quad_of(31, -1) == 1 and quad_of(300, 0) == 4
    assert quad_of(75, -1) == 1 and quad_of(76, -1) == 2 and quad_of(240, -1) == 3 and quad_of(241, -1) == 4


def _toy():
    rng = np.random.default_rng(0)
    n = 400
    return pd.DataFrame({"season": 2015, "date": pd.date_range("2015-01-01", periods=n, freq="D"), "a": rng.integers(0, 20, n).astype(str),
                         "b": (rng.integers(0, 20, n) + 20).astype(str), "site": 1.0, "margin": rng.normal(3, 10, n)})


def test_elo_pregame_expectation_ignores_own_and_future_results():
    G = _toy()
    e1, _ = elo_mle.run(G, 0.07, 3.3, 0.9, 30)
    G2 = G.copy()
    G2.loc[200:, "margin"] = -G2.loc[200:, "margin"] * 5  # change results from game 200 on
    e2, _ = elo_mle.run(G2, 0.07, 3.3, 0.9, 30)
    assert np.allclose(e1[:201], e2[:201])  # expectation for game i uses games < i only (game 200's own result cannot affect e[200])
    assert not np.allclose(e1[201:], e2[201:])
