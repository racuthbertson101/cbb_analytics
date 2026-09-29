"""Leakage tests: a game's prediction may only depend on information strictly before its date."""
import copy

import numpy as np
import pytest

from pipeline.warehouse.paths import table_path

pytestmark = pytest.mark.skipif(not table_path("games", 2019).exists(), reason="warehouse not built")

CFG = dict(lam=3, lam_t=2, halflife=None, halflife_t=60, cap=None)


@pytest.fixture(scope="module")
def ctx():
    from pipeline.models.engine import Context
    return Context(seasons=[2017, 2018, 2019])


def _tamper(sd, from_idx, rng):
    t = copy.deepcopy(sd)
    n = len(t.date) - from_idx
    t.ea = t.ea.copy()
    t.eb = t.eb.copy()
    t.poss = t.poss.copy()
    t.ea[from_idx:] = rng.uniform(60, 150, n)
    t.eb[from_idx:] = rng.uniform(60, 150, n)
    t.poss[from_idx:] = rng.uniform(55, 85, n)
    return t


def test_predictions_ignore_same_day_and_future_results(ctx):
    from pipeline.models.engine import block_predict, build_prior, finals_no_prior, prior_coefs
    fin = finals_no_prior(ctx, CFG)
    coefs = prior_coefs(ctx, fin, 2019)
    prior = build_prior(ctx, fin, 2019, coefs)
    sd = ctx.sd[2019]
    days = np.unique(sd.date)
    D0 = days[len(days) // 2]
    first_D0 = int(np.searchsorted(sd.date, D0, side="left"))  # results of games ON day D0 and later are scrambled
    tam = _tamper(sd, first_D0, np.random.default_rng(0))
    a = block_predict(sd, CFG, prior, 1)
    b = block_predict(tam, CFG, prior, 1)
    m = a.merge(b, on="game_id", suffixes=("_a", "_b"))
    upto = m[m.date_a <= D0]  # includes every game played on D0 itself
    assert len(upto) > 500
    assert np.allclose(upto.pred_a_a, upto.pred_a_b) and np.allclose(upto.pred_b_a, upto.pred_b_b)
    assert np.allclose(upto.pred_poss_a, upto.pred_poss_b)
    later = m[m.date_a > D0]
    assert not np.allclose(later.pred_a_a, later.pred_a_b)  # sanity: the test can detect dependence


def test_preseason_prior_ignores_own_season(ctx):
    """Season-S first-day predictions use only seasons < S: scrambling ALL of season 2019 changes nothing on day 1."""
    from pipeline.models.engine import block_predict, build_prior, finals_no_prior, prior_coefs
    sd19 = ctx.sd[2019]
    fin = finals_no_prior(ctx, CFG)
    prior = build_prior(ctx, fin, 2019, prior_coefs(ctx, fin, 2019))
    ctx2 = copy.copy(ctx)
    ctx2.sd = dict(ctx.sd)
    ctx2.sd[2019] = _tamper(sd19, 0, np.random.default_rng(1))
    fin2 = finals_no_prior(ctx2, CFG)
    prior2 = build_prior(ctx2, fin2, 2019, prior_coefs(ctx2, fin2, 2019))
    for k in prior:
        assert np.allclose(prior[k], prior2[k]), f"prior {k} depends on season-2019 results"
    a = block_predict(sd19, CFG, prior, 1)
    b = block_predict(ctx2.sd[2019], CFG, prior2, 1)
    day1 = a.date.min()
    m = a[a.date == day1].merge(b[b.date == day1], on="game_id")
    assert len(m) > 5 and np.allclose(m.pred_a_x, m.pred_a_y)


def test_fit_uses_only_first_n_games(ctx):
    from pipeline import models  # noqa: F401
    from pipeline.models import adjeff
    sd = ctx.sd[2018]
    n = len(sd.date) // 3
    p = dict(lam=3, lam_t=2)
    r1 = adjeff.fit(sd, n, int(sd.date[n]), p)
    r2 = adjeff.fit(_tamper(sd, n, np.random.default_rng(2)), n, int(sd.date[n]), p)
    assert np.allclose(r1.o, r2.o) and np.allclose(r1.d, r2.d) and np.allclose(r1.t, r2.t)
