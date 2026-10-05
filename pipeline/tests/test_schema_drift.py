"""ESPN schema drift must fail loudly (AUDIT R-4): missing keys, null box stats, or disagreement with hoopR."""
import copy
import json
from pathlib import Path

import pandas as pd
import pytest

from pipeline.ingest import espn
from pipeline.warehouse import canary, validate as V
from pipeline.warehouse.paths import table_path

FIX = json.loads((Path(__file__).parent / "fixtures" / "espn_summary_401856532.json").read_text(encoding="utf8"))
ROW = {"home_id": "130", "away_id": "139", "home_score": 95.0, "away_score": 72.0}


def test_fixture_parses():
    t, p = espn.parse_summary(FIX, "401856532", ROW)
    assert len(t) == 2 and {r["team_id"] for r in t} == {"130", "139"} and len(p) > 10


def test_renamed_team_stat_fails():
    d = copy.deepcopy(FIX)
    for x in d["boxscore"]["teams"][0]["statistics"]:
        if x["name"] == "turnovers":
            x["name"] = "totalTurnoversRenamed"
    with pytest.raises(espn.SchemaError, match="turnovers"):
        espn.parse_summary(d, "401856532", ROW)


def test_missing_player_key_fails():
    d = copy.deepcopy(FIX)
    grp = d["boxscore"]["players"][1]["statistics"][0]
    i = grp["keys"].index("minutes")
    grp["keys"][i] = "mins"
    with pytest.raises(espn.SchemaError, match="minutes"):
        espn.parse_summary(d, "401856532", ROW)


def test_null_box_stats_fail_validation(tmp_path, monkeypatch):
    if not table_path("team_games", 2026).exists():
        pytest.skip("warehouse not built")
    for t in ("games", "team_games", "player_games"):
        (tmp_path / t).mkdir()
        pd.read_parquet(table_path(t, 2026)).to_parquet(tmp_path / t / "2026.parquet", index=False)
    monkeypatch.setattr(V, "table_path", lambda t, y: tmp_path / t / f"{y}.parquet")
    assert V.validate(2026, live=True) == []
    tg = pd.read_parquet(tmp_path / "team_games" / "2026.parquet")
    tg.loc[tg.sample(frac=0.05, random_state=1).index, "fga"] = float("nan")  # ESPN renamed a field: values went missing
    tg.to_parquet(tmp_path / "team_games" / "2026.parquet", index=False)
    assert any("fga missing" in b for b in V.validate(2026, live=True))


def test_canary_flags_disagreement():
    ours = pd.DataFrame({"game_id": [str(i) for i in range(100)], "team_id": "1", "points": 70.0, "fga": 60.0})
    ref = ours.copy()
    assert canary.verdict(canary.compare(ours, ref)) is None
    ref.loc[:9, "fga"] = 0.0  # 10% disagree
    assert "disagrees" in canary.verdict(canary.compare(ours, ref))
    assert canary.verdict(canary.compare(ours.head(10), ref.head(10))) is None  # too little overlap to judge
