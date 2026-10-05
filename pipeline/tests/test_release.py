"""Manifest-based release sync (AUDIT R-2): change-only uploads, manifest last, failures leave the old manifest valid."""
import pandas as pd
import pytest

from pipeline import release


@pytest.fixture
def fake_data(tmp_path, monkeypatch):
    wh = tmp_path / "wh"
    for t, y in (("games", 2026), ("games", 2027), ("teams", 2026)):
        (wh / t).mkdir(parents=True, exist_ok=True)
        pd.DataFrame({"x": [y, len(t)]}).to_parquet(wh / t / f"{y}.parquet", index=False)
    art = tmp_path / "backtest"
    art.mkdir()
    (art / "a.json").write_text("{}")
    monkeypatch.setattr(release, "WH", wh)
    monkeypatch.setattr(release, "ART", art)
    monkeypatch.setattr(release, "SHOTS", tmp_path / "noshots")
    monkeypatch.setattr(release, "STAGE", tmp_path / "stage")
    return wh


def _published():
    local = release.local_files()
    return {"updated": "x", "files": {k: {"asset": release.versioned(k, v["sha256"]), "sha256": v["sha256"]} for k, v in local.items()}}


def test_nothing_changed_uploads_only_the_manifest(fake_data):
    sent = []
    out = release.upload(remote=_published(), uploader=lambda p: sent.append(p.name))
    assert out["changed"] == [] and sent == ["manifest.json"]


def test_only_changed_file_uploaded_under_a_new_name(fake_data):
    remote = _published()
    pd.DataFrame({"x": [1, 2, 3]}).to_parquet(fake_data / "games" / "2027.parquet", index=False)
    sent = []
    out = release.upload(remote=remote, uploader=lambda p: sent.append(p.name))
    assert out["changed"] == ["games__2027.parquet"]
    assert len(sent) == 2 and sent[0].startswith("games__2027.") and sent[0] != remote["files"]["games__2027.parquet"]["asset"] and sent[-1] == "manifest.json"
    assert out["manifest"]["files"]["games__2026.parquet"] == remote["files"]["games__2026.parquet"]


def test_tarball_hash_ignores_timestamps(fake_data):
    a = release.local_files()["model_artifacts.tar.gz"]["sha256"]
    (release.ART / "a.json").touch()
    assert release.local_files()["model_artifacts.tar.gz"]["sha256"] == a


def test_failure_mid_upload_leaves_previous_manifest(fake_data):
    remote = _published()
    for t in ("games", "teams"):
        pd.DataFrame({"x": [9]}).to_parquet(fake_data / t / "2026.parquet", index=False)
    sent = []

    def flaky(p):
        if len(sent) == 1:
            raise RuntimeError("network down")
        sent.append(p.name)

    with pytest.raises(RuntimeError):
        release.upload(remote=remote, uploader=flaky)
    assert "manifest.json" not in sent  # the published manifest was never replaced
    assert all(v["asset"] not in sent for v in remote["files"].values())  # and nothing it references was overwritten
