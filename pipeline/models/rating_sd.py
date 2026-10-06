"""Rating uncertainty (IMPROVEMENT_PLAN Phase 5c.1).

The adjusted-efficiency ridge has a Gaussian-prior reading: posterior Var(beta) = sigma2 * A^-1, A = X'WX + penalty. This module
1. estimates sigma2 (per-row efficiency noise, points per 100 possessions squared) from end-of-season fits, pooled over test
   seasons, with a degrees-of-freedom correction (sigma2 = sum w r^2 / (n_rows - 2 * teams));
2. validates walk-forward: at checkpoints during each season, the share of teams whose end-of-season efficiency margin lies
   within their earlier +/-1 sd band (target 60-75%), and how the band shrinks with games played.

    python -m pipeline.models.rating_sd estimate | validate
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from pipeline.warehouse.paths import PARAMS

from . import adjeff
from .backtest import BT
from .engine import Context, base_params, build_prior, finals_no_prior
from .production import load_prod

OUT = PARAMS / "rating_sd.json"
SEASONS = range(2012, 2027)
CHECKPOINTS = ["11-30", "12-31", "01-31", "02-28"]  # DEFINITION: month-end checkpoints for the coverage report


def sigma2() -> float:
    return json.loads(OUT.read_text())["sigma2_eff"]


def estimate() -> dict:
    prod = load_prod()
    cfg = prod["config"]
    ctx = Context()
    per = {}
    for S in SEASONS:
        if S not in ctx.sd or S - 1 not in ctx.sd:
            continue
        sub = object.__new__(Context)
        sub.G, sub.seasons, sub.sd = ctx.G, [y for y in ctx.seasons if y < S], {y: ctx.sd[y] for y in ctx.seasons if y < S}
        prior = build_prior(ctx, finals_no_prior(sub, cfg), S, prod["prior_coefs_current"])
        sd = ctx.sd[S]
        p = base_params(cfg)
        p.update(prior)
        r = adjeff.fit(sd, len(sd.date), int(sd.date[-1]) + 1, p)
        ea, eb = adjeff._cap(sd.ea, sd.eb, cfg.get("cap"))
        pa = r.mu + r.o[sd.ia] + r.d[sd.ib] + r.hca * sd.site
        pb = r.mu + r.o[sd.ib] + r.d[sd.ia] - r.hca * sd.site
        res = np.concatenate([ea - pa, eb - pb])
        per[str(S)] = {"rows": int(len(res)), "teams": int(len(sd.teams)), "sigma2": float((res ** 2).sum() / (len(res) - 2 * len(sd.teams)))}
    s2 = float(np.mean([v["sigma2"] for v in per.values()]))
    out = {"sigma2_eff": round(s2, 3), "sigma_eff": round(float(np.sqrt(s2)), 3), "by_season": per,
           "method": "residual variance of team-game efficiency (points per 100) at end-of-season fits, df-corrected, mean over seasons"}
    OUT.write_text(json.dumps(out, indent=1))
    return out


def validate() -> dict:
    """Coverage of end-of-season ratings by earlier +/-1 sd bands, and band width by games played (walk-forward artifacts)."""
    R = pd.read_parquet(BT / "adjeff_ratings.parquet")
    R = R[R.season.isin(list(SEASONS))].copy()
    R["em"] = R.adj_off - R.adj_def
    last = R.groupby("season").date.transform("max")
    fin = R[R.date == last].set_index(["season", "team_id"]).em
    cov, rev = {}, {}
    for cp in CHECKPOINTS:
        hits, rv = [], []
        for S, g in R.groupby("season"):
            y = S - 1 if cp[:2] in ("11", "12") else S
            d = pd.Timestamp(f"{y}-{cp}")
            snap = g[g.date <= d]
            if snap.empty:
                continue
            snap = snap[snap.date == snap.date.max()].set_index("team_id")
            f = fin.loc[S].reindex(snap.index)
            ok = snap.em_sd.notna() & f.notna()
            hits.append(((f[ok] - snap.em[ok]).abs() <= snap.em_sd[ok]))
            fsd = R[(R.season == S) & (R.date == R[R.season == S].date.max())].set_index("team_id").em_sd.reindex(snap.index)
            rv.append(pd.DataFrame({"d2": (f - snap.em) ** 2, "expect": snap.em_sd ** 2 - fsd ** 2}).dropna())
        h = pd.concat(hits)
        cov[cp] = {"n": int(len(h)), "within_1sd": round(float(h.mean()), 3)}
        D = pd.concat(rv)
        rev[cp] = {"observed_over_expected_variance": round(float(D.d2.mean() / D.expect.mean()), 3),
                   "within_1sd_of_revision": round(float((np.sqrt(D.d2) <= np.sqrt(D.expect.clip(lower=1e-6))).mean()), 3)}
    R["gp_bin"] = pd.cut(R.n_games, [-1, 0, 3, 6, 10, 15, 20, 25, 30, 45], labels=["0", "1-3", "4-6", "7-10", "11-15", "16-20", "21-25", "26-30", "31+"])
    width = R.groupby("gp_bin", observed=True).em_sd.mean()
    out = json.loads(OUT.read_text())
    out["coverage_final_within_1sd"] = cov
    out["revision_check"] = rev
    out["note_revision"] = ("The end-of-season rating contains the games the earlier rating used, so the plan's coverage test is biased "
                            "high. The calibrated check: the later revision (final - earlier) should have variance sd_earlier^2 - "
                            "sd_final^2, and 68% of revisions should fall within that sd.")
    out["mean_em_sd_by_games_played"] = {str(k): round(float(v), 2) for k, v in width.items()}
    out["note_coverage"] = "share of teams whose end-of-season margin lies within the earlier rating +/- 1 sd (target 60-75%)"
    OUT.write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    print(json.dumps({"estimate": estimate, "validate": validate}[sys.argv[1]](), indent=1)[:1500])
