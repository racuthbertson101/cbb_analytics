"""Screenshot QA for the static site: serve web/out, load every route at 1440x900 and 1920x1080, save screenshots and a report.

    uv run --with playwright python -m pipeline.tools.screenshots [--only name,name] [--port 8765]

Build first without a basePath (cd web && npx next build). Writes screenshots/<route>_<width>.png and screenshots/report.json
with, per page: console errors, page errors, 4xx/5xx responses, failed requests, horizontal overflow (document wider than the
viewport, plus the widest offending elements) and broken images. Exit code 1 if any page has a problem.

Ignored on purpose: requests aborted by navigation (Next.js link prefetches, net::ERR_ABORTED), and 404s for RSC prefetch files (`__next.*.txt`). The Windows build writes them as nested folders, the Linux
build that deploys writes flat files, and the live site returns 200 (AUDIT F-14).
"""
from __future__ import annotations

import argparse
import contextlib
import http.server
import json
import re
import socketserver
import sys
import threading
import time
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "web" / "out"
SHOTS = ROOT / "screenshots"
VIEWPORTS = [(1440, 900), (1920, 1080)]
IGNORE_URL = re.compile(r"__next\.[^/]*\.txt|\.txt\?_rsc=")


def routes() -> dict[str, str]:
    """Routes covering every page type, current season, upcoming (preseason) season, history and Game pages."""
    meta = json.loads((OUT / "data" / "meta.json").read_text())
    cur, up = meta["current_season"], meta.get("upcoming_season")
    pl = json.loads((OUT / "data" / "players" / f"{cur}.json").read_text())
    c = pl["cols"]
    star = max(pl["rows"], key=lambda r: r[c.index("min")] or 0)[c.index("id")]
    r = {
        "today": "/",
        "today_opening": "/?date=2026-11-02",
        "today_march": "/?date=2026-03-21",
        "rankings": "/rankings/",
        "rankings_hist": "/rankings/?season=2019&asof=2019-01-20",
        "team_florida": "/team/57/",
        "team_duke": "/team/150/",
        "team_lowmajor": "/team/2329/",
        "player": f"/player/?id={star}",
        "players": "/players/",
        "players_2025": "/players/?season=2025",
        "conferences": "/conferences/",
        "conference_bigten": "/conference/big_ten_conference/",
        "conference_acc": "/conference/atlantic_coast_conference/",
        "compare": "/compare/?a=57&b=150",
        "predictions": "/predictions/",
        "methodology": "/methodology/",
        "tournament": "/tournament/",
    }
    if up:
        r["rankings_preseason"] = f"/rankings/?season={up}"
        r["team_preseason"] = f"/team/2390/?season={up}"
    # Game pages: the current season's national final, a 2014-15 game, a game against a non-D-I team, two upcoming games
    games = lambda y: json.loads((OUT / "data" / "games" / f"{y}.json").read_text())["games"]  # noqa: E731
    gc = games(cur)
    r["game_final"] = f"/game/?id={[x for x in gc if x['t'] == 'ncaa'][-1]['id']}&season={cur}"
    r["game_2015"] = f"/game/?id={[x for x in games(2015) if x['t'] == 'ncaa'][-1]['id']}&season=2015"
    r["game_non_d1"] = f"/game/?id={next(x for x in gc if x['ok'] and not x['d1'])['id']}&season={cur}"
    nxt = games(up) if up else [x for x in gc if not x["ok"]]
    for i, x in enumerate(sorted([x for x in nxt if x.get("w") is not None and not x["ok"]], key=lambda x: -x["w"])[:2]):
        r[f"game_upcoming_{i + 1}"] = f"/game/?id={x['id']}&season={up or cur}"
    return r


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


OVERFLOW_JS = """() => {
  const vw = document.documentElement.clientWidth, sw = document.documentElement.scrollWidth;
  const wide = [];
  if (sw > vw) for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (r.right > vw + 1 && r.width > 0 && !el.closest('[data-scroll-x], .overflow-x-auto, .overflow-auto')) wide.push(el.tagName + '.' + String(el.className).split(' ').slice(0, 2).join('.') + ' ' + Math.round(r.right));
  }
  return { viewport: vw, scrollWidth: sw, offenders: wide.slice(0, 5) };
}"""
BROKEN_IMG_JS = """() => [...document.images].filter(i => i.complete && i.naturalWidth === 0 && i.src).map(i => i.src).slice(0, 10)"""


def main(argv=None) -> int:
    from playwright.sync_api import sync_playwright

    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args(argv)
    pages = routes()
    if a.only:
        pages = {k: v for k, v in pages.items() if k in a.only.split(",")}
    SHOTS.mkdir(exist_ok=True)
    report, t0 = {}, time.time()
    handler = partial(Quiet, directory=str(OUT))
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", a.port), handler) as srv:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for w, h in VIEWPORTS:
                pg = browser.new_page(viewport={"width": w, "height": h})
                ev: dict[str, list] = {}
                pg.on("console", lambda m: ev["console"].append(m.text[:200]) if m.type == "error" and not IGNORE_URL.search(m.text) and "404" not in m.text else None)
                pg.on("pageerror", lambda e: ev["pageerror"].append(str(e)[:200]))
                pg.on("response", lambda r: ev["http"].append(f"{r.status} {r.url}") if r.status >= 400 and not IGNORE_URL.search(r.url) else None)
                pg.on("requestfailed", lambda r: ev["failed"].append(f"{r.failure} {r.url[:150]}") if not IGNORE_URL.search(r.url) and "ERR_ABORTED" not in (r.failure or "") else None)
                for name, path in pages.items():
                    ev.update(console=[], pageerror=[], http=[], failed=[])
                    t = time.time()
                    with contextlib.suppress(Exception):
                        pg.goto(f"http://127.0.0.1:{a.port}{path}", wait_until="networkidle", timeout=30000)
                    pg.wait_for_timeout(800)
                    ov = pg.evaluate(OVERFLOW_JS)
                    imgs = pg.evaluate(BROKEN_IMG_JS)
                    pg.screenshot(path=str(SHOTS / f"{name}_{w}.png"))
                    rec = {**{k: list(v) for k, v in ev.items()}, "overflow": ov if ov["scrollWidth"] > ov["viewport"] else None,
                           "broken_images": imgs, "load_s": round(time.time() - t, 2), "path": path}
                    rec["ok"] = not (rec["console"] or rec["pageerror"] or rec["http"] or rec["failed"] or rec["overflow"] or imgs)
                    report[f"{name}_{w}"] = rec
                    print(f"{name:20} {w:5} {'ok' if rec['ok'] else 'PROBLEM'} {rec['load_s']:.1f}s", flush=True)
                pg.close()
            browser.close()
        srv.shutdown()
    bad = {k: {x: v for x, v in r.items() if v and x not in ("ok", "load_s", "path")} for k, r in report.items() if not r["ok"]}
    summary = {"pages": len(report), "problems": len(bad), "seconds": round(time.time() - t0)}
    (SHOTS / "report.json").write_text(json.dumps({"summary": summary, "pages": report}, indent=1))
    print(json.dumps(summary))
    for k, v in bad.items():
        print(" ", k, json.dumps(v)[:300])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
