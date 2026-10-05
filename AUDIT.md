# CBB Analytics: Audit (2026-09-29)

Reviewer hats: staff engineer, applied statistician, product designer. Scope: the whole repo at commit `6ab78c1`, the local build and the live site.
Every finding is tagged **VERIFIED** (I ran something or read the exact code path) or **ASSUMED** (inference not directly checked).
Severity: **critical** (wrong output users see now, or it breaks the in-season product), **high**, **medium**, **low**.

## Verdict in one paragraph

The core ratings engine is honestly built and the backtest is real: walk-forward, leakage-tested, well calibrated (ECE 0.008), beats every baseline in 15/15 seasons, and historical data matches known results. Everything around that core is weaker than PROGRESS.md claims. The site currently shows the 2026-27 preseason with **only 152 of about 365 D-I teams**, because of a D-I membership bug. The "win probability interval" is statistically meaningless. Player impact ratings fail a basic smell test (backup centers rate +25, star guards rate below zero), and that number feeds watchability and the Compare/Team pages. The Big Ten tiebreaker config is wrong. The live site's shot charts are 404s. The prediction log can be lost without anyone noticing. The spec's Game page was dropped without a logged decision. The frontend is competent but generic. The fixes are mostly small. The two new pages are the big pieces of work.

## Headline numbers (VERIFIED)

| Check | Result |
|---|---|
| `uv run pytest -q` | **161 passed** in 127 s |
| `npx next build` (no basePath) | **passes**, 413 static pages, 96 s, `web/out` = 130 MB |
| `next dev` smoke test | all 6 sampled routes 200 (0.7 to 4.0 s cold) |
| Live site `https://racuthbertson101.github.io/cbb_analytics/` | root 200, `data/meta.json` 200, RSC payloads 200, **`data/shots/2026/57.json` 404** |
| Playwright, 20 routes x 2 viewports (1440x900, 1920x1080) | 40 screenshots, 0 broken images, 0 broken internal links (408 checked), 1 overflow page |
| Walk-forward backtest 2012-2026 (81,567 games) | MAE 8.89, log loss 0.5263, accuracy 72.9%, ECE 0.008 |

Screenshots and the capture script (`shoot.py`, `report.json`) are in the session scratchpad: `C:\Users\reidc\AppData\Local\Temp\claude\C--Users-reidc-Documents-Possession\bb9c94eb-43a1-4028-a49e-1c448391e453\scratchpad\shots\<page>_<width>.png`. They are outside the repo because this audit could only write two files. Phase 5 of the plan adds a committed screenshot script.

---

## 1. Data correctness

### D-1 CRITICAL: the 2026-27 season has only 152 D-I teams and no conferences (VERIFIED)
- **Evidence:** `team_seasons/2027.parquet` has 355 rows, `is_d1.sum() == 152`, `conference.notna().sum() == 0`. For comparison, 2026 has 365 and 2025 has 364. On screen, `today_1440.png` shows D-I vs D-I games labeled "No prediction (non-D-I opponent)": Miami vs Florida, UCLA vs Arizona, Lafayette at Butler, Memphis vs Iowa State and dozens more. `rankings_2027_1440.png` renders 151 team logos (preseason table of about 150 teams).
- **Cause (code read):** `pipeline/warehouse/build.py:125-130`. With no standings file for 2027, `is_d1 = team_id in d1_prev` if `d1_prev` exists, else `n_games >= D1_MIN_GAMES (10)`. The offseason nightly calls `wbuild.build([season])` for one season (`pipeline/nightly.py:83`), so `d1_prev` is None. Against a partial 2027 schedule (1,629 games), only 152 teams have 10 or more games. ASSUMED that this is the exact path. The count matches it.
- **Why tests missed it:** `pipeline/tests/test_warehouse.py:7` limits `SEASONS` to `< 2027`, so `test_d1_team_count` never looks at the upcoming season.
- **Impact:** preseason rankings, Today predictions, conference pages and Compare for 2027 are wrong for about 60% of teams. This is the first thing a visitor sees.
- **Fix:** for a season without standings, build membership from the previous season's D-I set, then apply known realignment from ESPN's `groups` endpoint (or a small `config/membership_overrides.yaml` for new D-I programs). Always fill `conference`. Extend the D-I count test to the upcoming season (350 to 370) and assert that `conference` is non-null for every D-I row.

### D-2 HIGH: two duplicated games are counted twice in ratings (VERIFIED)
- **Evidence:** same date, same teams, same score, different ESPN ids: `313150043` / `400207381` (2011-11-11, 43 vs 2115, 73-69) and `330402443` / `400419060` (2013-02-09, 2443 vs 2277, 68-75). A third pair (2020-12-19, 140 vs 123410) is a real doubleheader with different scores against a non-D-I team.
- **Impact:** small on ratings. It proves the "no duplicates" test only checks `game_id` uniqueness.
- **Fix:** dedupe on (date, unordered team pair, score). Keep the 400-series id. Add a test.

