# Known issues

- BLOCKER: `gh repo create cbb_analytics --public` was denied by the auto-mode permission classifier ([Create Public Surface]). No remote exists. Blocks: pushes, `warehouse` release assets, GitHub Pages deploy, Actions dispatch. Owner action: create the repo (or allow the command), then `git remote add origin ...; git push -u origin main`.
- Source gap: NCAA tournament game counts are short in 2009 (58), 2010 (55), 2013 (55), 2017 (65) versus 67 expected; missing games are absent in the ESPN/hoopR schedule. Ratings use what exists.
- Game type heuristic: conference tournament games without headline on non-neutral sites are labeled `regular` (definition documented in build.py).
- Phase 3 live deploy (GitHub Pages) not done: no repo. `make site` builds web/out locally. basePath is env NEXT_PUBLIC_BASE_PATH.
- Player impact v1 (box-score): scale is inflated for extreme rebounders/shot-blockers (ecological regression on team averages) and defense R2 is ~0.45; top of the leaderboard skews to rim-protecting bigs. Kept as labeled v1; RAPM (Phase 9) is the intended upgrade.
- Roster-based preseason prior failed walk-forward CV (better in 6/14 seasons for offense, 7/14 defense), so NOT adopted; recent seasons (2025-26) show larger gains (transfer era) — revisit after the 2027 season.
- Position/height/class only from rosters for 2025+ (`ht`, `cls` null earlier).
- Margin-aware Elo matches the ridge model on margin MAE (9.006 vs 9.019, 2015-26): ridge model has room to improve (e.g. prior/carryover). Bradley-Terry gets 0 consensus weight (reported honestly).
- Non-adjeff systems and resume metrics are weekly snapshots (every 7th game date), not daily; player-driven rating is season-end only.
