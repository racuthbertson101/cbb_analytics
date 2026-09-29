# Progress

Last completed step: Phase 3 - site (Today, Rankings, Team, Methodology, Tournament placeholder) builds statically, screenshots reviewed (screenshots/ , python -m pipeline.tools.shots). Live deploy BLOCKED (no GitHub repo).
Next step: Phase 4 - player layer (pipeline/players, player pages, leaderboards).
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
- [ ] Phase 4: Players
- [ ] Phase 5: More ranking systems
- [ ] Phase 6: Conferences
- [ ] Phase 7: Watchability, accuracy, remaining pages
- [ ] Phase 8: Automation and extension points
- [ ] Phase 9: Stretch
- [ ] FINAL_REPORT.md
