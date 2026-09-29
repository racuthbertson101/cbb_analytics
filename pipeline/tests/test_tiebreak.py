import numpy as np

from pipeline.sims.tiebreak import GENERIC_FALLBACK, build_standing, order, resolve


def test_three_team_tie_h2h_mini_conference():
    st = build_standing(4, [(0, 1, 5), (0, 2, 5), (1, 2, 5)])
    assert resolve([0, 1, 2], st, ["h2h"]) == [0, 1, 2]


def test_three_team_cycle_falls_to_standings_then_restarts_on_remaining_pair():
    # 0>1, 1>2, 2>0 (perfect cycle). vs outside team 3: 0 and 1 won, 2 lost.
    st = build_standing(4, [(0, 1, 5), (1, 2, 5), (2, 0, 5), (0, 3, 5), (1, 3, 5), (3, 2, 5)])
    assert resolve([0, 1, 2], st, ["h2h", "vs_standings", "random"], restart=True) == [0, 1, 2]
    # without restart the pair {0,1} continues with the NEXT rule (random) instead of h2h, so 2 must still be last
    got = resolve([0, 1, 2], st, ["h2h", "vs_standings", "random"], restart=False)
    assert got[2] == 2


def test_two_team_tie_uses_head_to_head_then_common_opponents():
    # teams 0 and 1 split; both play team 2 (the top team) once: 0 beat 2, 1 lost to 2 -> 0 ranks first
    st = build_standing(3, [(0, 1, 3), (1, 0, 3), (0, 2, 4), (2, 1, 4)])
    assert resolve([0, 1], st, ["h2h", "vs_standings", "random"]) == [0, 1]


def test_order_breaks_ties_in_win_pct_groups():
    # 0,1,2 each 1-1 by a cycle; team 3 (0-3) last; h2h all even, vs_standings has no outside team ranked above them (3 is worst)
    res = [(0, 1, 2), (1, 2, 2), (2, 0, 2), (0, 3, 2), (1, 3, 2), (2, 3, 2)]
    st = build_standing(4, res, rng=np.random.default_rng(1))
    o = order(st, GENERIC_FALLBACK)
    assert o[3] == 3 and sorted(o[:3]) == [0, 1, 2]


def test_rating_rule_is_deterministic_final_step():
    st = build_standing(3, [(0, 1, 1), (1, 0, 1)], rating=[1.0, 3.0, 2.0])
    assert resolve([0, 1], st, ["h2h", "rating"]) == [1, 0]


def test_unequal_game_counts_use_win_pct():
    # 0 played 2 games vs group {1,2}: won both; 1 played 1 game vs group: lost... pct-based
    st = build_standing(3, [(0, 1, 2), (0, 2, 2), (2, 1, 2)])
    assert resolve([0, 1, 2], st, ["h2h"]) == [0, 2, 1]
