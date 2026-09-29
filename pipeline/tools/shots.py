"""Screenshot QA: serve web/out and capture page groups at 1440x900. Usage: python -m pipeline.tools.shots [base_path] [name=path ...]"""
import contextlib
import http.server
import socketserver
import sys
import threading
from functools import partial
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "web" / "out"
SHOTS = ROOT / "screenshots"

DEFAULT = {
    "today": "/?date=2026-03-21",
    "today_preview": "/?date=2026-11-02",
    "rankings": "/rankings/",
    "rankings_hist": "/rankings/?season=2019&asof=2019-01-20",
    "team": "/team/150/",
    "methodology": "/methodology/",
    "tournament": "/tournament/",
}


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def main(pages=None, port=8765):
    SHOTS.mkdir(exist_ok=True)
    pages = pages or DEFAULT
    handler = partial(Quiet, directory=str(OUT))
    with socketserver.ThreadingTCPServer(("127.0.0.1", port), handler) as srv:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1440, "height": 900})
            errs = []
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "404" not in m.text else None)
            pg.on("response", lambda r: errs.append("404 " + r.url) if r.status == 404 else None)
            pg.on("requestfailed", lambda r: errs.append("FAILED " + r.url[:90]))
            pg.on("pageerror", lambda e: errs.append(str(e)))
            for name, path in pages.items():
                errs.clear()
                pg.goto(f"http://127.0.0.1:{port}{path}", wait_until="networkidle")
                pg.wait_for_timeout(900)
                pg.screenshot(path=str(SHOTS / f"{name}.png"), full_page=False)
                print(name, "console errors:", errs[:3])
            b.close()
        srv.shutdown()


if __name__ == "__main__":
    extra = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
    main(extra or None)
