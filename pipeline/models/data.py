"""Game-level modeling frame built from the warehouse (D-I vs D-I completed games only)."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from pipeline.warehouse.paths import FIRST_SEASON, PARAMS, table_path


def possession_coef() -> float:
    """FTA coefficient of the box possession estimate, estimated from data (params/possessions.json)."""
    p = PARAMS / "possessions.json"
    return json.loads(p.read_text())["fta_coef"] if p.exists() else 0.475


def fit_possession_coef(seasons) -> dict:
    """Estimate c in poss = FGA - ORB + TOV + c*FTA so both teams' estimates agree (they must, in a real game)."""
    dn, df = [], []
    for y in seasons:
        tg = pd.read_parquet(table_path("team_games", y))
        tg = tg[tg.both_d1 & tg.fga.notna() & tg.opp_fga.notna()]
        dn.append((tg.fga - tg.orb + tg.tov) - (tg.opp_fga - tg.opp_orb + tg.opp_tov))
        df.append(tg.fta - tg.opp_fta)
    dn, df = pd.concat(dn), pd.concat(df)
    c = float(-(dn * df).sum() / (df * df).sum())
    rmse0 = float(np.sqrt(((dn + 0.475 * df) ** 2).mean()))
    rmse1 = float(np.sqrt(((dn + c * df) ** 2).mean()))
    return {"fta_coef": c, "rmse_at_0.475": rmse0, "rmse_at_fit": rmse1, "n_team_games": int(len(dn)),
            "note": "c minimizes squared disagreement between the two teams' possession estimates"}


def load_games(seasons=None, only_d1=True) -> pd.DataFrame:
    """One row per completed game: a = home (or arbitrary 'home' on neutral), b = away."""
    c = possession_coef()
    out = []
    for y in seasons or range(FIRST_SEASON, 2027):
        p = table_path("games", y)
        if not p.exists():
            continue
        g = pd.read_parquet(p)
        g = g[g.completed & (g.both_d1 if only_d1 else True)]
        tg = pd.read_parquet(table_path("team_games", y))
        h = tg[tg.home_away == "home"].set_index("game_id")
        a = tg[tg.home_away == "away"].set_index("game_id")
        m = g.set_index("game_id")[["season", "game_date", "home_id", "away_id", "home_score", "away_score", "neutral_site",
                                    "game_type", "conference_game", "home_conf_id", "away_conf_id"]].join(
            h[["fga", "orb", "tov", "fta"]].add_prefix("h_"), how="inner").join(
            a[["fga", "orb", "tov", "fta"]].add_prefix("a_"), how="inner")
        ph = m.h_fga - m.h_orb + m.h_tov + c * m.h_fta
        pa = m.a_fga - m.a_orb + m.a_tov + c * m.a_fta
        m["poss"] = (ph + pa) / 2
        m = m.dropna(subset=["poss"])
        m = m[(m.poss > 35) & (m.poss < 120)]
        out.append(m.drop(columns=[x for x in m.columns if x[:2] in ("h_", "a_") and x not in ("h_", "a_")]).reset_index())
    G = pd.concat(out, ignore_index=True)
    G = G.rename(columns={"game_date": "date", "home_id": "a", "away_id": "b", "home_score": "pts_a", "away_score": "pts_b"})
    G["site"] = np.where(G.neutral_site, 0.0, 1.0)
    G["ea"] = 100 * G.pts_a / G.poss
    G["eb"] = 100 * G.pts_b / G.poss
    G["margin"] = G.pts_a - G.pts_b
    return G.sort_values(["date", "game_id"]).reset_index(drop=True)


if __name__ == "__main__":
    r = fit_possession_coef(range(FIRST_SEASON, 2027))
    (PARAMS).mkdir(parents=True, exist_ok=True)
    (PARAMS / "possessions.json").write_text(json.dumps(r, indent=2))
    print(r)
    G = load_games()
    print(G.shape, G.groupby("season").size().describe()[["min", "max"]].to_dict())
    print(G[["poss", "ea", "eb"]].describe().loc[["mean", "std"]])
