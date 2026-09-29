"""Export ranking systems (Elo, Bradley-Terry, player-driven, consensus) and resume metrics per season at weekly snapshots."""
from __future__ import annotations

import json
import pickle

import numpy as np
import pandas as pd

from pipeline.models import elo_mle
from pipeline.models.backtest import BT
from pipeline.models.bt import snap_days
from pipeline.models.data import load_games
from pipeline.players.team_rating import season_final
from pipeline.warehouse.paths import CURRENT_SEASON, PARAMS, table_path

from .contract import write, r1

POSS = 68.5  # points-per-game conversion factor for per-100 ratings (mean D-I possessions; display scale only)


def _extras():
    """Drop-in systems from pipeline/models/extra (registry pattern: no core edits needed)."""
    import importlib
    import pkgutil

    from pipeline.models import extra
    return [importlib.import_module(f"pipeline.models.extra.{m.name}") for m in pkgutil.iter_modules(extra.__path__) if not m.name.startswith("_")]


def main():
    G = load_games()
    poss = float(G.poss.mean())
    R = pd.read_parquet(BT / "adjeff_ratings.parquet")
    RES = pd.read_parquet(BT / "resume.parquet")
    bt = pickle.load(open(BT / "bt_snaps.pkl", "rb"))
    cons = json.loads((PARAMS / "consensus.json").read_text())["production"]
    ep = json.loads((PARAMS / "elo_mle.json").read_text())
    w3 = np.array([cons["weights"][k] for k in ("adjeff", "elo", "bt")])
    w3 = w3 / w3.sum()
    # player-driven display slope (OLS of adjusted margin on player-driven margin), display only
    xs, ys = [], []
    for y in range(2010, CURRENT_SEASON + 1):
        f = season_final(y).join(R[(R.season == y) & (R.date == R[R.season == y].date.max())].set_index("team_id"), how="inner")
        xs.append(f.pd_margin.values)
        ys.append((f.adj_off - f.adj_def).values)
    x, yv = np.concatenate(xs), np.concatenate(ys)
    slope = float((x * yv).sum() / (x * x).sum())
    (PARAMS / "player_driven.json").write_text(json.dumps({"display_slope_to_adj_margin": slope, "note": "display scaling only; the player-driven rating enters mean rank, not consensus weights"}, indent=1))
    seasons = list(range(2010, CURRENT_SEASON + 1))
    for y in seasons:
        p = ep.get(str(y)) or (ep["2012"] if y < 2012 else ep[max(ep, key=int)])
        Gy = G[G.season <= y].reset_index(drop=True)
        days = np.unique(G[G.season == y].date.values)
        sd = snap_days(days)
        _, snaps = elo_mle.run(Gy, p["K"], p["hca"], p["carry"], p["cap"], snapshots={(d, y) for d in sd[:-1]})
        elo_by = {s[1]: s[2] for s in snaps if s[0] == y}
        elo_final = [s for s in snaps if s[0] == y and s[1] == "final"][-1][2]
        d1 = sorted(set(pd.read_parquet(table_path("team_seasons", y)).query("is_d1").team_id))
        ti = {t: i for i, t in enumerate(d1)}
        Ry = R[R.season == y]
        btd = bt[y]
        bt_teams = {t: i for i, t in enumerate(btd["teams"])}
        scale = json.loads((PARAMS / "consensus.json").read_text())["production"]["bt_margin_scale"]
        pdf = season_final(y)
        n = len(sd)
        M = {k: np.full((n, len(d1)), np.nan) for k in ("adj", "elo", "bt", "cons", "mrank", "pd", "wab", "sor", "sos", "ncsos", "q1w", "q1l", "q2w", "q2l", "q3w", "q3l", "q4w", "q4l")}
        for i, D in enumerate(sd):
            r = Ry[Ry.date == pd.Timestamp(D)].set_index("team_id")
            adj = ((r.adj_off - r.adj_def) * poss / 100).reindex(d1).values
            eloD = elo_final if i == n - 1 else elo_by.get(D, {})
            elo = np.array([eloD.get(t, np.nan) for t in d1])
            b = btd["snaps"][i][1]
            btv = np.array([b[bt_teams[t]] * scale if t in bt_teams else np.nan for t in d1])
            M["adj"][i], M["elo"][i], M["bt"][i] = adj, elo, btv
            ok = ~np.isnan(adj) & ~np.isnan(elo) & ~np.isnan(btv)
            c = w3[0] * adj + w3[1] * elo + w3[2] * btv
            M["cons"][i] = np.where(ok, c, np.nan)
            rk = np.vstack([pd.Series(v).rank(ascending=False).values for v in (adj, elo, btv)])
            mr = rk.mean(axis=0)
            if i == n - 1:
                pdv = np.array([pdf.pd_margin.get(t, np.nan) * slope * poss / 100 for t in d1])
                M["pd"][i] = pdv
                rk4 = np.vstack([rk, pd.Series(pdv).rank(ascending=False).values])
                mr = np.nanmean(rk4, axis=0)
            M["mrank"][i] = np.where(ok, mr, np.nan)
            rs = RES[(RES.season == y) & (RES.day == pd.Timestamp(D))].set_index("team_id").reindex(d1)
            for k in ("wab", "sor", "sos", "ncsos", "q1w", "q1l", "q2w", "q2l", "q3w", "q3l", "q4w", "q4l"):
                M[k][i] = rs[k].values
        dates = [str(pd.Timestamp(d).date()) for d in sd]
        out = {"season": y, "dates": dates, "teams": d1, "poss": poss}
        for k, v in M.items():
            if k in ("sor",):
                out[k] = [[None if np.isnan(a) else round(float(a), 4) for a in row] for row in v]
            elif k.startswith("q"):
                out[k] = [[None if np.isnan(a) else int(a) for a in row] for row in v]
            else:
                out[k] = [r1(row) for row in v]
        for mod in _extras():
            out[mod.KEY] = mod.snapshots(y, d1, dates)
        write(f"systems/{y}.json", out)
        print("systems", y, flush=True)


if __name__ == "__main__":
    main()
