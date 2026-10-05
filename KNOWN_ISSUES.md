# Known issues

- Source gap: NCAA tournament game counts are 64 in 2008-2010 (65 played, the opening-round game is missing) and 65 in 2017 (67 played). CORRECTED 2026-10-05: the earlier 58/55/55 counts for 2009/2010/2013 were a classifier bug (the CIT exclusion matched "Kansas City"), not a source gap.
- Game type heuristic: conference tournament games without headline on non-neutral sites are labeled `regular` (definition documented in build.py).
- Player impact v1 (box-score): scale is inflated for extreme rebounders/shot-blockers (ecological regression on team averages) and defense R2 is ~0.45; top of the leaderboard skews to rim-protecting bigs. Kept as labeled v1; RAPM (Phase 9) is the intended upgrade.
- Position/height/class only from rosters for 2025+ (`ht`, `cls` null earlier).
- Margin-aware Elo is close to the ridge model on margin error (2015-26 MAE: adjusted efficiency 8.973, Elo 9.006); the consensus beats both (8.910). Bradley-Terry gets 0 consensus weight (reported honestly).
- Non-adjeff systems and resume metrics are weekly snapshots (every 7th game date), not daily; player-driven rating is season-end only.
- Shots data: the 2025 (2024-25) shots release has ~0.19M shots vs ~0.71M for 2026 (incomplete source), so shot charts are exported for the latest season only; earlier seasons' shots are not used.
- Roster prior look-ahead: for 2012-2026 the 'roster' used in the preseason prior is the set of players who actually appeared for the team that season (true preseason rosters exist only for 2025+). This is mild look-ahead (it knows who ended up playing); the walk-forward evidence (14/14 offense seasons improved in team-rating RMSE, game-level log loss 0.5289 -> 0.5263) is therefore slightly optimistic. The upcoming season uses the real roster table.
- Big Ten tiebreaker config is structurally wrong, not just unverified (AUDIT C-1, H-8). It restarts after partial resolution, lacks the D-I win-percentage step and has the wrong bye lines. Fix scheduled in IMPROVEMENT_PLAN.md Phase 6 (target about Jan 10, before conference play matters).
- Conference renames for 2026-27 (WAC is now "United Athletic Conference", MAAC shows as "Metro Conference" in ESPN data) reuse the old leagues' tiebreaker configs via `conference_aliases` in `config/membership_overrides.yaml`; their rules have not been re-checked.
