"""Site size budget (IMPROVEMENT_PLAN 4.2): measure the exported data, apply the documented drop order when over budget.

    uv run python -m pipeline.tools.site_size [--limit-mb 400] [--dry-run]

Measures web/public/data (the build copies it into web/out; code and fonts add a few MB). When the total exceeds the limit,
shard sets are deleted in this order until it fits, and meta.json records what was kept so the site never requests a
dropped shard:
  1. shot shards (incl. per-game bins) except the latest season
  2. win-probability series older than the latest two seasons (gamedetail, Phase 3b)
  3. player logs before 2020
  4. team logs before 2014
Exit 1 if the site is still over the limit after every drop.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "web" / "public" / "data"
LIMIT_MB = 400  # DEFINITION: size target from SPEC (hard cap 800 MB)


def mb(p: Path) -> float:
    if p.is_file():
        return p.stat().st_size / 1e6
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 1e6


def breakdown(out: Path) -> dict[str, float]:
    return dict(sorted(((p.name, round(mb(p), 1)) for p in out.iterdir()), key=lambda x: -x[1]))


def _season_dirs(out: Path, name: str):
    d = out / name
    return sorted((int(p.name), p) for p in d.iterdir() if p.is_dir() and p.name.isdigit()) if d.exists() else []


def drop_rules(out: Path):
    """(description, meta key, value, paths to delete). Evaluated lazily so each rule sees the current tree."""
    gd = _season_dirs(out, "gamedetail")
    latest = max((y for y, _ in gd), default=None)
    sh = _season_dirs(out, "shots")
    latest_shots = max((y for y, _ in sh), default=None)
    yield ("shot shards except the latest season", "shots_first", latest_shots, [p for y, p in sh if y != latest_shots])
    yield ("win-probability series older than the latest two seasons", "gamedetail_first", (latest or 0) - 1,
           [p for y, p in gd if latest is not None and y < latest - 1])
    yield ("player logs before 2020", "playerlog_first", 2020, [p for y, p in _season_dirs(out, "playerlogs") if y < 2020])
    yield ("team logs before 2014", "teamlog_first", 2014, [p for y, p in _season_dirs(out, "teamlogs") if y < 2014])


def enforce(out: Path = OUT, limit_mb: float = LIMIT_MB, dry: bool = False) -> dict:
    total = mb(out)
    report = {"total_mb": round(total, 1), "limit_mb": limit_mb, "breakdown": breakdown(out), "dropped": []}
    for desc, key, value, paths in drop_rules(out):
        if total <= limit_mb:
            break
        if not paths:
            continue
        freed = sum(mb(p) for p in paths)
        report["dropped"].append({"rule": desc, "freed_mb": round(freed, 1), "meta": {key: value}})
        if not dry:
            for p in paths:
                shutil.rmtree(p) if p.is_dir() else p.unlink()
            meta = out / "meta.json"
            if meta.exists():
                m = json.loads(meta.read_text())
                m.setdefault("limits", {})[key] = value
                meta.write_text(json.dumps(m, separators=(",", ":")))
        total -= freed
    report["final_mb"] = round(total, 1)
    report["ok"] = total <= limit_mb
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-mb", type=float, default=LIMIT_MB)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    r = enforce(OUT, a.limit_mb, a.dry_run)
    print(f"site data {r['total_mb']} MB (limit {r['limit_mb']} MB)")
    for k, v in list(r["breakdown"].items())[:12]:
        print(f"  {k:24} {v:8.1f} MB")
    for d in r["dropped"]:
        print(f"  DROPPED {d['rule']}: {d['freed_mb']} MB")
    print(("OK " if r["ok"] else "OVER BUDGET ") + f"{r['final_mb']} MB")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
