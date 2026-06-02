#!/usr/bin/env python3
"""Create a 100% offline mirror of swgpets.com/pets (pet list, pet pages, images)."""

from __future__ import annotations

import argparse
import hashlib
import re
import time
import urllib.parse
from collections import deque
from html.parser import HTMLParser
from pathlib import Path

from swgpets.config import MIRROR_DIR, UPSTREAM_BASE, UPSTREAM_HOSTS, USER_AGENT
from swgpets.curl_fetch import fetch_to_file

ASSET_EXTENSIONS = {
    ".css",
    ".js",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".webp",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
}

PAGE_PREFIXES = ("/pets", "/pet/", "/specials", "/special")
ASSET_PREFIXES = ("/templates/", "/images/")
SPECIAL_PATHS = {"/favicon.ico", "/special", "/specials"}

# Beastmaster special ability IDs (pet search dropdown).
SPECIAL_IDS = (
    "1", "2", "3", "4", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16",
    "17", "18", "19", "20", "21", "22", "25", "26", "28", "29", "31", "32", "33",
)

REWRITE_HOSTS = re.compile(
    rb"https?://(?:www\.)?swgpets\.com|//(?:www\.)?swgpets\.com",
    re.IGNORECASE,
)

URL_IN_CSS = re.compile(r"url\(['\"]?([^'\"\)]+)['\"]?\)", re.IGNORECASE)


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {k: v for k, v in attrs if k and v}
        for key in ("href", "src", "action", "background"):
            value = attr_map.get(key)
            if value:
                self.links.add(value)


def is_asset_path(path: str) -> bool:
    lower = path.lower().split("?", 1)[0]
    return any(lower.endswith(ext) for ext in ASSET_EXTENSIONS)


def in_scope(path: str) -> bool:
    base = path.split("?", 1)[0]
    query = path.split("?", 1)[1] if "?" in path else ""
    if base in SPECIAL_PATHS:
        return True
    if any(base.startswith(prefix) for prefix in PAGE_PREFIXES):
        return True
    if any(base.startswith(prefix) for prefix in ASSET_PREFIXES):
        return True
    # Creature lists linked from special pages ("where to acquire").
    if base.startswith("/creatures") and "specials=" in query:
        return True
    return False


def normalize_path(path: str, query: str = "") -> str | None:
    """Return canonical site path+query like /pets?letter=A."""
    parsed = urllib.parse.urlparse(path if path.startswith("/") else f"/{path}")
    if parsed.scheme in ("http", "https"):
        if parsed.netloc not in UPSTREAM_HOSTS:
            return None
        base = parsed.path or "/"
        q = parsed.query or query
    else:
        base = parsed.path or "/"
        q = parsed.query or query
    if not in_scope(base):
        return None
    return base + (f"?{q}" if q else "")


def query_slug(query: str) -> str:
    if not query:
        return ""
    parsed = urllib.parse.parse_qs(query, keep_blank_values=True)
    parts: list[str] = []
    for key in sorted(parsed):
        for value in sorted(parsed[key]):
            safe_k = re.sub(r"[^\w.-]+", "_", key)
            safe_v = re.sub(r"[^\w.-]+", "_", value) or "empty"
            parts.append(f"{safe_k}_{safe_v}")
    return "_".join(parts) if parts else hashlib.sha256(query.encode()).hexdigest()[:12]


def mirror_dest(path_query: str, root: Path) -> Path:
    """Map /pets?letter=A -> mirror/pets/letter_A/index.html."""
    if "?" in path_query:
        path, query = path_query.split("?", 1)
    else:
        path, query = path_query, ""

    path = path or "/"
    segments = [segment for segment in path.split("/") if segment]

    if query:
        slug = query_slug(query)
        if segments:
            if is_asset_path("/" + segments[-1]):
                return root.joinpath(*segments)
            return root.joinpath(*segments, slug, "index.html")
        return root / slug / "index.html"

    if not segments:
        return root / "index.html"

    if is_asset_path(path):
        return root.joinpath(*segments)

    return root.joinpath(*segments, "index.html")


