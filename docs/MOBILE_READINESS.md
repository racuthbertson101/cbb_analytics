# Mobile readiness list (documentation only; no mobile work was done)

The site is desktop first (1280-1920 px). Nothing blocks mobile, but these are the concrete gaps.

1. **Navigation**: the top bar lists 8 tabs in one row (`web/components/Nav.tsx`, tabs in `web/config/site.json`). Needs a hamburger/bottom tab bar below ~768 px and the search button as an icon.
2. **Fixed grid columns**: cards use `grid-cols-3/4/5` (Today game cards, team stat cards, team page 3-column sections, player page, conference page). Replace with responsive classes (`grid-cols-1 sm:grid-cols-2 lg:grid-cols-3`), and stack `col-span-2` blocks.
3. **Wide tables**: Rankings (12-19 columns), Players (18), Conference projections (up to 18 finish columns). Wrap in horizontal scroll with a sticky first column (team name) and consider hiding secondary columns (Tempo, Trend, Conf) under `sm`.
4. **Controls rows**: selectors (season/date/system/conference/search) wrap awkwardly; move into a collapsible filter sheet.
5. **Charts**: Recharts charts use fixed heights (h-64/h-72); they resize by width already (ResponsiveContainer) but need shorter aspect ratios, larger touch targets and no hover-only tooltips (use tap).
6. **Hover-only UI**: the watchability breakdown popover (`group-hover`) needs a tap/focus alternative.
7. **Command palette**: fixed 560 px width, Ctrl/Cmd+K only; needs full-width sheet and a visible trigger.
8. **Touch sizes**: chips and table headers are 12-13 px text with small hit areas; raise to 44 px targets for primary actions.
9. **Data weight**: per-season JSON shards are 1-3 MB (games, ratings, systems). On mobile networks lazy-load the systems shard only when a non-default system or the Résumé view is chosen, and gzip is applied by GitHub Pages already.
10. **Viewport/meta and PWA**: add `viewport` meta (Next adds a default), a web manifest and icons, and a service worker caching `/data/*.json` (see `docs/EXTENDING.md`).
11. **Typography**: `font-size: 14px` base with dense tables; verify contrast of the heat cells outside a dark room (the diverging scale keeps lightness in a narrow band by design).
12. **Testing**: extend `pipeline/tools/screenshots.py` with a 390x844 viewport pass and check for horizontal overflow on every page group.