### D-3 MEDIUM: the game-type heuristic labels non-NCAA events as NCAA (VERIFIED)
- **Evidence:** 2022 "The Basketball Classic - Championship" (324 vs 278, HTC Center) is typed `ncaa`, because the headline matches `championship` (`build.py:59-60`) and "Basketball Classic" is not on the exclusion list. That makes 2022 show 68 NCAA games. The 2009 national final (Ford Field, UNC vs Michigan State) has `neutral_site = False`, so home court was applied to it.
- **Impact:** NCAA-tournament backtest slices, `game_type` filters and any tournament module training data are slightly contaminated.
- **Fix:** classify NCAA games by `tournament_id` and bracket round headlines (whitelist "Men's Basketball Championship", "First Four", "Final Four", "Regional") rather than blacklisting other events. Force `neutral_site=True` for NCAA and NIT semifinal and final rounds. Add a test that each season has 63 to 68 NCAA games (none in 2020).

### D-4 MEDIUM: box score player sums fail in about 2% of 2008-2013 games (VERIFIED)
- **Evidence:** share of team games where team points differ from the sum of player points: 1.6% (2008), 2.4-2.9% (2009-2013), 0.03-0.17% from 2014 on. Games with a gap over 2 points: 150-281 per season before 2014, 0-11 after.
- **Impact:** early-season player lines (minutes shares, usage) are incomplete for those teams. The ratings are unaffected, because they use team boxes. Nightly validation tolerates up to 5% of mismatches, so a partial ESPN outage at 4% would pass.
- **Fix:** flag `player_box_complete` per team game. Drop flagged games from player-rate denominators. Tighten nightly validation to 1% for the live season.

### D-5 LOW: 2008-2025 spot checks pass (VERIFIED); 2026 is ASSUMED
- Every NCAA final from 2008 to 2025 matches known results. Examples: 2008 Kansas 75-68 Memphis, 2012 Kentucky 67-59 Kansas, 2016 Villanova 77-74 UNC, 2019 Virginia 85-77 Texas Tech, 2021 Baylor 86-70 Gonzaga, 2025 Florida 65-63 Houston.
- Known player lines match: De'Andre Hunter 27 (2019 final), Donte DiVincenzo 31 (2018), Anthony Davis 6 points and 16 rebounds (2012), Will Richard 18, Walter Clayton Jr. 11 and L.J. Cryer 19 (2025).
- 2026 final "Michigan 69-63 UConn" is in the data. I cannot confirm it independently, so it is ASSUMED correct.
- Team box scores match game scores exactly (0 mismatches across all seasons).
- Conference realignment is by season: Texas and Oklahoma Big 12 then SEC in 2025, UCLA Pac-12 then Big Ten, SMU AAC then ACC.
- D-I counts are 341-365 for 2008-2026.

### D-6 MEDIUM: season labels are inconsistent across pages (VERIFIED)
- Selectors correctly show "2025-26" and "2026-27" everywhere (rankings, team, player, conference, compare).
- Prose and tables mix conventions. The Accuracy page says "Walk-forward backtest (2012-2026)". Methodology says "test seasons 2012-2026" and "2015-2026". URLs and data files use `season=2027`. The Today offseason banner shows "Mon, Nov 2, 2026" with no season label. The Conference page puts a Feb 15 standings snapshot next to an end-of-season power ranking without saying they come from different dates.
- **Fix:** add one `seasonLabel(y)` helper, use it everywhere text is rendered, and ban raw end-year numbers in UI copy (a lint test can grep the built HTML for the pattern `20\d\d-20\d\d`). Put a season chip in every page header.

### D-7 MEDIUM: the 2027 roster table misses 47 D-I teams (VERIFIED)
- `rosters/2027.parquet` covers 318 of 365 D-I teams. Only 79.5% of 2026 players with 600+ minutes appear on any 2027 roster (some graduated, some genuinely missing).
- **Impact:** for teams without rosters, returning and incoming minutes share come out as 0, so the roster prior shrinks them toward the league mean. Their preseason ratings are wrong in a systematic direction.
- **Fix:** when a team has no roster rows, fall back to the lag-only prior (coefficients already exist) and flag it on the page. Refresh rosters weekly in the offseason. That already happens, but the problem is not surfaced.

---

## 2. Modeling

