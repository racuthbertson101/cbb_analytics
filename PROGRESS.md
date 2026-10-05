# Progress

Status: original build (Phases 0-9 below) is published, but the 2026-09-29 audit (`AUDIT.md`) found real gaps: no Game page, impact v1 not credible, a wrong Big Ten tiebreaker, a fragile prediction log. Current work follows `IMPROVEMENT_PLAN.md` (checklist at the bottom).
Last completed step: see "Improvement plan" below.
Blockers: none. Repo https://github.com/racuthbertson101/cbb_analytics created and pushed; Pages, workflow permissions and the `warehouse` release (139 assets, refreshed 2026-10-05) set up.

Live URL: https://racuthbertson101.github.io/cbb_analytics/ (deploy.yml and a manual nightly.yml dispatch both succeeded on 2026-09-29)

## Checklist
- [x] Phase 0: Setup and audit. Tools verified, structure, CLAUDE.md, DECISIONS.md, KNOWN_ISSUES.md, 4 skills (incl. frontend-design), DATA_AUDIT.md (start season 2008)..
- [x] Phase 1: Warehouse. 2008-2027 tables (games, team_games, player_games, teams, team_seasons, rosters, player_seasons, player_impacts); 135+ validation tests; rebuild is idempotent; ESPN incremental ingest verified to reproduce warehouse rows exactly (games/box/players). Release-asset publishing coded (`pipeline/release.py`, dry-run tested) and run successfully on GitHub.
  - Row counts (2026): games 6,318 (6,300 completed), team_games 12,598, player_games ~196,900, team_seasons 728 (365 D-I). 2027: 1,629 scheduled games, 5,461 roster rows.
