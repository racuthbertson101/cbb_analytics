"""UI copy rules (AUDIT D-6): seasons are shown as "2025-26", never as end-year ranges like "2012-2026"."""
import re
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[2] / "web"
END_YEAR_RANGE = re.compile(r"\b20\d\d-20\d\d\b")


def test_no_end_year_ranges_in_component_copy():
    hits = [f"{p.name}: {m.group(0)}" for p in (WEB / "components").glob("*.tsx") for m in END_YEAR_RANGE.finditer(p.read_text(encoding="utf8"))]
    assert not hits, hits


def test_no_end_year_ranges_in_built_html():
    out = WEB / "out"
    if not out.exists():
        pytest.skip("site not built")
    hits = []
    for p in out.rglob("*.html"):
        text = re.sub(r"<script.*?</script>|<[^>]+>", " ", p.read_text(encoding="utf8", errors="ignore"), flags=re.S)
        hits += [f"{p.relative_to(out)}: {m.group(0)}" for m in END_YEAR_RANGE.finditer(text)]
    assert not hits, hits[:10]