### M-1 HIGH: the "win probability interval" is not an interval on the probability (VERIFIED)
- **Evidence:** `pipeline/models/production.py:48-52` computes `win_prob_lo/hi = P(win | margin + q10)` and `P(win | margin + q90)`, where q10 and q90 are *outcome* residual quantiles (-14.3 and +14.0 points). Every game therefore gets roughly a "10% to 90%" band. It shows on the Compare page as markers spanning most of the bar (`compare_1440.png`), on every Today card, and in the logged `plo/phi` fields.
- **Impact:** it tells the user nothing, and the page presents it as uncertainty in the estimate. A stats-literate visitor will distrust the whole site.
- **Fix:** drop the probability band, or replace it with *estimate* uncertainty: the posterior sd of the predicted margin from the ridge normal equations (the `A` matrix in `adjeff.fit` is already there, since Var(beta) is proportional to A⁻¹), pushed through the calibrated CDF. Validate walk-forward that the band shrinks as the season progresses. Keep the outcome interval on the *margin* and label it "80% of results land in".

### M-2 MEDIUM: margin intervals ignore date and tempo (VERIFIED)
- **Evidence:** one pooled residual quantile pair. Walk-forward 80% coverage by month: Nov 76.5%, Dec 79.0%, Jan 80.7%, Feb 81.3%, Mar 81.5%. By tempo: under 64 possessions 81.7%, over 72 possessions 77.8%.
- **Fix:** scale quantiles by the same tempo-dependent sigma used for win probability, plus a days-into-season term (games played by both teams). Fit walk-forward and report coverage by month on Methodology.

### M-3 MEDIUM: model *type* choices were selected on pooled test seasons (VERIFIED)
- **Evidence:** `pipeline/models/evaluate.py:108-127`. Constant versus tempo-dependent spread and raw/Platt/isotonic calibration are each picked by pooled out-of-sample log loss over **all** test seasons 2012-2026, and then reported on those same seasons. The parameters inside each choice are properly walk-forward. The choice itself is not.
- **Impact:** tiny, because the candidates differ by 0.0002-0.0005 log loss. It is still a documented claim that is not quite true: METHODS.md says "spread model and calibrator use only seasons before S".
- **Fix:** make the choice walk-forward too (pick the best on seasons before S for each S), or state the one-bit selection on the Methodology page.

### M-4 MEDIUM: the roster prior has mild look-ahead, and the leakage test cannot see it (VERIFIED)
- **Evidence:** `pipeline/players/prior_eval.py:21` uses `cache[S][team_id, athlete_id]` (players who *appeared* in season S) as the "roster" for every season before 2025, including the test season. The impact model for each S is trained on seasons before S, which is correct.
- **Size of the look-ahead, measured on 2026:** roster-table features versus appeared-player features correlate at 0.96-0.98, with mean absolute difference 0.018 in returning minutes share. So the look-ahead is small, as the docs say. ASSUMED caveat: the 2026 ESPN roster table may itself be a late-season snapshot, which would understate the gap.
- **Blind spot:** `test_leakage.py::test_preseason_prior_ignores_own_season` removes season-2019 results but reuses the precomputed `roster_feats.pkl`. Roster features are never recomputed, so the test would pass even if they leaked badly.
- **Fix:** make roster features a function of (season, as-of date) and test it. For historical seasons, approximate the preseason roster as "players with minutes in the first 3 games of the season or on the prior team's roster", and re-run the prior evaluation.

### M-5 MEDIUM: replay and live refits use the production prior coefficients fit through 2026 (VERIFIED)
- `ratings_asof` (`production.py:73`) always uses `prod["prior_coefs_current"]`, which is fit on seasons up to and including 2026. `make replay DATE=2026-02-15` therefore uses coefficients that saw 2026 final ratings, as do the Compare page and any historical as-of fit that goes through `production.py`. The backtest itself uses per-season coefficients correctly.
- **Impact:** small. It explains the "matches backtest within 0.02" result. It is not a clean replay.
- **Fix:** look up `prior_coefs_by_season[season]` (already stored in `adjeff.json`) when season is at or before the last fitted season.

### M-6 MEDIUM: the consensus beats the flagship model but is not used for predictions (VERIFIED)
- `pipeline/params/consensus.json`: walk-forward 2015-26 MAE is 8.910 for the consensus versus 8.973 for adjusted efficiency, and log loss 0.5271 versus 0.5296 (both uncalibrated). The weights are fit walk-forward, not on the scored data, which is fine.
- Every published prediction still comes from adjusted efficiency only.
- **Fix:** add a calibrated consensus predictor to the backtest harness. If it wins in most seasons, promote it to production and keep adjusted efficiency as the explainable decomposition.

