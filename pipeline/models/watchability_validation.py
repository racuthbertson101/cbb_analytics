"""External check of the watchability score (IMPROVEMENT_PLAN Phase 5b.3): do higher scores go with national TV and crowds?

For completed D-I games of the seasons with broadcast data, Spearman rank correlation of the exported score (and of each
component) with (a) a national-TV flag and (b) attendance. The star-power component is also scored with v1 and v2 impacts.
Watchability weights stay a judgment call; this only reports how well the result agrees with what TV and fans choose.

    python -m pipeline.models.watchability_validation
"""
from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from pipeline.export.contract import OUT
from pipeline.warehouse.paths import PARAMS, table_path

# DEFINITION: national = broadcast or national cable networks; streaming-only (ESPN+, Peacock-only feeds) and regional/conference
# networks are not national.
NATIONAL = re.compile(r"\b(ABC|CBS|NBC|FOX|ESPN|ESPN2|ESPNU|ESPNEWS|FS1|FS2|TBS|TNT|truTV|CBSSN|CBS Sports Network)\b", re.I)
STREAMING = re.compile(r"ESPN\+|ESPN3|Peacock|Paramount\+|FloSports|Max\b", re.I)
COMP = ["quality", "competitiveness", "tempo", "star_power", "stakes"]


def national(tv) -> bool:
    if not isinstance(tv, str) or not tv:
        return False
    parts = [p.strip() for p in tv.split(",")]
    return any(NATIONAL.search(p) and not STREAMING.search(p) for p in parts)


def season_rows(y: int) -> pd.DataFrame | None:
    gp = OUT / "games" / f"{y}.json"
    if not gp.exists() or not table_path("games", y).exists():
        return None
    G = pd.DataFrame(json.loads(gp.read_text())["games"])
    G = G[G.ok & G.d1 & G.w.notna()].copy()
    if "tv" not in G or G.tv.notna().mean() < 0.5:  # the games export carries tv and attendance (att)
        return None
    G["national"] = G.tv.map(national).astype(float)
    G["attendance"] = pd.to_numeric(G.get("att"), errors="coerce")
    for i, c in enumerate(COMP):
        G[c] = G.wc.map(lambda v, i=i: v[i] if isinstance(v, list) else np.nan)
    G["season"] = y
    return G


def rho(a, b) -> float | None:
    m = pd.notna(a) & pd.notna(b)
    return None if m.sum() < 50 else round(float(spearmanr(a[m], b[m]).statistic), 3)


def run(seasons=range(2016, 2027)) -> dict:
    rows = [r for y in seasons if (r := season_rows(y)) is not None]
    D = pd.concat(rows, ignore_index=True)
    att = D.attendance.where(D.attendance > 0)
    out = {"definition_national": NATIONAL.pattern, "seasons": sorted(int(s) for s in D.season.unique()), "n_games": int(len(D)),
           "national_share": round(float(D.national.mean()), 3),
           "score": {"vs_national_tv": rho(D.w, D.national), "vs_attendance": rho(D.w, att)},
           "components": {c: {"vs_national_tv": rho(D[c], D.national), "vs_attendance": rho(D[c], att)} for c in COMP},
           "by_season": {str(int(y)): {"n": int(len(g)), "vs_national_tv": rho(g.w, g.national), "vs_attendance": rho(g.w, g.attendance.where(g.attendance > 0))}
                         for y, g in D.groupby("season")},
           "note": "Spearman rank correlations over completed D-I games; positive = higher watchability goes with national TV / bigger crowds."}
    (PARAMS / "watchability_validation.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    print(json.dumps({k: v for k, v in run().items() if k != "by_season"}, indent=1))
