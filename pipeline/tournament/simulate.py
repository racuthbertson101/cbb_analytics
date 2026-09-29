"""Monte Carlo bracket simulation with any predictor implementing predict(team_a, team_b, site, date) -> {'win_prob_a': ...}."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .bracket import ROUNDS, SEED_ORDER, Bracket


def simulate_bracket(bracket: Bracket, predictor, n_sims: int = 10000, seed: int = 0, date=None) -> pd.DataFrame:
    """Returns a DataFrame indexed by team id with the probability of reaching each round (columns) and winning the title."""
    rng = np.random.default_rng(seed)
    cache: dict[tuple[str, str], float] = {}

    def p(a, b):
        k = (a, b)
        if k not in cache:
            cache[k] = float(predictor.predict(a, b, 0.0, date)["win_prob_a"])
            cache[(b, a)] = 1.0 - cache[k]
        return cache[k]

    teams = bracket.teams()
    reach = {t: np.zeros(len(ROUNDS) + 1) for t in teams}  # index i = reached round i (0 = made field), last = champion
    play_in = {(pi.region, pi.seed): pi for pi in bracket.play_in}
    for _ in range(n_sims):
        region_winners = []
        for ri, reg in enumerate(bracket.regions):
            field_ = {}
            for s in reg.slots:
                t = s.team
                if t is None:
                    pi = play_in[(ri, s.seed)]
                    a, b = pi.teams
                    t = a if rng.random() < p(a, b) else b
                field_[s.seed] = t
            alive = [field_[s] for s in SEED_ORDER]
            for t in alive:
                reach[t][0] += 1
            rnd = 0
            while len(alive) > 1:
                nxt = []
                for i in range(0, len(alive), 2):
                    a, b = alive[i], alive[i + 1]
                    w = a if rng.random() < p(a, b) else b
                    nxt.append(w)
                rnd += 1
                for t in nxt:
                    reach[t][rnd] += 1
                alive = nxt
            region_winners.append(alive[0])
        finalists = []
        for i, j in bracket.final_four:
            a, b = region_winners[i], region_winners[j]
            w = a if rng.random() < p(a, b) else b
            reach[w][5] += 1
            finalists.append(w)
        a, b = finalists
        champ = a if rng.random() < p(a, b) else b
        reach[champ][6] += 1
    cols = ["Field", "R32", "Sweet 16", "Elite 8", "Final Four", "Title game", "Champion"]
    return pd.DataFrame({t: v / n_sims for t, v in reach.items()}, index=cols).T
