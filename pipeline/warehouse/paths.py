from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPORT = "mbb"  # parameterized so women's basketball could be added later
RAW = ROOT / "data" / "raw" / "sdv"
WH = ROOT / "data" / "warehouse" / SPORT
PARAMS = ROOT / "pipeline" / "params"
FIRST_SEASON = 2008  # DEFINITION: first season with >=98% box coverage + neutral flag (see DATA_AUDIT.md)


def table_path(table: str, season: int) -> Path:
    return WH / table / f"{season}.parquet"
