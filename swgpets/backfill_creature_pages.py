#!/usr/bin/env python3
"""Backfill /creature/Name detail pages linked from the creature browser."""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

from swgpets.backup import download_missing_assets, fetch_mirror_page, mirror_dest
from swgpets.config import MIRROR_DIR
from swgpets.fix_mirror_urls import rewrite_mirror_tree

CREATURE_LINK = re.compile(r'href="(/creature/[^"#?]+)"')


def discover_creature_pages(root: Path) -> set[str]:
    found: set[str] = set()
    for html in root.rglob("index.html"):
        text = html.read_text(encoding="utf-8", errors="replace")
        for match in CREATURE_LINK.finditer(text):
            found.add(match.group(1))
    return found


def main() -> None:
    parser = argparse.ArgumentParser(description="Mirror /creature/* detail pages")
    parser.add_argument("--output", type=Path, default=MIRROR_DIR)
    parser.add_argument("--prefer", choices=("auto", "live", "wayback"), default="auto")
    parser.add_argument("--delay", type=float, default=0.12)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--limit", type=int, default=0, help="Max pages to fetch (0 = all)")
    parser.add_argument("--skip-assets", action="store_true")
    args = parser.parse_args()

    root = args.output
    paths = sorted(discover_creature_pages(root))
    missing = [p for p in paths if not mirror_dest(p, root).is_file()]
    print(f"Found {len(paths)} creature detail links, {len(missing)} missing on disk")

    if args.limit > 0:
        missing = missing[: args.limit]

    ok = 0
    fail = 0
    for path in missing:
        source = fetch_mirror_page(
            path,
            root,
            prefer=args.prefer,
            wb_timeout=args.timeout,
        )
        if source:
            ok += 1
            if ok % 50 == 0 or ok <= 5:
                print(f"[{source}] {path}")
        else:
            fail += 1
            print(f"[skip] {path}")
        time.sleep(args.delay)

    # Second pass: creature pages may link to other creatures.
    extra = sorted(
        p
        for p in discover_creature_pages(root)
        if not mirror_dest(p, root).is_file()
    )
    if extra and (args.limit == 0 or ok < args.limit):
        print(f"Fetching {len(extra)} additional creature pages discovered after crawl...")
        for path in extra:
            if args.limit > 0 and ok >= args.limit:
                break
            source = fetch_mirror_page(path, root, prefer=args.prefer, wb_timeout=args.timeout)
            if source:
                ok += 1
            else:
                fail += 1
            time.sleep(args.delay)

    rewrite_mirror_tree(root)

    if not args.skip_assets:
        print("Downloading images for creature detail pages...")
        saved, missed = download_missing_assets(
            root,
            prefer=args.prefer,
            delay=args.delay,
            wb_timeout=args.timeout,
        )
        print(f"Assets: downloaded {saved}, failed {missed}")

    print(f"Done. fetched {ok}, failed {fail}")


if __name__ == "__main__":
    main()
