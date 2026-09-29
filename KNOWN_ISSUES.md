# Known issues

- BLOCKER: `gh repo create cbb_analytics --public` was denied by the auto-mode permission classifier ([Create Public Surface]). No remote exists. Blocks: pushes, `warehouse` release assets, GitHub Pages deploy, Actions dispatch. Owner action: create the repo (or allow the command), then `git remote add origin ...; git push -u origin main`.
- Source gap: NCAA tournament game counts are short in 2009 (58), 2010 (55), 2013 (55), 2017 (65) versus 67 expected; missing games are absent in the ESPN/hoopR schedule. Ratings use what exists.
- Game type heuristic: conference tournament games without headline on non-neutral sites are labeled `regular` (definition documented in build.py).
- Phase 3 live deploy (GitHub Pages) not done: no repo. `make site` builds web/out locally. basePath is env NEXT_PUBLIC_BASE_PATH.
