"""RAPM (Phase 5a.2) recovers a planted player effect on synthetic stints."""
import numpy as np
import pandas as pd

from pipeline.players.rapm import fit


def test_recovers_planted_offense_effect():
    rng = np.random.default_rng(0)
    players = [f"p{i}" for i in range(40)]
    rows = []
    for k in range(6000):
        off = list(rng.choice(players, 5, replace=False))
        dfn = list(rng.choice([p for p in players if p not in off], 5, replace=False))
        poss = 8.0
        y = 100 + (12 if "p0" in off else 0) - (8 if "p1" in dfn else 0) + rng.normal(0, 40)  # p0 great offense, p1 great defense
        rows.append({"game_id": str(k // 30), "off": off, "def": dfn, "pts": y * poss / 100, "poss": poss, "site": 0.0, "y": y})
    m = fit(pd.DataFrame(rows), lam=50)
    o, d = dict(zip(m["players"], m["off"])), dict(zip(m["players"], m["def"]))
    others = np.mean([o[p] for p in players[2:]])
    assert o["p0"] - others > 8 and d["p1"] > 5          # shrunk toward zero, but clearly found
    assert abs(o["p1"]) < 3 and abs(d["p0"]) < 3
