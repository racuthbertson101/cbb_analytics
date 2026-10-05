"""WCAG contrast check for the site's color tokens: every text token on every surface must reach 4.5:1 (AA, body text).

    uv run python -m pipeline.tools.contrast        # exit 1 if any pair fails

Tokens are read from the :root block of web/app/globals.css, so the check follows the stylesheet.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

CSS = Path(__file__).resolve().parents[2] / "web" / "app" / "globals.css"
SURFACES = ["bg", "surface", "surface-2"]
TEXT = ["text", "muted", "faint", "accent", "accent-2", "bad", "good"]
AA = 4.5  # DEFINITION: WCAG 2.x AA threshold for normal-size text


def tokens(css: str) -> dict[str, str]:
    root = re.search(r":root\s*{(.*?)}", css, re.S).group(1)
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", root))


def luminance(hex_: str) -> float:
    c = [int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def main() -> int:
    t = tokens(CSS.read_text(encoding="utf8"))
    fails = 0
    print(f"{'text':10}" + "".join(f"{s:>12}" for s in SURFACES))
    for k in TEXT:
        rs = [ratio(t[k], t[s]) for s in SURFACES]
        fails += sum(r < AA for r in rs)
        print(f"{k:10}" + "".join(f"{r:>11.2f}{'!' if r < AA else ' '}" for r in rs))
    print("all pairs >= 4.5:1" if not fails else f"{fails} pair(s) below 4.5:1")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
