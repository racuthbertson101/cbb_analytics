---
name: cbb_modeling_rules
description: Rules for building/altering rating systems and predictions in cbb_analytics (leakage, fitted vs defined constants, walk-forward validation, calibration, shared interface).
---
# Modeling rules
- **No leakage.** Rating/prediction for a game uses only games strictly before its date (same-day games excluded). `pipeline/tests` has a leakage test; keep it passing.
- **No guessed constants.** Anything that changes a rating or prediction is estimated from data or chosen by walk-forward validation and written to `pipeline/params/*.json` with validation evidence. Definitions (quadrant cutoffs, bubble team, tiebreakers) are allowed but labeled `# DEFINITION` in code and on the Methodology page. Watchability weights are a labeled judgment call.
- **Walk-forward:** for each test season S, tune hyperparameters on seasons < S only, fit on games before each date, predict, score. Report MAE, RMSE (margin), log loss, Brier, reliability curve, accuracy by confidence bucket.
- **Baselines:** home-team-wins, previous-season-rating-only, simple Elo. If a system doesn't beat home-wins, don't present it as predictive; log it.
- **Calibration:** win prob from margin via residual-derived spread, then isotonic/Platt on held-out seasons. Report numbers whatever they are.
- **Interface** (every system in `pipeline/models/`, registered in the registry):
  `fit(games_before_date, params) -> ratings`;
  `predict(team_a, team_b, site, date) -> {margin, total, score_a, score_b, win_prob_a, interval}`.
- To add a system: new module implementing the interface, register it in `pipeline/models/registry.py`, add a backtest entry, add site toggle via config. No core edits.
