"""Phase 2 backtest: walk-forward adjusted-efficiency predictions for every test season, plus baselines and calibration.

Outputs (pipeline/params/): backtest.json, BACKTEST.md, adjeff.json (production params + evidence);
data/backtest/: per-game predictions and pregame ratings (as of every game date).
"""
from __future__ import annotations

import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.warehouse.paths import PARAMS, ROOT

from . import adjeff
from .engine import Context, base_params, block_predict, build_prior, finals_no_prior, prior_coefs

TUNE = ROOT / "data" / "tuning"
BT = Path(os.environ["CBB_ARTIFACTS"]) if os.environ.get("CBB_ARTIFACTS") else ROOT / "data" / "backtest"  # override for replay
FIRST_TUNE, FIRST_TEST = 2010, 2012
SEASONS = list(range(FIRST_TUNE, 2027))

_ctx = None


def _init():
    global _ctx
    _ctx = Context()


def _cfgs(df):
    return df.cfg.map(json.loads)


def select_cfg(results: pd.DataFrame, S: int, col: str) -> dict:
    """Walk-forward selection: best pooled error over tuning seasons strictly before S."""
    d = results[results.season < S]
    g = d.groupby("cfg").apply(lambda x: x[col].sum() / x.n.sum(), include_groups=False)
    return json.loads(g.idxmin())


def combined_cfg(S: int, eff=None, tempo=None) -> dict:
    eff = eff if eff is not None else pd.read_parquet(TUNE / "eff2.parquet")
    tempo = tempo if tempo is not None else pd.read_parquet(TUNE / "tempo2.parquet")
    e = select_cfg(eff, max(S, FIRST_TEST), "sse")
    t = select_cfg(tempo, max(S, FIRST_TEST), "sse_poss")
    cfg = {k: e.get(k) for k in ("lam", "halflife", "cap", "lam_h")}
    cfg["lam_t"], cfg["halflife_t"] = t["lam_t"], t["halflife_t"]
    return cfg


def run_season(S: int):
    """Daily walk-forward for season S. Returns (game predictions, pregame ratings, cfg, prior coefs)."""
    cfg = combined_cfg(S)
    fin = finals_no_prior(_ctx, cfg)
    coefs = prior_coefs(_ctx, fin, S)
    prior = build_prior(_ctx, fin, S, coefs)
    sd = _ctx.sd[S]
    rat = []

    def hook(r, D, sd_, lo, hi):
        t = r.table()
        t["date"] = pd.Timestamp("1970-01-01") + pd.Timedelta(days=D)
        t["hca"] = r.hca
        t["mu"] = r.mu
        rat.append(t)

    pr = block_predict(sd, cfg, prior, 1, hook)
    # end-of-season snapshot (fit on every game of the season) so the final table exists
    pfin = base_params(cfg)
    pfin.update(prior)
    hook(adjeff.fit(sd, len(sd.date), int(sd.date[-1]) + 1, pfin), int(sd.date[-1]) + 1, sd, 0, 0)
    f = sd.frame[["game_id", "a", "b", "site", "pts_a", "pts_b", "poss", "game_type", "neutral_site"]]
    pr = pr.merge(f, on="game_id")
    pr["season"] = S
    pr["date"] = pd.Timestamp("1970-01-01") + pd.to_timedelta(pr.date, unit="D")
    R = pd.concat(rat, ignore_index=True)
    R["season"] = S
    # previous-season-rating-only baseline: last season's final no-prior fit, applied to all of S's games
    base = None
    if S - 1 in fin:
        pf = fin[S - 1]
        ok = pr.a.isin(pf.tix) & pr.b.isin(pf.tix)
        ia, ib = pr.a[ok].map(pf.tix).values, pr.b[ok].map(pf.tix).values
        sa, sb, _ = pf.predict_arrays(ia, ib, pr.site[ok].values)
        base = pd.DataFrame({"game_id": pr.game_id[ok].values, "prev_margin": sa - sb})
        pr = pr.merge(base, on="game_id", how="left")
    return pr, R, cfg, coefs


def run_all(workers=8):
    BT.mkdir(parents=True, exist_ok=True)
    preds, rats, meta = [], [], {}
    with ProcessPoolExecutor(workers, initializer=_init) as ex:
        for S, (pr, R, cfg, coefs) in zip(SEASONS, ex.map(run_season, SEASONS)):
            preds.append(pr)
            rats.append(R)
            meta[S] = {"cfg": cfg, "prior_coefs": coefs}
            print("season", S, len(pr), flush=True)
    P = pd.concat(preds, ignore_index=True)
    R = pd.concat(rats, ignore_index=True)
    P.to_parquet(BT / "adjeff_preds.parquet")
    R.to_parquet(BT / "adjeff_ratings.parquet")
    (BT / "meta.json").write_text(json.dumps(meta, indent=1, default=str))
    return P, R, meta


if __name__ == "__main__":
    run_all()
