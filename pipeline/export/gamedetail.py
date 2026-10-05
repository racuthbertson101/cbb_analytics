"""Game-detail shards (IMPROVEMENT_PLAN Phase 3b.3): win-probability series and game-flow stats.

    gamedetail/<season>/<game_id>.json   {v, cols: [t, h, a, wp], wp: [[...]], runs, lead_changes, ties, largest, excitement, pct}
    gamedetail/<season>/index.json       {ids: [...]} games that have a detail file (the Game page checks it, so no 404s)

Seasons 2025 on (DETAIL_FIRST). Only games whose play-by-play final equals the box score get a file. WP comes from the
walk-forward in-game model for that season (pipeline/params/ingame.json: production[season] is fit on earlier seasons only).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from pipeline.models import ingame
from pipeline.warehouse.paths import PARAMS, table_path

from .contract import write

DETAIL_FIRST = 2025  # DEFINITION: first season with game-detail shards (size budget, IMPROVEMENT_PLAN 4.2)
RUN_MIN = 8          # DEFINITION: a "run" is 8 or more unanswered points
V = 1


def pregame(season: int) -> pd.DataFrame:
    """Calibrated pregame home win probability per game: the walk-forward backtest when it covers the season, otherwise the
    nightly pregame predictions (adjeff_preds) through the production calibration (fit on earlier seasons)."""
    pre = ingame.pregame()
    pre = pre[pre.season == season]
    if len(pre):
        return pre
    from pipeline.models.backtest import BT
    from pipeline.models.production import Predictor, load_prod

    prod = load_prod()
    cal = Predictor.__new__(Predictor)
    cal.sig, cal.gx, cal.gy = prod["sigma_coef"], np.array(prod["calibration_grid_x"]), np.array(prod["calibration_grid_y"])
    P = pd.read_parquet(BT / "adjeff_preds.parquet")
    P = P[P.season == season]
    m = (P.pred_a - P.pred_b).values
    return pd.DataFrame({"game_id": P.game_id.astype(str).values, "season": season, "pm": m, "p0": cal._win_prob(m, P.pred_poss.values)})


def runs(h: np.ndarray, a: np.ndarray, t: np.ndarray) -> list:
    """Unanswered scoring runs of RUN_MIN+ points: [start_t, end_t, side ('h'/'a'), points]."""
    out, side, pts, start, last = [], None, 0, 0, 0
    for i in range(1, len(h)):
        dh, da = h[i] - h[i - 1], a[i] - a[i - 1]
        s = "h" if dh > 0 and da == 0 else "a" if da > 0 and dh == 0 else None
        if s is None:
            continue
        if s != side:
            if side and pts >= RUN_MIN:
                out.append([int(start), int(last), side, int(pts)])
            side, pts, start = s, 0, t[i - 1]
        pts += dh if s == "h" else da
        last = t[i]
    if side and pts >= RUN_MIN:
        out.append([int(start), int(last), side, int(pts)])
    return out


def flow(m: np.ndarray) -> dict:
    """Lead changes (the leader switches, possibly through a tie), ties after tip, largest lead per side."""
    lead = np.sign(m[m != 0])
    return {"lead_changes": int((lead[1:] != lead[:-1]).sum()) if len(lead) > 1 else 0,
            "ties": int(((m[1:] == 0) & (m[:-1] != 0)).sum()),
            "largest": {"h": int(max(m.max(), 0)), "a": int(max(-m.min(), 0))}}


def series(game: pd.DataFrame, coef: dict, p0: float, home_won: bool) -> np.ndarray:
    """[t, home, away, wp] from tip to the final whistle. Starts at p0, ends at exactly 1 or 0."""
    t, ot = ingame.clock(game.elapsed.values)
    wp = ingame.predict(coef, game.home.values - game.away.values, t, ot, np.full(len(game), p0))
    arr = np.column_stack([game.elapsed.values, game.home.values, game.away.values, wp])
    tip = np.array([[0, 0, 0, p0]])
    arr = np.vstack([tip, arr[arr[:, 0] > 0] if arr[0, 0] == 0 else arr])
    arr[-1, 3] = 1.0 if home_won else 0.0
    return arr


def export_season(y: int) -> int:
    path = table_path("pbp_scores", y)
    prm = PARAMS / "ingame.json"
    if not path.exists() or not prm.exists():
        return 0
    coef = json.loads(prm.read_text())["production"].get(str(y))
    if coef is None:
        return 0
    s = pd.read_parquet(path)
    g = pd.read_parquet(table_path("games", y))
    g = g[g.completed & (g.game_type != "exhibition")].set_index("game_id")
    pre = pregame(y).set_index("game_id")
    docs = {}
    for gid, gm in s.groupby("game_id", sort=False):
        if gid not in g.index or gid not in pre.index:
            continue
        r = g.loc[gid]
        if gm.home.iloc[-1] != r.home_score or gm.away.iloc[-1] != r.away_score:
            continue  # incomplete feed (KNOWN_ISSUES)
        arr = series(gm, coef, float(pre.loc[gid, "p0"]), r.home_score > r.away_score)
        m = arr[:, 1] - arr[:, 2]
        docs[gid] = {"v": V, "season": y, "id": gid, "cols": ["t", "h", "a", "wp"],
                     "wp": [[int(x[0]), int(x[1]), int(x[2]), round(float(x[3]), 3)] for x in arr],
                     "runs": runs(arr[:, 1], arr[:, 2], arr[:, 0]), **flow(m),
                     "excitement": round(float(np.abs(np.diff(arr[:, 3])).sum()), 2)}
    if not docs:
        return 0
    ex = np.sort([d["excitement"] for d in docs.values()])
    for gid, d in docs.items():
        d["excitement_pct"] = round(float(np.searchsorted(ex, d["excitement"], side="right") / len(ex)), 3)
        write(f"gamedetail/{y}/{gid}.json", d)
    write(f"gamedetail/{y}/index.json", {"v": V, "season": y, "ids": sorted(docs)})
    return len(docs)


def export_gamedetail(seasons=None):
    from pipeline.warehouse.paths import CURRENT_SEASON

    for y in seasons or range(DETAIL_FIRST, CURRENT_SEASON + 1):
        print(f"gamedetail {y}: {export_season(y)} games", flush=True)


if __name__ == "__main__":
    export_gamedetail()
