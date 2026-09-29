# Extending the project

## Add a ranking system

1. Write a module in `pipeline/models/` implementing the shared interface and register it:

   ```python
   from pipeline.models.registry import register

   @register("mysys")
   class MySystem:
       name = "My system"
       @staticmethod
       def fit(games_before_date, params): ...      # only games strictly before the date
       # the returned ratings object exposes predict(team_a, team_b, site, date)
       #   -> {margin, total, score_a, score_b, win_prob_a, interval}
   ```
2. Backtest it walk-forward (see `pipeline/models/evaluate.py` and the `cbb_modeling_rules` skill): every constant estimated from data, evidence written to `pipeline/params/`.
3. To show it in the Rankings toggle, drop a module into `pipeline/models/extra/` (see `_template.py`) exposing `KEY` and `snapshots(season, teams, dates)`. `pipeline.export.systems` exports it automatically into `systems/<season>.json`.
4. Add `["mysys", "My system"]` to `rankingSystems` in `web/config/site.json`. No core file changes.

## Add a site tab

Create `web/app/<name>/page.tsx` (client component wrapped in `<Suspense>` if it uses `useSearchParams`), read data through `useJson()` / `dataUrl()` (basePath aware), and add `["/<name>/", "Label"]` to `nav` in `web/config/site.json`. Add any new JSON to the exporter under `pipeline/export/` and document it in `docs/DATA_CONTRACT.md`. Static-param routes (teams, conferences) use `generateStaticParams`; high-cardinality entities (players, games) use query-string routes plus small JSON shards.

## Add a conference tiebreaker rule

Rules are data: `config/tiebreakers/<conference>.yaml` (`rules` list of tokens, `restart_on_partial`, `qualifiers`, `bye_seed_lines`, `source_url`, `status: verified|fallback`). Tokens are implemented in `pipeline/sims/tiebreak.py` (`rule_keys`); add a token there and use it in YAML. Edit `pipeline/sims/make_configs.py` to regenerate all configs.

## Add women's basketball

The path layer is parameterized by `SPORT = "mbb"` (`pipeline/warehouse/paths.py`): warehouse tables live under `data/warehouse/<sport>/`. Steps: point `pipeline/ingest/download.py` at the `espn_womens_college_basketball_*` release tags (same file layout), change the ESPN base URL in `pipeline/ingest/espn.py` to `womens-college-basketball`, set `SPORT = "wbb"` (or make it an environment variable), refit everything (`make ratings`), give the site a `wbb` data prefix (`dataUrl()` in `web/lib/data.ts`) and a sport switch in `web/config/site.json`, and add conference tiebreaker configs. The models and simulations are sport-agnostic apart from the possession constant (refit automatically) and the D-I definition.

## Add a PWA and a mobile layout later

- PWA: add `web/public/manifest.webmanifest`, icons, and a service worker that caches `/data/*.json` (stale-while-revalidate) and the app shell; register it from `app/layout.tsx`. All data is static files, so offline support is a cache policy.
- Mobile: layouts use CSS grid with fixed column counts (`grid-cols-3/4`) and 1440-1920 px assumptions. Steps: responsive column classes (`sm:`/`lg:` prefixes), a collapsible nav, horizontally scrollable tables with sticky first column, and a bottom sheet for the search palette. Tables already use tabular numerals and dense rows, so only widths need work. A written readiness list is in `KNOWN_ISSUES.md`.

## Tournament work (stub is in place)

`pipeline/tournament` has the bracket schema (regions, seeds, play-in games, rounds) and `simulate_bracket(bracket, predictor, n_sims)`, which accepts any object with `predict()` (for example the object returned by `pipeline.models.production.Predictor`). Game type (`ncaa`, `nit`, ...) and seed columns already exist in the warehouse `games` table.
