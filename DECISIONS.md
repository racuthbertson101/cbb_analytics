# Decisions
Log of ambiguous choices: date, decision, reason.

- 2026-09-28: The working folder `Possession` is the repo root (SPEC layout shows `cbb_analytics/` as root). The GitHub repo is to be named `cbb_analytics`. Reason: stay inside the given folder.
- 2026-09-28: Creating the public GitHub repo was denied by the permission classifier. Work continues locally with git only; all GitHub steps (push, release assets, Pages, Actions dispatch) are blocked until the user allows repo creation. See KNOWN_ISSUES.md.
- 2026-09-28: Start season = 2008. Threshold: >=98% of completed games with both team and player boxes and a populated neutral flag (2008 first qualifies; neutral flag missing before). 2003-2007 excluded from fits.
- 2026-09-28: Do not use `mbb_ratings` / `mbb_player_value` release files (unclear provenance, third-party opinions would contaminate our ratings).
- 2026-09-28: Season convention: season = year the season ends.
- 2026-09-29: Ridge lam, recency, blowout cap, team-specific HCA, tempo lam chosen by walk-forward grids (pipeline/models/tune.py). Team-specific HCA rejected; calibration chosen by walk-forward log loss (Platt). Minor limitation: tempo config in efficiency grid was fixed at (2,60); burn-in seasons 2010-11 configs chosen with seasons<2012.
- BLAS threads pinned to 1 (pipeline/__init__.py, conftest.py): 1000x speedup.
- 2026-09-29: Conference tiebreaker status = verified only if the ordered rule text was found on an official conference page (19 of 31); others fallback with best-known rules. NET/RPI steps replaced by our rating (labeled). Tournament field sizes taken from 2026 data/known format (config values, not verified).
- Standings sims are produced for replay snapshots (2026-02-15 + final); the nightly job will sim the live date with 20,000 sims.
- 2026-09-29: Nightly downloads ALL seasons of the small warehouse tables (not only current+previous): Elo, consensus and the site exports use full history. PBP/shots never published. Model artifacts (data/backtest) and the prediction log ride along as release assets.
- 2026-09-29: ESPN needs a plain `Mozilla/5.0` User-Agent (unusual agents and a full Chrome string sent by requests get HTTP 403).
- 2026-09-29: Bug found and fixed: the standings loader dropped teams that appear in the "College Basketball Crown" pseudo-group before deduping (Oklahoma lost D-I status in 2025-26); all model artifacts were refit after the fix.
- 2026-09-29: Offseason nightly behaviour: when the upcoming season has no completed games, only its schedule/rosters are refreshed and the site shows the last completed season plus preseason projections.
- 2026-09-29: frontend-design skill installed from github.com/anthropics/skills into .claude/skills/frontend-design.
