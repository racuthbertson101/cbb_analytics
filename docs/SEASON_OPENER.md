# Season opener checklist (2026-27)

The first real nightly run of the season is **Mon Nov 2, 2026, 07:30 UTC** (GitHub often starts scheduled runs late: the October runs started between 12:40 and 16:20 UTC).
Local items were run on 2026-10-05; GitHub items are for the owner, with exact commands.

## 1. Local: two consecutive replay nights (rehearsal mode)

```bash
uv run python -m pipeline.nightly --today 2026-02-15 --rehearsal --rehearsal-reset --force --nsim 3000 --no-build
uv run python -m pipeline.nightly --today 2026-02-16 --rehearsal --force --nsim 3000
```

- [x] Ingest finds games: night 1 re-ingested 258 completed games (2026-02-11..14), night 2 added the 32 games of Feb 15 (290).
- [x] Validation passes both nights (null ceilings, 99% player-sum agreement). Night 2 is a Monday, and the canary agreed with hoopR on 680/680 team-games.
- [x] Log rows and HEAD advance: 380 rows after night 1, 737 after night 2 (`data/rehearsal/predictions/HEAD.json`). `log.check()` is clean.
- [x] The second night's predictions are the scored ones: all 348 games logged on both nights are scored on the Feb 16 prediction. Feb 15 games are scored on the Feb 15 prediction (`days_before` 0).
- [x] The standings simulation uses the run date: snapshot `asof` 2026-02-15 on night 1 and 2026-02-16 on night 2. No hardcoded date.
- [x] The site builds, and status.json shows "data through 2026-02-15" for the footer.
- [x] Real data untouched: the SHA-256 of all 148 files in `predictions/`, `data/warehouse/` and `data/backtest/` was identical before and after every rehearsal and drill.

## 2. Local: opening night, offseason to live

```bash
uv run python -m pipeline.nightly --today 2026-11-02 --rehearsal --rehearsal-reset --force --nsim 3000
```

- [x] **Found and fixed two crashes** (the real Nov 2 run would have failed): with zero completed games, the live path crashed building player tables and then exporting rankings. Fix: the preseason prior becomes the season's first rating snapshot; player tables, validation, BT and résumé wait for results. The site flips to the live season once results are expected, and a run with expected but missing results fails.
- [x] `live` flips: the night predicts and logs, while the site keeps the preseason view (current 2025-26, upcoming 2026-27) until results exist.
- [x] The preseason prior is used: Miami @ Florida p = 0.9067 in both the log and the site.
- [x] Predictions exist: 355 logged for Nov 2-9, every D-I game. ESPN's live scoreboard added about 360 games missing from the bulk schedule (Nov 2: 169 games, all 119 D-I games predicted).
- [x] No false "non-D-I" labels: the 50 non-D-I games on Nov 2 really involve non-D-I opponents.
- [x] **Extra, the first-results morning** (the real 2025-26 opener, which has results): `--today 2025-11-03 --rehearsal-reset`, then `--today 2025-11-04`. Night 2 ingested 169 results, validation passed, the site flipped to the live season, and the Accuracy page scored 108 games, all on same-day predictions (`days_before` 0). `--today 2025-11-06` also ran clean after a parser fix (below).

## 3. Local failure drills

- [x] **Network down mid-ingest** (requests routed through a dead proxy, `--today 2025-11-05 --rehearsal`): exit 1 with `RuntimeError: ESPN request failed after retries`. `web/out/index.html` (hash and mtime) and the log HEAD were unchanged.
- [x] **Corrupted ESPN summary** (cached summary 401811102 with `turnovers` renamed, `--today 2025-11-06 --rehearsal`): exit 1 with `SchemaError: 1 of 240 completed games: game 401811102: ESPN summary missing ['turnovers']`. The cache was restored byte for byte. Also covered by `pipeline/tests/test_schema_drift.py`.
  - The first attempt found a **real bug**: ESPN listed a Bluefield DNP player with no athlete id (game 401826937), and the parser crashed with `KeyError: 'id'`. Such players are now skipped (regression test added).
- [x] **Deleted log** (rehearsal `predictions/log/` removed, HEAD kept): `check()` gives "log has 0 rows but HEAD says 955". The next night exits 1: "refusing to append to a log that fails verification". Also `test_missing_or_shortened_log_fails`.
- [x] **Interrupted release upload** (injected uploader failing on the 3rd file, real local files): two assets went up under new versioned names, the manifest was never uploaded, and the previously published manifest and its assets were untouched. Also `test_failure_mid_upload_leaves_previous_manifest`.

## 4. Owner, around Oct 20: rehearsal dispatch on GitHub

```bash
gh workflow run nightly.yml -f rehearsal=true -f today=2026-02-15 -f nsim=3000
gh run watch $(gh run list --workflow nightly.yml --limit 1 --json databaseId -q '.[0].databaseId')
gh run download $(gh run list --workflow nightly.yml --limit 1 --json databaseId -q '.[0].databaseId') -n rehearsal-2026-02-15 -D rehearsal-out
```

- [ ] Run green; the `deploy` and `sync` jobs show as skipped.
- [ ] The artifact contains `web/out/index.html` and `data/rehearsal/predictions/HEAD.json` with rows > 0.
- [ ] Live site and release unchanged: `gh release view warehouse --json assets -q '.assets|length'` is the same before and after, and the site footer's "updated" time did not move.

## 5. Owner, around Oct 27: opening-night rehearsal on GitHub

```bash
gh workflow run nightly.yml -f rehearsal=true -f today=2026-11-02 -f nsim=3000
```

- [ ] Run green. The artifact's `data/rehearsal/nightly_status.json` has `"live": true` and `"logged"` > 300.

## 6. Owner, Nov 1: final checks

```bash
gh workflow list                                                    # nightly is "active" (scheduled workflows pause after 60 days without repo activity)
gh release download warehouse -p manifest.json -O - | head -5       # manifest present (written by the first Monday sync, Oct 12)
gh api repos/:owner/cbb_analytics/pages -q .build_type              # "workflow"
gh api repos/:owner/cbb_analytics/actions/permissions/workflow -q .default_workflow_permissions   # "write"
cat predictions/HEAD.json                                           # rows 0, last_hash "genesis"
uv run python -c "import pandas as pd; t=pd.read_parquet('data/warehouse/mbb/team_seasons/2027.parquet'); print(t.is_d1.sum())"   # >= 355
```

- [ ] All six checks pass.

## 7. Nov 2 morning (first real run)

```bash
gh run list --workflow nightly.yml --limit 1
git pull && cat predictions/HEAD.json && ls predictions/log/2026/
```

- [ ] Workflow green: build, deploy and sync all succeeded.
- [ ] `predictions/log/2026/11-02.csv` committed by github-actions, with about 350 rows.
- [ ] The site footer shows today's update time. The Today page's win probabilities match the CSV's `p`.

## 8. Nov 3 morning

- [ ] The first results were ingested (`nightly_status.json` in the run log: `completed` > 0), and the site's current season is 2026-27.
- [ ] The Accuracy page scores the Nov 2 games. `HEAD.json` rows increased, and `days_before` is 0 or 1.

If any step fails, the previous site stays up (deploy runs only after a green build). Fix, then re-run with `gh workflow run nightly.yml`.
