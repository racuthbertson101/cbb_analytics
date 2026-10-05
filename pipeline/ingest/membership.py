"""D-I conference membership for a season from ESPN's core API (groups/50 = NCAA Division I).

Used for seasons whose sportsdataverse standings file does not exist yet (the upcoming season). About 65 small
requests per season, all cached under data/raw/espn/groups/. The parsed table is written to
data/raw/espn/membership/membership_<season>.parquet, which the warehouse build reads.

    python -m pipeline.ingest.membership 2027 [--force]
"""
from __future__ import annotations

import re
import sys

import pandas as pd

from .espn import RAW, _get

CORE = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/seasons/{y}/types/2/groups"
MIN_TEAMS = 300  # DEFINITION: sanity floor; a smaller answer means ESPN has not populated the season yet


def path(season: int):
    return RAW / "membership" / f"membership_{season}.parquet"


def _ids(items, kind):
    return [re.search(rf"{kind}/(\d+)", i["$ref"]).group(1) for i in items]


def fetch(season: int, force: bool = False) -> pd.DataFrame | None:
    base = CORE.format(y=season)
    cache = RAW / "groups" / str(season)
    kids = _get(f"{base}/50/children", {"limit": 100}, cache / "children.json", force)
    if not kids or not kids.get("items"):
        return None
    rows = []
    for gid in _ids(kids["items"], "groups"):
        g = _get(f"{base}/{gid}", {}, cache / f"g{gid}.json", force)
        t = _get(f"{base}/{gid}/teams", {"limit": 100}, cache / f"g{gid}_teams.json", force)
        if not g or not t:
            continue
        for tid in _ids(t.get("items", []), "teams"):
            rows.append({"team_id": tid, "conf_id": float(gid), "conference": g["name"], "season": season})
    df = pd.DataFrame(rows).drop_duplicates("team_id")
    if len(df) < MIN_TEAMS:
        return None
    path(season).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path(season), index=False)
    return df


if __name__ == "__main__":
    df = fetch(int(sys.argv[1]), force="--force" in sys.argv)
    print("no membership" if df is None else f"{len(df)} teams in {df.conf_id.nunique()} conferences")
