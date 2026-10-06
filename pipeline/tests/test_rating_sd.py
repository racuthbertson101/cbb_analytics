"""Rating uncertainty (Phase 5c.1): the posterior band shrinks as games are played (synthetic season)."""
import numpy as np
import pandas as pd

from pipeline.models import adjeff


def _season(n_teams=20, n_games=600, seed=1):
    rng = np.random.default_rng(seed)
    true = rng.normal(0, 8, n_teams)
    ia = rng.integers(0, n_teams, n_games)
    ib = (ia + rng.integers(1, n_teams, n_games)) % n_teams
    date = np.sort(rng.integers(0, 120, n_games))
    site = np.ones(n_games)
    ea = 100 + true[ia] / 2 + 1.5 + rng.normal(0, 12, n_games)
    eb = 100 - true[ib] / 2 - 1.5 + rng.normal(0, 12, n_games)
    teams = np.array([str(i) for i in range(n_teams)])
    g = pd.DataFrame({"game_id": [str(i) for i in range(n_games)]})
    return adjeff.SeasonData(2030, teams, {t: i for i, t in enumerate(teams)}, date, ia, ib, site, ea, eb,
                             np.full(n_games, 68.0), (ea - eb) * 0.68, g.game_id.values, g)


def test_band_shrinks_with_games_played():
    sd = _season()
    p = {"lam": 3.0, "lam_t": 3.0, "with_sd": True, "sigma2_eff": 150.0}
    widths = [float(np.mean(adjeff.fit(sd, n, int(sd.date[max(n - 1, 0)]) + 1, p).em_sd)) for n in (0, 30, 120, 600)]
    assert all(a > b for a, b in zip(widths, widths[1:])), widths
    assert widths[0] > 2 * widths[-1]


def test_no_sd_unless_asked():
    sd = _season()
    assert adjeff.fit(sd, 100, 60, {"lam": 3.0, "lam_t": 3.0}).em_sd is None