### M-7 LOW-MEDIUM: neutral-site games are slightly miscalibrated (VERIFIED)
- Neutral games (n=9,670): mean predicted 0.581 versus observed 0.598, margin bias -0.35. Non-neutral games: 0.652 versus 0.649, bias +0.29. The listed "home" team at neutral sites carries information (proximity, host).
- **Fix:** test a "nominal home at neutral site" coefficient walk-forward. Keep it only if it helps.

### M-8 LOW: home court estimate is sane (VERIFIED)
- Fitted HCA is 2.1-2.8 points per 100 possessions per side (`adjeff_ratings.parquet`, by season). That works out to about 3.0-3.8 points of margin at 68 possessions, trending down from 2010 to 2026 (2.71 to 2.13), which matches the known decline. Team-specific HCA was tested and rejected. Good.
- Spread: sigma = 10.97 + 0.101 × (possessions - 68). The 68 is a centering constant, not a fitted value, and is harmless. Calibration early season (Nov-Dec) versus late is equally good (for example stated 0.807 vs observed 0.791 in the 0.7-0.9 bin).

### M-9 LOW: NCAA tournament backtest is good (VERIFIED)
- 924 games: MAE 9.08, log loss 0.543, accuracy 71.0%, bias +0.01. By season accuracy runs 63% (2014) to 78% (2025) and log loss 0.445 to 0.624.
- There is no seed-only baseline for the tournament slice. Add one ("better seed wins", with seed-difference logistic fit walk-forward) so the 71% has context.

### M-10 LOW: last season's final ratings pass the smell test (VERIFIED)
- 2025-26 final top 10: Michigan (37-3, +27.2), Duke, Arizona, Houston, Illinois, Florida, Iowa State, Purdue, UConn, Michigan State. Title game in data: Michigan over UConn. The order is plausible, with no mid-major artifacts at the top.

### M-11 MEDIUM: conference simulations ignore rating uncertainty (VERIFIED by code read)
- `pipeline/sims/conference.py` samples each remaining game independently around fixed ratings.
- **Impact:** title and seed probabilities are too confident in January and February. Real rating error is correlated across all of a team's remaining games.
- **Fix:** each simulation draws one team-strength shock from the rating posterior sd (M-1) and applies it to all of that team's games. Validate by replaying 2016-2026 from Feb 1 and scoring title probabilities (Brier) with and without shocks.

---

## 3. Conference simulations and tiebreakers

### C-1 HIGH: the Big Ten config is wrong (VERIFIED against the official 2025-26 PDF)
- Official 2025-26 "Big Ten Men's Basketball Procedures for Tournament Seeding" (mirror: `img.boostsport.ai/boost-cms/2026-Big-Ten-MBB-Tournament-Tiebreakers.pdf`; the URL in the config now returns 404).
  - Two-team ties: h2h, then record against teams down the final standings (tied groups count as a collective), then **won-loss percentage against all D-I opponents**, then **NET**.
  - Multi-team ties: the same steps, but "if a team or teams are separated... remaining teams go to the **next** tiebreaker", **not** back to the start.
- The current config uses `restart_on_partial: true`, has no D-I win-percentage step, adds `random`, and sets `bye_seed_lines: [4]`. The official format has three bye tiers (seeds 1-4, 5-8, 9-14).
- **Fix:** add a `d1_win_pct` rule token (it needs non-conference results in `Standing`), support per-rule restart semantics, correct the config, and mark it `verified` with the new URL.

### C-2 MEDIUM: "verified" is overstated for about 9 of the 19 verified conferences (VERIFIED from the config source URLs)
- Sources are 7-13 years old: America East (2013), Big 12 (2011 URL, "last updated 2015-16"), Big South (2015), Summit (2016-17), Southland (2017), MAAC (2018), MVC (2018).
- The SEC source (`secsports.com/article/11098238`, dated 2017) returns no rule text when fetched.
- Several leagues use NET as a late step but are configured without it.
- The ACC check is fine: `theacc.com/mbbseeding` matches the config (h2h, then down the standings, re-apply among the remaining teams, coin flip).
- **Fix:** split status into `verified_current` (official page for the current season), `verified_stale` (official but more than 2 seasons old) and `fallback`. Show the source date on the conference page.

### C-3 Fallback upgrades attempted in this audit (VERIFIED where stated)

| Conference | Current status | Finding | Action |
|---|---|---|---|
| Atlantic 10 | fallback | The official A-10 page (`atlantic10.com/ViewArticle.dbml?DB_OEM_ID=31600&ATCLID=209901106`, dated 2015-02-21) matches the config: two-team h2h, then common opponents down the standings, then coin toss; 3+ teams: group record, then two-team procedure, then draw lots. | Upgrade to `verified_stale` |
| Big Ten | fallback | Wrong (C-1) | Rewrite, `verified_current` |
| Mountain West | fallback | Secondary sources (Wikipedia, MWC Connection) say h2h, record vs highest seed outside the tie, then higher NET, unchanged since 2020. The config matches, but no official page was found. | Keep fallback. Rules are ASSUMED right. |
| Big West | fallback | No official text found | Keep fallback |
| ASUN, Big Sky, C-USA, MEAC, NEC, SoCon, WCC, WAC | fallback | Not re-researched in this pass (usage budget) | Phase 3 task |

