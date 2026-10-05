from datetime import date

from pipeline.nightly import in_full_window, main, season_of


def test_season_of():
    assert season_of(date(2026, 9, 28)) == 2027 and season_of(date(2027, 3, 1)) == 2027 and season_of(date(2026, 4, 6)) == 2026


def test_full_run_window_november_to_mid_april():
    assert in_full_window(date(2026, 11, 1)) and in_full_window(date(2027, 1, 15)) and in_full_window(date(2027, 4, 15))
    assert not in_full_window(date(2027, 4, 16)) and not in_full_window(date(2026, 10, 31)) and not in_full_window(date(2026, 7, 4))


def test_check_mode_writes_github_output(tmp_path, monkeypatch):
    out = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    assert main(["--check", "--today", "2026-10-04"]) == 0  # offseason Sunday: skip
    assert main(["--check", "--today", "2026-10-05"]) == 0  # offseason Monday: light run
    assert main(["--check", "--today", "2026-10-04", "--force"]) == 0
    assert main(["--check", "--today", "2026-12-02"]) == 0
    assert out.read_text().split() == ["run=false", "run=true", "run=true", "run=true"]


def test_rehearsal_points_every_path_at_scratch_copies(tmp_path):
    """Phase 2.7: a rehearsal never writes the real warehouse, artifacts or prediction log."""
    import json
    import subprocess
    import sys

    import pytest

    from pipeline.nightly import setup_rehearsal
    from pipeline.warehouse.paths import ROOT

    if not (ROOT / "data" / "warehouse").exists() or not (ROOT / "data" / "backtest").exists():
        pytest.skip("warehouse not built")
    env = setup_rehearsal(date(2026, 11, 2), root=tmp_path / "reh")
    code = ("import json; from pipeline.warehouse.paths import WH; from pipeline.models.backtest import BT; "
            "from pipeline.predictions import log; print(json.dumps([str(WH), str(BT), str(log.DIR)]))")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env={**__import__("os").environ, **env}, capture_output=True, text=True, check=True)
    paths = json.loads(out.stdout.strip().splitlines()[-1])
    assert all(str(tmp_path / "reh") in p for p in paths), paths
    assert (tmp_path / "reh" / "predictions" / "HEAD.json").exists()
