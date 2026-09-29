# CBB Analytics

Personal D-I men's college basketball ratings/predictions site. Full spec: `SPEC.md`. State: `PROGRESS.md`. Judgment calls: `DECISIONS.md`. Fallbacks: `KNOWN_ISSUES.md`.

## Operating rules (from SPEC section 0)
1. Never ask the user questions or wait for input; choose the best option and log it in DECISIONS.md.
2. Keep PROGRESS.md current after every meaningful step; every phase must be resumable from PROGRESS.md, CLAUDE.md and git.
3. Commit after every completed step; push at the end of each phase (if a remote exists).
4. Max 3 real attempts per problem, then fallback + KNOWN_ISSUES.md.
5. Verify before claiming done (tests, `next build`, screenshots).
6. Stay inside the project folder; never commit secrets.
7. Conserve usage: summarize output, cache downloads on disk, background long jobs.
8. No guessed constants in modeling: estimate or walk-forward tune, store in pipeline/params/ with evidence. Definitions are labeled as definitions.
9. No leakage: a game's rating/prediction uses only pre-game info (tested).
10. Be polite to data sources; never scrape KenPom/Barttorvik/Sports Reference HTML.

## Skills
`.claude/skills/cbb_modeling_rules`, `cbb_data_conventions`, `cbb_web_design`.

## Dev
Python via `uv` (`uv run pytest`), site in `web/` (Next.js static export). Makefile: backfill, ratings, site, replay DATE=..., test.
