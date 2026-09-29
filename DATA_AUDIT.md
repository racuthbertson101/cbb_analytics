# Data Audit (Phase 0)

Source: sportsdataverse-data GitHub releases (hoopR ESPN men's college basketball Parquet files), fetched to `data/raw/sdv/` by `pipeline/ingest/download.py`. Audit script: `pipeline/ingest/audit.py`. Season = year the season ends (2026 = 2025-26). Snapshot date 2026-09-28; season 2027 has a schedule (1,629 future games) but no results.

## Available datasets (release tag -> files)
| Kind | Tag | Seasons | Notes |
|---|---|---|---|
| schedules | espn_mens_college_basketball_schedules | 2002-2027 | game list, scores, logos, colors, conference ids, rankings, records, neutral flag (2008+), tournament ids |
| team box | ..._team_boxscores | 2003-2026 | full team box (FGA, FTA, ORB, TO, ...) |
| player box | ..._player_boxscores | 2003-2026 | minutes, shooting, rebounds, etc; DNP rows flagged |
| standings | ..._standings | 2003-2026 | conference (group) membership per season, W-L |
| rosters | ..._rosters | 2025-2027 only | class, height, position. Earlier seasons must be derived from player box |
| player season stats | ..._player_season_stats | 2025-2026 only | |
| team season stats | ..._team_season_stats | 2003-2026 | |
| pbp | ..._pbp | 2003, 2006-2026 | large (5-90 MB/season); local only |
| shots | ..._shots | 2003, 2006-2026 | x/y shot locations; local only |
| NCAA lineups / RAPM | ncaa_mbb_lineups (2010-2019+), ncaa_mbb_rapm (2011-2020) | 2010/11-2020ish | stats.ncaa.org derived, different ID space than ESPN; needs crosswalk (Phase 9) |
| mbb_ratings, mbb_player_value | mbb_ratings, mbb_player_value | 2006-2026 | third-party derived; NOT used (provenance unclear, would leak other systems' opinions) |

## Per-season coverage (schedule rows with both-team box / player box; D-I share computed in Phase 1)
| Season | Games (schedule) | Completed | Both-team box % | Player box % | Minutes non-null (all rows) % | Neutral flag % neutral | Conf ID % |
|---|---|---|---|---|---|---|---|
| 2003 | 4990 | 4990 | 0.0 | 0.0 | 88.5 | 0.0 | 98.9 |
| 2004 | 4983 | 4983 | 0.2 | 0.2 | 79.9 | 0.0 | 99.1 |
| 2005 | 5048 | 5048 | 86.5 | 82.6 | 75.2 | 0.0 | 99.2 |
| 2006 | 5172 | 5172 | 95.2 | 90.9 | 75.0 | 0.0 | 99.1 |
| 2007 | 5480 | 5480 | 95.7 | 94.8 | 75.1 | 0.0 | 99.5 |
| 2008 | 5448 | 5448 | 99.2 | 98.9 | 75.6 | 14.6 | 99.8 |
| 2009 | 5726 | 5726 | 98.5 | 95.9 | 75.4 | 9.7 | 99.7 |
| 2010 | 5761 | 5761 | 99.8 | 96.7 | 75.1 | 9.9 | 99.8 |
| 2011 | 5771 | 5771 | 99.7 | 96.3 | 75.8 | 10.6 | 99.6 |
| 2012 | 5776 | 5776 | 99.7 | 97.0 | 75.3 | 10.4 | 99.7 |
| 2013 | 5817 | 5817 | 99.7 | 98.6 | 74.6 | 11.0 | 99.8 |
| 2014 | 5948 | 5948 | 99.6 | 99.7 | 66.4 | 11.4 | 99.7 |
| 2015 | 5932 | 5932 | 99.9 | 100.0 | 66.2 | 10.8 | 99.9 |
| 2016 | 5893 | 5893 | 99.8 | 99.8 | 66.0 | 10.9 | 99.8 |
| 2017 | 5960 | 5960 | 99.4 | 99.3 | 66.5 | 11.0 | 99.9 |
| 2018 | 6003 | 6003 | 100.0 | 100.0 | 65.0 | 11.3 | 99.9 |
| 2019 | 6049 | 6049 | 100.0 | 100.0 | 65.3 | 11.0 | 100.0 |
| 2020 | 5767 | 5767 | 99.8 | 100.0 | 63.3 | 8.0 | 99.9 |
| 2021 | 4285 | 4285 | 100.0 | 100.0 | 64.5 | 11.7 | 99.9 |
| 2022 | 5976 | 5976 | 99.8 | 99.8 | 62.8 | 11.6 | 99.9 |
| 2023 | 6261 | 6228 | 99.9 | 99.9 | 63.8 | 12.3 | 100.0 |
| 2024 | 6249 | 6243 | 100.0 | 100.0 | 63.4 | 11.9 | 99.9 |
| 2025 | 6299 | 6292 | 99.9 | 100.0 | 61.4 | 11.9 | 99.9 |
| 2026 | 6318 | 6300 | 100.0 | 100.0 | 64.8 | 11.2 | 100.0 |

PBP and shot data are flagged per game in the schedule (`PBP` share of games: 51% in 2008, 89% in 2015, 97-99% in 2025-26).

## Findings
- **Team IDs**: ESPN `team_id` is used throughout; ids are stable across seasons in the files sampled (schedule, box, standings share the same ids). Verified again by validation tests in Phase 1.
- **Neutral site flag**: present only from 2008 (0% flagged before that => flag missing, not "none neutral"). ~11% of games neutral from 2008.
- **Game type**: `season_type` (2 regular, 3 postseason), `type_abbreviation` (STD/TRNMNT/EXH/...), `notes_headline` (tournament/event names such as "NCAA Men's Basketball Championship ... Round", "NIT", "Classic"), `conference_competition`, `tournament_id`, `groups_*`. Game type classification is derived in Phase 1 from these.
- **Division I**: schedule includes ~700 teams per season, of which ~340-366 have 10+ games (the D-I set); non-D-I opponents appear as extra teams. D-I membership per season will be defined in Phase 1 from standings conference membership (teams listed in a D-I conference group that season), and cross-checked with game counts (expect 350-365).
- **Conference by season**: available from `home_conference_id`/`away_conference_id` in schedules (>=99% populated) and `standings` groups (32 groups in 2026; includes a "College Basketball Crown" pseudo group to exclude).
- **Minutes**: present for all players who played (100% of non-DNP rows); ~35% of rows are DNP.
- **Missing fields**: no possessions column (estimate from box: FGA - OREB + TO + 0.475 FTA); no team-level conference tournament flag; rosters pre-2025 absent; no player class/height before 2025 (class derivable from first-season appearance as an approximation).
- **Cancelled/postponed games** exist as rows with no score; excluded.
- 2020 has no NCAA tournament (COVID); 2021 has a shortened, irregular season (4,285 games, many cancellations) and is a poor training year (flagged; downweight/exclude as a test season for calibration).

## Start-season decision
Threshold (logged in DECISIONS.md): >=98% of completed games with both team boxes AND player boxes, and a populated neutral-site flag. First qualifying season is **2008** (99.2% team box, 98.9% player box, neutral flag present). Seasons 2003-2007 are kept in `data/raw` but excluded from fits (95% box coverage and no neutral flag). Usable: **2008-2026** (19 seasons; 2021 flagged as irregular). Walk-forward test seasons will start ~2011 after a 3-season burn-in.

## Dependencies by phase
- Phase 1 warehouse: schedules, team box, player box, standings, rosters.
- Phase 2 ratings: games + team box (possessions estimate) + neutral flag.
- Phase 4 players: player box (minutes), rosters (2025+), player season stats for cross-checks.
- Phase 6 conferences: standings/conference ids by season, schedules with future games (2027 schedule exists).
- Phase 9: pbp, shots, ncaa lineups/RAPM.
