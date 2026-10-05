# Methods

The live, always-current version of this document is the site's Methodology page, generated from `pipeline/params/`. This file explains the design.

## Data

Bulk ESPN-derived Parquet releases from the sportsdataverse project (schedules, team and player box scores, standings, rosters) cover 2008 onward with at least 98% box-score coverage; ESPN's public JSON endpoints (scoreboard and game summary) provide daily updates. The warehouse keeps ESPN team and athlete IDs, game type, neutral-site flags, and conference by season. Division I membership per season is defined from standings. See `DATA_AUDIT.md`.

## Adjusted efficiency (main rating)

Response: points per 100 possessions for each team in each D-I game. Predictors: offense dummy of the team, defense dummy of the opponent, home court (+1/0/-1). Ridge regression shrinks team effects toward a preseason prior (a regression on the last two seasons' final ratings). Possessions per game are FGA - OREB + TOV + c·FTA with c estimated so both teams' estimates agree; tempo has its own ridge model. Predicted score = predicted possessions × efficiency. Win probability is the normal CDF of the margin over a tempo-dependent spread estimated from historical residuals, then calibrated on held-out seasons. The 80% interval is an outcome interval on the margin from residual quantiles (80% of results land in it); there is no interval on the win probability (an estimate interval from rating uncertainty is planned). Ridge strength, recency decay, blowout cap and team-specific home court were chosen or rejected by walk-forward validation (`pipeline/models/tune.py`).

## Backtest

For each test season S the model is refit at every game date using earlier games only; hyperparameters, prior coefficients and the spread and calibration parameters use only seasons before S. Two one-time choices were made on pooled results from all test seasons: spread form (constant vs tempo-dependent) and calibrator type (raw, Platt or isotonic); the candidates differ by under 0.001 log loss (`pipeline/models/evaluate.py`). Metrics: MAE/RMSE of margin, log loss, Brier, reliability curve, accuracy by confidence bucket, versus baselines (home team wins, previous-season rating, simple Elo). Leakage tests (`pipeline/tests/test_leakage.py`) scramble same-day and future results and assert that earlier predictions do not change.

## Other systems

Margin-aware Elo (Gaussian maximum likelihood), results-only Bradley-Terry (ridge logistic), résumé metrics (WAB, SOR, quadrants; definitions in `pipeline/models/resume.py`), player-driven rating (below), and a consensus fitted by non-negative least squares on held-out margin error.

## Players

Per-player rates use ratio-of-sums with team totals. Impact v1 (experimental) regresses team adjusted offense/defense on minutes-weighted player rate features; a low-minutes shrinkage was tested and validation chose none (k = 0). It fails face validity (it overrates rebounders and shot blockers), so the site shows it only on player pages, labeled experimental. A roster-based preseason prior (returning and incoming players, from their previous-season impact and minutes) was tested against the ratings-only prior by walk-forward cross validation and adopted. RAPM from play-by-play is planned (IMPROVEMENT_PLAN.md Phase 5); play-by-play has not been downloaded yet.

## Conferences

Monte Carlo (>= 20,000 simulations): known games fixed, remaining games sampled as predicted margin plus noise, integer scores, per-conference tiebreaker rules from `config/tiebreakers/*.yaml` with restart-on-partial-split semantics.

## Watchability

Five components (quality, competitiveness, tempo, star power, stakes) scaled 0-100 by historical percentile; weights are a labeled judgment call in `config/watchability.yaml`.

## Automation

`pipeline/nightly.py` runs ingest -> validate -> refit -> predict -> log -> simulate -> export -> build; `pipeline/replay.py` runs the same path against a truncated past date.
