"""Append-only prediction log. Predictions are written before games start and never edited.

Each row carries a hash chained to the previous row, so any later edit or deletion is detectable with verify().
Evaluation always uses the FIRST logged prediction for a game (the earliest, so it cannot be updated after the fact).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pandas as pd

from pipeline.warehouse.paths import ROOT

LOG = Path(os.environ["CBB_PREDICTION_LOG"]) if os.environ.get("CBB_PREDICTION_LOG") else ROOT / "data" / "predictions" / "log.parquet"
FIELDS = ["game_id", "made_at", "game_date", "home_id", "away_id", "neutral", "pm", "ph", "pa", "p", "plo", "phi", "model_version"]


def _hash(prev: str, row: dict) -> str:
    payload = prev + json.dumps({k: (None if pd.isna(row[k]) else row[k]) for k in FIELDS}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def read() -> pd.DataFrame:
    return pd.read_parquet(LOG) if LOG.exists() else pd.DataFrame(columns=FIELDS + ["row_hash"])


def append(new: pd.DataFrame, made_at: str, log_path=None) -> int:
    """Append predictions for games that have not started. Games already logged are skipped (never overwritten)."""
    path = log_path or LOG
    old = pd.read_parquet(path) if path.exists() else pd.DataFrame(columns=FIELDS + ["row_hash"])
    have = set(old.game_id.astype(str))
    new = new[~new.game_id.astype(str).isin(have)].copy()
    if new.empty:
        return 0
    new["made_at"] = made_at
    new["game_id"] = new.game_id.astype(str)
    prev = old.row_hash.iloc[-1] if len(old) else "genesis"
    rows = []
    for r in new[FIELDS].to_dict("records"):
        prev = _hash(prev, r)
        rows.append({**r, "row_hash": prev})
    out = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path, index=False)
    return len(rows)


def verify(log_path=None) -> bool:
    path = log_path or LOG
    if not path.exists():
        return True
    df = pd.read_parquet(path)
    prev = "genesis"
    for r in df[FIELDS + ["row_hash"]].to_dict("records"):
        h = r.pop("row_hash")
        prev = _hash(prev, r)
        if prev != h:
            return False
    return True
