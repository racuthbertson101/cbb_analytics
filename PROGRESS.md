# Progress

Last completed step: Phase 7 - watchability (config/watchability.yaml), append-only prediction log + Accuracy page, Compare page, Ctrl+K search, team previous seasons
Next step: Phase 8 - automation: nightly.yml, refit.yml, incremental ESPN ingest, replay test, README, docs/METHODS.md + EXTENDING.md, tournament stub
Blockers: GitHub public repo creation denied (see KNOWN_ISSUES.md). Continue locally.

## Checklist
- [x] Phase 0 (except GitHub repo, blocked): Setup and audit
  - [x] tools verified (git, gh auth with repo+workflow, python 3.14, uv, node 24)
  - [x] folder structure, git init
  - [ ] GitHub repo created and pushed (BLOCKED)
  - [x] CLAUDE.md, PROGRESS.md, DECISIONS.md, KNOWN_ISSUES.md
  - [x] skills (frontend-design skill install pending, GitHub clone)
  - [x] DATA_AUDIT.md (start season 2008)
- [ ] Phase 1: Warehouse (built + tested; release-asset publishing BLOCKED with no GitHub repo; ESPN incremental ingest deferred to Phase 8)
  - Row counts 2026: games 6318, team_games 12598, player_games 196874, team_seasons 728 (364 D-I). 2008-2026 games total ~110k. 2027: 1629 scheduled games, rosters 5461
- [x] Phase 2: Core ratings and predictions. Backtest 2012-2026 (~85k games): MAE 8.93, RMSE 11.35, log loss 0.5289, Brier 0.1785, acc 72.8%, ECE 0.007. Baselines log loss: home wins 0.654, prev-season 0.588, Elo 0.547. Beats home baseline in 15/15 seasons. Team-specific HCA rejected (hurt OOS); blowout cap ~neutral; no recency decay; lam=3. Params: pipeline/params/adjeff.json, backtest.json, BACKTEST.md. Pregame ratings by date: data/backtest/adjeff_ratings.parquet
- [x] Phase 3 (local): Vertical slice; `next build` passes (376 pages, 60 MB out); live URL not possible without repo -> KNOWN_ISSUES
- [x] Phase 4: Players (impact v1 in-sample R2 off 0.71 / def 0.44; roster prior rejected by CV; see params/players.json)
- [x] Phase 5: More ranking systems. Test 2015-26 margin MAE: adjeff 9.019, Elo 9.006, BT 9.378, prev 9.957, consensus 8.947 (weights adjeff .47 elo .50 bt 0 prev .02); consensus logloss .5293 vs adjeff .5325
- [x] Phase 6: Conferences (tests pass: tiebreak scenarios incl. 3-team tie, sim sanity; sims run for 2026 at 2026-02-15 and final)
- [ ] Phase 7: Watchability, accuracy, remaining pages
- [ ] Phase 8: Automation and extension points
- [ ] Phase 9: Stretch
- [ ] FINAL_REPORT.md
