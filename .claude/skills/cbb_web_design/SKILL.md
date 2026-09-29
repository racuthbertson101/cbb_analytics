---
name: cbb_web_design
description: Design tokens, table/chart conventions, logo component, static export and basePath gotchas, and screenshot QA for the cbb_analytics Next.js site.
---
# Web design
- Dark-first. Tokens as CSS variables in `web/app/globals.css` (bg, surface, border, text, muted, accent, diverging heat scale). Team colors as accents only.
- Type: `next/font` (a distinctive display face + a clean sans + tabular numerals via `font-variant-numeric: tabular-nums` for all numbers).
- Tables: TanStack Table, dense, sticky header, sortable, percentile heat cells using a perceptually sound diverging scale checked for contrast, sparklines where useful. Skeletons + useful empty states.
- Charts: Recharts, one shared style (grid, axis, tooltip). Same palette across charts.
- `<TeamLogo>`: ESPN logo URL, `onError` falls back to a monogram in the team color.
- Static export gotchas: `output: 'export'`, `images.unoptimized`, `basePath`/`assetPrefix` from env `NEXT_PUBLIC_BASE_PATH` (`/cbb_analytics` in prod). Every `fetch` goes through a `dataUrl(path)` helper that prepends basePath. Dynamic routes need `generateStaticParams`; high-cardinality entities (players, games) use client routes with query params + JSON shards.
- Replay: `?asof=YYYY-MM-DD` overrides "today".
- Screenshot QA: Playwright + Chromium at 1440x900, one shot per page group, inspect for contrast/overflow/alignment/empty states, fix before closing a phase.
- Design should not read as templated: deliberate palette, strong hierarchy, restrained motion. (frontend-design skill ideas folded in here if the repo clone fails.)
