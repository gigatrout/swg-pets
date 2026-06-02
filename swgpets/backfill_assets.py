#!/usr/bin/env python3
"""Download images/icons/CSS referenced by mirrored HTML but not yet on disk."""

from __future__ import annotations

import argparse
from pathlib import Path

from swgpets.backup import collect_asset_links, download_missing_assets, mirror_dest
from swgpets.config import MIRROR_DIR


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill static assets (creature icons, ability ranks, flags) into ./mirror"
    )
    parser.add_argument("--output", type=Path, default=MIRROR_DIR)
    parser.add_argument("--prefer", choices=("auto", "live", "wayback"), default="auto")
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument("--live-timeout", type=int, default=30)
    parser.add_argument("--wb-timeout", type=int, default=120)
    parser.add_argument("--limit", type=int, default=0, help="Max assets to download (0 = all)")
    parser.add_argument("--dry-run", action="store_true", help="Only report missing assets")
    args = parser.parse_args()

    root = args.output
    links = collect_asset_links(root)
    missing = sorted(
        path
        for path in links
        if not mirror_dest(path, root).is_file()
        or mirror_dest(path, root).stat().st_size == 0
    )
    print(f"Scanned mirror: {len(links)} asset refs, {len(missing)} missing on disk")

    if args.dry_run:
        for path in missing[:50]:
            print(f"  {path}")
        if len(missing) > 50:
            print(f"  ... and {len(missing) - 50} more")
        return

    if not missing:
        print("Nothing to download.")
        return

    limit = args.limit if args.limit > 0 else None
    saved, missed = download_missing_assets(
        root,
        prefer=args.prefer,
        delay=args.delay,
        live_timeout=args.live_timeout,
        wb_timeout=args.wb_timeout,
        links=set(missing),
        limit=limit,
    )
    print(f"Done. Downloaded {saved}, failed {missed}, still missing {len(missing) - saved}")


if __name__ == "__main__":
    main()
