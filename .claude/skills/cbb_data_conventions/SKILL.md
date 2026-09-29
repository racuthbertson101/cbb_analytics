---
name: cbb_data_conventions
description: ID conventions, warehouse schemas, idempotent ingestion, D-I filtering, caching, ESPN etiquette and release asset naming for cbb_analytics.
---
# Data conventions
- Keys: ESPN team_id, athlete_id, game_id (strings). Name aliases in a crosswalk table. `sport = mbb` is a parameter in paths/config.
- Tables (parquet, per season under `data/warehouse/<sport>/<table>/<season>.parquet`): games, team_games, player_games, players, teams, team_seasons (conference by season), rosters.
- games stores game_type (regular, conf_tourney, ncaa, nit, other_post, exhibition), neutral_site, seed fields when present.
- D-I membership defined per season from data (teams with enough games vs D-I opponents). Non-D-I games stay in the warehouse but are excluded from fits; still shown on schedules.
- Ingestion is idempotent: dedupe on game_id, schema validation, rerun = no change. Recheck last 3 days each night.
- Cache every download/API response on disk in `data/raw/` (gitignored). Limit concurrency (<=4), retries with backoff, normal UA.
- Never scrape HTML from KenPom, Barttorvik, Sports Reference.
- Season convention: season = year the season ends (2025 = 2024-25).
- Release assets: tag `warehouse`, name `<table>__<season>.parquet`, plus small model artifacts. PBP and shots are not published.
