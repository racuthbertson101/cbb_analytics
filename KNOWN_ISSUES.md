# Known issues

- BLOCKER: `gh repo create cbb_analytics --public` was denied by the auto-mode permission classifier ([Create Public Surface]). No remote exists. Blocks: pushes, `warehouse` release assets, GitHub Pages deploy, Actions dispatch. Owner action: create the repo (or allow the command), then `git remote add origin ...; git push -u origin main`.
