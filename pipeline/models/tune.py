"""Hyperparameter grids evaluated blockwise (weekly refits) per season; selection is walk-forward (see select_cfg)."""
from __future__ import annotations

import itertools
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.warehouse.paths import ROOT

from .engine import Context, finals_no_prior, season_eval

OUT = ROOT / "data" / "tuning"
TUNE_SEASONS = list(range(2010, 2027))

_ctx = None


def _init():
    global _ctx
    _ctx = Context()


def _key(cfg):
    return json.dumps(cfg, sort_keys=True, default=str)


def _run(cfg):
    fin = finals_no_prior(_ctx, cfg)
    rows = []
    for S in TUNE_SEASONS:
        e = season_eval(_ctx, S, cfg, fin, step=7)
        e.pop("coefs")
        rows.append({**e, "cfg": _key(cfg)})
    return rows


def run_grid(cfgs, name, workers=14):
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    with ProcessPoolExecutor(workers, initializer=_init) as ex:
        for i, r in enumerate(ex.map(_run, cfgs)):
            rows.extend(r)
            print(name, i + 1, "/", len(cfgs), flush=True)
    df = pd.DataFrame(rows)
    df.to_parquet(OUT / f"{name}.parquet")
    return df


def tempo_grid():
    return [dict(lam=10, lam_t=a, halflife=None, halflife_t=b, cap=None, skip_eff=True)
            for a, b in itertools.product([0.5, 1, 2, 3, 5], [None, 30, 60])]


def eff_grid(tempo_cfg_by_season=None):
    return [dict(lam=a, halflife=b, cap=c, lam_h=h, lam_t=2, halflife_t=60)
            for a, b, c, h in itertools.product([1.5, 3, 4.5, 6], [None, 300], [None, 60, 45], [None])]


if __name__ == "__main__":
    which = sys.argv[1]
    if which == "tempo":
        run_grid(tempo_grid(), "tempo2")
    else:
        run_grid(eff_grid(), "eff2")
