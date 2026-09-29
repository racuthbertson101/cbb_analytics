# Final report

## Status in one paragraph

Everything in the spec was built and verified locally: warehouse (2008-2027), adjusted-efficiency ratings with a walk-forward backtest, five more ranking systems and a consensus, a player layer, conference simulations with per-conference tiebreaker rules, watchability, an append-only prediction log, a 413-page static site, a nightly pipeline plus replay test, workflows, docs and stretch items. ****Update: it is now published** at https://racuthbertson101.github.io/cbb_analytics/ (repo racuthbertson101/cbb_analytics; `deploy.yml` and a manual `nightly.yml` dispatch both succeeded).

## What works (verified)

- **Tests**: 161 pass (warehouse validation for every season, leakage, tiebreaker scenarios including a three-team tie, conference simulation sanity, prediction-log tamper detection, watchability, tournament stub, ESPN parser vs warehouse, nightly window logic, player rate sanity).
- **Warehouse**: idempotent build (hash-verified); D-I count 341-365 per season; NCAA tournament games found for every season (some source gaps: 2009/2010/2013).
- **Incremental ESPN ingest** re-created 58 games (team and player box scores) for 2026-03-19..24 with 100% agreement on scores, flags, team stats and player minutes/points, and a second run changed nothing.
- **Replay test** (`make replay DATE=2026-02-15`): truncates the warehouse to that morning, re-ingests from ESPN with results masked, validates, refits, predicts the next 7 days (378 predictions logged), simulates conferences, exports and builds. Ratings match the walk-forward backtest within 0.02 points. Offseason mode (`--today 2026-09-29`) also runs end to end.
- **Site**: Today (with replay `?asof=` / `?date=`), Rankings (6 systems, résumé view, as-of date, preseason 2026-27), Team, Player, Players, Conferences, Conference, Accuracy, Compare, Methodology, Tournament placeholder, Ctrl+K search. Also verified under `basePath=/cbb_analytics`.

## Key fitted parameters and backtest (test seasons 2012-2026, 81,567 games)

| System | MAE | RMSE | Log loss | Accuracy |
|---|---|---|---|---|
| Adjusted efficiency (calibrated) | 8.89 | 11.28 | 0.5263 | 72.9% |
| Simple Elo (win/loss) | 9.46 | 12.04 | 0.5473 | 71.5% |
| Previous-season rating only | 9.89 | 12.54 | 0.5879 | 67.8% |
| Home team wins | 11.14 | 14.23 | 0.6536 | 64.9% (non-neutral) |

Calibration: Platt (chosen by walk-forward log loss), expected calibration error 0.008; a stated 70% wins about 71%. NCAA tournament games (924): MAE 9.08, log loss 0.543, accuracy 71.0%.
Ridge strength 3, no recency decay, blowout cap 60 (essentially neutral), team-specific home court rejected (hurt out of sample), possession FTA weight 0.4857, tempo ridge 3 with 30-day half-life, margin spread 11.0 + 0.104 per possession above 68. Roster prior: adopted (see below). Consensus (2015-26): MAE 8.91 vs adjusted efficiency 8.97 and Elo 9.01; weights adjusted efficiency 0.58, Elo 0.37, previous-season 0.05, Bradley-Terry 0. Player impact: in-sample R2 0.71 offense / 0.44 defense; correlation with published NCAA RAPM 0.27 (offense 0.38, defense 0.23).

## Every fallback and judgment call (details in DECISIONS.md / KNOWN_ISSUES.md)

- **GitHub blocked** (above). All GitHub-dependent phase checks (push, release assets, live URL, workflow dispatch) are therefore not done.
- **A bug and a correction found late**: (1) the Crown pseudo-group dropped Oklahoma's D-I status in 2025-26 (fixed, every artifact refit); (2) my first roster-prior evaluation was invalid (athlete-id format made roster features all zero, so it said "not adopted"). After the fix the roster prior improved next-season team ratings in 14/14 (offense) and 12/14 (defense) walk-forward seasons and improved game-level log loss from 0.5289 to 0.5263, so it is adopted. The evidence is slightly optimistic because historical "rosters" are the players who actually appeared that season (true preseason rosters exist only for 2025+).
- **Definitions** (labeled in code and on the Methodology page): start season 2008, D-I membership from standings, game-type heuristic, bubble = rank 45, SOR reference = top 25 average, NCAA quadrant cutoffs, weekly snapshots, our rating in place of NET/RPI. **Judgment call**: watchability weights (`config/watchability.yaml`).
- **Conference tiebreakers**: 19 of 31 verified from official conference pages (via search excerpts and fetched pages); 12 fallback (Big Ten's PDF could not be read, some conferences had no findable official text). Tournament field sizes are config values, not verified.
- Impact v1 scale is inflated for extreme rebounders/shot blockers and defense is weakly identified from box scores; it is a labeled v1.
- Elo matches the ridge model closely on margin error; Bradley-Terry adds nothing to the consensus.
- Shots data is complete only for 2026 (2025 file has about a quarter of the shots), so shot charts cover the latest season only. Game logs kept for 3 seasons (size budget). Non-adjusted systems and résumé metrics are weekly snapshots; player-driven rating is season-end only.
- Nightly downloads all seasons of the small warehouse tables (not only current + previous) because Elo, consensus and site exports use full history.
- ESPN returns 403 to unusual or full-Chrome user agents from python-requests; the client sends `Mozilla/5.0`.
- The live scoreboard on the Accuracy page starts empty because no live season has been observed; the prediction log starts when the nightly job first runs in season.

## Exact next steps

1. Watch the first scheduled nightly runs (07:30 UTC). Offseason runs are light (Mondays plus manual).
2. After the 2026-27 season: run `refit.yml` (or `make ratings`), re-check the roster-prior evidence, and fill in verified tiebreaker text for the 12 fallback conferences.
3. Tournament module (stub ready), true preseason rosters for the prior, RAPM from play-by-play, mobile list in `docs/MOBILE_READINESS.md`.
