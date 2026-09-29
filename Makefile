.PHONY: backfill warehouse ratings systems site replay test shots nightly
PY=uv run python
backfill:
	$(PY) -m pipeline.ingest.download schedules,team_box,player_box,standings,team_season_stats 2003 2027
	$(PY) -m pipeline.ingest.download rosters,player_season_stats 2025 2027
	$(PY) -m pipeline.warehouse.build
	$(PY) -m pipeline.players.seasons
warehouse:
	$(PY) -m pipeline.warehouse.build
	$(PY) -m pipeline.players.seasons
# Full refit of every model artifact and hyperparameter (slow: ~35 min). Run after each season or after a data fix.
ratings:
	$(PY) -m pipeline.models.data
	$(PY) -m pipeline.models.tune tempo
	$(PY) -m pipeline.models.tune eff
	$(PY) -m pipeline.models.backtest
	$(PY) -m pipeline.models.evaluate
	$(PY) -m pipeline.players.prior_eval
	$(PY) -m pipeline.players.build_players
	$(PY) -m pipeline.models.elo_mle
	$(PY) -m pipeline.models.bt
	$(PY) -m pipeline.models.consensus
	$(PY) -m pipeline.models.resume
	$(PY) -m pipeline.sims.make_configs
site:
	$(PY) -m pipeline.export.conferences --stats --sim 2026:2026-02-15 2026:2026-04-10
	$(PY) -m pipeline.export.contract
	$(PY) -m pipeline.export.players
	$(PY) -m pipeline.export.systems
	$(PY) -m pipeline.export.accuracy
	cd web && npx next build
# Run the whole nightly path as if today were DATE, e.g. make replay DATE=2026-02-15 (then `make site` restores the normal site)
replay:
	$(PY) -m pipeline.replay $(DATE)
nightly:
	$(PY) -m pipeline.nightly
test:
	uv run pytest -q
shots:
	$(PY) -m pipeline.tools.shots
