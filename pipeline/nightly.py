"""Nightly pipeline: ingest -> validate -> refit live season -> predict next 7 days -> log -> simulate conferences -> export -> build.

    python -m pipeline.nightly [--today YYYY-MM-DD] [--nsim 20000] [--base-path /cbb_analytics] [--no-build] [--force] [--check]

--today runs the whole path "as if" it were that date; with --rehearsal it runs against scratch copies (data/rehearsal).
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


def should_run(d: date, force: bool = False) -> bool:
    return force or in_full_window(d) or d.weekday() == 0


REHEARSAL = Path(__file__).resolve().parents[1] / "data" / "rehearsal"


def setup_rehearsal(today: date, reset: bool = False, root: Path | None = None) -> dict:
    """Scratch copies of the warehouse, model artifacts and prediction log; returns the env overrides pointing at them.

    Created on first use (or with reset) and truncated to `today` (results on/after it removed, as on a real morning).
    Later nights reuse the same copy, so consecutive rehearsal nights advance like real ones. The real data/, predictions/
    and the release are never touched; exports still go to web/public/data (generated, gitignored).
    """
    import shutil

    from pipeline.replay import truncate

    base = Path(__file__).resolve().parents[1]
    r = root or REHEARSAL
    if reset and r.exists():
        shutil.rmtree(r)
    if not r.exists():
        shutil.copytree(base / "data" / "warehouse", r / "warehouse")
        shutil.copytree(base / "data" / "backtest", r / "backtest")
        shutil.copytree(base / "predictions", r / "predictions")
        if (r / "warehouse" / "mbb" / "games" / f"{season_of(today)}.parquet").exists():
            log(f"rehearsal: truncated {truncate(r / 'warehouse', season_of(today), pd_ts(today))} games on/after {today}")
    return {"CBB_WAREHOUSE": str(r / "warehouse"), "CBB_ARTIFACTS": str(r / "backtest"), "CBB_PREDICTION_LOG": str(r / "predictions")}


def pd_ts(d: date):
    import pandas as pd

    return pd.Timestamp(d)


def log(msg):
    print(f"[nightly {datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", default=None)
    ap.add_argument("--nsim", type=int, default=20000)
    ap.add_argument("--base-path", default=os.environ.get("NEXT_PUBLIC_BASE_PATH", ""))
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--no-ingest", action="store_true", help="skip ESPN ingest and the offseason schedule refresh (rebuild exports and site only)")
    ap.add_argument("--no-log", action="store_true", help="do not append to the prediction log (deploy.yml republishes without logging)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--rehearsal", action="store_true", help="run against scratch copies in data/rehearsal (see setup_rehearsal)")
    ap.add_argument("--rehearsal-reset", action="store_true", help="start the rehearsal copy fresh from the real data")
    ap.add_argument("--check", action="store_true", help="only decide whether today is a run day; writes run=true|false to $GITHUB_OUTPUT")
    a = ap.parse_args(argv)
    today = date.fromisoformat(a.today) if a.today else datetime.now(timezone.utc).astimezone().date()
    season = season_of(today)
    run = should_run(today, a.force)
    if a.check:
        log(f"{today}: {'run day' if run else 'not a run day (outside Nov 1 - Apr 15 and not a Monday)'}")
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"run={'true' if run else 'false'}\n")
        return 0
    if not run:
        log(f"{today} is outside the full-run window and not a Monday: nothing to do")
        return 0
    if a.rehearsal:  # must happen before any pipeline module reads the path overrides
        os.environ.update(setup_rehearsal(today, a.rehearsal_reset))
        log(f"REHEARSAL for {today}: data in {REHEARSAL}; real data, predictions/ and the release are untouched")
    import pandas as pd

    wh = Path(os.environ["CBB_WAREHOUSE"]) if os.environ.get("CBB_WAREHOUSE") else Path(__file__).resolve().parents[1] / "data" / "warehouse"
    gp = wh / "mbb" / "games" / f"{season}.parquet"

    def completed_count():
        return int(pd.read_parquet(gp, columns=["completed"]).completed.sum()) if gp.exists() else 0

    # offseason (no results yet for `season`): current = last completed season, upcoming = `season`; only schedule/rosters refresh
    live = completed_count() > 0 or in_full_window(today) and today >= date(season - 1, 11, 1)
    # the site's current season is the live one once results are expected (games scheduled before today); until then
    # (opening morning) the site keeps the preseason view while the night still predicts and logs (Phase 2 rehearsal finding)
    sched = pd.read_parquet(gp, columns=["game_date", "game_type"]) if gp.exists() else pd.DataFrame(columns=["game_date", "game_type"])
    results_expected = live and bool(((sched.game_date < pd.Timestamp(today)) & (sched.game_type != "exhibition")).any())
    cur = season if results_expected else season - 1
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

    if not live and not a.no_ingest:
        from pipeline.ingest import download
        from pipeline.warehouse import build as wbuild

        log(f"offseason: refreshing schedule and rosters for {season}")
        for kind in ("schedules", "rosters", "standings"):
            download.fetch(kind, season, force=True)
        from pipeline.ingest import membership

        if membership.fetch(season, force=True) is None:
            log(f"ESPN membership for {season} unavailable: carrying last season's D-I set forward")
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
        started = completed_count() > 0
        if results_expected and not started:
            raise SystemExit(f"{season} games were scheduled before {today} but no results were ingested")
        if not started:
            log(f"no completed {season} games yet: preseason ratings; player tables, validation and résumé wait for the first results")
    if live and started:
        # 1b. score timelines for the live season from the cached ESPN summaries (win-probability charts)
        from pipeline.pbp import espn_plays

        log(f"score timelines: {espn_plays.update(season)} games")
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
        # impact v2 for the live season: box prior from players_v2.json, team-adjusted (live RAPM needs live stints)
        from pipeline.players import impact_v2

        P2 = json.loads((ROOT / "pipeline" / "params" / "players_v2.json").read_text())["prior"]
        v2 = impact_v2.season_impacts(season, P2)
        table_path("player_impacts_v2", season).parent.mkdir(parents=True, exist_ok=True)
        v2.to_parquet(table_path("player_impacts_v2", season), index=False)

        # 3. validate
        bad = validate(season, live=True)
        status["validation"] = bad
        if bad:
            raise SystemExit(f"validation failed: {bad}")
        log("validation ok")
        if today.weekday() == 0 and not a.no_ingest:  # weekly canary vs the independent hoopR parse (AUDIT R-4)
            from pipeline.warehouse import canary

            status["canary"] = {k: v for k, v in canary.run(season, today).items() if k != "bad"}
            log(f"canary {status['canary']}")
            if status["canary"].get("verdict"):
                raise SystemExit(f"canary failed: {status['canary']['verdict']}")

    if live:
        # 4. refit ratings for the live season (production params) and refresh dependent artifacts
        G = load_games()
        log(f"refit {season}: {livefit.patch_artifacts(season, G, today)}")
        if started:
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
                                "neutral": up.neutral_site.values, "pm": fp.pm.values, "ph": fp.ph.values, "pa": fp.pa.values, "p": fp.p.values,
                                **({"p_est_lo": fp.pel.values, "p_est_hi": fp.peh.values} if "pel" in fp else {}),
                                "model_version": "adjeff-v1"})
            # a replay/rehearsal of a past date is stamped at that date's scheduled run time, so tip-off ordering stays real
            made_at = datetime.now(timezone.utc).isoformat() if a.today is None else f"{today}T07:30:00+00:00"
            status["logged"] = 0 if a.no_log else plog.append(new, made_at)
        else:
            status["logged"] = 0
        problems = plog.check()
        if problems:
            raise SystemExit(f"prediction log failed verification: {problems}")

        # 6. conference simulations as of today (before exports: watchability uses title leverage)
        conferences.sim_standings(season, str(today), nsim=a.nsim, workers=a.workers, keep_only=True)


    elif not (ROOT / "web" / "public" / "data" / "standings" / f"{cur}.json").exists():
        # offseason: standings demo snapshots for the last completed season (mid-February replay + final actual standings)
        g_ = pd.read_parquet(table_path("games", cur))
        last_ = str(g_[g_.completed].game_date.max().date())
        for d_ in (f"{cur}-02-15", last_):
            conferences.sim_standings(cur, d_, nsim=a.nsim, workers=a.workers)

    # 7. exports (shot shards first: meta.shot_seasons lists what exists). Shards come with the release download;
    # rebuilt when missing, and weekly in season once the source publishes the live season's shots.
    from pipeline.export import shots

    if not (contract.OUT / "shots" / str(cur) / "league.json").exists() or (live and today.weekday() == 0):
        shots.export_shots(cur, force=live)
    upcoming = season if cur != season else None
    contract.export_all(current=cur, upcoming=upcoming)
    players.export_players()
    from pipeline.export import games as game_exports

    game_exports.export_logs()
    from pipeline.export import gamedetail

    gamedetail.export_gamedetail()
    conferences.tiebreak_index()
    conferences.conference_stats(list(range(2010, cur + 1)))
    systems.main()
    from pipeline.export import compare_extras, profiles

    profiles.export_profiles()  # after systems (rating ranks) and shots (shot mix)
    compare_extras.export_compare_extras(cur)
    accuracy.live_summary()
    accuracy.backtest_summary()

    # publish run status for the site footer (AUDIT F-5, R-6)
    gc = pd.read_parquet(table_path("games", cur), columns=["game_date", "completed"])
    status["data_through"] = str(gc[gc.completed].game_date.max().date()) if gc.completed.any() else None
    status.update(live=live, updated=datetime.now(timezone.utc).isoformat())
    contract.write("status.json", {"data_through": status["data_through"], "season": cur, "live": live, "today": str(today),
                                   "updated": status["updated"], "logged": status.get("logged"), "source": "nightly"})

    # 8. size budget (drop order in pipeline/tools/site_size.py), then the static site build
    from pipeline.tools import site_size

    size = site_size.enforce()
    status["site_mb"] = size["final_mb"]
    log(f"site data {size['total_mb']} MB, dropped {[d['rule'] for d in size['dropped']]}")
    if not size["ok"]:
        raise SystemExit(f"site data {size['final_mb']} MB is over the {size['limit_mb']} MB budget after every drop")
    if not a.no_build:
        env = dict(os.environ, NEXT_PUBLIC_BASE_PATH=a.base_path)
        subprocess.run("npx next build", cwd=ROOT / "web", shell=True, check=True, env=env)
    status["seconds"] = round(time.time() - t0)
    (Path(os.environ["CBB_WAREHOUSE"]).parent if a.rehearsal else ROOT / "data").joinpath("nightly_status.json").write_text(json.dumps(status, indent=1, default=str))
    log(f"done in {status['seconds']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