### C-4 MEDIUM: engine semantics are not configurable enough (VERIFIED)
- `pipeline/sims/tiebreak.py`:
  - One global `restart_on_partial` per conference. The Big Ten restarts after no step. ACC, A-10 and SEC reduce to the two-team procedure. Some leagues restart only after h2h.
  - `vs_standings` always groups outside teams by raw win percentage. Some leagues use the *resolved* seed order of outside teams.
  - `build_standing` records road games only for the away team (`rg[a,h]`). That is fine, but conference games at neutral sites count as road games.
  - No token for D-I win percentage, NET-style metric or conference point differential cap.
- **Tests:** 6 tiebreak tests plus 3 simulation tests. They are all synthetic. There is **no validation against real outcomes**.
- **Fix:** add a backtest that replays each conference's actual final standings for 2019-2026 through the engine and compares against the real conference tournament seeds. ESPN standings or tournament bracket seeds give ground truth, and `home_seed`/`away_seed` exist for conference tournament games in some seasons. ASSUMED availability. Report agreement per conference, and treat a mismatch as a config bug.

### C-5 LOW: tournament field sizes and bye lines are unverified config values (VERIFIED, self-declared in configs)

---

## 4. Player layer and watchability

### P-1 CRITICAL for credibility: impact ratings fail the smell test (VERIFIED)
- 2026, players with 500+ minutes:
  - Top 12 are all bigs, mostly bench bigs: Najai Hines (Seton Hall, 17.9 mpg) +27.2, Rafael Castro +27.2, Caleb Van De Griend +26.9, Tarris Reed Jr. +25.9, Rueben Chinyelu +25.9, Ugonna Onyenso (18.7 mpg) +25.0.
  - Bottom 8 are all guards (as low as -14.7).
  - Mean impact by position: C +13.7, F +6.7, G -2.2. SD 7.3 points per 100. Real-world RAPM spread is roughly 2 to 3.
  - Bennett Stirtz (Iowa, 19.8 ppg, 61.3 TS%, 93rd-percentile usage, Elite Eight) rates **-0.4**.
  - Florida's page (`team_florida_1440.png`) shows Chinyelu +25.9 and Handlogten +21.5, but Boogie Fland -5.4.
- **Cause:** ecological regression. Team-level adjusted offense and defense are regressed on minutes-weighted team averages of rate stats, so team-level correlations (rebounding and rim protection with defense) get assigned to individuals. `shrink_k_minutes = 0` (no low-minute shrinkage was chosen). Defense R² is 0.44.
- **Impact:** Team and Player pages, the Players leaderboard and watchability "star power" all use this number. The roster prior uses it too, but only through aggregates that are validated at team level, so the prior itself is fine.
- **Fix (Phase 4):**
  1. Download play-by-play (it is **not** on disk: `data/raw/sdv` has no `pbp` folder, despite DATA_AUDIT.md).
  2. Build stints and fit RAPM per season with a box-score prior (BPM-style: regress multi-season RAPM on individual box rates with position and role terms).
  3. Constrain each team's minutes-weighted sum to match its adjusted margin.
  4. Validate out of sample: next-season RAPM prediction, and the team prior via the existing CV.
  5. Until then, hide the Impact column or label it "experimental".

### P-2 MEDIUM: the RAPM comparison is weak evidence (VERIFIED)
- Correlation with published NCAA RAPM is 0.27 overall (0.23 defense), over 2011-2020 only, in a different ID space. It is reported honestly, but it is the number that should have stopped the v1 rating from being shown so prominently.

### P-3 MEDIUM: watchability is plausible but unvalidated and inherits P-1 (VERIFIED code; usefulness ASSUMED)
- Components are percentile-scaled (good) and weights are labeled as a judgment call (good).
- "Star power" is the best player's previous-season impact. That selects backup centers, not stars.
- The Methodology page never explains watchability. It still says "a fuller watchability score arrives later" (`MethodologyView.tsx:183`). The Today top strip ranks "KENT @ LT 8.3" first on opening night, which is not a watchable-game list anyone would recognise.
- **Fix:**
  1. Replace star power with a usage-weighted scorer or RAPM measure.
  2. Validate against a weak external proxy: national TV windows from the ESPN scoreboard `broadcasts` field, and `attendance` (already in `games`). Report rank correlation on Methodology.
  3. Show a component breakdown on hover and on the Game page.

