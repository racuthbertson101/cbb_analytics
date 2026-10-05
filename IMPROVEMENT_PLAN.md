# CBB Analytics: Improvement Plan (2026-09-29, reordered)

Companion to `AUDIT.md`. Finding IDs (D-1, M-1, ...) refer to that file.
Usage sizes are for a Claude Pro plan:
- **S**: under half a session
- **M**: about one session
- **L**: 2 or more sessions, split at the marked checkpoints

Model names: Opus 5.5 (`claude-opus-5-5`), Sonnet 5.5 (`claude-sonnet-5-5`), Haiku 4.5.

**Phase order (owner's choice):**

| # | Phase | Size | Model and effort | Deadline |
|---|---|---|---|---|
| 1 | Quick fixes and honesty pass | S-M | Sonnet 5.5, medium | as soon as possible |
| 2 | Pipeline reliability and dress rehearsal | M | Sonnet 5.5, high | **complete before Nov 2, 2026** |
| 3 | Game page | L (3a, 3b) | 3a Sonnet 5.5 high; 3b Opus 5.5 high | — |
| 4 | Compare page (team-level features only) | L (4a, 4b) | 4a Opus 5.5 high; 4b Sonnet 5.5 high | — |
| 5 | RAPM impact, star power, proper M-1 estimate interval | L (5a, 5b, 5c) | Opus 5.5, high | — |
| 6 | Modeling cleanup and conference fixes | M-L (6a, 6b) | 6a Opus 5.5 high; 6b Sonnet 5.5 high | before conference play heats up (about Jan 10) if possible |
| 7 | Design pass | M | Sonnet 5.5, medium | — |

---

## 1. Top 10 changes ranked by value versus effort

| Rank | Change | Findings | Value | Effort | Phase |
|---|---|---|---|---|---|
| 1 | Fix upcoming-season D-I membership and conferences (152 → about 365 teams); extend tests to 2027 | D-1 | Critical: the preseason site is wrong for 60% of teams | S | 1 |
| 2 | Publish shot bins or hide the card; remove live 404s | F-1 | Every team and player page | S | 1 |
| 3 | Remove the fake win-probability band; label impact v1 experimental | M-1, P-1 | Removes the two biggest credibility hits | S | 1 |
| 4 | Anchor the prediction log in git; score the last prediction before tip-off | R-1, R-3 | Makes the public accuracy claim true and durable | M | 2 |
| 5 | Change-only, manifest-based release uploads; separate deploy and sync jobs | R-2 | Removes the most likely nightly failure mode | S-M | 2 |
| 6 | Game page with every score linked to it | Spec gap, F-6 | Biggest missing product surface | L | 3 |
| 7 | Compare page v2 with team-level matchup context and a walk-forward feature test | F-7 | Most-requested analytical view | L | 4 |
| 8 | Proper estimate interval from rating uncertainty | M-1 | The site's core number becomes defensible | M (inside 5) | 5 |
| 9 | Correct the Big Ten tiebreaker; honest verification status | C-1, C-2 | Standings sims right for a top league | S-M | 6 |
| 10 | Test consensus as the production predictor | M-6 | Free accuracy if it validates | M | 6 |

## 2. Quick wins (all folded into Phase 1 unless noted)

1. Dedupe the two duplicate games by (date, team pair, score) and add a test (D-2).
2. Whitelist NCAA headlines (fixes "The Basketball Classic" typed as `ncaa`); force neutral for NCAA games (D-3).
3. Extend `test_warehouse.py` `SEASONS` to include the upcoming season for membership tests (D-1).
4. FINAL_REPORT/PROGRESS: delete the stale "GitHub blocked" lines (H-2).
5. Methodology: delete the "fuller watchability score arrives later" bullet and add a Watchability section showing `config/watchability.yaml` weights as a judgment call (H-3).
6. Raise `--faint` to about `#858b96` (F-3).
7. Let the Methodology table wrap prose cells (F-2).
8. Delete `web/public/{file,globe,next,vercel,window}.svg` (F-11).
9. Publish `data/status.json` and show a freshness footer (F-5, R-6).
10. Add a DECISIONS.md entry that the Game page was omitted, pointing to this plan (H-1).
11. `deploy.yml`: remove the hardcoded demo sims (R-5, in Phase 2).
12. Cache `uv` in Actions (R-7, in Phase 2).

---

## 3. Phases

Common acceptance checks for every phase:
- `uv run pytest -q` all green.
- `cd web && npx next build` passes.
- `uv run --with playwright python pipeline/tools/screenshots.py` (created in Phase 1) produces 1440 and 1920 screenshots with 0 page errors, 0 horizontal overflow and 0 broken images, and the session looks at them.
- PROGRESS.md updated, one commit per task, push at the end of the phase.

**Formatting note:** the full design pass is last (Phase 7). To avoid building the Game and Compare pages twice, Phase 3 creates `web/lib/format.ts` (the formatter module) and the small shared components (`GameLink`, `SeasonChip`, `ContextTag`, `MatchupBar`). Phases 3 to 5 use them. Phase 7 then restyles everything through tokens and CSS, not markup rewrites.

### Phase 1: Quick fixes and honesty pass (S-M, Sonnet 5.5, medium effort)

| Task | Findings | Files | Acceptance |
|---|---|---|---|
| 1.1 Upcoming-season D-I membership: when standings are missing, use the previous season's D-I set plus `config/membership_overrides.yaml` (new programs, conference moves), and fill `conference`. Never use the `n_games >= 10` fallback on an incomplete schedule; the offseason nightly passes `d1_prev`. | D-1 | `pipeline/warehouse/build.py`, `config/membership_overrides.yaml` (new), `pipeline/nightly.py` | `team_seasons/2027` has 355-370 D-I rows, `conference` non-null for all of them; Today (2026-11-02) predicts Miami–Florida and UCLA–Arizona; the preseason rankings have ≥ 355 teams |
| 1.2 Tests cover the upcoming season (D-I count, conference non-null) | D-1 | `pipeline/tests/test_warehouse.py` | New test fails on the old code |
| 1.3 Dedupe duplicate games (keep the 400-series id); NCAA whitelist by headline and `tournament_id`; neutral for NCAA and NIT late rounds | D-2, D-3 | `build.py`, tests | 0 same-date same-pair same-score duplicates; NCAA count per season 63-68 (0 in 2020); 2022 "Basketball Classic" is `other_post` |
| 1.4 Shots: stage 2026 shot *bins* as a release asset; `deploy.yml` and `nightly.py` run `export.shots`; the ShotChart card hides on a 404 | F-1 | `pipeline/release.py`, `.github/workflows/deploy.yml`, `pipeline/nightly.py`, `TeamView.tsx`, `PlayerView.tsx` | With the asset absent, no shot card and no console error |
| 1.5 Methodology overflow: prose cells wrap | F-2 | `MethodologyView.tsx`, `globals.css` | scrollWidth equals viewport at 1440 and 1920 |
| 1.6 Contrast: raise `--faint` to `#858b96`, and add `pipeline/tools/contrast.py` checking every text token on every surface | F-3 | `globals.css`, new tool | All text pairs ≥ 4.5:1 |
| 1.7 Freshness: publish `data/status.json` from `nightly_status.json`; site footer "Data through … · updated …", amber after 36 h in season | F-5, R-6 | `pipeline/nightly.py`, `web/app/layout.tsx`, `Footer.tsx` (new) | Screenshot shows the footer; a forced old timestamp shows amber |
| 1.8 Delete create-next-app leftovers | F-11 | `web/public/*.svg` | — |
| 1.9 Season labels: one `seasonLabel(y)` helper; a season chip on every page header; no end-year-only season ranges in UI copy ("2012-2026" becomes "2011-12 to 2025-26"); the Conference page labels the standings date and the power-ranking date separately | D-6 | `web/lib/format.ts` (new, seeded with `seasonLabel`), components | A test greps `web/out/**/*.html` for `\b20\d\d-20\d\d\b` and finds 0 matches |
| 1.10 Docs corrections: remove "GitHub blocked" and "dispatch BLOCKED"; "all phases done" replaced by an honest status with a link to this plan; Methodology watchability section with judgment-call weights; the Methodology intro no longer claims prose "cannot go stale"; spread-model and calibrator selection described accurately; DATA_AUDIT notes play-by-play was never downloaded; DECISIONS entry for the missing Game page | H-1..H-8 | `PROGRESS.md`, `FINAL_REPORT.md`, `DECISIONS.md`, `DATA_AUDIT.md`, `docs/METHODS.md`, `MethodologyView.tsx` | Each H-item in AUDIT.md §7 addressed or explicitly deferred |
| 1.11 Impact v1: rename the column to "Box impact (experimental)" with a tooltip on the position bias, or hide it on Team and Players pages; the Player page keeps it with the label; leaderboards default-sort by points per 40 | P-1 | `TeamView.tsx`, `PlayersView.tsx`, `PlayerView.tsx` | No unlabeled impact number anywhere |
| 1.12 Remove the probability band: drop `win_prob_lo/hi` from exports, the prediction log schema (the log has no live rows yet) and all UI; keep the 80% **margin** outcome interval labeled "80% of results land in". The estimate interval returns in Phase 5. | M-1 | `pipeline/models/production.py`, `pipeline/export/contract.py`, `pipeline/predictions/log.py`, `pipeline/nightly.py`, Today, Compare, Accuracy components | `grep -r "plo\|phi\|win_prob_lo" web pipeline` finds only the changelog; screenshots show no band |
| 1.13 Commit the screenshot tool (serve `web/out` with `http.server`; 20 routes × 2 viewports; console errors, 4xx, overflow, broken images to `screenshots/report.json`) | — | `pipeline/tools/screenshots.py` | Runs in under 3 minutes |

### Phase 2: Pipeline reliability and dress rehearsal (M, Sonnet 5.5, high effort). Must finish before Nov 2, 2026.

| Task | Findings | Files | Acceptance |
|---|---|---|---|
| 2.1 Prediction log in git: nightly writes `predictions/log/YYYY/MM-DD.csv` (new rows only) and `predictions/HEAD.json` {rows, last_hash} and commits them from the workflow; `verify()` fails when the log is missing or shorter than HEAD | R-1 | `pipeline/predictions/log.py`, `.github/workflows/nightly.yml`, tests | Tests: deleting the parquet fails `verify()`; editing one row fails |
| 2.2 Log every night; score the **last** prediction with `made_at < game_datetime`; store `days_before`; the Accuracy page shows the distribution | R-3 | `log.py`, `pipeline/export/accuracy.py`, `PredictionsView.tsx` | Two-night replay proves the second night's prediction is the scored one |
| 2.3 Manifest release sync: hash staged files; upload only changed files under versioned names; write `manifest.json` last; download reads the manifest; prune versions older than 7 days | R-2 | `pipeline/release.py` | Dry run with nothing changed uploads only the manifest; a simulated mid-upload failure leaves the previous manifest valid |
| 2.4 Split workflow jobs: `build` → `deploy` and `build` → `sync` (release upload plus log commit), each failing independently | R-2 | `.github/workflows/nightly.yml` | Job graph documented in README |
| 2.5 `deploy.yml` runs the nightly export path with `--no-ingest --no-log`; no hardcoded sim dates anywhere | R-5 | `deploy.yml`, `Makefile`, `pipeline/nightly.py` | `grep -r "2026-02-15" .github Makefile pipeline/nightly.py` finds nothing |
| 2.6 Schema drift guards: required keys on raw ESPN summary JSON; null ceilings per column for completed D-I games (`fga`, `fta`, `orb`, `tov`, `minutes` ≤ 1%); live-season player-sum tolerance 1%; weekly canary comparing last week's ESPN ingest with the hoopR release | R-4 | `pipeline/ingest/espn.py`, `pipeline/warehouse/validate.py`, tests with a mutated fixture | The mutated fixture fails validation |
| 2.7 `rehearsal` input on `nightly.yml`: runs the full path against `--today <date>` using a scratch warehouse copy and a scratch prediction log, **skips deploy and sync**, uploads the built site and logs as a workflow artifact | — | `nightly.yml`, `pipeline/nightly.py` | Local run with `--rehearsal` touches neither `data/predictions/` nor the release |
| 2.8 Cache `uv` in Actions | R-7 | workflows | — |
| 2.9 Write `docs/SEASON_OPENER.md` (the dress-rehearsal checklist below) and run every local item | — | new doc | Local checklist items ticked in the doc |

**Dress rehearsal checklist (`docs/SEASON_OPENER.md`):**

1. **Local, during Phase 2:** full `pipeline.nightly --today 2026-02-15 --rehearsal`, then `--today 2026-02-16 --rehearsal`. Checks:
   - Ingest finds games.
   - Validation passes.
   - Log rows and HEAD advance.
   - The second night's predictions are the scored ones.
   - The standings sim uses the date, not a hardcoded one.
   - The site builds and shows the freshness footer.
2. **Local:** `--today 2026-11-02 --rehearsal` (opening night, offseason-to-live transition). Checks: `live` flips correctly, the preseason prior is used, predictions exist for about 150+ D-I games, and there are no "non-D-I" false labels.
3. **Local failure drills:**
   - Kill the network mid-ingest: the job fails and the previous `web/out` is untouched.
   - Corrupt one ESPN fixture: validation fails.
   - Delete the local log: `verify()` fails.
   - Interrupt the manifest upload (dry-run mode): the previous manifest is still valid.
4. **Owner or session, around Oct 20:** dispatch `nightly.yml` with `rehearsal=true, today=2026-02-15`. Download the artifact. Confirm that the live site and the release are unchanged.
5. **Around Oct 27:** repeat with `today=2026-11-02`.
6. **Nov 1:** confirm the cron is enabled, `warehouse` release manifest present, Pages source is Actions, `predictions/HEAD.json` exists with 0 rows, the workflow has `contents: write`, and D-I count for 2027 is at least 355.
7. **Nov 2, 07:30 UTC:** first real run. **Nov 2 morning check:**
   - Workflow green.
   - Log committed with the day's rows.
   - Site footer shows today.
   - Today page predictions match the log.
8. **Nov 3 morning:** the first results were ingested; the Accuracy page scores them; `HEAD.json` rows increased; `days_before` is 0 or 1.

### Phase 3: Game page (L, two sessions)

- **3a:** Sonnet 5.5, high effort.
- **3b:** Opus 5.5, high effort (in-game model); the UI part of 3b can drop to Sonnet if usage is tight.

Full design in §4.2. It shows the margin outcome interval, with no estimate band until Phase 5. Watchability is shown for upcoming games, with star power labeled experimental until Phase 5.

| Task | Files | Acceptance |
|---|---|---|
| **3a.1** Shared UI kit: `web/lib/format.ts` (`fmtRating`, `fmtEff`, `fmtPct` with "<1%", `fmtInt`, `fmtScore`, `seasonLabel`), `GameLink`, `SeasonChip`, `ContextTag`, `MatchupBar` | `web/lib`, `web/components/ui/*` | New code uses no `toFixed` |
| **3a.2** Exports: `teamlogs/<season>/<team>.json` (per-game team box, both sides, compact arrays) for 2010-2027; extend `playerlogs` to 2017-2027 | `pipeline/export/games.py` (new), `docs/DATA_CONTRACT.md` | Sizes printed |
| **3a.3** Route `/game/?id=&season=`: completed layout (header, prediction vs result, box scores, team stat comparison, expected vs actual by player) and upcoming layout (prediction, waterfall, watchability breakdown, head-to-head, key battles) | `web/app/game/page.tsx`, `web/components/GameView.tsx` | Screenshots: 2026 final, a 2015 game, a game vs a non-D-I team, two upcoming 2026-27 games |
| **3a.4** Expected vs actual by player uses only pre-game season-to-date per-minute rates × minutes played | exporter, `pipeline/tests/test_leakage.py` | Leakage test passes |
| **3a.5** Link every score: Today, Team results, Player game log, Accuracy recent games, Conference results | components | Playwright: every `.score` element is inside `a[href*="/game/"]` |
| **3a.6** `pipeline/tools/site_size.py`: fails over 400 MB, prints the breakdown, applies the drop order from §4.2; nightly runs it before deploy | new tool, `nightly.py` | Under 400 MB |
| **Checkpoint 3a** | | |
| **3b.1** Download hoopR play-by-play 2016-2027 to `data/raw/sdv/pbp` (cached, polite, never published); parse to a compact table; coverage table in DATA_AUDIT.md | `pipeline/ingest/download.py`, `pipeline/pbp/parse.py` (new) | ≥ 95% of 2016+ D-I games parse; final pbp score equals the box score ≥ 99% |
| **3b.2** In-game WP model: logistic on [margin/√(t+1), pregame spread·t/2400, margin, OT flag], anchored to the calibrated pregame probability; walk-forward (seasons < S); calibration by time-remaining bucket in `params/ingame.json` and on Methodology | `pipeline/models/ingame.py` | Calibration within ±2 pp in every time bucket |
| **3b.3** `gamedetail/<season>/<id>.json` for 2025-2027: WP series (score changes, about 150 points), runs of 8-0 or more, lead changes, ties, largest lead, excitement index, per-game shot bins (2026+) | exporter | Budget holds |
| **3b.4** Game page: WP chart, runs, lead-change stats, game shot chart | `GameView.tsx` | Screenshots incl. an overtime game |

### Phase 4: Compare page with team-level features (L, two sessions)

- **4a:** Opus 5.5, high effort (exports and the walk-forward feature test).
- **4b:** Sonnet 5.5, high effort (UI).

**Scope rule:** only team-level features in this phase.
- **Player-derived features wait for Phase 5:** impact numbers, star dependence, depth measures, rotation impact, player-feature matchup tests.
- **Shown now as plain facts:** the rotation section shows names, class, height, minutes and box stats, with no impact and no derived dependence scores. A "Personnel impact arrives with RAPM ratings" note sits in place of the gated items.
- **Prediction block:** the margin outcome interval only; the estimate band arrives in Phase 5.

| Task | Files | Acceptance |
|---|---|---|
| **4a.1** `profiles/<season>.json` 2010-2027: four factors both ways with percentiles, shooting and zone mix, TOV and foul rates, all rating systems and ranks, résumé, recent form vs expectation, variance and upset rates, plain rotation facts | `pipeline/export/profiles.py` | About 1 MB per season |
| **4a.2** `teamhistory/<team>.json`: every game since 2008 for head-to-head and common opponents | exporter | About 6 MB total |
| **4a.3** Team-level matchup backtest on walk-forward residuals, **pre-registered** features: tempo clash, 3PA rate × opponent 3PA-allowed, ORB% × opponent DRB%, TOV% × opponent forced TOV%, FT rate × opponent FT rate allowed, rest-day difference. Ridge, fit on seasons before S. Adoption rule written into `params/matchup_eval.json` **before** running: pooled log loss improves by ≥ 0.0005 **and** improves in ≥ 10 of 15 seasons. | `pipeline/models/matchup.py` | Per-feature and joint results saved; decision in DECISIONS.md |
| **4a.4** `analogs.json` from `oos_preds` (predicted margin × predicted possessions bins → outcome quantiles, favorite win %, n) | `export/analogs.py` | About 50 KB |
| **Checkpoint 4a** | | |
| **4b.1** Rebuild `/compare/` per §4.1 sections 1-14 and 16-17 (section 15 in its reduced plain-facts form). Every section carries a `ContextTag` read from `matchup_eval.json`. | `CompareView.tsx`, `web/app/compare/page.tsx` | Screenshots: Michigan vs Duke 2025-26 neutral, a cross-season pair, a mid-major pair; first-load transfer under 2.5 MB |

### Phase 5: RAPM impact ratings, star power, proper estimate interval (L, three sessions, Opus 5.5, high effort)

Requires Phase 3b's play-by-play.

| Task | Findings | Files | Acceptance |
|---|---|---|---|
| **5a.1** Stints from play-by-play substitutions; possessions per stint | P-1 | `pipeline/pbp/stints.py` | ≥ 90% of 2016+ D-I games give 5-v-5 stints; possessions within 3% of the box estimate |
| **5a.2** RAPM per season (ridge, offense and defense, home term), walk-forward λ | P-1, P-2 | `pipeline/players/rapm.py` | Next-season RAPM correlation reported |
| **Checkpoint 5a** | | | |
| **5b.1** Box prior (BPM-style) on multi-season RAPM with position and role terms; final impact = RAPM shrunk toward the prior by possessions; team sums constrained to adjusted margin | P-1 | `pipeline/players/impact.py` | Assertions: position means within ±2 points per 100; SD 2-4; no player under 15 mpg in the top 25; next-season team prediction ≥ v1 |
| **5b.2** Re-run the roster-prior CV with v2 impacts; adopt only if better | P-1 | `prior_eval.py`, `roster_prior.py` | Decision logged |
| **5b.3** Watchability star power uses v2; validate watchability against national-TV flags and attendance (Spearman) and show it on Methodology | P-3 | `pipeline/models/watchability.py` | `params/watchability_validation.json` |
| **5b.4** Remove the "experimental" label if 5b.1 passes, otherwise keep it (KNOWN_ISSUES.md) | P-1 | UI | — |
| **Checkpoint 5b** | | | |
| **5c.1** Rating uncertainty from `adjeff.fit`: Var(β) = σ²_eff·A⁻¹; the margin sd for a pair from the variances and covariance | M-1 | `pipeline/models/adjeff.py`, `production.py` | Walk-forward: end-of-season ratings fall inside earlier ±1 sd bands 60-75% of the time (reported) |
| **5c.2** Estimate band: calibrated CDF at margin ± 1.28·sd_est, labeled "80% range of our estimate". New log fields `p_est_lo/hi` (append-only schema bump, versioned). Shown on Today, Game and Compare. | M-1 | `production.py`, `export/contract.py`, `log.py`, UI | Band width shrinks with games played (Methodology chart) |
| **5c.3** Compare player gate opens: rotation impact, depth, star dependence; the player-feature matchup backtest (star dependence × opponent defensive depth) with the same pre-registered rule as 4a.3 | — | `matchup.py`, `CompareView.tsx`, `GameView.tsx` | ContextTags updated from params |

### Phase 6: Modeling cleanup and conference fixes (M-L, two sessions)

- **6a:** Opus 5.5, high effort.
- **6b:** Sonnet 5.5, high effort, web allowed.

| Task | Findings | Files | Acceptance |
|---|---|---|---|
| **6a.1** Conditional margin intervals: quantiles of r/σ(possessions, games played), σ fit walk-forward | M-2 | `evaluate.py`, `production.py` | Walk-forward 80% coverage 78-82% in every month and tempo quartile |
| **6a.2** Roster-feature leakage test (recompute with masked data); historical "early-season roster" approximation; re-run `prior_eval` | M-4 | `pipeline/tests/test_leakage.py`, `pipeline/players/prior_eval.py` | New test passes; decision logged with numbers |
| **6a.3** Teams missing a 2027 roster fall back to the lag-only prior, flagged in the UI (moved here from the audit's data list) | D-7 | `engine.py`, `contract.py`, Rankings and Team UI | 47 teams flagged |
| **6a.4** Replay and historical as-of fits use `prior_coefs_by_season[season]` | M-5 | `production.py` | Test: replay prior equals backtest prior for 2026 |
| **6a.5** Calibrated consensus predictor in the backtest; promote by the rule written into `consensus.json` first (better pooled log loss **and** wins in ≥ 8 of 12 seasons) | M-6 | `consensus.py`, `production.py` | Decision and evidence saved |
| **6a.6** Conference sims with correlated rating shocks from 5c.1's sd; backtest Feb 1 title probabilities 2016-2026 with and without, keep the better by Brier | M-11 | `pipeline/sims/conference.py` | Evidence JSON; Methodology updated |
| **Checkpoint 6a** | | | |
| **6b.1** Engine: per-rule `on_split: restart \| continue \| two_team`; tokens `d1_win_pct` and `metric` (our rating, labeled NET substitute); `vs_standings` outside-team mode `collective \| seeded` | C-1 | `pipeline/sims/tiebreak.py`, `conference.py` | Unit test for the Big Ten 4-team example from its PDF (4-0, 3-1, 2-2, 2-2) |
| **6b.2** Big Ten config per the official 2025-26 procedures:<br>• h2h<br>• record down the standings, tied outside teams treated as a collective<br>• D-I win pct<br>• metric<br>• remaining teams go to the NEXT step<br>• bye tiers 1-4, 5-8, 9-14 | C-1 | `config/tiebreakers/big_ten_conference.yaml`, `make_configs.py` | Status `verified_current` |
| **6b.3** Status split `verified_current` / `verified_stale` / `fallback` with `source_date`, shown on the conference page; re-research of SEC, Big 12 and the other stale sources plus all 12 fallbacks; A-10 upgraded to `verified_stale` | C-2, C-3 | configs, `ConferenceView.tsx`, DECISIONS.md | Every config has `source_date`; a before/after table in DECISIONS.md |

### Phase 7: Design pass (M, Sonnet 5.5, medium effort)

Implements §4.3 across the whole site, including the Game and Compare pages built earlier.

| Task | Findings | Files | Acceptance |
|---|---|---|---|
| 7.1 Tokens and type scale from §4.3; retire `--faint` for text; team-color contrast clamp | F-3 | `globals.css`, `layout.tsx`, `web/lib/color.ts` | The contrast tool passes |
| 7.2 Migrate every remaining `toFixed` to `web/lib/format.ts`; percentages, integers and ratings use consistent decimals | F-12 | all components | `grep -r toFixed web/components` returns nothing |
| 7.3 Tables: sticky header and first column; `<button>` in `th` with `aria-sort`; `:focus-visible` rings; 32 px rows; heat as tint plus edge bar; luck on a neutral scale; scroll-edge fades; lazy logos | F-4, F-9, F-13, F-15 | `globals.css`, table components, `TeamLogo.tsx` | Keyboard-only sort works (Playwright) |
| 7.4 Chart theme `web/lib/chart.ts` applied to every chart (trend, sparkline, calibration, WP, margin distribution) | — | charts | Screenshots reviewed |
| 7.5 Today: D-I cards first, non-D-I games in a compact list, no repeated "Home: X"; the nav label clip fixed | F-8, F-10 | `TodayView.tsx`, `Nav.tsx` | Opening-night screenshot |
| 7.6 Page headers get team-color or signal bands; sections use hairline rules instead of boxed cards | — | layouts | Full screenshot review at 1440 and 1920 |

### Backlog (not scheduled in the seven phases)

| Item | Findings |
|---|---|
| Walk-forward choice of spread and calibrator *types* | M-3 |
| Neutral-site "nominal home" coefficient test | M-7 |
| NCAA-tournament seed baselines | M-9 |
| Tiebreaker ground-truth validation against actual conference tournament seeds 2019-2026 | C-4 |
| Verify tournament field sizes | C-5 |
| `player_box_complete` flag for 2008-2013 gaps | D-4 |

---

## 4. Designs

### 4.1 Compare page (built in Phase 4, completed in Phase 5)

**Goal:** someone who has never watched either team should be able to picture the game: who controls pace, where each team's points come from, which mismatch decides it, and how likely an upset is.

**Governing rule:** a feature may change the *prediction* only if it passed the pre-registered walk-forward test (4a.3 for team-level features, 5c.3 for player features). Otherwise it is displayed with a grey `ContextTag`: "Context only: tested out of sample, did not improve predictions (Δ log loss +0.0002)". Tags read from `params/matchup_eval.json`, so they cannot drift.

**URL:** `/compare/?a=<id>&b=<id>&site=a|n|b&season=<y>&seasonB=<y2?>&asof=<date?>`. Short links are shareable.

**Layout at 1440 wide:** a 12-column grid. Sticky matchup header. Sections flow "Prediction → How it plays → Who they are → History".

1. **Matchup header (sticky, 88 px):** logos, names, records, conferences, and a team-color band on each side.
   - Controls: palette-style team pickers; site segmented control [A home | Neutral | B home]; per-side season selectors (linked by default; unlinking enables a labeled cross-season hypothetical); as-of date for the current season.
2. **Prediction block** (model input)
   - Condensed display numerals for the predicted score. Margin and total below.
   - Win-probability `MatchupBar`.
   - Margin distribution chart: A's winning region shaded in A's color and B's in B's; predicted-margin line; "80% of results land in −9 to +15" band; hover shows P(A by 10+), P(within 3).
   - Sensitivity strip: A home, neutral and B home side by side.
   - **Phase 5 adds** the estimate band bracket ("80% range of our estimate") and "if our ratings are off by one sd".
   - **Phase 6 upgrades** the distribution to the date- and tempo-conditioned σ.
3. **Margin decomposition waterfall** (model input, exact algebra, no fitting)
   - Margin = poss/100 × [(o_A − o_B) + (d_B − d_A) + 2·hca·site].
   - Bars: A's offense, B's offense, A's defense, B's defense, home court, total. Note: "68.4 possessions; each point per 100 is worth 0.68 points here".
4. **Tempo clash:** possessions are model input; "who controls pace" is context. Tempo dots on a D-I percentile axis, the predicted-possessions marker, and the analog spread of possessions.
5. **Offense vs defense, both directions:** ratings are model input. Mirrored percentile bars on one 0-100 axis with verdict chips ("strength vs strength", "mismatch").
6. **Four factors both directions:** context unless 4a.3 adopts an interaction. A 4×2 grid with values, percentiles and deltas; the biggest gap is tagged "Key battle".
7. **Shooting profile** (context)
   - Shot-mix bars (rim, mid, three) against what the opponent allows. 3P%, 2P%, FT%.
   - Hex mini maps when shots exist (2026+). Otherwise hidden with "Shot locations available from 2025-26".
8. **Ball security and fouls** (context): TOV%, forced TOV%, steal rate, fouls per 40, opponent FT rate.
9. **All ranking systems side by side** (context): adjusted efficiency, consensus, Elo, Bradley-Terry, player-driven, WAB, SOR and SOS, with a rank dumbbell.
10. **Résumé and schedule** (context): quadrant records, SOS, nonconference SOS, record vs top 50, best win and worst loss (GameLinks).
11. **Recent form vs expectation** (context): the last 10 games as bars of (actual − pregame predicted margin), GameLinked; season rating sparkline.
12. **Rest and schedule:** context unless 4a.3 adopts rest. Days since the last game, games in the last 7 days, road games in the last 10 days.
13. **Common opponents** (context): per-opponent results and margins vs expectation for both teams, and a summary line.
14. **Head-to-head since 2008** (context): date, site, score, prediction vs result, GameLinked.
15. **Rotation and personnel** (context)
   - **Phase 4:** top 9 by minutes with class, height, mpg, usage, TS%; team minutes-weighted height, experience, returning-minutes share.
   - **Phase 5 adds:** v2 impact per player, depth (top-5 minutes share weighted by impact), star dependence (top player usage × minutes share, usage Herfindahl), and their tested ContextTags.
16. **Consistency and upset profile** (context)
   - Residual SD of game results with a percentile.
   - Upset rates (losses as a ≥ 70% favorite, wins as a ≤ 30% underdog) vs expected counts.
   - One generated sentence, labeled context only.
17. **Historical analogs** (context; honest framing)
   - "In 1,214 past games with a predicted margin within 1.5 and possessions within 3, the favorite won 61%; 80% of margins fell between −12 and +16."
   - Five closest four-factor-profile games, GameLinked.
   - Stated as a calibration view, not a new prediction.

**Cross-season hypothetical mode:** ratings relative to each season's mean, neutral site, possessions from the mean tempo in the later season's league context. Banner: "Hypothetical: different seasons; ratings are relative to each season's average."

**Data:**

| Data | Size |
|---|---|
| `profiles/<season>.json` | about 1 MB × 18 = 18 MB |
| `teamhistory/<team>.json` | about 6 MB |
| `analogs.json` | 50 KB |
| `ratings/<season>.json`, `shots/<season>/<team>.json` | existing |

First load is about 2.1 MB uncompressed, about 350 KB gzipped (ASSUMED ratio).

### 4.2 Game page (Phase 3; estimate band added in Phase 5)

**Route:** `/game/?id=<game_id>&season=<y>`. Client route, no static params.

**Data per view:**
- The game row from `games/<season>.json`. Add a monthly index shard if P75 first load is over 1.5 s.
- `teamlogs/<season>/<teamA|teamB>.json`
- `playerlogs/<season>/<teamA|teamB>.json` (2017+)
- `gamedetail/<season>/<id>.json` (2025+)

#### Completed game layout
1. **Scoreboard header:** team-color split band; logos; final score in condensed numerals; OT tag; date, venue, attendance, game type (for example "NCAA Tournament · Elite Eight"), AP ranks, seeds; links to both teams.
2. **Prediction vs result strip:**
   - "Pregame: Michigan by 4.2 (64%) · Final: Michigan by 6 · Result vs expectation +1.8 (58th percentile of outcomes)".
   - A mini margin distribution with the actual result marked.
   - A logged-prediction badge with timestamp and hash when the game is in the append-only log.
   - The estimate band arrives in Phase 5.
3. **Win-probability chart** (2025+, Phase 3b):
   - Home WP from 0 to 100% with a 50% midline and leading-team color fill; half and OT gridlines.
   - Runs of 8-0 or more annotated.
   - Hover shows clock, score and WP.
   - Stats row: lead changes, ties, largest leads, excitement index with percentile.
4. **Box scores:** starters then bench, sortable, with a totals row. Columns: MIN PTS FG 3P FT ORB DRB REB AST STL BLK TO PF (+/- once Phase 5 stints exist). Player links.
5. **Team stats comparison:** mirrored bars for possessions, PPP, eFG%, TOV%, ORB%, FT rate, paint points, fast-break points, points off turnovers, largest lead, each with the team's season-average tick.
6. **Expected vs actual by player:** players with 10+ minutes; a dot plot of points and rebounds vs expectation. Expected = pre-game season-to-date per-minute rate × minutes played; the formula is in a tooltip.
7. **Game shot chart** (2026+): makes and misses with zone FG% vs the team's season.

#### Upcoming game layout
1. The header with tip time, TV (ESPN `broadcasts` when present) and the watchability badge.
2. The prediction block and waterfall from the Compare engine, and a "Full comparison" link pre-filled.
3. **Watchability breakdown:** five bars with percentile and weight; "weights are a judgment call" linked to Methodology; stakes sub-components listed. Star power is marked experimental until Phase 5.
4. Key battles (top two four-factor gaps), plain rotation facts, rest days, head-to-head, common opponents.
5. Switches to the completed layout once the game is ingested.

**Linking rule:** every rendered score or matchup row anywhere uses `<GameLink>`, checked by Playwright in 3a.5.

#### Sharding and size budget

| Shard | Seasons | Estimate | Phase |
|---|---|---|---|
| Existing site | all | 130 MB (measured) | — |
| `teamlogs/<season>/<team>.json` | 2010-2027 | about 45 MB (ASSUMED) | 3a |
| `playerlogs` extended to 11 seasons | 2017-2027 | +72 MB (9 MB per season measured) | 3a |
| `gamedetail/<season>/<id>.json` | 2025-2027 | about 75 MB (ASSUMED, about 4 KB per game) | 3b |
| `profiles`, `teamhistory`, `analogs` | all | about 24 MB | 4a |
| **Total** | | **about 346 MB** | under the 400 MB target, well under the 800 MB cap |

**Drop order if over budget** (enforced by `pipeline/tools/site_size.py`, logged in KNOWN_ISSUES.md):
1. Per-game shot bins except the latest season.
2. WP series older than the latest two seasons. Keep the summary stats in `teamlogs`.
3. Player logs before 2020.
4. Team logs before 2014.

**Format rules for all new shards:**
- Columnar arrays with a `cols` header.
- Floats rounded to 1 decimal (probabilities to 3).
- No pretty-printing.
- String IDs.
- Versioned `v` field.
- Documented in `docs/DATA_CONTRACT.md`.

### 4.3 Design direction (Phase 7)

**Concept:** "night edition sports page". The site should read like a late-edition newspaper agate page designed for screens. Hairline rules instead of boxed cards. Big condensed numerals for scores and ratings. Dense, quiet tables. Team colors only as identity (bands, bars, WP areas). One hot signal color per page.

**Color tokens** (text pairs checked against WCAG AA in the audit):

| Token | Value | Use | Contrast on surface-2 (#1a1d22) |
|---|---|---|---|
| `--bg` | `#0b0c0e` | page | |
| `--surface` | `#121417` | sections | |
| `--surface-2` | `#1a1d22` | table headers, inputs | |
| `--rule` | `#262a31` | 1 px hairlines, grid | |
| `--ink` | `#ecebe6` | primary text | 14.2 |
| `--ink-2` | `#a9adb5` | secondary text | 7.5 |
| `--ink-3` | `#858b96` | tertiary text, ranks, captions | 4.9 |
| `--signal` | `#ff7a4d` | the one accent | 6.6 |
| `--pos` / `--neg` | `#3cc9a7` / `#f27a62` | deltas | 8.1 / 6.2 |
| heat ends | `#1f6f5f` … `#2a2e35` … `#8a3a2a` | percentile cells, 35% alpha tint plus a 3 px edge bar | ink on the ends: 5.0 / 6.5 |

Team colors pass through a clamp: below 3:1 against `--bg`, use `alt_color`, else lighten in OKLCH until 3:1.

**Type scale** (major third, 14 px base):
- 11, 12, 14, 16, 20, 25, 31, 39, 49 px.
- Families:
  - Display: Bricolage Grotesque at `font-stretch: 75%` for headings and scoreboard numerals.
  - Body: Inter Tight with `"tnum" 1, "cv11" 1` for all numbers.
  - JetBrains Mono is dropped from the UI.
- Headers are sentence case. Tracking is −0.02em at 31 px and above.

**Layout:**
- 1360 px max, 12-column grid.
- Sections separated by 1 px rules and 40 px of space. Cards only for interactive widgets.
- 6 px team-color or signal band in page headers.

**Table density:**
- 32 px rows, 13 px numerals, 12 px headers.
- Fixed decimals per column. Ranks in `--ink-3`.
- Sticky header and first column. No zebra striping; hover fill.
- Tinted heat with an edge bar. Column-group header rows.

**Charts** (`web/lib/chart.ts`):
- No borders. Horizontal 1 px gridlines. 11 px `--ink-3` axes.
- 2 px series with direct end labels instead of legends.
- Tabular-figure tooltips on `--surface-2`.
- A one-line caption per chart.
- Team-color areas at 22% alpha with a 2 px edge.
- 80×20 sparklines with an end dot.

**Signature components:** `MatchupBar`, `Scoreline`, `PercentileBar`, `GameLink`, `SeasonChip`, `ContextTag`.

**Motion:** 120-150 ms fades on data swap only.

---

## 5. Risks and open questions (resolved)

| Question | Decision | Reason |
|---|---|---|
| Why remove the probability band in Phase 1 rather than fix it then? | The fix needs rating covariance and validation (Phase 5). A wrong band is worse than none. | Honesty first; the margin interval stays |
| Log schema change in Phase 1 and again in Phase 5? | Phase 1 removes `plo/phi` before any live rows exist. Phase 5 adds `p_est_lo/hi` with a versioned schema, and old rows keep their hashes. | Append-only integrity |
| Game and Compare built before the design pass? | Yes, per the owner's order. The shared UI kit and formatter come in 3a.1, so Phase 7 restyles through tokens rather than rewriting markup. | Limits double work |
| Big Ten tiebreaker fixed only in Phase 6 | Accepted. Conference play starts around late December; the plan flags "about Jan 10" as the target. If Phase 6 slips, run 6b alone first; it is independent of 6a except 6a.6. | Owner's order; 6b is self-contained |
| M-11 needs rating sd | It comes from 5c.1, so M-11 sits in Phase 6 after Phase 5 | Dependency |
| Matchup features changing predictions | Only via pre-registered walk-forward rules (4a.3, 5c.3); otherwise context-only tags | Spec rule 8 and the owner's instruction |
| Player features on Compare before RAPM | Gated. Phase 4 shows plain facts only. | Impact v1 fails face validity (P-1) |
| Where does the immutable prediction log live? | Daily CSV plus a HEAD hash committed to git | The only free append-evident store |
| Rehearsal pollution risk | The `rehearsal` mode uses scratch warehouse and log copies and skips deploy and sync | Protects the live log and site |
| Play-by-play range | 2016+ only | Coverage and cost |
| The RAPM fails validation | Keep v1 labeled experimental; KNOWN_ISSUES.md | Rule 4 |
| Tiebreaker research dead ends | Keep fallback after 3 lookups; record in DECISIONS.md | Usage |

---

## 6. Paste-ready prompts, one per phase

Paste one per fresh session, in order. Phases 3 to 6 have split prompts at their checkpoints.

### Prompt: Phase 1 (Sonnet 5.5, medium effort, size S-M)
```
Read CLAUDE.md, then IMPROVEMENT_PLAN.md sections 2 and 3 (Phase 1), and these AUDIT.md findings: D-1, D-2, D-3, D-6, F-1, F-2, F-3, F-5, F-11, R-6, H-1 to H-8, P-1, M-1.
Implement ONLY Phase 1 (tasks 1.1-1.13). Do not start other phases.
Rules: never ask me questions; when something is ambiguous choose the best option and log it in DECISIONS.md. I am on Windows without make: run the Makefile's commands directly (uv run python -m ..., cd web && npx next build). Max 3 real attempts per problem, then fallback + KNOWN_ISSUES.md. Conserve usage: print heads and summaries, not full dumps; background long jobs with logs.
Key points: the upcoming season must have 355-370 D-I teams with conferences; the win-probability band (plo/phi, win_prob_lo/hi) is removed everywhere (exports, log schema, UI) while the 80% margin outcome interval stays, labeled "80% of results land in"; impact v1 is hidden or labeled "Box impact (experimental)" everywhere it appears; docs must say only what the code does.
Verify: uv run pytest -q; rebuild the 2027 warehouse tables and print the D-I count; cd web && npx next build; create pipeline/tools/screenshots.py (Playwright via `uv run --with playwright`, serve web/out with python -m http.server, 20 routes x 1440x900 and 1920x1080, record console errors, 4xx, overflow, broken images into screenshots/report.json) and pipeline/tools/contrast.py, run both, and LOOK at Today (?date=2026-11-02), preseason Rankings, Team, Player, Compare and Methodology screenshots.
After each task update PROGRESS.md (add an "Improvement plan" checklist if missing) and commit with a clear message ending with the Co-Authored-By line from your instructions. Push to the existing remote at the end of the phase.
```

### Prompt: Phase 2 (Sonnet 5.5, high effort, size M; must finish before Nov 2, 2026)
```
Read CLAUDE.md, then IMPROVEMENT_PLAN.md section 3 (Phase 2, including the dress rehearsal checklist) and AUDIT.md findings R-1, R-2, R-3, R-4, R-5, R-7.
Implement ONLY Phase 2 (tasks 2.1-2.9). Never ask me questions; log judgment calls in DECISIONS.md. Windows, no make: run commands directly. Max 3 attempts per problem, then fallback + KNOWN_ISSUES.md. Conserve usage.
Key constraints: the prediction log becomes append-evident via daily CSVs plus predictions/HEAD.json committed to git by the nightly workflow; scoring uses the last prediction made before tip-off; release sync is manifest-based and change-only; nightly jobs split so deploy and sync fail independently; deploy.yml has no hardcoded sim dates; ESPN schema drift fails validation; a `rehearsal` mode uses scratch copies of the warehouse and log and skips deploy and sync. Do NOT dispatch any workflow or change GitHub settings in this session; only change repo files.
Write docs/SEASON_OPENER.md from the checklist in the plan, then run every LOCAL item (two consecutive replay nights 2026-02-15 and 2026-02-16 with --rehearsal, the 2026-11-02 opening-night rehearsal, and the four failure drills) and tick them in the doc with results. Leave the GitHub dispatch items (Oct 20, Oct 27, Nov 1, Nov 2, Nov 3) unticked with exact commands for the owner.
Verify: uv run pytest -q (new tests: missing-log verify fails, tampered row fails, mutated ESPN fixture fails validation, manifest dry run uploads only the manifest when nothing changed, rehearsal mode leaves data/predictions untouched); cd web && npx next build; run pipeline/tools/screenshots.py and check the Accuracy page and freshness footer.
Update PROGRESS.md after each task, commit each task (Co-Authored-By line from your instructions), push at the end.
```

### Prompt: Phase 3a (Sonnet 5.5, high effort, size M)
```
Read CLAUDE.md, the cbb_web_design and cbb_data_conventions skills, then IMPROVEMENT_PLAN.md section 3 (Phase 3) and section 4.2 (Game page design, sharding table, drop order), and docs/DATA_CONTRACT.md.
Implement ONLY Phase 3a (tasks 3a.1-3a.6): the shared UI kit and web/lib/format.ts, teamlogs and extended playerlogs exports, the client route /game/?id=&season= with the completed and upcoming layouts from 4.2 WITHOUT play-by-play sections (those are 3b), expected-vs-actual by player using only pre-game season-to-date rates (with a leakage test), GameLink on every score across the site, and pipeline/tools/site_size.py (fail over 400 MB, print breakdown, apply the documented drop order) run by nightly before deploy. No estimate band yet (Phase 5): show the margin outcome interval. Mark watchability star power "experimental".
Never ask me questions; log decisions in DECISIONS.md. Windows, no make. Max 3 attempts, then fallback + KNOWN_ISSUES.md. Conserve usage.
Verify: uv run pytest -q; exports regenerate; site_size.py under 400 MB; cd web && npx next build; screenshots at 1440 and 1920 of the 2026 national final, a 2015 game, a game vs a non-D-I team, and two upcoming 2026-27 games; a Playwright check that every score element sits inside a link to /game/. Update docs/DATA_CONTRACT.md.
Commit each task (Co-Authored-By line from your instructions), update PROGRESS.md with "next: Phase 3b", push at the end.
```

### Prompt: Phase 3b (Opus 5.5, high effort, size M)
```
Read CLAUDE.md, the cbb_modeling_rules and cbb_data_conventions skills, then IMPROVEMENT_PLAN.md section 3 (Phase 3, tasks 3b.*) and section 4.2. Phase 3a must be complete (check PROGRESS.md).
Implement ONLY Phase 3b: download hoopR play-by-play for 2016-2027 (cached under data/raw/sdv/pbp, polite, never published as release assets) in the background; parse to a compact table with coverage checks (final pbp score equals box score >= 99%) and add a coverage table to DATA_AUDIT.md; fit the in-game win probability model walk-forward (seasons < S), anchored to the calibrated pregame probability, with calibration by time-remaining bucket saved to pipeline/params/ingame.json and rendered on Methodology; export gamedetail shards for 2025-2027 (WP series downsampled to score changes, runs of 8-0 or more, lead changes, ties, largest lead, excitement index, per-game shot bins 2026+); add those sections to the Game page.
Never ask me questions; log decisions in DECISIONS.md. Windows, no make. Max 3 attempts, then fallback + KNOWN_ISSUES.md. Conserve usage.
Verify: uv run pytest -q (add: WP series ends at 0 or 1, WP within [0,1], in-game model for season S never trained on season S); site_size.py under 400 MB; cd web && npx next build; screenshots of three completed 2026 games including an overtime game.
Commit each task (Co-Authored-By line from your instructions), update PROGRESS.md, push at the end.
```

### Prompt: Phase 4a (Opus 5.5, high effort, size M)
```
Read CLAUDE.md and the cbb_modeling_rules skill, then IMPROVEMENT_PLAN.md section 3 (Phase 4) and section 4.1 (Compare design). Phase 3 must be complete (check PROGRESS.md).
Implement ONLY Phase 4a (4a.1-4a.4), TEAM-LEVEL FEATURES ONLY: export profiles/<season>.json (with plain rotation facts but no impact, depth or star-dependence scores) and teamhistory/<team>.json; run the team-level matchup residual backtest with the pre-registered features and the adoption rule written into pipeline/params/matchup_eval.json BEFORE running (pooled log loss improves by >= 0.0005 AND improves in >= 10 of 15 test seasons, else context only); save per-feature and joint results and the decision; export analogs.json. No guessed weights: any adopted feature enters production only through the params file with its evidence. Player-derived features are out of scope until Phase 5.
Never ask me questions; log the decision in DECISIONS.md. Windows, no make. Max 3 attempts, then fallback + KNOWN_ISSUES.md. Conserve usage.
Verify: uv run pytest -q (add a leakage test: profile inputs as of a date use only earlier games); site_size.py under 400 MB; Methodology shows the matchup test table; cd web && npx next build.
Commit each task (Co-Authored-By line from your instructions), update PROGRESS.md with "next: Phase 4b", push at the end.
```

### Prompt: Phase 4b (Sonnet 5.5, high effort, size M)
```
Read CLAUDE.md, the cbb_web_design and frontend-design skills, then IMPROVEMENT_PLAN.md section 4.1 (Compare design) and pipeline/params/matchup_eval.json. Phase 4a must be complete.
Implement ONLY Phase 4b: rebuild the Compare page per 4.1 sections 1-14, 16 and 17, plus section 15 in its reduced Phase 4 form (plain rotation facts, and a "Personnel impact arrives with RAPM ratings" note in place of impact, depth and star dependence). Use the shared UI kit and web/lib/format.ts from Phase 3a. Every section carries a ContextTag read from matchup_eval.json. Every game reference uses GameLink. Hide sections without data for a season, with a one-line note. No estimate band yet (Phase 5).
Never ask me questions; log decisions in DECISIONS.md. Windows, no make. Max 3 attempts, then fallback + KNOWN_ISSUES.md. Conserve usage.
Verify: cd web && npx next build; screenshots at 1440 and 1920 for Michigan vs Duke 2025-26 neutral, a cross-season pair (2015 Kentucky vs 2026 Michigan), and a mid-major pair; zero overflow and zero console errors in screenshots/report.json; first-load transfer under 2.5 MB (measure with Playwright). Update docs/DATA_CONTRACT.md.
Commit each task (Co-Authored-By line from your instructions), update PROGRESS.md, push at the end.
```

### Prompt: Phase 5a (Opus 5.5, high effort, size M)
```
Read CLAUDE.md and the cbb_modeling_rules skill, then IMPROVEMENT_PLAN.md section 3 (Phase 5) and AUDIT.md section 4 (P-1 to P-3). Phase 3b's play-by-play must exist (check PROGRESS.md and data/raw/sdv/pbp).
Implement ONLY Phase 5a (5a.1-5a.2): stints from play-by-play substitutions with possessions per stint (>= 90% of 2016+ D-I games, possessions within 3% of the box estimate), and per-season RAPM (ridge, offense and defense, home term) with walk-forward ridge strength and next-season correlation reported in pipeline/params/rapm.json.
Never ask me questions; log decisions in DECISIONS.md. Windows, no make; background long fits with logs. Max 3 attempts, then fallback + KNOWN_ISSUES.md. Conserve usage.
Verify: uv run pytest -q (add stint sanity tests: 5 players per side, minutes sum to game length within tolerance); evidence saved.
Commit each task (Co-Authored-By line from your instructions), update PROGRESS.md with "next: Phase 5b", push at the end.
```

### Prompt: Phase 5b (Opus 5.5, high effort, size M)
```
Read CLAUDE.md and the cbb_modeling_rules skill, then IMPROVEMENT_PLAN.md section 3 (Phase 5, tasks 5b.*). Phase 5a must be complete.
Implement ONLY Phase 5b: the BPM-style box prior fit on multi-season RAPM with position and role terms; final impact = RAPM shrunk toward the prior by possessions, team sums constrained to adjusted margin; re-run the roster-prior cross validation with v2 impacts (adopt only if better); switch watchability star power to v2 and validate watchability against national-TV flags and attendance (Spearman), shown on Methodology; remove the "experimental" label only if the smell-test assertions pass.
Turn these smell tests into assertions: position mean impacts within +/-2 points per 100, SD between 2 and 4, no player under 15 mpg in the top 25. If they still fail after 3 real attempts, keep v1 labeled experimental and log it in KNOWN_ISSUES.md.
Never ask me questions; log decisions in DECISIONS.md. Windows, no make. Conserve usage.
Verify: uv run pytest -q; evidence in pipeline/params/players_v2.json and watchability_validation.json; Methodology updated from params; cd web && npx next build; screenshots of Players, Florida and Iowa 2025-26 team pages and Bennett Stirtz's player page, and check the top and bottom 10 names make basketball sense.
Commit each task (Co-Authored-By line from your instructions), update PROGRESS.md with "next: Phase 5c", push at the end.
```

### Prompt: Phase 5c (Opus 5.5, high effort, size M)
```
Read CLAUDE.md and the cbb_modeling_rules skill, then IMPROVEMENT_PLAN.md section 3 (Phase 5, tasks 5c.*), section 4.1 (sections 2 and 15) and AUDIT.md M-1. Phase 5b must be complete.
Implement ONLY Phase 5c: (1) rating uncertainty from the ridge normal equations in adjeff.fit (Var(beta) = sigma2_eff * inverse of A; pair margin sd from variances and covariance), validated walk-forward (share of end-of-season ratings inside earlier +/-1 sd bands, target 60-75%, reported); (2) the proper M-1 estimate band = calibrated CDF at margin +/- 1.28 sd, labeled "80% range of our estimate", added to exports, a versioned append-only log schema (new fields p_est_lo/p_est_hi; existing rows keep their hashes), Today, Game and Compare; a Methodology chart showing band width shrinking with games played; (3) open the Compare player gate: rotation impact, depth and star dependence, plus the player-feature matchup backtest (star dependence x opponent defensive depth) under the same pre-registered rule as Phase 4a, updating matchup_eval.json and the ContextTags.
Never ask me questions; log decisions in DECISIONS.md. Windows, no make. Max 3 attempts, then fallback + KNOWN_ISSUES.md. Conserve usage.
Verify: uv run pytest -q (add: band shrinks with games played on a synthetic season; log verify passes across the schema bump); cd web && npx next build; screenshots of Today, a Game page, Compare and Methodology.
Commit each task (Co-Authored-By line from your instructions), update PROGRESS.md, push at the end.
```

### Prompt: Phase 6a (Opus 5.5, high effort, size M)
```
Read CLAUDE.md and the cbb_modeling_rules skill, then IMPROVEMENT_PLAN.md section 3 (Phase 6, tasks 6a.*) and AUDIT.md findings M-2, M-4, M-5, M-6, M-11, D-7. Phase 5c must be complete (the rating sd is needed for 6a.6).
Implement ONLY Phase 6a: date- and tempo-conditioned margin intervals fit walk-forward (80% coverage 78-82% in every month and tempo quartile); a roster-feature leakage test that recomputes features with masked data, plus the historical early-season roster approximation and a re-run of prior_eval with the decision logged; lag-only prior fallback for teams without 2027 rosters, flagged in the UI; replay and historical as-of fits use prior_coefs_by_season[season]; a calibrated consensus predictor in the backtest, promoted only by the rule written into consensus.json before running (better pooled log loss AND wins in >= 8 of 12 seasons); conference sims with correlated per-team rating shocks, backtested on Feb 1 title probabilities 2016-2026 by Brier, keeping the better version. Every choice walk-forward; evidence in pipeline/params/; results rendered on Methodology.
Never ask me questions; log decisions in DECISIONS.md. Windows, no make; background long jobs with logs. Max 3 attempts, then fallback + KNOWN_ISSUES.md. Conserve usage.
Verify: uv run pytest -q (new: roster-feature leakage, replay prior equals backtest prior for 2026); backtest reports regenerate; cd web && npx next build; screenshots of Methodology, Accuracy, a conference page and preseason Rankings.
Commit each task (Co-Authored-By line from your instructions), update PROGRESS.md with "next: Phase 6b", push at the end.
```

### Prompt: Phase 6b (Sonnet 5.5, high effort, size S-M)
```
Read CLAUDE.md, then IMPROVEMENT_PLAN.md section 3 (Phase 6, tasks 6b.*) and AUDIT.md section 3 (C-1 to C-4). This phase can run before 6a if needed; it is independent.
Implement ONLY Phase 6b: tiebreak engine semantics (per-rule on_split restart/continue/two_team; tokens d1_win_pct and metric; vs_standings outside mode collective/seeded); the corrected Big Ten config from the official 2025-26 procedures (h2h; record vs teams down the standings with tied teams as a collective; D-I win pct; metric as the NET substitute; remaining teams go to the NEXT step, not a restart; bye tiers 1-4/5-8/9-14), status verified_current; the status split verified_current / verified_stale / fallback with source_date shown on the conference page; re-research of SEC, Big 12 and the other stale sources plus all 12 fallback conferences on official conference websites (WebSearch/WebFetch; at most about 3 lookups per conference; never scrape stats sites); upgrade Atlantic 10 to verified_stale.
Never ask me questions; put a before/after table in DECISIONS.md. Windows, no make. Max 3 attempts per conference, then keep fallback and note it. Conserve usage.
Verify: uv run pytest -q including new tiebreak tests (the Big Ten 4-team example: 4-0, 3-1, 2-2, 2-2 among the group); rerun the demo and live standings sims; cd web && npx next build; screenshot the Big Ten and one fallback conference page.
Commit each task (Co-Authored-By line from your instructions), update PROGRESS.md, push at the end.
```

### Prompt: Phase 7 (Sonnet 5.5, medium effort, size M)
```
Read CLAUDE.md, the cbb_web_design and frontend-design skills, then IMPROVEMENT_PLAN.md sections 3 (Phase 7) and 4.3 (design direction), and AUDIT.md section 5.
Implement ONLY Phase 7 (7.1-7.6) across the whole site, including the Game and Compare pages: the exact color tokens and type scale in 4.3, the team-color contrast clamp, migration of every remaining toFixed to web/lib/format.ts, accessible sortable tables (button in th, aria-sort, focus-visible), 32 px rows with tinted heat plus edge bar, luck on a neutral scale, scroll-edge fades, lazy logos, one chart theme in web/lib/chart.ts applied to every chart, the Today layout change, the nav label fix, page-header bands and hairline-rule sections instead of boxed cards. Restyle through tokens, CSS and the shared UI kit; do not rewrite page logic.
Never ask me questions; log judgment calls in DECISIONS.md. Windows, no make. Max 3 attempts, then fallback + KNOWN_ISSUES.md. Conserve usage.
Verify: pipeline/tools/contrast.py passes (all text >= 4.5:1); `grep -r toFixed web/components` returns nothing; cd web && npx next build; run pipeline/tools/screenshots.py at 1440 and 1920 and LOOK at every page for contrast, overflow, alignment and consistency; a Playwright check sorts a table using only the keyboard.
Update PROGRESS.md after each task, commit each (Co-Authored-By line from your instructions), push at the end.
```