- [x] Phase 2: Core ratings (adjusted efficiency). Walk-forward 2012-2026 (81,567 games): MAE 8.89, RMSE 11.28, log loss 0.5263, Brier 0.1775, accuracy 72.9%, ECE 0.008; beats home-wins (0.654), previous-season (0.588) and simple Elo (0.547) baselines in 15/15 seasons vs home wins. Leakage tests pass.
- [x] Phase 3: Vertical slice (the spec's Game page was NOT built; see DECISIONS 2026-10-05). Site builds (413 static pages, 130 MB), screenshots reviewed, basePath build verified locally. Live at the URL above.
- [x] Phase 4: Players. Season lines, impact v1, roster-based preseason prior ADOPTED after CV (offense better in 14/14 seasons, defense 12/14) and confirmed at game level, player pages, leaderboards, shot charts, RAPM comparison (corr 0.27).
- [x] Phase 5: Other systems. Elo (MLE), Bradley-Terry, résumé (WAB/SOR/quadrants), player-driven, NNLS consensus (adjeff .58, Elo .37, prev .05, BT 0), toggles + résumé view.
- [x] Phase 6: Conferences. 31 tiebreaker configs (19 verified, 12 fallback), engine + tests (3-team tie), 20k-sim standings, pages.
- [x] Phase 7: Watchability, prediction log (append-only, hash-chained), Accuracy page, Compare, search palette, history (season/as-of selectors, trends, previous seasons).
- [x] Phase 8: Automation. `pipeline/nightly.py`, `pipeline/replay.py` (replay test PASSED twice for 2026-02-15), workflows (nightly/refit/deploy), README, METHODS, EXTENDING, DATA_CONTRACT. Manual dispatch of nightly and deploy succeeded on 2026-09-29.
- [x] Phase 9: Stretch. Shot charts (latest season), RAPM comparison, mobile readiness list (docs/MOBILE_READINESS.md).
- [x] FINAL_REPORT.md

## Improvement plan (IMPROVEMENT_PLAN.md)
- [x] Nightly workflow fix (2026-10-05): off days end green after a `--check` guard (they failed every night at the Pages upload).
- [x] Phase 1: Quick fixes and honesty pass (2026-10-05)
  - [x] 1.1 Upcoming-season D-I membership (ESPN membership API, carry-forward fallback, overrides): 2027 has 365 D-I teams, all with conferences
  - [x] 1.2 Tests cover the upcoming season
  - [x] 1.3 Dedupe double-id games; NCAA typing by tournament id (fixed the "Kansas City" CIT bug); NCAA games neutral
  - [x] 1.4 Shot shards as a release asset; meta.shot_seasons; no 404 requests
  - [x] 1.5 Methodology tables wrap
  - [x] 1.6 --faint #858b96; pipeline/tools/contrast.py (all pairs >= 4.5:1)
  - [x] 1.7 status.json + freshness footer
  - [x] 1.8 create-next-app SVGs deleted
  - [x] 1.9 seasonLabel/seasonRange in web/lib/format.ts, season chips, no end-year ranges
  - [x] 1.10 Docs corrections (H-1..H-7; H-8 deferred to Phase 6)
  - [x] 1.11 Impact v1 hidden on Team/Players, labeled experimental on Player
  - [x] 1.12 Win-probability band removed everywhere; margin outcome interval kept
  - [x] 1.13 pipeline/tools/screenshots.py (20 routes x 1440/1920; 40/40 loads clean, 97 s). Verified 2026-10-05: pytest 226 passed; warehouse 2027 = 365 D-I in 32 conferences; full refit (MAE 8.8898, log loss 0.5263, ECE 0.008, NCAA slice 935 games); preseason rankings 365 teams; Nov 2 2026: 50/50 games predicted (Miami-Florida, UCLA-Arizona included); next build 413 pages, 128 MB; screenshots of Today (Nov 2), preseason Rankings, Team, Player, Compare and Methodology reviewed.
  - [x] Extra (found in verification): conference pages for every league in the data (Pac-12 pages 404'd); preseason table uses the upcoming season's conferences.
  - [x] Rebuilt warehouse, refit artifacts and shot bins uploaded to the `warehouse` release.
- [x] Phase 2: Pipeline reliability and dress rehearsal (2026-10-05; GitHub dispatch items are for the owner, see docs/SEASON_OPENER.md sections 4-8)
  - [x] 2.1 Prediction log in git (`predictions/log/YYYY/MM-DD.csv` + `HEAD.json`); verify fails on missing/edited/extra rows
  - [x] 2.2 Log every night; score the last prediction before tip-off; days_before on the Accuracy page
  - [x] 2.3 Manifest-based, change-only release sync with versioned assets, manifest last, prune after 7 days
  - [x] 2.4 nightly.yml jobs: build -> deploy, build -> sync (independent); job graph in README
  - [x] 2.5 deploy.yml and `make site` = `pipeline.nightly --force --no-ingest --no-log`; no hardcoded sim dates
  - [x] 2.6 Schema drift: required ESPN keys, null ceilings, 99% live player-sum, Monday canary vs hoopR
  - [x] 2.7 Rehearsal mode (`--rehearsal`, workflow input), scratch copies in data/rehearsal
  - [x] 2.8 uv cache in all workflows
  - [x] 2.9 docs/SEASON_OPENER.md; all local items run and ticked. The rehearsals found and fixed three would-be opening-week failures: zero-results morning crash (player tables), the rankings export on the same morning, and an ESPN player with no id. pytest 242 passed; actionlint clean; screenshots 40/40 clean.
- [ ] Owner, before Nov 2: GitHub rehearsal dispatches (Oct 20, Oct 27) and the Nov 1 checks in docs/SEASON_OPENER.md
- [x] Phase 3: Game page (2026-10-05)
  - [x] 3a.1 web/lib/format.ts formatters, ui/GameLink, ScoreLink, ContextTag, MatchupBar, SeasonChip; games export gains dt, v, att, tv, an/hn; warehouse games.tv
  - [x] 3a.2 teamlogs 2010+ (32 MB) and playerlogs 2017+ (104 MB, with starters, ORB/DRB, scores, names, expectations)
  - [x] 3a.3 /game/?id=&season=: completed and upcoming layouts (screenshots: 2026 final, 2015 final, non-D-I game, two upcoming 2026-27 games)
  - [x] 3a.4 Expected vs actual uses earlier dates only (3 leakage tests)
  - [x] 3a.5 Every score links to /game/ (screenshot tool check: 504 linked scores, 0 unlinked)
  - [x] 3a.6 pipeline/tools/site_size.py (228.8 MB of 400 MB; drop order; run by nightly before the build)
  - Verified 2026-10-05: pytest 248 passed, next build ok, 50/50 screenshot loads clean
  - [x] 3b.1 Play-by-play 2016-2026 parsed (pbp = box: 99.0% 2024-25, 99.9% 2025-26; DATA_AUDIT coverage table)
  - [x] 3b.2 In-game WP, walk-forward (log loss 0.3745 out of sample; regulation buckets ECE <= 0.9 pp; OT 2.3 pp in KNOWN_ISSUES)
  - [x] 3b.3 gamedetail shards 2025+ (11,325 games), live timelines from ESPN summaries, per-game shot bins
  - [x] 3b.4 Game page: WP chart with runs and hover, flow stats, excitement percentile, game shot charts; Methodology section
  - Verified 2026-10-05: pytest 255 passed; site 252.7 MB; next build ok; 52/52 screenshot loads clean (incl. a 2OT game)
- [ ] Phase 4: Compare page <- NEXT
- [x] Phase 3: Game page (2026-10-05)
- [ ] Phase 5: RAPM impact, star power, estimate interval
- [ ] Phase 6: Modeling cleanup and conference fixes
- [ ] Phase 7: Design pass
