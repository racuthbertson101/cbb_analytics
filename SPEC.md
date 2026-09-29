# CBB Analytics: Build Spec

A personal Division I men's college basketball statistics, ratings and prediction website. Think KenPom plus EvanMiya plus Sports Reference, with better graphics and team logos. Built to run itself daily and to be extended (tournament prediction comes next).

---

## 0. Operating rules (read first, obey always)

1. **Never ask the user a question and never wait for input.** If something is ambiguous, choose the most reasonable option, write the choice and the reason to `DECISIONS.md`, and continue.
2. **Keep `PROGRESS.md` current.** It holds a checklist of phases and steps with status, the last completed step, the next step, and blockers. Update it after every meaningful step. This session can be cut off at any moment by usage limits, so every phase must be resumable from `PROGRESS.md`, `CLAUDE.md` and git alone.
3. **Commit after every completed step** with a clear message. Push to GitHub at the end of every phase.
4. **Limit retries.** If a problem takes more than 3 real attempts, pick a fallback, log it in `KNOWN_ISSUES.md`, and move on. Never sink the whole run into one problem.
5. **Verify before claiming done.** Run the tests, run `next build`, look at screenshots. A phase is done only when its checks pass, or the failure is logged in `KNOWN_ISSUES.md` with the reason.
6. **Stay inside the project folder.** Do not modify anything outside it, except installing packages and configuring the GitHub repo created for this project. Never commit secrets or tokens.
7. **Conserve usage.** Summarize tool output instead of printing it. Print dataframe heads and shapes, not full tables. Run long jobs in the background with logs. Cache every download and every API response on disk so reruns are cheap. Do not reread large files without a reason.
8. **No guessed constants in the modeling.** Any number that changes a rating or a prediction must be estimated from data or chosen by walk forward validation, then stored in a params file along with the validation evidence. Definitions (for example quadrant cutoffs, tiebreaker rules, the definition of a bubble team) are allowed but must be labeled as definitions in code and on the Methodology page.
9. **No leakage.** A rating or prediction for a game uses only information available before that game started. Write a test that proves this.
10. **Be polite to data sources.** Limit concurrency, use retries with backoff, identify with a normal user agent, and cache. Never scrape HTML from KenPom, Barttorvik, Sports Reference or similar sites.

## 1. Goal

A public website, updated automatically every night during the season, with:

* Team and player statistics for every Division I men's team, going back as far as reliable data exists, down to box score level for both teams and players.
* Several ranking systems built on different philosophies, plus a consensus.
* A prediction for every game (predicted score, predicted margin, win probability with an interval).
* Conference level statistics and rankings, and projected conference standings from simulation with real tiebreakers.
* A game watchability rating for every upcoming game.
* A transparent Methodology page showing every fitted parameter and every backtest result.

Excluded: referee ratings and other obscure KenPom extras. No betting lines. Women's basketball is out of scope but keep paths and config parameterized by `sport = mbb` so it could be added.

## 2. Fixed decisions

* **Pipeline:** Python 3.11+, managed with `uv`. Libraries: pandas or polars, numpy, scipy, scikit-learn, duckdb, pyarrow, pytest. No deep learning. No gradient boosting in v1.
* **Storage:** Parquet files queried with DuckDB. No hosted database.
* **Site:** Next.js (App Router), TypeScript, Tailwind CSS, static export (`output: 'export'`). No server runtime. Deployed to GitHub Pages from a public repo named `cbb_analytics`. Set `basePath` correctly and make every data fetch respect it.
* **Automation:** GitHub Actions on the public repo (free minutes).
* **Design:** Dark mode first. Web (desktop) first, 1280 to 1920 px wide. Do not hard code layouts in a way that would block mobile later, but do not spend time on mobile now.
* **Logos:** Use the logo URLs from ESPN's teams data (verify they load). Fall back to a monogram in the team color.

## 3. Repository layout

