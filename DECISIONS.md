# Decisions
Log of ambiguous choices: date, decision, reason.

- 2026-09-28: The working folder `Possession` is the repo root (SPEC layout shows `cbb_analytics/` as root). The GitHub repo is to be named `cbb_analytics`. Reason: stay inside the given folder.
- 2026-09-28: Creating the public GitHub repo was denied by the permission classifier. Work continues locally with git only; all GitHub steps (push, release assets, Pages, Actions dispatch) are blocked until the user allows repo creation. See KNOWN_ISSUES.md.
- 2026-09-28: Start season = 2008. Threshold: >=98% of completed games with both team and player boxes and a populated neutral flag (2008 first qualifies; neutral flag missing before). 2003-2007 excluded from fits.
- 2026-09-28: Do not use `mbb_ratings` / `mbb_player_value` release files (unclear provenance, third-party opinions would contaminate our ratings).
- 2026-09-28: Season convention: season = year the season ends.
- 2026-09-29: Ridge lam, recency, blowout cap, team-specific HCA, tempo lam chosen by walk-forward grids (pipeline/models/tune.py). Team-specific HCA rejected; calibration chosen by walk-forward log loss (Platt). Minor limitation: tempo config in efficiency grid was fixed at (2,60); burn-in seasons 2010-11 configs chosen with seasons<2012.
- BLAS threads pinned to 1 (pipeline/__init__.py, conftest.py): 1000x speedup.
