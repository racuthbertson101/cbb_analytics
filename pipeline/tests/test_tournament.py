import numpy as np

from pipeline.tournament import PlayIn, simulate_bracket, standard_bracket


class SeedPredictor:
    """Fake predictor: strength = 100 - seed, deterministic outcomes when `sure`."""
    def __init__(self, strength, sure=True):
        self.s, self.sure = strength, sure

    def predict(self, a, b, site=0.0, date=None):
        d = self.s[a] - self.s[b]
        p = float(d > 0) if self.sure else 0.5
        return {"win_prob_a": p}


def _bracket(play_in=False):
    regions = {r: [f"{r}{s}" for s in range(1, 17)] for r in "ABCD"}
    pis = []
    if play_in:
        regions["A"][15] = ""  # 16-seed slot decided by a play-in
        pis = [PlayIn(0, 16, ("A16a", "A16b"))]
    return standard_bracket(regions, pis)


def test_chalk_bracket_always_produces_the_top_seed_champion():
    b = _bracket()
    strength = {t: 100 - int(t[1:]) + (0.01 if t[0] == "A" else 0) for t in b.teams()}
    r = simulate_bracket(b, SeedPredictor(strength), n_sims=50)
    assert r.loc["A1", "Champion"] == 1.0 and abs(r.Champion.sum() - 1.0) < 1e-9
    assert r.loc["B1", "Elite 8"] == 1.0 and r.loc["A16", "R32"] == 0.0


def test_coin_flip_bracket_spreads_title_probability_and_supports_play_in():
    b = _bracket(play_in=True)
    strength = {t: 0 for t in b.teams()}
    r = simulate_bracket(b, SeedPredictor(strength, sure=False), n_sims=4000, seed=1)
    assert abs(r.Champion.sum() - 1.0) < 1e-9
    assert abs(r.loc["A16a", "Field"] - 0.5) < 0.05  # play-in participants each make the field about half the time
    assert r.loc["B3", "Champion"] > 0.0
    assert np.isclose(r.loc["B1", "Field"], 1.0)
