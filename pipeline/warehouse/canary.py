"""Weekly canary (AUDIT R-4): compare the last week's ESPN-ingested team box scores with the independent hoopR release.

The nightly ingest parses ESPN JSON itself; the sportsdataverse/hoopR release parses the same games with different code. If
the two disagree on points or field-goal attempts for more than a few games, one parser has drifted.

    python -m pipeline.warehouse.canary 2027 2027-01-12
"""
from __future__ import annotations

import sys
from datetime import date, timedelta

import pandas as pd

from .paths import table_path

MIN_AGREE = 0.98    # DEFINITION: share of overlapping team-games that must agree on points and FGA
MIN_OVERLAP = 50    # DEFINITION: below this many overlapping team-games the canary reports but does not judge


def compare(ours: pd.DataFrame, ref: pd.DataFrame) -> dict:
    """ours/ref: team-game rows with game_id, team_id, points, fga. Returns overlap size, agreement share and examples."""
    k = ["game_id", "team_id"]
    m = ours[k + ["points", "fga"]].merge(ref[k + ["points", "fga"]], on=k, suffixes=("", "_ref"))
    if m.empty:
        return {"overlap": 0, "agree": None, "bad": []}
    ok = (m.points.astype(float) == m.points_ref.astype(float)) & (m.fga.astype(float) == m.fga_ref.astype(float))
    return {"overlap": int(len(m)), "agree": float(ok.mean()), "bad": m[~ok].head(5).to_dict("records")}


def verdict(res: dict) -> str | None:
    """Failure message, or None when the canary passes or has too little overlap to judge."""
    if res["overlap"] < MIN_OVERLAP or res["agree"] is None:
        return None
    if res["agree"] < MIN_AGREE:
        return f"ESPN ingest disagrees with hoopR on {1 - res['agree']:.1%} of {res['overlap']} team-games, e.g. {res['bad'][:2]}"
    return None


def run(season: int, today: date) -> dict:
    from pipeline.ingest import download

    p = download.fetch("team_box", season, force=True)
    if p is None:
        return {"overlap": 0, "agree": None, "bad": [], "note": "hoopR release not available for this season"}
    ref = pd.read_parquet(p, columns=["game_id", "team_id", "team_score", "field_goals_attempted"])
    ref = ref.rename(columns={"team_score": "points", "field_goals_attempted": "fga"})
    for c in ("game_id", "team_id"):
        ref[c] = pd.to_numeric(ref[c], errors="coerce").astype("Int64").astype(str)
    ours = pd.read_parquet(table_path("team_games", season))
    ours = ours[ours.game_date >= pd.Timestamp(today - timedelta(days=7))]
    res = compare(ours, ref)
    res["verdict"] = verdict(res)
    return res


if __name__ == "__main__":
    r = run(int(sys.argv[1]), date.fromisoformat(sys.argv[2]))
    print({k: v for k, v in r.items() if k != "bad"}, r["bad"][:2])
