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
	# pass 1 (lag-only preseason prior) produces the frozen impact-model targets; pass 2 adds the roster prior
	rm -f data/backtest/roster_feats.pkl data/backtest/impact_targets.parquet
	$(PY) -m pipeline.models.data
	$(PY) -m pipeline.models.tune tempo
	$(PY) -m pipeline.models.tune eff
	$(PY) -m pipeline.models.backtest
	$(PY) -m pipeline.models.evaluate
	$(PY) -m pipeline.players.prior_eval
	$(PY) -m pipeline.players.build_players
	$(PY) -m pipeline.players.roster_prior
	$(PY) -m pipeline.models.tune eff
	$(PY) -m pipeline.models.backtest
	$(PY) -m pipeline.models.evaluate
	$(PY) -m pipeline.players.rapm_compare
	$(PY) -m pipeline.models.elo_mle
	$(PY) -m pipeline.models.bt
	$(PY) -m pipeline.models.consensus
	$(PY) -m pipeline.models.resume
	$(PY) -m pipeline.pbp.parse
	$(PY) -m pipeline.models.ingame
	$(PY) -m pipeline.sims.make_configs
site:
	# same export path as the nightly run and deploy.yml, without ingest or logging
	$(PY) -m pipeline.nightly --force --no-ingest --no-log
# Rehearse the whole nightly path as if today were DATE on scratch copies, e.g. make replay DATE=YYYY-MM-DD (then `make site` restores the normal site)
replay:
	$(PY) -m pipeline.replay $(DATE)
nightly:
	$(PY) -m pipeline.nightly
test:
	uv run pytest -q
shots:
	uv run --with playwright python -m pipeline.tools.screenshots
