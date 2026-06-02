#!/usr/bin/env python3
"""Backfill top-nav pages (Creatures, Tools) into the offline mirror."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from swgpets.backup import download_missing_assets, extract_links, fetch_mirror_page, mirror_dest
from swgpets.config import MIRROR_DIR
from swgpets.curl_fetch import fetch_to_file
from swgpets.nav_paths import TEMPLATE_ASSETS, nav_seed_paths


def discover_creature_links(root: Path) -> set[str]:
    """Extra /creatures?... links from the main creature browser page."""
    found: set[str] = set()
    index = root / "creatures" / "index.html"
    if not index.is_file():
        return found
    text = index.read_text(encoding="utf-8", errors="replace")
    for link in extract_links(text, "/creatures"):
        if link.startswith("/creatures?"):
            found.add(link.split("#", 1)[0])
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill Creatures + Tools nav pages into ./mirror")
    parser.add_argument("--output", type=Path, default=MIRROR_DIR)
    parser.add_argument("--prefer", choices=("auto", "live", "wayback"), default="auto")
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument(
        "--skip-letters",
        action="store_true",
        help="Only fetch /creatures index, not A-Z letter tabs",
    )
    parser.add_argument("--skip-assets", action="store_true")
    args = parser.parse_args()

    root = args.output
    paths = nav_seed_paths(include_creature_letters=not args.skip_letters)
    print(f"Backfilling {len(paths)} nav pages into {root.resolve()}")

    ok = 0
    for path_query in paths:
        source = fetch_mirror_page(
            path_query,
            root,
            prefer=args.prefer,
            wb_timeout=args.timeout,
        )
        if source:
            ok += 1
            print(f"[{source}] {path_query}")
        else:
            print(f"[skip] {path_query}")
        time.sleep(args.delay)

    extra = discover_creature_links(root)
    if extra:
        print(f"Backfilling {len(extra)} creature filter links from /creatures page...")
        for path_query in sorted(extra):
            source = fetch_mirror_page(
                path_query,
                root,
                prefer=args.prefer,
                wb_timeout=args.timeout,
            )
            if source:
                ok += 1
                print(f"[{source}] {path_query}")
            time.sleep(args.delay * 0.5)

    for asset in TEMPLATE_ASSETS:
        dest = mirror_dest(asset, root)
        if dest.is_file() and dest.stat().st_size > 0:
            continue
        source = fetch_to_file(asset, dest, prefer=args.prefer, wb_timeout=args.timeout)
        if source:
            print(f"[{source}] {asset}")

    if not args.skip_assets:
        print("Downloading images/icons for nav pages...")
        saved, missed = download_missing_assets(
            root,
            prefer=args.prefer,
            delay=args.delay,
            wb_timeout=args.timeout,
        )
        print(f"Assets: downloaded {saved}, failed {missed}")

    from swgpets.fix_mirror_urls import rewrite_mirror_tree

    fixed = rewrite_mirror_tree(root)
    print(f"Fixed Wayback URLs in {fixed} files")

    print(f"Done. {ok} nav pages saved or already present.")


if __name__ == "__main__":
    main()
