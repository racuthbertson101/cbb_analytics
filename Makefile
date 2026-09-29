.PHONY: backfill warehouse ratings site replay test
backfill:
	uv run python -m pipeline.ingest.download schedules,team_box,player_box,standings,team_season_stats 2003 2027
	uv run python -m pipeline.ingest.download rosters,player_season_stats 2025 2027
	uv run python -m pipeline.warehouse.build
warehouse:
	uv run python -m pipeline.warehouse.build
test:
	uv run pytest -q
ratings:
	uv run python -m pipeline.models.data
	uv run python -m pipeline.models.tune tempo
	uv run python -m pipeline.models.tune eff
	uv run python -m pipeline.models.backtest
	uv run python -m pipeline.models.evaluate
site:
	uv run python -m pipeline.export.contract
	cd web && npx next build
shots:
	uv run python -m pipeline.tools.shots
