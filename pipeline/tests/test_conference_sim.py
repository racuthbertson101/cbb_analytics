import numpy as np
import pandas as pd

from pipeline.sims.conference import simulate_conference

CFG = {"rules": ["h2h", "vs_standings", "random"], "qualifiers": 2, "bye_seed_lines": [1], "restart_on_partial": True}


def _rem(rows):
    return pd.DataFrame(rows, columns=["hi", "ai", "pm", "tot", "sig"])


def test_finished_season_is_deterministic():
    known = [(0, 1, 5.0), (0, 2, 5.0), (1, 2, 5.0)]
    r = simulate_conference([0, 1, 2], known, _rem([]), np.zeros(3), CFG, nsim=200)
    assert (r["finish"][0] == [1, 0, 0]).all() and (r["finish"][2] == [0, 0, 1]).all()
    assert r["p_title"][0] == 1.0 and r["best"][0] == 1 and r["worst"][0] == 1


def test_finish_probabilities_sum_to_one_and_symmetric_coinflip():
    # two equal teams, one game between them at neutral-like pm=0 -> 50/50 title; tie impossible, so h2h decides
    r = simulate_conference([0, 1], [], _rem([(0, 1, 0.0, 140.0, 10.0)]), np.zeros(2), CFG, nsim=8000, seed=3)
    assert np.allclose(r["finish"].sum(axis=1), 1.0)
    assert abs(r["p_title"][0] - 0.5) < 0.03
    assert abs(r["exp_wins"].sum() - 1.0) < 1e-9


def test_three_team_tie_scenario_h2h_orders_group():
    # after the known games teams 0,1,2 are all 1-1 in a cycle; team 3 beat 2 and lost to 0,1. vs_standings resolves 2 last.
    known = [(0, 1, 5.0), (1, 2, 5.0), (2, 0, 5.0), (0, 3, 5.0), (1, 3, 5.0), (3, 2, 5.0)]
    r = simulate_conference([0, 1, 2, 3], known, _rem([]), np.zeros(4), dict(CFG, qualifiers=3), nsim=100)
    assert r["finish"][2][2] == 1.0 or r["finish"][2][3] == 1.0  # team 2 finishes below 0 and 1
    assert r["finish"][0][0] == 1.0 and r["finish"][1][1] == 1.0