def rewrite_body(body: bytes) -> bytes:
    """Strip absolute swgpets.com URLs so links work on the local server."""
    if b"<" in body[:200] or b"text" in body[:50].lower():
        return REWRITE_HOSTS.sub(b"", body)
    lowered = body[:512].lower()
    if b"url(" in lowered or b".css" in lowered:
        return REWRITE_HOSTS.sub(b"", body)
    return body


def extract_links(html: str, base_path: str) -> set[str]:
    parser = LinkParser()
    try:
        parser.feed(html)
    except Exception:
        return set()

    found: set[str] = set()
    base_url = urllib.parse.urljoin(UPSTREAM_BASE + "/", base_path)
    for raw in parser.links:
        joined = urllib.parse.urljoin(base_url, raw)
        parsed = urllib.parse.urlparse(joined)
        if parsed.netloc and parsed.netloc not in UPSTREAM_HOSTS:
            continue
        normalized = normalize_path(parsed.path or "/", parsed.query)
        if normalized:
            found.add(normalized)
    return found


def extract_css_urls(css: str, base_path: str) -> set[str]:
    found: set[str] = set()
    base_url = urllib.parse.urljoin(UPSTREAM_BASE + "/", base_path)
    for match in URL_IN_CSS.finditer(css):
        joined = urllib.parse.urljoin(base_url, match.group(1))
        parsed = urllib.parse.urlparse(joined)
        if parsed.netloc and parsed.netloc not in UPSTREAM_HOSTS:
            continue
        normalized = normalize_path(parsed.path or "/")
        if normalized:
            found.add(normalized)
    return found


def collect_asset_links(root: Path) -> set[str]:
    """Return site paths (/images/...) for assets referenced in mirrored HTML/CSS."""
    found: set[str] = set()
    for html_file in root.rglob("index.html"):
        rel = html_file.relative_to(root)
        base_path = "/" + str(rel.parent).replace("\\", "/")
        text = html_file.read_text(encoding="utf-8", errors="replace")
        for link in extract_links(text, base_path):
            path_only = link.split("?", 1)[0]
            if is_asset_path(path_only):
                found.add(path_only)

    for css_file in root.rglob("*.css"):
        rel = "/" + str(css_file.relative_to(root))
        css = css_file.read_text(encoding="utf-8", errors="replace")
        for link in extract_css_urls(css, rel):
            path_only = link.split("?", 1)[0]
            if is_asset_path(path_only):
                found.add(path_only)
    return found


def download_missing_assets(
    root: Path,
    *,
    prefer: str = "auto",
    delay: float = 0.25,
    live_timeout: int = 30,
    wb_timeout: int = 120,
    links: set[str] | None = None,
    limit: int | None = None,
) -> tuple[int, int]:
    """Download assets referenced in the mirror that are not yet on disk."""
    pending = sorted(links if links is not None else collect_asset_links(root))
    saved = 0
    missed = 0
    for path in pending:
        if limit is not None and saved >= limit:
            break
        dest = mirror_dest(path, root)
        if dest.is_file() and dest.stat().st_size > 0:
            continue
        source = fetch_to_file(
            path,
            dest,
            live_timeout=live_timeout,
            wb_timeout=wb_timeout,
            prefer=prefer,
        )
        if source:
            if dest.suffix.lower() == ".css":
                dest.write_bytes(rewrite_body(dest.read_bytes()))
            saved += 1
            print(f"[asset {saved}] [{source}] {path}")
        else:
            missed += 1
            print(f"[miss] {path}")
        time.sleep(delay)
    return saved, missed


def seed_paths() -> list[str]:
    seeds = ["/pets", "/specials", "/special", "/favicon.ico"]
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        seeds.append(f"/pets?letter={letter}")
    for letter in "BCDEFHKPRSTW":
        seeds.append(f"/special?letter={letter}")
    for sid in SPECIAL_IDS:
        seeds.append(f"/pets?specials={sid}")
    return seeds


