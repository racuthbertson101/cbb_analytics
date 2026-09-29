"""Phase 9 stretch: compare the box-score impact rating (v1) with the published NCAA RAPM dataset (sportsdataverse ncaa_mbb_rapm, 2011-2020).

RAPM rows are keyed by NCAA ids and names ("FIRST.LAST", team name), so players are matched by season + team + normalized name.
This is a comparison only: RAPM is not used in any rating.
"""
from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd
import requests
from scipy.stats import spearmanr

from pipeline.warehouse.paths import PARAMS, ROOT, table_path

URL = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/ncaa_mbb_rapm/ncaa_mbb_rapm_{y}.parquet"
RAW = ROOT / "data" / "raw" / "ncaa"


def norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", str(s).lower())


def load_rapm(y: int) -> pd.DataFrame | None:
    p = RAW / f"rapm_{y}.parquet"
    if not p.exists():
        r = requests.get(URL.format(y=y), headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        if r.status_code != 200:
            return None
        RAW.mkdir(parents=True, exist_ok=True)
        p.write_bytes(r.content)
    d = pd.read_parquet(p)
    d = d[d.estimand == "league"] if "estimand" in d else d
    d["key_name"] = d.player.map(norm)
    d["key_team"] = d.team.map(norm)
    return d


def main(seasons=range(2011, 2021)):
    rows, per = [], {}
    for y in seasons:
        rp = load_rapm(y)
        if rp is None or not table_path("player_impacts", y).exists():
            continue
        pi = pd.read_parquet(table_path("player_impacts", y))
        tm = pd.read_parquet(table_path("teams", y)).set_index("team_id")
        pi = pi.assign(key_name=pi["name"].map(norm), key_team=pi.team_id.map(tm.location).map(norm))
        m = pi.merge(rp[["key_name", "key_team", "orapm", "drapm", "rapm_net", "off_poss"]], on=["key_name", "key_team"])
        m = m[(m["min"] >= 300)]
        if len(m) < 100:
            continue
        per[str(y)] = {"n_matched": int(len(m)), "n_rapm": int(len(rp)), "corr_net": float(np.corrcoef(m.imp, m.rapm_net)[0, 1]),
                       "corr_off": float(np.corrcoef(m.imp_o, m.orapm)[0, 1]), "corr_def": float(np.corrcoef(m.imp_d, m.drapm)[0, 1]),
                       "spearman_net": float(spearmanr(m.imp, m.rapm_net)[0])}
        rows.append(m.assign(season=y))
    A = pd.concat(rows)
    out = {"per_season": per, "pooled": {"n": int(len(A)), "corr_net": float(np.corrcoef(A.imp, A.rapm_net)[0, 1]), "corr_off": float(np.corrcoef(A.imp_o, A.orapm)[0, 1]),
                                         "corr_def": float(np.corrcoef(A.imp_d, A.drapm)[0, 1]), "spearman_net": float(spearmanr(A.imp, A.rapm_net)[0])},
           "note": "Matched by season+team+name for players with >=300 minutes. RAPM is the published NCAA dataset; it is a comparison only."}
    # how much of RAPM does the box rating explain, with a fitted scale?
    b = np.polyfit(A.imp, A.rapm_net, 1)
    out["pooled"]["slope_rapm_on_box"] = float(b[0])
    (PARAMS / "rapm_compare.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out["pooled"], indent=1))
    print({k: (v["n_matched"], round(v["corr_net"], 3)) for k, v in per.items()})


if __name__ == "__main__":
    main()
