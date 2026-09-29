"""Nightly pipeline: ingest -> validate -> refit live season -> predict next 7 days -> log -> simulate conferences -> export -> build.

    python -m pipeline.nightly [--today YYYY-MM-DD] [--nsim 20000] [--base-path /cbb_analytics] [--no-build] [--force]

--today runs the whole path "as if" it were that date (replay mode; use with CBB_WAREHOUSE pointing at a truncated warehouse copy).
Season window guard: full run November 1 - April 15; otherwise a light weekly run (Mondays) unless --force.
Fails loudly (non-zero exit) on any error, so a scheduled job never deploys a broken site.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


def season_of(d: date) -> int:
    return d.year + 1 if d.month >= 9 else d.year


def in_full_window(d: date) -> bool:
    return (d.month, d.day) >= (11, 1) or (d.month, d.day) <= (4, 15)


def log(msg):
    print(f"[nightly {datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", default=None)
    ap.add_argument("--nsim", type=int, default=20000)
    ap.add_argument("--base-path", default=os.environ.get("NEXT_PUBLIC_BASE_PATH", ""))
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--no-ingest", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    today = date.fromisoformat(a.today) if a.today else datetime.now(timezone.utc).astimezone().date()
    season = season_of(today)
    if not in_full_window(today) and today.weekday() != 0 and not a.force:
        log(f"{today} is outside the full-run window and not a Monday: nothing to do")
        return 0
    import pandas as pd

    wh = Path(os.environ["CBB_WAREHOUSE"]) if os.environ.get("CBB_WAREHOUSE") else Path(__file__).resolve().parents[1] / "data" / "warehouse"
    gp = wh / "mbb" / "games" / f"{season}.parquet"

    def completed_count():
        return int(pd.read_parquet(gp, columns=["completed"]).completed.sum()) if gp.exists() else 0

    # offseason (no results yet for `season`): current = last completed season, upcoming = `season`; only schedule/rosters refresh
    live = completed_count() > 0 or in_full_window(today) and today >= date(season - 1, 11, 1)
    cur = season if live else season - 1
    os.environ["CBB_CURRENT_SEASON"] = str(cur)  # must be set before importing modules that read it

    from pipeline.export import accuracy, conferences, contract, players, systems
    from pipeline.ingest import espn
    from pipeline.models import live as livefit
    from pipeline.models.data import load_games
    from pipeline.predictions import log as plog
    from pipeline.warehouse.paths import ROOT, table_path
    from pipeline.warehouse.validate import validate

    t0 = time.time()
    status = {"today": str(today), "season": season, "started": datetime.now(timezone.utc).isoformat()}

    if not live:
        from pipeline.ingest import download
        from pipeline.warehouse import build as wbuild

        log(f"offseason: refreshing schedule and rosters for {season}")
        for kind in ("schedules", "rosters", "standings"):
            download.fetch(kind, season, force=True)
        wbuild.build([season])
    # 1. ingest completed games (recheck the last few days) and the schedule for the next 7 days
    if live and not a.no_ingest:
        last = espn.last_completed_date(season)
        start = (last - pd.Timedelta(days=espn.RECHECK_DAYS)).date() if last is not None else date(season - 1, 11, 1)
        days = espn.daterange(min(start, today), today + timedelta(days=7))
        log(f"ingest {days[0]}..{days[-1]}")
        status["ingest"] = espn.ingest_days(season, days, workers=a.workers, now=today, cutoff=today)
        log(f"ingest result {status['ingest']}")

    if live:
        # 2. player tables for the live season (fixed impact model)
        from pipeline.players import seasons as pseasons
        from pipeline.players.impact import ImpactModel, load_ps

        pseasons.build_all([season])
        pj = json.loads((ROOT / "pipeline" / "params" / "players.json").read_text())
        model = ImpactModel.from_json(pj["model"])
        ps = load_ps(season)
        imp = model.impacts(ps, pj["shrink_k_minutes"])
        out = ps.merge(imp[["athlete_id", "team_id", "imp_o", "imp_d", "imp"]], on=["athlete_id", "team_id"])
        out.to_parquet(table_path("player_impacts", season), index=False)

        # 3. validate
        bad = validate(season)
        status["validation"] = bad
        if bad:
            raise SystemExit(f"validation failed: {bad}")
        log("validation ok")

        # 4. refit ratings for the live season (production params) and refresh dependent artifacts
        G = load_games()
        log(f"refit {season}: {livefit.patch_artifacts(season, G)}")
        livefit.refresh_bt(season, G)
        livefit.refresh_resume(season)

        # 5. predictions for the next 7 days -> append-only log
        from pipeline.export.contract import _predict_table
        from pipeline.models.backtest import BT
        from pipeline.models.production import Predictor, load_prod

        prod = load_prod()
        R = pd.read_parquet(BT / "adjeff_ratings.parquet")
        Rs = R[(R.season == season)]
        tbl = Rs[Rs.date == Rs.date.max()].set_index("team_id")
        g = pd.read_parquet(table_path("games", season))
        up = g[~g.completed & (g.game_date >= pd.Timestamp(today)) & (g.game_date <= pd.Timestamp(today + timedelta(days=7))) & g.home_id.isin(tbl.index) & g.away_id.isin(tbl.index)]
        if len(up):
            cal = Predictor.__new__(Predictor)
            import numpy as np
            cal.sig, cal.gx, cal.gy = prod["sigma_coef"], np.array(prod["calibration_grid_x"]), np.array(prod["calibration_grid_y"])
            fp = _predict_table(tbl, prod, cal, up.home_id.values, up.away_id.values, up.neutral_site.values)
            new = pd.DataFrame({"game_id": up.game_id.values, "game_date": up.game_date.astype(str).values, "home_id": up.home_id.values, "away_id": up.away_id.values,
                                "neutral": up.neutral_site.values, "pm": fp.pm.values, "ph": fp.ph.values, "pa": fp.pa.values, "p": fp.p.values, "plo": fp.lo.values,
                                "phi": fp.hi.values, "model_version": "adjeff-v1"})
            status["logged"] = plog.append(new, datetime.now(timezone.utc).isoformat())
        else:
            status["logged"] = 0
        assert plog.verify(), "prediction log failed verification"

        # 6. conference simulations as of today (before exports: watchability uses title leverage)
        conferences.sim_standings(season, str(today), nsim=a.nsim, workers=a.workers, keep_only=True)


    # 7. exports
    upcoming = season if not live else None
    contract.export_all(current=cur, upcoming=upcoming)
    players.export_players()
    conferences.tiebreak_index()
    conferences.conference_stats(list(range(2010, cur + 1)))
    systems.main()
    accuracy.live_summary()
    accuracy.backtest_summary()

    # 8. static site build
    if not a.no_build:
        env = dict(os.environ, NEXT_PUBLIC_BASE_PATH=a.base_path)
        subprocess.run("npx next build", cwd=ROOT / "web", shell=True, check=True, env=env)
    status["seconds"] = round(time.time() - t0)
    (ROOT / "data" / "nightly_status.json").write_text(json.dumps(status, indent=1, default=str))
    log(f"done in {status['seconds']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