```
cbb_analytics/
  CLAUDE.md  SPEC.md  PROGRESS.md  DECISIONS.md  KNOWN_ISSUES.md  DATA_AUDIT.md
  .claude/skills/            project skills (section 13)
  pipeline/
    ingest/                  bulk loaders, ESPN client, validation
    warehouse/               table schemas, DuckDB helpers
    models/                  one module per rating system, shared interface
    sims/                    conference sims, tiebreaker engine, later bracket sims
    tournament/              stub package (section 11)
    export/                  JSON writers and the data contract
    tests/
    params/                  fitted parameters and validation evidence (committed)
  config/                    watchability.yaml, tiebreakers/*.yaml, conferences
  data/                      gitignored: raw cache, warehouse parquet, pbp, shots
  web/                       Next.js app
  docs/                      DATA_CONTRACT.md, METHODS.md, EXTENDING.md
  .github/workflows/         nightly.yml, refit.yml, deploy pieces
  Makefile                   backfill, ratings, site, replay DATE=..., test
```

## 4. Data

### Sources, in priority order

1. **Bulk release files from the sportsdataverse projects** (hoopR men's college basketball data, published as Parquet on GitHub releases). Find the exact repos, release tags and asset names with the GitHub API (`gh api`) and by reading the hoopR source. Look for: schedules, team box scores, player box scores, rosters, player season stats, play by play, shot events, and any NCAA derived datasets (lineups, possessions, RAPM).
2. **ESPN public JSON endpoints** for daily updates and gaps: scoreboard for a date (Division I group filter, high limit), game summary with box score, teams, team rosters, team schedules. Discover the exact URLs and parameters from the hoopR source instead of guessing.
3. **CollegeBasketballData API** only if a key exists in the environment. It is not required and must not be a dependency.

### Audit (Phase 0 deliverable: `DATA_AUDIT.md`)

Per season: total games, Division I games, percent with team box scores, percent with player box scores, percent with play by play, percent with shot data, missing fields, whether minutes are present, whether neutral site and game type flags exist, whether team IDs are stable, and whether conference membership by season is available. Choose the start season as the earliest season with complete enough box score coverage, and log the threshold you used. Note which datasets each later phase depends on.

### Warehouse

Parquet, one file per table per season where sensible. Tables: `games`, `team_games`, `player_games`, `players`, `teams`, `team_seasons` (with conference by season, because membership changes over time), `rosters`. Play by play and shots are stored locally but are not needed by the nightly job.

* Use ESPN team and athlete IDs as keys. Keep a crosswalk of name aliases.
* Game type must be stored (regular season, conference tournament, NCAA tournament, NIT, other postseason, exhibition) and neutral site must be stored.
* Division I membership is defined per season from the data. Games involving non Division I opponents stay in the warehouse but are excluded from rating fits and are still shown on team schedules.
* Ingestion must be idempotent: rerunning changes nothing. Dedupe on game ID. Validate schemas.
* Validation tests: no duplicate game IDs, both teams present for every game, team points equal the sum of player points within a small tolerance, possessions are plausible, about 350 to 365 Division I teams per season, dates are sane.
* Publish the warehouse (without play by play and shots) as GitHub Release assets under a tag named `warehouse`, one asset per table per season, so the nightly job downloads only the current and previous season plus small model artifacts.

## 5. Modeling

Every rating system implements a shared interface so systems, the simulator and the future tournament module can plug together:

```
fit(games_before_date, params) -> ratings
predict(team_a, team_b, site, date) -> {margin, total, score_a, score_b, win_prob_a, interval}
```

### 5.1 Adjusted efficiency (the main predictive system)

Ridge regression in the Barttorvik and KenPom family. For each team in each game, the response is points per 100 possessions. Predictors are offense team dummies, defense team dummies, and a site variable (home, away, neutral). Sample weights combine recency decay and a downweight or cap for blowout margins. A separate tempo model estimates possessions.

Everything below is estimated or tuned, not guessed:

* **Home court advantage** is estimated from data. Test whether team specific home court effects (shrunk toward the league mean) improve out of sample prediction. Keep them only if they do.
* **Ridge strength, recency decay and the blowout treatment** are chosen by walk forward validation: for each test season S, tune on seasons before S only.
* **Preseason prior:** ratings at the start of a season shrink toward a prior predicted from last season's final rating and, once the player layer exists (Phase 4), returning minutes and returning player impact. The prior enters as the shrinkage target of the ridge fit, so its influence fades naturally as games accumulate. The prior's regression coefficients and its strength are fit from history.
* **Score prediction:** predicted possessions times predicted efficiency for each side.
* **Win probability:** derived from the predicted margin using a spread distribution estimated from historical residuals (allow the spread to depend on predicted tempo if the data supports it), then calibrated on held out seasons (isotonic or Platt, whichever validates better). A stated 70 percent must win about 70 percent of the time.
* **Interval:** score and margin intervals from historical residual quantiles.

### 5.2 Backtest (required)

Walk forward over every usable test season. For every game, predict using only prior games. Report MAE and RMSE of margin, log loss, Brier score, a reliability (calibration) curve, and accuracy by confidence bucket. Compare against baselines: home team wins, previous season rating only, and a simple Elo. Save results as JSON and Markdown in `pipeline/params/` and render them on the Methodology page. Store ratings as of every game date for every season (pregame ratings), which also powers rating trend charts.

If a system fails to beat the home team wins baseline, do not present it as predictive. Log it.

### 5.3 Other ranking systems (Phase 5)

1. **Elo:** margin aware, with home court, seasonal carryover and K all fit by maximum likelihood on training seasons.
2. **Results only Bradley Terry:** ridge logistic on win and loss only, ignoring margin.
3. **Résumé metrics:** wins above bubble, strength of record, strength of schedule variants, quadrant records, luck (actual wins minus expected wins). Bubble team definition, quadrant cutoffs and site adjustments are definitions. Use our own predictive rating in place of NET and label it clearly.
4. **Player driven rating:** team rating built bottom up from roster minutes and player impact (Phase 4), in the spirit of EvanMiya.
5. **Consensus:** blend weights fit by non negative least squares on held out margin error, and a mean rank. Weights are learned, not chosen.

An optional challenger such as a boosted tree may be tested inside the backtest, and is adopted only if it clearly beats ridge out of sample across most seasons. Log the result either way.

## 6. Conferences

* **Conference statistics and rankings** for any stat (adjusted offense, adjusted defense, adjusted margin, tempo, four factors, strength of schedule, nonconference record, actual versus expected performance against other conferences), for the current season and history by season. Use conference membership as of each season.
* **Projected standings by simulation.** Monte Carlo with at least 20,000 simulations of the remaining conference games, using the game prediction model. Sample actual scores (predicted margin plus residual noise, and a sampled total) so point differential tiebreakers work. Known results are fixed.
* **Tiebreaker engine.** Ordered rule lists per conference, stored as data in `config/tiebreakers/*.yaml`. Research the current official tiebreaker rules for every Division I conference on the web, implement them, and save the source URL in each config. Mark each conference as `verified` (rule text found in an official source) or `fallback` (generic rules used). The generic fallback: head to head, record against common opponents, record against the top of the standings in order, then random. Handle multiple team ties correctly, including the common rule that a partially resolved tie restarts the process for the teams that remain.
* **Outputs per team:** expected wins, distribution of final finish position, probability of the regular season title and of each seed or bye line, best possible and worst possible finish, and clinch or elimination flags. Teams that qualify for a conference tournament differ per league, so make the qualifier count a config value.
* **Tests:** hand built scenarios with known answers, including a three team tie.
* Unbalanced schedules must work with no special code.

## 7. Player layer

* Tables: player game logs and season lines with per 40 and per 100 possession rates and the usual advanced rates (usage, true shooting, effective field goal, assist, turnover, offensive and defensive rebound, steal and block rates, free throw rate, three point rate), computed with team totals. Minutes share. Class, position and height from rosters.
* **Impact rating v1 (box score based, fitted):** regress team offensive and defensive efficiency, adjusted for opponent, on minutes weighted player rate features. The coefficients come from the data, so the weights on each stat are learned. Shrink for low minutes. Validate out of sample: does the roster based rating predict future team performance better than the prior rating alone? Report the result.
* If the audit found lineup or RAPM data, ingest it and compare it against the v1 impact rating. Computing RAPM from raw play by play is a stretch item (Phase 9).
* Use returning minutes and impact in the preseason prior only if cross validation says it helps.
* Percentile ranks versus all Division I players in the same season, and a nearest neighbor "similar players" list if time allows.

## 8. Game watchability

A 1 to 10 score for each upcoming game with a visible component breakdown.

* Components: quality (both teams' ratings), competitiveness (predicted closeness), tempo, star power (top player impact), and stakes (ranking proximity, conference title leverage from the simulation, bubble proximity from résumé metrics).
* Each component is scaled to 0 to 100 by its percentile in the historical distribution, so the scaling is data derived.
* The component weights are a judgment call because there is no ground truth. Put them in `config/watchability.yaml` with a comment saying so, and say so on the Methodology page.

## 9. Website

**Architecture:** static export, JSON data files generated by the pipeline into `web/public/data/` (gitignored, produced during the Actions build). Static params only for low cardinality entities (teams, conferences, seasons). High cardinality entities (players, games) use client side routes with query parameters that fetch small JSON shards. Shard data by season and entity and document it in `docs/DATA_CONTRACT.md`. Size budget: deployed site under 800 MB, target under 400 MB. If over budget, drop the oldest game level detail first (full box scores for old seasons) and log it.

**Pages:**

1. **Today:** all games for the selected date with logos, predicted score, win probability bar with interval, watchability score, conference filter, and a top games strip.
2. **Rankings:** the main table. A toggle between ranking systems and the consensus. Columns include record, adjusted offense, adjusted defense, adjusted margin, tempo, strength of schedule, luck, quad record, and rank change. Sortable, filterable by conference, percentile heat coloring. Season selector and an "as of date" selector for history.
3. **Team page:** logo header, all rating systems, schedule and results with predictions versus actual, remaining schedule with win probabilities, four factors and splits, rating trend chart, roster and player stats, conference standing and projection, previous seasons.
4. **Player page and player leaderboards:** season lines, game logs, percentile ranks, impact rating.
5. **Game page:** box score, team stats, the pregame prediction, and result versus expectation.
6. **Conferences:** rankings by any stat, power ranking, projected standings with finish probability tables.
7. **Predictions and accuracy:** a live scoreboard of how the model is doing, calibration curve, and results by confidence bucket. Predictions are logged before games start and never edited (append only log).
8. **Compare:** pick any two teams and site, get the prediction (this also serves the tournament work later).
9. **Methodology:** every fitted parameter with its value and validation evidence, backtest tables and charts, all definitions, all judgment calls, and data source credits. Generate it from `pipeline/params/` so it never goes stale.
10. **Search:** a command palette over teams and players from a small prebuilt index.
11. **Tournament:** placeholder route that reads an empty JSON file and says it is coming.

**Design (make it look genuinely good, not templated):**

* Dark theme with a deliberate palette and design tokens. Team colors as accents. Restrained motion.
* A strong typographic system with `next/font`. Tabular numerals for all numbers. Dense but readable tables.
* Team logos everywhere, with the monogram fallback.
* A perceptually sound diverging color scale for percentile heat cells, checked for contrast.
* Consistent chart style. Use Recharts or visx. Sparklines in tables.
* TanStack Table for sorting and filtering. Skeleton loading states and useful empty states.
* **Offseason behavior:** show the last completed season and preseason projections for the upcoming season if roster data allows. Support a replay mode (`?asof=YYYY-MM-DD` and `make replay DATE=...`) so any past date can be shown as if it were today. Use this for development and screenshots since the season is not running yet.
* **Screenshot QA:** install Playwright and Chromium, take screenshots of every page group at 1440 by 900, look at them, and fix contrast, overflow, alignment and empty state problems before marking a phase done.

## 10. Automation

* `nightly.yml`: scheduled at `30 7 * * *` UTC (about 3:30 am Eastern, so late West Coast games are final) plus manual dispatch. Steps: checkout, set up `uv` and Node, download warehouse assets (current and previous season plus model artifacts) from the `warehouse` release, ingest completed games since the last ingested date (and recheck the last 3 days for corrections), validate, refit current season ratings with the stored params, predict games for the next 7 days, append to the prediction log, run conference simulations, export JSON, build the site, deploy to GitHub Pages, and upload the updated warehouse assets.
* A season window guard inside the script: full run from November through mid April, and a light weekly run otherwise.
* On any failure the job must fail loudly and leave the previous deployment untouched.
* `refit.yml`: manual dispatch to refit hyperparameters after each season.
* Enable GitHub Pages and set workflow permissions with `gh api`. Deploy with the official Pages actions.
* **Replay test (required):** run the whole nightly path locally against a past date from last season (data truncated to that date) and confirm it produces a correct site. This is the closest you can get to testing an in season night in September.

## 11. Extensibility (leave room, do not build the features yet)

* `pipeline/tournament/` stub with a bracket schema (regions, seeds, play in games, rounds), and `simulate_bracket(bracket, predictor, n_sims)` that takes any object implementing `predict()`. Include a small test with a fake bracket.
* Game type and seed fields already present in the warehouse.
* New ranking systems and new site tabs are added through a registry and config, not by editing core files. Document the steps in `docs/EXTENDING.md`, including how to add women's basketball and how to add a PWA and mobile layout later.

## 12. Phases

Each phase ends with its checks, a `PROGRESS.md` update, a commit and a push.

**Phase 0: Setup and audit.**
Verify tools (`git`, `gh auth status` with repo and workflow scopes, Python 3.11+, `uv`, Node 20+). Install what is missing when possible without sudo, otherwise log it. Create the folder structure, `git init`, create the public repo with `gh repo create cbb_analytics --public` and push. Write `CLAUDE.md`, `PROGRESS.md`, `DECISIONS.md`, `KNOWN_ISSUES.md`. Create the skills (section 13). Run the data audit and choose the season range.
Check: `DATA_AUDIT.md` complete, repo pushed.

**Phase 1: Warehouse.**
Backfill all usable seasons, build the incremental ingest command, write the validation tests, publish the release assets.
Check: tests pass, rerunning ingestion changes nothing, row counts recorded in `PROGRESS.md`.

**Phase 2: Core ratings and predictions.**
Section 5.1 and 5.2, with pregame ratings stored for every game date.
Check: leakage test passes, backtest report exists, model beats baselines, calibration curve is close to the diagonal (report the numbers whatever they are).

**Phase 3: Vertical slice and first deploy.**
Data contract v1, site shell and design system, Rankings, Today (with replay date), a basic Team page, Methodology page, and the first deploy to GitHub Pages using a manual workflow.
Check: `next build` passes, screenshots reviewed, live URL returns 200 and is recorded in `PROGRESS.md`. From here on, the deployed site should always work.

**Phase 4: Players.**
Section 7, player pages and leaderboards, upgrade the preseason prior if cross validation supports it.

**Phase 5: More ranking systems.**
Section 5.3, consensus, and the ranking toggles and résumé columns on the site.

**Phase 6: Conferences.**
Section 6 and its pages.
Check: tiebreaker tests pass, every conference labeled `verified` or `fallback`.

**Phase 7: Watchability, accuracy tracking and remaining pages.**
Section 8, Predictions and accuracy, Compare, history browsing (season selector, as of date, rating trends), search.

**Phase 8: Automation and extension points.**
Section 10 and 11, the replay test, a `README.md` for the human owner, `docs/METHODS.md` and `docs/EXTENDING.md`.
Check: the replay test passes and a manual dispatch of `nightly.yml` succeeds on GitHub.

**Phase 9: Stretch, in this order, only if time remains.**
Shot charts on team and player pages if the shots data is usable. RAPM from lineups or play by play compared against the box impact rating. A written mobile readiness list (documentation only).

**Finish:** write `FINAL_REPORT.md`: what works, what does not, the key fitted parameters and backtest metrics, every fallback and judgment call, and exact next steps.

## 13. Skills and CLAUDE.md (create in Phase 0)

Create `CLAUDE.md` at the repo root (short): the operating rules from section 0, pointers to `SPEC.md`, `PROGRESS.md` and the skills. It is loaded automatically in every new session, which is what makes resuming work.

Create these project skills as `.claude/skills/<name>/SKILL.md` with `name` and `description` frontmatter. Keep each under about 80 lines to save usage:

1. `cbb_modeling_rules`: no leakage, no guessed constants, walk forward validation procedure, calibration reporting, definitions versus fitted parameters, how to add a ranking system through the shared interface.
2. `cbb_data_conventions`: ID conventions, table schemas, idempotent ingestion, Division I filtering, caching, polite use of ESPN endpoints, release asset naming.
3. `cbb_web_design`: design tokens, table and chart conventions, logo component and fallback, static export and basePath gotchas, the screenshot QA routine.

Also try to install Anthropic's `frontend-design` skill: clone `github.com/anthropics/skills`, find the `frontend-design` folder, and copy it into `.claude/skills/`. If that fails, fold its ideas into `cbb_web_design` and log it.
