# Progress

Last completed step: Phases 0-9 built and verified locally; FINAL_REPORT.md written.
Next step (needs the owner): GitHub steps that the permission classifier blocked (see KNOWN_ISSUES.md and README "Publishing to GitHub Pages"):
create the public repo and push, publish the `warehouse` release assets, enable Pages, dispatch `deploy.yml` then `nightly.yml`, record the live URL below.
Blockers: none. Repo https://github.com/racuthbertson101/cbb_analytics created and pushed; Pages, workflow permissions and the `warehouse` release (138 assets) set up.

Live URL: https://racuthbertson101.github.io/cbb_analytics/ (deploy.yml and a manual nightly.yml dispatch both succeeded on 2026-09-29)

## Checklist
- [x] Phase 0: Setup and audit. Tools verified, structure, CLAUDE.md, DECISIONS.md, KNOWN_ISSUES.md, 4 skills (incl. frontend-design), DATA_AUDIT.md (start season 2008). GitHub repo creation BLOCKED.
- [x] Phase 1: Warehouse. 2008-2027 tables (games, team_games, player_games, teams, team_seasons, rosters, player_seasons, player_impacts); 135+ validation tests; rebuild is idempotent; ESPN incremental ingest verified to reproduce warehouse rows exactly (games/box/players). Release-asset publishing coded (`pipeline/release.py`, dry-run tested) but BLOCKED (no repo).
  - Row counts (2026): games 6,318 (6,300 completed), team_games 12,598, player_games ~196,900, team_seasons 728 (365 D-I). 2027: 1,629 scheduled games, 5,461 roster rows.
- [x] Phase 2: Core ratings (adjusted efficiency). Walk-forward 2012-2026 (81,567 games): MAE 8.89, RMSE 11.28, log loss 0.5263, Brier 0.1775, accuracy 72.9%, ECE 0.008; beats home-wins (0.654), previous-season (0.588) and simple Elo (0.547) baselines in 15/15 seasons vs home wins. Leakage tests pass.
- [x] Phase 3: Vertical slice. Site builds (413 static pages, 130 MB), screenshots reviewed, basePath build verified locally. Live deploy BLOCKED.
- [x] Phase 4: Players. Season lines, impact v1, roster-based preseason prior ADOPTED after CV (offense better in 14/14 seasons, defense 12/14) and confirmed at game level, player pages, leaderboards, shot charts, RAPM comparison (corr 0.27).
- [x] Phase 5: Other systems. Elo (MLE), Bradley-Terry, résumé (WAB/SOR/quadrants), player-driven, NNLS consensus (adjeff .58, Elo .37, prev .05, BT 0), toggles + résumé view.
- [x] Phase 6: Conferences. 31 tiebreaker configs (19 verified, 12 fallback), engine + tests (3-team tie), 20k-sim standings, pages.
- [x] Phase 7: Watchability, prediction log (append-only, hash-chained), Accuracy page, Compare, search palette, history (season/as-of selectors, trends, previous seasons).
- [x] Phase 8: Automation. `pipeline/nightly.py`, `pipeline/replay.py` (replay test PASSED twice for 2026-02-15), workflows (nightly/refit/deploy), README, METHODS, EXTENDING, DATA_CONTRACT. Manual dispatch on GitHub BLOCKED.
- [x] Phase 9: Stretch. Shot charts (latest season), RAPM comparison, mobile readiness list (docs/MOBILE_READINESS.md).
- [x] FINAL_REPORT.md
