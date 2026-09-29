import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPORT = "mbb"  # parameterized so women's basketball could be added later
RAW = ROOT / "data" / "raw" / "sdv"
WH = Path(os.environ["CBB_WAREHOUSE"]) / SPORT if os.environ.get("CBB_WAREHOUSE") else ROOT / "data" / "warehouse" / SPORT  # override for replay/tests
PARAMS = ROOT / "pipeline" / "params"
CURRENT_SEASON = int(os.environ.get("CBB_CURRENT_SEASON", 2026))  # latest season with ratings (the live season during play)
FIRST_SEASON = 2008  # DEFINITION: first season with >=98% box coverage + neutral flag (see DATA_AUDIT.md)


def table_path(table: str, season: int) -> Path:
    return WH / table / f"{season}.parquet"