---

## 5. Frontend (VERIFIED with Playwright unless noted)

| # | Sev | Finding | Evidence | Fix |
|---|---|---|---|---|
| F-1 | high | Live shot charts request files that do not exist (404). `deploy.yml` and `nightly.py` never run `pipeline.export.shots`, and shots are not a release asset. | `curl .../data/shots/2026/57.json` returns 404. Locally they render (`team_florida_1440.png`). | Publish shot bins as a small release asset and export in both workflows. Hide the card when the file is missing. |
| F-2 | high | The Methodology page overflows horizontally: scrollWidth 1784 px at 1440, 2024 px at 1920. The parameter table's "how it was chosen" column spills off the card. | `methodology_1440.png`, `report.json` `over: TABLE.dense` | Allow wrapping in `.dense td` for prose columns. Stack the parameter table as definition rows. |
| F-3 | medium | `--faint` (#5b667a) text fails WCAG AA: 3.16:1 on surface, 2.92:1 on surface-2. It is used for footnotes, "No prediction", rank sub-labels and table captions. | Contrast computed from `app/globals.css` tokens | Raise to about #7d889c (4.6:1 on surface-2) and keep "faint" for non-text decoration only. |
| F-4 | medium | Sortable table headers are `th` elements with `cursor:pointer` and no button role, `aria-sort` or keyboard access. Most components have 0 `aria-` attributes. Focus styles are a border colour change only. | grep `aria-`: Compare 0, Team 0, Player 0, Methodology 0 | Put a `<button>` inside each `th`, add `aria-sort`, and a visible `:focus-visible` ring. |
| F-5 | medium | Nothing on the site says when the data was last updated, although `meta.generated` exists. No staleness warning if the nightly run fails. | grep `generated`: only Conference and Methodology use it | Add a footer: "Data through Tue Apr 7 · updated 3:41 am ET", turning amber after 36 h during the season. |
| F-6 | medium | Scores are not links anywhere (Today, Team results, Player game log, Accuracy recent games). There is no Game page. | screenshots | See Game page design. |
| F-7 | medium | The Compare page is a single card: logos, score, one bar, three numbers (`compare_1440.png`). It does not use data the site already has. | screenshot | See Compare design. |
| F-8 | medium | The Today page spends two-thirds of opening night on 45 identical "No prediction (non-D-I opponent)" cards (partly D-1). Each card repeats "Home: X" above the team names. | `today_1440.png` | Fix D-1. Collapse non-D-I games into a compact list at the bottom. |
| F-9 | medium | The Player and Team game logs show "W +6" with no score and no link. Tables clip inside internal scroll boxes with no visible scroll affordance (Results table ends at Jan 3). | `player_1440.png`, `team_florida_1440.png` | Show the score, link it, and fade the edge on scroll containers. |
| F-10 | low | The Nav's "Men's Division I" label is clipped at 1440 px. | `rankings_1440.png` top-right | Drop it or move it to the footer. |
| F-11 | low | Leftover create-next-app assets ship with the site (`file.svg`, `globe.svg`, `next.svg`, `vercel.svg`, `window.svg`). | `web/out/` listing | Delete them. |
| F-12 | low | Number formatting is inconsistent. `fmt()` uses `toFixed(1)` everywhere, so there is no thousands separator in some tables ("81,604" is formatted in one place, raw in others). Percentages appear with 0 decimals in some places and 1 in others ("6.3%", "0.6%" next to "81%"), and "~73" is used for predicted scores. | Conference and Today screenshots | Use one formatter module (`fmtPct`, `fmtPts`, `fmtRating`, `fmtInt`) with fixed decimals per unit. Show <1% probabilities as "<1%". |
| F-13 | low | The Luck column uses the same good/bad heat scale as ratings. Luck is not a quality measure. | `rankings_1440.png` | Use a neutral diverging scale for luck. |
| F-14 | low | Only local 404s for RSC prefetch `__next.*.__PAGE__.txt`. The Windows build writes nested folders, Linux writes flat files. The live site returns 200. | Console on every page locally. Live curl 200. | None for production. Note it in the web skill so it is not chased again. |
| F-15 | info | Performance is fine: warm static loads 0.9-1.7 s locally; the first cold hit was 9 s. Rankings loads 365 ESPN logo images per view. | `report.json` `load_s` | Lazy-load logos below the fold (`loading="lazy"`). Size-hint them. |

**Does it look templated? Yes, moderately.** It is the standard "dark dashboard" look: navy-black cards with 1 px borders and 10 px radius everywhere, uppercase 11 px grey section labels, teal and orange heat, one amber accent, and every card the same weight. The typography choices (Bricolage Grotesque, Inter Tight, JetBrains Mono) are good, but the scale is flat: page titles about 28 px, then nearly everything 12-14 px. Nothing looks like a sports publication. The design direction is in the plan (IMPROVEMENT_PLAN.md §4.3).

---

## 6. Pipeline reliability

### R-1 HIGH: the prediction log can disappear silently (VERIFIED by code read)
- The "append-only, hash-chained" log lives only in a GitHub release asset. `release.upload` does `gh release upload --clobber` one file at a time (`pipeline/release.py:59-62`). `--clobber` deletes and then uploads, so a failure in between leaves no asset.
- The next night, `release download` gets no log, `log.verify()` returns `True` when the file does not exist (`pipeline/predictions/log.py:48-50`), and a new chain starts from "genesis". Nothing detects the reset.
- The chain head is never anchored anywhere immutable, so the whole log could be regenerated after the fact. The claim "never edited" is unprovable.
- **Fix:**
  1. Commit a daily `predictions/HEAD` file (row count and last hash) to git from the workflow.
  2. `verify()` fails if the local log is shorter than the committed head.
  3. Also commit the day's new rows as a small CSV under `predictions/YYYY/MM-DD.csv`: a few KB per night, and git becomes the immutable log.

### R-2 HIGH: nightly uploads every asset every night, non-atomically (VERIFIED)
- About 138 assets, one `gh` call each, all seasons, even though only the current season changes. A mid-run failure leaves a mix of old and new tables.
- The Pages deploy is gated only on the build job, so if uploads fail after `upload-pages-artifact`, the whole job fails and the site does not deploy, although it was fine. Upload failure and deploy should be independent.
- **Fix:** upload only changed files (hash manifest). Upload new assets under temporary names, then rename (or keep a `manifest.json` asset that is written last and names the versioned files). Move the upload to its own job after deploy.

### R-3 HIGH: the scored prediction is up to 7 days stale (VERIFIED)
- The nightly logs predictions for today+7 days and `append` skips games already logged (`log.py:31-36`). The *first* logged prediction for a game is the one scored, usually made about a week earlier with week-old ratings.
- The backtest scores next-day predictions, so the live Accuracy page will look worse than the backtest for a reason unrelated to model quality.
- **Fix:** log every night (keep all rows). Score the **last prediction made before tip-off** (`made_at < game_datetime`). Show "made N days before" on the page.

### R-4 MEDIUM: ESPN schema drift would pass validation (VERIFIED by code read)
- `parse_summary` turns missing keys into NaN (`espn.py:102,124-133`).
- `validate()` checks possessions only on rows where `fga.notna()`, and skips the check when there are zero such rows. Player-sum and team-box checks tolerate 3-5%.
- If ESPN renames box-score labels, a night could ingest scores with empty team stats. Ratings then fit on NaN or drop games silently.
- **Fix:** a schema contract test on the raw JSON (required keys present on 100% of completed games), a null-rate ceiling per column (for example `fga` null ≤ 1% of completed D-I games), and a canary that compares ESPN totals with the hoopR release for the previous week, run weekly.

### R-5 MEDIUM: nightly and deploy hardcode demo simulation dates (VERIFIED)
- `deploy.yml` and the Makefile run `conferences --sim 2026:2026-02-15 2026:2026-04-10`. `nightly.py:167-172` simulates `{cur}-02-15` in the offseason.
- In-season, deploy.yml would overwrite live standings with the Feb 15 demo if someone republishes the design.
- **Fix:** deploy.yml should run the same export path as nightly with `--no-ingest`, never a hardcoded date.

### R-6 LOW: idempotency and staleness
- Ingest is idempotent (FINAL_REPORT says a second run changed nothing; ASSUMED, not re-run here). The 3-day recheck is reasonable.
- No site-level staleness signal (F-5). `nightly_status.json` is written locally but never published. Publish it as `data/status.json`.

### R-7 LOW: cost is fine (ASSUMED)
- Public repo, so Actions minutes are free. The local replay run took 143 s. The cloud run is probably 10-20 minutes including `npm install` and 20k simulations. Nightly downloads about 130 MB and uploads about 130 MB.
- R-2's change-only upload removes most of the upload traffic. Cache `uv` and `node_modules`: npm is cached, uv is not.

---

## 7. Docs honesty

| # | Sev | Claim | Reality |
|---|---|---|---|
| H-1 | high | PROGRESS.md: "all phases done", "Everything in the spec was built" (FINAL_REPORT.md) | No Game page (spec §9 page 5). No PBP on disk. Shot charts 404 live. Compare is minimal. Not logged in DECISIONS.md. |
| H-2 | medium | FINAL_REPORT.md "Every fallback" section still says "GitHub blocked... All GitHub-dependent phase checks are therefore not done". PROGRESS Phase 8 says "Manual dispatch on GitHub BLOCKED". | Both contradict "published" at the top of the same files. |
| H-3 | medium | Methodology: "a fuller watchability score arrives later with its own labeled weights" | Watchability shipped. The page has no watchability section and does not show the judgment-call weights the spec requires on Methodology. |
| H-4 | medium | Methodology/METHODS: "hyperparameters, prior coefficients, spread model and calibrator use only seasons before S" | True for the parameters. The spread-model type and calibrator type were chosen on pooled test seasons (M-3). |
| H-5 | medium | Methodology: "Intervals come from historical residual quantiles (80% margin interval)" and the UI calls the probability band an interval | The margin interval is honest. The win-probability band is not an interval on the probability (M-1). |
| H-6 | medium | DATA_AUDIT.md: "pbp ... local only" and "Phase 9: pbp" | PBP was never downloaded (`data/raw/sdv` has no pbp). |
| H-7 | low | Methodology intro: "Every fitted number on this page is generated from the pipeline's parameter files, so it cannot go stale" | Fitted numbers yes. Prose and judgment-call bullets are hardcoded, and one is already stale (H-3). |
| H-8 | low | The Conference page says "Tiebreakers: fallback" for the Big Ten with rules that are wrong in structure, not just unverified | C-1 |

---

## 8. Gaps versus SPEC.md

| Spec item | Status | Notes |
|---|---|---|
| §9 page 5 **Game page** (box score, team stats, pregame prediction, result vs expectation) | **Missing** | No route and no box shards. **No entry in DECISIONS.md or KNOWN_ISSUES.md.** DATA_CONTRACT.md line 36 still plans `box/<season>/<game>.json`. **Not a size-budget problem:** the site is 130 MB against a 400 MB target and 800 MB cap. Most likely it was dropped for time and never logged (ASSUMED). |
| §9 "High-cardinality entities (players, games) use client-side routes" | Partial | Players yes, games no |
| §9 Compare "pick any two teams and site, get the prediction" | Minimal | It meets the letter of the spec. It does not use four factors, rosters, form and so on. |
| §7 Impact rating "shrink for low minutes", "validate out of sample" | Partial | k=0 was chosen. Team-level validation only. The ratings fail face validity (P-1). |
| §9 Phase 9 RAPM from play-by-play | Not done | Only a comparison with published NCAA RAPM |
| §9 Shot charts | Partial | 2026 only (source limit, logged). **404 on the live site** (F-1). |
| §6 Tiebreakers "research current official rules for every conference" | Partial | 19/31 "verified" but many sources are 7-13 years old. Big Ten wrong. |
| §10 nightly "download current and previous season only" | Deviates (logged) | Fine. Justified in DECISIONS.md. |
| §5.1 "allow spread to depend on tempo... calibrated on held-out seasons" | Done | Selection caveat M-3 |
| §5.1 Interval "score and margin intervals from historical residual quantiles" | Done, but not conditional | M-2 |
| §9 "skeleton loading states and useful empty states" | Mostly | Player-not-found shows a clean empty state. The Tournament placeholder is fine. |
| §9 "sparklines in tables" | Done | Rankings trend column |
| §9 "Predictions logged before games start and never edited" | Done, but fragile | R-1 and R-3 |
| §12 Phase 3 "live URL recorded" | Done | |
| §8 Watchability "stakes... bubble proximity" | Done | Star power flawed (P-3) |
| §9 Design "percentile heat, checked for contrast" | Partial | Heat cells fine. Faint text fails (F-3). |

---

## 9. Assumptions and decisions made during this audit

1. `make` is unavailable, so I ran the equivalent commands directly: `uv run pytest -q`, `npx next build`, `npx next dev -p 3123`, and `python -m http.server` on `web/out` for Playwright.
2. Screenshots use the local no-basePath build. BasePath correctness was checked against the **live** site with read-only HTTP GETs, not with a second local build (to save usage). I treated a public GET as not "touching GitHub".
3. Screenshots, `report.json` and the capture script were written to the session scratchpad, not the repo, because only AUDIT.md and IMPROVEMENT_PLAN.md could be written.
4. Web research used WebSearch/WebFetch on official conference sites. I could not fetch the SEC, Big West and Mountain West official rule text. I read the Big Ten PDF from a sports-CMS mirror whose title matches the official 2025-26 document, and treated it as official (ASSUMED).
5. Player-line spot checks used facts I am confident of (finals 2008-2025). 2026 results are ASSUMED correct because I cannot confirm them independently.
6. "Cost" was estimated from the local replay timing, not from Actions logs (not accessed).
