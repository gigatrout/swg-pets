#!/usr/bin/env python3
"""Sync pages and assets from swgpets.com (live or Wayback) into ./cache."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from swgpets.config import CACHE_DIR, MIRROR_DIR
from swgpets.fetch import fetch_bytes, live_fetch_url
from swgpets.prefetch import extract_from_html, prefetch
from swgpets.server import cache_path

# Core site sections to refresh.
def _is_html_path(path: str, dest: Path) -> bool:
    lower = path.lower().split("?", 1)[0]
    if lower.endswith((".css", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".js", ".svg", ".woff", ".woff2")):
        return False
    if lower.endswith((".html", ".php")) or lower.endswith("/") or lower == "/":
        return True
    return dest.suffix in (".html", ".php", "") or "html" in dest.name


CORE_PATHS = [
    "/",
    "/pets",
    "/creatures",
    "/specials",
    "/research",
    "/planner",
    "/spots",
    "/lyase",
    "/known",
    "/sheet",
    "/exp",
    "/statcalc",
    "/hydro",
    "/oekevo",
    "/family",
    "/unknown",
    "/about",
    "/profiles",
    "/profile-pets",
    "/galaxies",
    "/expertise",
    "/wiki/",
    "/templates/swgpets/swgpets.css",
    "/templates/swgpets/swgpetsmenu.css",
    "/favicon.ico",
    "/templates/swgpets/images/swgpets_header.png",
    "/templates/swgpets/images/spacer.png",
    "/templates/swgpets/images/tail_top.png",
    "/templates/swgpets/images/tail_left.png",
    "/templates/swgpets/images/tail_right.png",
]


def save_to_cache(path: str, body: bytes, cache_dir: Path) -> Path:
    url = live_fetch_url(path)
    dest = cache_path(url, cache_dir)
    if (path == "/" or path == "") and dest.name != "index.html":
        dest = cache_dir / "index.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    return dest


def sync_pages(
    *,
    cache_dir: Path,
    paths: list[str],
    prefer: str,
    delay: float,
    timeout: int,
) -> list[Path]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    saved_html: list[Path] = []
    live_count = 0
    wayback_count = 0

    for path in paths:
        try:
            body, source = fetch_bytes(path, timeout=timeout, prefer=prefer)
        except RuntimeError as exc:
            print(f"FAIL {path}: {exc}")
            continue

        dest = save_to_cache(path, body, cache_dir)
        if source == "live":
            live_count += 1
        else:
            wayback_count += 1
        print(f"[{source}] {path} -> {dest} ({len(body)} bytes)")

        if _is_html_path(path, dest):
            saved_html.append(dest)
        time.sleep(delay)

    print(f"Pages: {live_count} live, {wayback_count} wayback, {len(paths)} attempted")
    return saved_html


def discover_extra_paths(cache_dir: Path) -> list[str]:
    """Pull same-origin links from cached HTML (pets by letter, etc.)."""
    extra: list[str] = []
    for html_file in cache_dir.rglob("*.html"):
        try:
            text = html_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for url in extract_from_html(text, "https://www.swgpets.com/"):
            parsed = __import__("urllib.parse", fromlist=["urlparse"]).urlparse(url)
            if parsed.path and not parsed.path.endswith((".png", ".css", ".js", ".gif", ".ico")):
                extra.append(parsed.path + (f"?{parsed.query}" if parsed.query else ""))
    # Pet list A-Z
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        extra.append(f"/pets?letter={letter}")
    return sorted(set(extra))


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync SWG Pets content into cache")
    parser.add_argument("--cache", type=Path, default=CACHE_DIR)
    parser.add_argument("--prefer", choices=("auto", "live", "wayback"), default="auto")
    parser.add_argument("--delay", type=float, default=0.35)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--max-assets", type=int, default=3000)
    parser.add_argument("--skip-prefetch", action="store_true")
    parser.add_argument("--full", action="store_true", help="Also sync links found in HTML")
    args = parser.parse_args()

    paths = list(CORE_PATHS)
    html_files = sync_pages(
        cache_dir=args.cache,
        paths=paths,
        prefer=args.prefer,
        delay=args.delay,
        timeout=args.timeout,
    )

    if args.full:
        extra = discover_extra_paths(args.cache)
        print(f"Discovered {len(extra)} extra paths...")
        more_html = sync_pages(
            cache_dir=args.cache,
            paths=extra,
            prefer=args.prefer,
            delay=args.delay,
            timeout=args.timeout,
        )
        html_files.extend(more_html)

    if not args.skip_prefetch:
        seeds = sorted(set(html_files) | set(args.cache.rglob("*.html")))
        print(f"Prefetching assets from {len(seeds)} HTML files...")
        prefetch(
            cache_dir=args.cache,
            seeds=seeds,
            max_assets=args.max_assets,
            delay=max(args.delay, 0.15),
            timeout=args.timeout,
            prefer=args.prefer,
        )

    print(f"Done. Cache: {args.cache.resolve()}")
    print("Restart ./start.sh to use updated content.")


if __name__ == "__main__":
    main()
