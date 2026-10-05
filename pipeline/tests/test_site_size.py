import json

from pipeline.tools.site_size import enforce


def _tree(tmp_path):
    for y in (2017, 2019, 2021):
        d = tmp_path / "playerlogs" / str(y)
        d.mkdir(parents=True)
        (d / "1.json").write_bytes(b"x" * 300_000)
    for y in (2012, 2016):
        d = tmp_path / "teamlogs" / str(y)
        d.mkdir(parents=True)
        (d / "1.json").write_bytes(b"x" * 100_000)
    (tmp_path / "meta.json").write_text(json.dumps({"current_season": 2026}))
    return tmp_path


def test_under_budget_drops_nothing(tmp_path):
    r = enforce(_tree(tmp_path), limit_mb=5)
    assert r["ok"] and r["dropped"] == []


def test_drop_order_until_under_budget(tmp_path):
    out = _tree(tmp_path)
    r = enforce(out, limit_mb=0.55)  # 1.1 MB: player logs before 2020 go first (frees 0.6 MB)
    assert r["ok"] and [d["rule"] for d in r["dropped"]] == ["player logs before 2020"]
    assert not (out / "playerlogs" / "2017").exists() and (out / "playerlogs" / "2021").exists() and (out / "teamlogs" / "2012").exists()
    assert json.loads((out / "meta.json").read_text())["limits"] == {"playerlog_first": 2020}


def test_still_over_budget_fails(tmp_path):
    r = enforce(_tree(tmp_path), limit_mb=0.1)
    assert not r["ok"] and len(r["dropped"]) == 2
