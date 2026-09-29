"""Cached downloader for sportsdataverse release assets (polite: low concurrency, retries, disk cache)."""
from __future__ import annotations
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

BASE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download"
RAW = Path(__file__).resolve().parents[2] / "data" / "raw" / "sdv"
UA = {"User-Agent": "Mozilla/5.0 (cbb_analytics research; contact via repo)"}

TAGS = {
    "schedules": ("espn_mens_college_basketball_schedules", "mbb_schedule_{y}.parquet"),
    "team_box": ("espn_mens_college_basketball_team_boxscores", "team_box_{y}.parquet"),
    "player_box": ("espn_mens_college_basketball_player_boxscores", "player_box_{y}.parquet"),
    "standings": ("espn_mens_college_basketball_standings", "standings_{y}.parquet"),
    "rosters": ("espn_mens_college_basketball_rosters", "rosters_{y}.parquet"),
    "team_season_stats": ("espn_mens_college_basketball_team_season_stats", "team_season_stats_{y}.parquet"),
    "player_season_stats": ("espn_mens_college_basketball_player_season_stats", "player_season_stats_{y}.parquet"),
    "pbp": ("espn_mens_college_basketball_pbp", "play_by_play_{y}.parquet"),
    "shots": ("espn_mens_college_basketball_shots", "shots_{y}.parquet"),
}

def fetch(kind: str, year: int, force: bool = False) -> Path | None:
    tag, pat = TAGS[kind]
    name = pat.format(y=year)
    dest = RAW / kind / name
    if dest.exists() and dest.stat().st_size > 0 and not force:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"{BASE}/{tag}/{name}"
    for attempt in range(4):
        try:
            r = requests.get(url, headers=UA, timeout=120)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            tmp = dest.with_suffix(".part")
            tmp.write_bytes(r.content)
            tmp.replace(dest)
            return dest
        except Exception:
            time.sleep(2 ** attempt)
    return None

def fetch_all(kind: str, years, workers: int = 3):
    with ThreadPoolExecutor(workers) as ex:
        return dict(zip(years, ex.map(lambda y: fetch(kind, y), years)))

if __name__ == "__main__":
    import sys
    kinds = sys.argv[1].split(",")
    y0, y1 = int(sys.argv[2]), int(sys.argv[3])
    for k in kinds:
        res = fetch_all(k, range(y0, y1 + 1))
        print(k, sum(v is not None for v in res.values()), "of", len(res))
