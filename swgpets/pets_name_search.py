"""Offline /pets?search_name= filtering by pet name substring match."""

from __future__ import annotations

import html
import re
import urllib.parse
from functools import lru_cache
from pathlib import Path

PET_ROW_RE = re.compile(r"(<tr height=50>.*?</tr>)", re.S)
PET_LINK_RE = re.compile(r'href="/pet/([^"#?]+)"')
PAGINATION_RE = re.compile(r'<a href="/pets\?page=\d+">[^<]*</a>(?:\s*&nbsp;)?', re.I)
SEARCH_NAME_INPUT_RE = re.compile(
    r"(name='search_name'\s+value=\")[^\"]*(\")",
    re.I,
)


def pet_display_name(slug: str) -> str:
    return urllib.parse.unquote(slug.replace("+", " ").replace("_", " "))


def _slug_sort_key(slug: str) -> tuple[str, int]:
    display = pet_display_name(slug).lower()
    # Prefer + slugs over _ duplicates when both exist.
    return (display, 0 if "+" in slug else 1)


def pets_name_search_term(query: str) -> str | None:
    parsed = urllib.parse.parse_qs(query, keep_blank_values=True)
    values = parsed.get("search_name", [])
    if not values:
        return None
    term = values[-1].strip()
    return term or None


@lru_cache(maxsize=1)
def _index_pet_rows(mirror_dir_str: str) -> dict[str, str]:
    mirror_dir = Path(mirror_dir_str)
    pets_root = mirror_dir / "pets"
    if not pets_root.is_dir():
        return {}

    rows: dict[str, str] = {}
    for html_file in pets_root.rglob("index.html"):
        try:
            text = html_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in PET_ROW_RE.finditer(text):
            row = match.group(1)
            link = PET_LINK_RE.search(row)
            if not link:
                continue
            slug = link.group(1)
            rows.setdefault(slug, row)
    return rows


def _all_pet_slugs(mirror_dir: Path) -> list[str]:
    pet_root = mirror_dir / "pet"
    if not pet_root.is_dir():
        return []
    return [path.name for path in pet_root.iterdir() if path.is_dir()]


def filter_pet_slugs_by_name(term: str, slugs: list[str]) -> list[str]:
    term_lower = term.strip().lower()
    if not term_lower:
        return []

    best: dict[str, str] = {}
    for slug in slugs:
        display = pet_display_name(slug)
        if term_lower not in display.lower():
            continue
        key = display.lower()
        current = best.get(key)
        if current is None or _slug_sort_key(slug) < _slug_sort_key(current):
            best[key] = slug
    return sorted(best.values(), key=_slug_sort_key)


def _minimal_pet_row(slug: str) -> str:
    name = html.escape(pet_display_name(slug))
    safe_slug = html.escape(slug, quote=True)
    return (
        "<tr height=50>"
        f"<td class='row1' colspan='9' style='padding-left: 5px;'>"
        f"<span class='gen'><b><a href=\"/pet/{safe_slug}\">{name}</a></b></span>"
        "</td></tr>"
    )


def build_pets_name_search_page(term: str, mirror_dir: Path) -> bytes | None:
    """Build a /pets search results page filtered by pet name substring."""
    template_path = mirror_dir / "pets" / "index.html"
    if not template_path.is_file():
        return None

    row_index = _index_pet_rows(str(mirror_dir.resolve()))
    slugs = sorted(set(row_index) | set(_all_pet_slugs(mirror_dir)))
    matches = filter_pet_slugs_by_name(term, slugs)
    if not matches:
        matches = []

    template = template_path.read_text(encoding="utf-8", errors="replace")
    rows = list(PET_ROW_RE.finditer(template))
    pet_rows = [match for match in rows if PET_LINK_RE.search(match.group(1))]
    if not pet_rows:
        return None

    start = pet_rows[0].start()
    end = pet_rows[-1].end()
    rendered_rows = "".join(row_index.get(slug, _minimal_pet_row(slug)) for slug in matches)
    page = template[:start] + rendered_rows + template[end:]

    safe_term = html.escape(term, quote=True)
    page = SEARCH_NAME_INPUT_RE.sub(rf"\1{safe_term}\2", page, count=1)
    page = PAGINATION_RE.sub("", page)
    return page.encode("utf-8")
