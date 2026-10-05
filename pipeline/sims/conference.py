"""Monte Carlo conference standings: known results fixed, remaining games sampled from the game prediction model.

Sampled margin = predicted margin + normal noise (spread from the fitted margin-spread model, tempo dependent); sampled total =
predicted total + normal noise (sd fitted from backtest residuals); both are rounded to integer scores so point differential
tiebreakers work. Standings use the real per-conference tiebreaker rules (config/tiebreakers/*.yaml).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from pipeline.models.backtest import BT
from pipeline.warehouse.paths import PARAMS, ROOT, table_path

from .tiebreak import Standing, order

CFG_DIR = ROOT / "config" / "tiebreakers"


def slug(name):
    return name.lower().replace(" ", "_").replace("/", "_")


def load_cfg(conf_name: str) -> dict:
    aliases = yaml.safe_load((ROOT / "config" / "membership_overrides.yaml").read_text(encoding="utf8")).get("conference_aliases") or {}
    p = CFG_DIR / f"{slug(aliases.get(conf_name, conf_name))}.yaml"
    return yaml.safe_load((p if p.exists() else CFG_DIR / "_fallback.yaml").read_text(encoding="utf8"))


def total_sd() -> float:
    p = PARAMS / "sim_noise.json"
    if p.exists():
        return json.loads(p.read_text())["total_sd"]
    P = pd.read_parquet(BT / "adjeff_preds.parquet")
    sd = float(((P.pts_a + P.pts_b) - (P.pred_a + P.pred_b)).std())
    p.write_text(json.dumps({"total_sd": sd, "note": "sd of (actual total - predicted total) over the walk-forward backtest"}, indent=1))
    return sd


def rating_table(season: int, asof: str) -> pd.DataFrame:
    """Backtest ratings (walk-forward, fit on games before `asof`) with league mean and home advantage."""
    R = pd.read_parquet(BT / "adjeff_ratings.parquet")
    R = R[(R.season == season) & (R.date <= pd.Timestamp(asof))]
    d = R.date.max()
    return R[R.date == d].set_index("team_id")


def predict_games(tbl: pd.DataFrame, prod: dict, home, away, neutral):
    from scipy.stats import norm  # noqa: F401
    h, a = tbl.loc[home], tbl.loc[away]
    hca = tbl.hca.iloc[0] * np.where(neutral, 0.0, 1.0)
    mu = tbl.mu.iloc[0]
    ea = h.adj_off.values + a.adj_def.values - mu + hca
    eb = a.adj_off.values + h.adj_def.values - mu - hca
    poss = (h.adj_tempo.values + a.adj_tempo.values) / 2
    sig = np.maximum(prod["sigma_coef"][0] + prod["sigma_coef"][1] * (poss - 68.0), 3.0)
    return (ea - eb) * poss / 100, (ea + eb) * poss / 100, sig


def simulate_conference(teams, known, remaining, rating, cfg, nsim=20000, seed=0, tsd=11.0):
    """teams: list of ids. known: list of (hi, ai, home_margin). remaining: DataFrame(hi, ai, pm, tot, sig).
    Returns dict of per-team result arrays."""
    n = len(teams)
    rng = np.random.default_rng(seed)
    H0 = np.zeros((n, n)); PD0 = np.zeros((n, n)); RW0 = np.zeros((n, n)); RG0 = np.zeros((n, n))
    for h, a, m in known:
        if m > 0:
            H0[h, a] += 1
        else:
            H0[a, h] += 1
            RW0[a, h] += 1
        RG0[a, h] += 1
        PD0[h, a] += m
        PD0[a, h] -= m
    K = len(remaining)
    S = nsim
    H = np.repeat(H0[None], S, 0).astype(np.int16)
    PD = np.repeat(PD0[None], S, 0).astype(np.int16)
    RW = np.repeat(RW0[None], S, 0).astype(np.int16)
    RG = np.repeat(RG0[None], S, 0).astype(np.int16)
    if K:
        hi, ai = remaining.hi.values, remaining.ai.values
        z = rng.standard_normal((S, K))
        m = np.rint(remaining.pm.values[None] + remaining.sig.values[None] * z)
        zero = m == 0
        m = np.where(zero, np.where(remaining.pm.values[None] + remaining.sig.values[None] * z >= 0, 1, -1), m).astype(np.int16)
        win = m > 0
        for k in range(K):
            h, a = hi[k], ai[k]
            H[:, h, a] += win[:, k]
            H[:, a, h] += ~win[:, k]
            RG[:, a, h] += 1
            RW[:, a, h] += ~win[:, k]
            PD[:, h, a] += m[:, k]
            PD[:, a, h] -= m[:, k]
    wins = H.sum(axis=2)
    games = (H + H.transpose(0, 2, 1)).sum(axis=2)
    pct = np.round(wins / np.maximum(games, 1), 9)
    rules, restart = cfg["rules"], cfg.get("restart_on_partial", True)
    pos = np.zeros((S, n), dtype=np.int16)  # finish place 1..n per team
    tr = np.random.default_rng(seed + 1)
    for s in range(S):
        p = pct[s]
        if len(np.unique(p)) == n:
            ordr = np.argsort(-p, kind="stable")
        else:
            st = Standing(n, wins[s], games[s], H[s], PD[s], RW[s], RG[s], rating, tr)
            ordr = order(st, rules, restart)
        pos[s, ordr] = np.arange(1, n + 1)
    # summaries
    q, byes = cfg.get("qualifiers", n), cfg.get("bye_seed_lines", [])
    best_w = wins.max(axis=1, keepdims=True)
    res = {"exp_wins": wins.mean(axis=0), "exp_games": games.mean(axis=0)}
    res["finish"] = np.stack([(pos == p).mean(axis=0) for p in range(1, n + 1)], axis=1)
    res["p_title"] = res["finish"][:, 0]
    res["p_title_share"] = (wins == best_w).mean(axis=0)
    res["p_qualify"] = (pos <= q).mean(axis=0)
    res["p_bye"] = {str(b): (pos <= b).mean(axis=0) for b in byes}
    res["exp_finish"] = pos.mean(axis=0)
    # win-count bounds (ties assumed favorable for best, unfavorable for worst)
    cur_w = H0.sum(axis=1)
    rem_g = np.zeros(n)
    if K:
        for h, a in zip(remaining.hi.values, remaining.ai.values):
            rem_g[h] += 1
            rem_g[a] += 1
    max_w, min_w = cur_w + rem_g, cur_w
    res["best"] = np.array([1 + int(sum(1 for j in range(n) if j != i and min_w[j] > max_w[i])) for i in range(n)])
    res["worst"] = np.array([n - int(sum(1 for j in range(n) if j != i and max_w[j] < min_w[i])) for i in range(n)])
    res["cur_w"], res["cur_g"] = cur_w, H0.sum(axis=1) + H0.sum(axis=0)
    return res


def run_season(season: int, asof: str, nsim=20000, prod=None, seed=0, only=None):
    prod = prod or json.loads((PARAMS / "adjeff.json").read_text())
    tsd = total_sd()
    g = pd.read_parquet(table_path("games", season))
    ts = pd.read_parquet(table_path("team_seasons", season))
    tbl = rating_table(season, asof)
    ts = ts[ts.is_d1 & ts.conference.notna() & ts.team_id.isin(tbl.index)]
    d = pd.Timestamp(asof)
    out = {}
    for conf, grp in ts.groupby("conference"):
        if only and conf not in only:
            continue
        teams = sorted(grp.team_id)
        ix = {t: i for i, t in enumerate(teams)}
        cg = g[g.conference_game & (g.game_type == "regular") & g.home_id.isin(ix) & g.away_id.isin(ix)]
        played = cg[cg.completed & (cg.game_date < d)]
        known = [(ix[r.home_id], ix[r.away_id], float(r.home_score - r.away_score)) for r in played.itertuples()]
        rest = cg[(cg.game_date >= d)]
        rem = pd.DataFrame(columns=["hi", "ai", "pm", "tot", "sig"])
        if len(rest):
            pm, tot, sig = predict_games(tbl, prod, rest.home_id.values, rest.away_id.values, rest.neutral_site.values)
            rem = pd.DataFrame({"hi": rest.home_id.map(ix).values, "ai": rest.away_id.map(ix).values, "pm": pm, "tot": tot, "sig": sig})
        rating = (tbl.adj_off - tbl.adj_def).reindex(teams).values
        cfg = load_cfg(conf)
        res = simulate_conference(teams, known, rem, rating, cfg, nsim, seed, tsd)
        out[conf] = {"teams": teams, "cfg": {k: cfg[k] for k in ("status", "rules", "qualifiers", "bye_seed_lines", "source_url")}, "res": res, "n_remaining": len(rem)}
        print("sim", season, asof, conf, len(teams), "remaining", len(rem), flush=True)
    return out
