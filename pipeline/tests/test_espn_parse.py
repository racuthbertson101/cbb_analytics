import pandas as pd
import pytest

from pipeline.ingest import espn
from pipeline.warehouse.paths import table_path

SB = espn.RAW / "scoreboard" / "20260321.json"
SM = espn.RAW / "summary" / "401856532.json"
pytestmark = pytest.mark.skipif(not (SB.exists() and SM.exists() and table_path("games", 2026).exists()), reason="ESPN cache or warehouse missing")


def test_scoreboard_and_summary_parse_match_warehouse():
    import json
    b = espn.parse_scoreboard(json.loads(SB.read_text()))
    g = b[b.game_id == "401856532"].iloc[0]
    assert g.home_id == "130" and g.away_id == "139" and g.home_score == 95 and g.away_score == 72 and g.completed and g.neutral_site
    t, p = espn.parse_summary(json.loads(SM.read_text()), "401856532", g.to_dict())
    wt = pd.read_parquet(table_path("team_games", 2026))
    wt = wt[wt.game_id == "401856532"].set_index("team_id")
    for r in t:
        w = wt.loc[r["team_id"]]
        assert r["fga"] == w.fga and r["tov"] == w.tov and r["points"] == w.points and r["opp_fga"] == w.opp_fga
    assert len(p) > 10 and sum(x["points"] for x in p if x["team_id"] == "130" and x["points"] == x["points"]) == 95