def backup_site(
    *,
    root: Path,
    prefer: str,
    delay: float,
    live_timeout: int,
    wb_timeout: int,
    max_pages: int,
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    queue: deque[str] = deque(seed_paths())
    seen_pages: set[str] = set()
    saved_pages = 0
    saved_assets = 0

    print(f"Backing up SWG Pets /pets section -> {root.resolve()}")
    print(f"Source: live first, Wayback fallback (prefer={prefer})")

    while queue and saved_pages < max_pages:
        path_query = queue.popleft()
        if path_query in seen_pages:
            continue
        seen_pages.add(path_query)

        path_only = path_query.split("?", 1)[0]
        if is_asset_path(path_only):
            continue

        dest = mirror_dest(path_query, root)
        if dest.is_file() and dest.stat().st_size > 0:
            body = dest.read_bytes()
            source = "cached"
        else:
            fetch_path = path_only + (
                f"?{path_query.split('?', 1)[1]}" if "?" in path_query else ""
            )
            source = fetch_to_file(
                fetch_path,
                dest,
                live_timeout=live_timeout,
                wb_timeout=wb_timeout,
                prefer=prefer,
            )
            if not source:
                print(f"skip page {path_query}")
                continue
            body = rewrite_body(dest.read_bytes())
            dest.write_bytes(body)
            saved_pages += 1
            print(f"[page {saved_pages}] [{source}] {path_query} -> {dest}")

        html = body.decode("utf-8", errors="replace")
        for link in extract_links(html, path_only):
            link_path = link.split("?", 1)[0]
            if is_asset_path(link_path):
                asset_dest = mirror_dest(link, root)
                if not asset_dest.is_file():
                    if fetch_to_file(
                        link_path + (f"?{link.split('?', 1)[1]}" if "?" in link else ""),
                        asset_dest,
                        live_timeout=live_timeout,
                        wb_timeout=wb_timeout,
                        prefer=prefer,
                    ):
                        saved_assets += 1
                        print(f"  [asset {saved_assets}] {link}")
                    time.sleep(delay)
            elif link not in seen_pages:
                queue.append(link)

        time.sleep(delay)

    # Second pass: prefetch assets referenced in saved HTML/CSS.
    asset_queue: deque[str] = deque(collect_asset_links(root))
    asset_seen: set[str] = set()

    while asset_queue:
        path_query = asset_queue.popleft()
        if path_query in asset_seen:
            continue
        asset_seen.add(path_query)
        dest = mirror_dest(path_query, root)
        if dest.is_file() and dest.stat().st_size > 0:
            continue
        path_only = path_query.split("?", 1)[0]
        source = fetch_to_file(
            path_only + (f"?{path_query.split('?', 1)[1]}" if "?" in path_query else ""),
            dest,
            live_timeout=live_timeout,
            wb_timeout=wb_timeout,
            prefer=prefer,
        )
        if source:
            if dest.suffix.lower() in (".css",):
                dest.write_bytes(rewrite_body(dest.read_bytes()))
            saved_assets += 1
            print(f"[asset {saved_assets}] [{source}] {path_query}")
        time.sleep(delay)

    total = sum(1 for _ in root.rglob("*") if _.is_file())
    print(f"Done. {saved_pages} pages, {saved_assets} assets, {total} files total under {root}")

    index = root / "index.html"
    if not index.is_file():
        index.write_text(
            '<!DOCTYPE html><html><head><meta http-equiv="refresh" content="0; url=/pets">'
            '<title>SWG Pets</title></head><body><p><a href="/pets">SWG Pets — Pet List</a></p></body></html>',
            encoding="utf-8",
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline backup of swgpets.com/pets (list, pet pages, images)"
    )
    parser.add_argument("--output", type=Path, default=MIRROR_DIR)
    parser.add_argument("--prefer", choices=("auto", "live", "wayback"), default="auto")
    parser.add_argument("--delay", type=float, default=0.35)
    parser.add_argument("--live-timeout", type=int, default=30)
    parser.add_argument("--wb-timeout", type=int, default=120)
    parser.add_argument("--max-pages", type=int, default=5000)
    args = parser.parse_args()
    backup_site(
        root=args.output,
        prefer=args.prefer,
        delay=args.delay,
        live_timeout=args.live_timeout,
        wb_timeout=args.wb_timeout,
        max_pages=args.max_pages,
    )


if __name__ == "__main__":
    main()
