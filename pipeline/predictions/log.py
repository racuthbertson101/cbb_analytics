"""Append-only prediction log, stored in git so it cannot be lost or rewritten silently (AUDIT R-1).

Layout (repo root, committed by the nightly workflow's sync job):
    predictions/log/YYYY/MM-DD.csv   rows written on that UTC date (each night adds a file; rows are never edited)
    predictions/HEAD.json            {"rows": n, "last_hash": ...}: the chain head after the latest append

Every row carries a SHA-256 hash chained to the previous row. verify() recomputes the chain and fails when a row was
edited, when rows are missing (the log is shorter than HEAD), or when HEAD itself is missing while rows exist. Because
both the rows and HEAD are in git history, rewriting the past also shows up as a rewritten commit.

Every night logs a prediction for every scheduled game in the next 7 days (AUDIT R-3). Scoring uses, for each game, the
LAST prediction made before tip-off (`scored()`), so the live accuracy measures next-day predictions like the backtest.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pandas as pd

from pipeline.warehouse.paths import ROOT

DIR = Path(os.environ["CBB_PREDICTION_LOG"]) if os.environ.get("CBB_PREDICTION_LOG") else ROOT / "predictions"
FIELDS = ["game_id", "made_at", "game_date", "home_id", "away_id", "neutral", "pm", "ph", "pa", "p", "model_version"]
# schema 3 (Phase 5c.2): the 80% range of our estimate of p. Optional: a row without them (schema 2) hashes exactly as before,
# so the chain verifies across the schema bump.
OPTIONAL = ["p_est_lo", "p_est_hi"]
STR = ["game_id", "made_at", "game_date", "home_id", "away_id", "model_version"]
DECIMALS = {"pm": 2, "ph": 2, "pa": 2, "p": 4}  # DEFINITION: stored precision; rounding first makes CSV round trips hash-stable
SCHEMA = 3  # 1 = old parquet log (never had live rows); 2 = git CSV log; 3 = adds optional p_est_lo/p_est_hi


def _canon(r: dict) -> dict:
    out = {k: str(r[k]) for k in STR}
    out["neutral"] = bool(r["neutral"]) if not isinstance(r["neutral"], str) else r["neutral"] == "True"
    out.update({k: round(float(r[k]), d) for k, d in DECIMALS.items()})
    for k in OPTIONAL:  # only when present: older rows keep their original payload and hash
        v = r.get(k)
        if v is not None and v == v and v != "":
            out[k] = round(float(v), 4)
    return out


def _hash(prev: str, row: dict) -> str:
    return hashlib.sha256((prev + json.dumps(row, sort_keys=True)).encode()).hexdigest()


def _files(d: Path) -> list[Path]:
    return sorted((d / "log").glob("*/*.csv"))


def _head(d: Path) -> dict | None:
    p = d / "HEAD.json"
    return json.loads(p.read_text()) if p.exists() else None


def read(log_dir: Path | None = None) -> pd.DataFrame:
    d = log_dir or DIR
    fs = _files(d)
    if not fs:
        return pd.DataFrame(columns=FIELDS + ["row_hash"])
    return pd.concat([pd.read_csv(f, dtype={k: str for k in STR + ["row_hash"]}) for f in fs], ignore_index=True)


def append(new: pd.DataFrame, made_at: str, log_dir: Path | None = None) -> int:
    """Log one prediction per game for this run. A game already logged on the same UTC date (a re-run) is skipped."""
    d = log_dir or DIR
    problems = check(d)
    if problems:
        raise RuntimeError(f"refusing to append to a log that fails verification: {problems}")
    old = read(d)
    day = made_at[:10]
    have = set(old.game_id[old.made_at.str[:10] == day]) if len(old) else set()
    new = new.assign(made_at=made_at, game_id=new.game_id.astype(str))
    new = new[~new.game_id.isin(have)].drop_duplicates("game_id")
    if new.empty:
        return 0
    head = _head(d) or {"rows": 0, "last_hash": "genesis"}
    prev, rows = head["last_hash"], []
    cols = FIELDS + [k for k in OPTIONAL if k in new]
    for r in new[cols].to_dict("records"):
        c = _canon(r)
        prev = _hash(prev, c)
        rows.append({**c, "row_hash": prev})
    f = d / "log" / day[:4] / f"{day[5:]}.csv"
    f.parent.mkdir(parents=True, exist_ok=True)
    cols_out = FIELDS + [k for k in OPTIONAL if any(k in x for x in rows)] + ["row_hash"]
    if f.exists():  # keep the day file's header; a same-day re-run cannot add columns mid-file
        cols_out = list(pd.read_csv(f, nrows=0).columns)
    pd.DataFrame(rows).reindex(columns=cols_out).to_csv(f, mode="a", header=not f.exists(), index=False)
    (d / "HEAD.json").write_text(json.dumps({"rows": head["rows"] + len(rows), "last_hash": prev, "updated": made_at, "schema": SCHEMA}, indent=1))
    return len(rows)


def check(log_dir: Path | None = None) -> list[str]:
    """Problems with the log (empty list = intact)."""
    d = log_dir or DIR
    head, fs = _head(d), _files(d)
    if head is None:
        return ["rows exist but predictions/HEAD.json is missing"] if fs else []
    df = read(d)
    if len(df) < head["rows"]:
        return [f"log has {len(df)} rows but HEAD says {head['rows']} (rows deleted or files missing)"]
    if len(df) > head["rows"]:
        return [f"log has {len(df)} rows but HEAD says {head['rows']} (rows added without updating HEAD)"]
    prev = "genesis"
    for i, r in enumerate(df.to_dict("records")):
        prev = _hash(prev, _canon(r))
        if prev != r["row_hash"]:
            return [f"row {i} (game {r['game_id']}, made {r['made_at']}) does not match its hash: edited"]
    if head["rows"] and prev != head["last_hash"]:
        return ["chain end does not match HEAD.last_hash"]
    return []


def verify(log_dir: Path | None = None) -> bool:
    return not check(log_dir)


def scored(L: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """The scored prediction per game: the last one made before tip-off, with days_before (game date minus made date).

    games needs game_id, game_date and game_datetime (UTC, naive). Without a tip-off time the game is assumed to start at
    16:00 UTC (11 am / noon Eastern) on its date.
    DEFINITION: 16:00 UTC is a conservative earliest-tip default, not a fitted value.
    """
    if L.empty:
        return L.assign(days_before=pd.Series(dtype=int))
    g = games[["game_id", "game_date", "game_datetime"]].copy()
    g["tip"] = g.game_datetime.fillna(pd.to_datetime(g.game_date) + pd.Timedelta(hours=16))
    m = L.drop(columns=["game_date"]).merge(g, on="game_id", how="inner")
    made = pd.to_datetime(m.made_at, utc=True).dt.tz_localize(None)
    m = m[made < m.tip].assign(_made=made[made < m.tip])
    m = m.sort_values(["game_id", "_made"]).drop_duplicates("game_id", keep="last")
    m["days_before"] = (pd.to_datetime(m.game_date).dt.normalize() - m._made.dt.normalize()).dt.days
    return m.drop(columns=["_made", "tip"])
