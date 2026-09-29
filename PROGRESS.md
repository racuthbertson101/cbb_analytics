# Progress

Last completed step: Phase 1 - warehouse built (2008-2027), 135 validation tests pass, rebuild is idempotent (hash-verified)
Next step: Phase 2 - ridge adjusted-efficiency model + walk-forward backtest (pipeline/models/adjeff.py)
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
- [ ] Phase 2: Core ratings and predictions
- [ ] Phase 3: Vertical slice and first deploy
- [ ] Phase 4: Players
- [ ] Phase 5: More ranking systems
- [ ] Phase 6: Conferences
- [ ] Phase 7: Watchability, accuracy, remaining pages
- [ ] Phase 8: Automation and extension points
- [ ] Phase 9: Stretch
- [ ] FINAL_REPORT.md
