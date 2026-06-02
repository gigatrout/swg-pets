#!/usr/bin/env python3
"""Backfill /specials, /special/*, and /pets?specials=* into the existing mirror."""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

from swgpets.backup import download_missing_assets, extract_links, mirror_dest, rewrite_body
from swgpets.config import MIRROR_DIR as DEFAULT_MIRROR
from swgpets.curl_fetch import fetch_to_file

# Special ability IDs from the pet search dropdown on /pets.
SPECIAL_IDS = [
    "1", "2", "3", "4", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16",
    "17", "18", "19", "20", "21", "22", "25", "26", "28", "29", "31", "32", "33",
]


def discover_special_paths(root: Path) -> set[str]:
    found: set[str] = set()
    for html_file in root.rglob("index.html"):
        text = html_file.read_text(encoding="utf-8", errors="replace")
        for link in extract_links(text, "/"):
            if link.startswith("/special") or link.startswith("/specials"):
                found.add(link.split("#", 1)[0])
        for match in re.finditer(r'href="/special/([^"?#]+)"', text):
            name = match.group(1)
            found.add(f"/special/{name}")
            found.add(f"/special?name={name}")
    return found


def fetch_page(path_query: str, root: Path, *, prefer: str, timeout: int) -> bool:
    path_only = path_query.split("?", 1)[0]
    dest = mirror_dest(path_query, root)
    if dest.is_file() and dest.stat().st_size > 500:
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    fetch_path = path_only + (
        f"?{path_query.split('?', 1)[1]}" if "?" in path_query else ""
    )
    order = (prefer,) if prefer != "auto" else ("live", "wayback")
    for source_name in order:
        source = fetch_to_file(
            fetch_path, dest, live_timeout=30, wb_timeout=timeout, prefer=source_name
        )
        if source and dest.stat().st_size > 500:
            dest.write_bytes(rewrite_body(dest.read_bytes()))
            return True
        if dest.exists():
            dest.unlink(missing_ok=True)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill specials into mirror")
    parser.add_argument("--output", type=Path, default=DEFAULT_MIRROR)
    parser.add_argument("--prefer", choices=("auto", "live", "wayback"), default="auto")
    parser.add_argument("--delay", type=float, default=0.3)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()

    root = args.output
    paths: set[str] = {"/specials", "/special"}
    paths.update(discover_special_paths(root))
    for sid in SPECIAL_IDS:
        paths.add(f"/pets?specials={sid}")
    for letter in "BCDEFHKPRSTW":
        paths.add(f"/special?letter={letter}")

    print(f"Backfilling {len(paths)} special-related pages into {root.resolve()}")
    ok = 0
    for path_query in sorted(paths):
        if fetch_page(path_query, root, prefer=args.prefer, timeout=args.timeout):
            ok += 1
            print(f"[ok] {path_query}")
        else:
            print(f"[skip] {path_query}")
        time.sleep(args.delay)

    # Creature "Acquire" lists linked from special detail pages.
    creature_paths: set[str] = set()
    for html_file in root.rglob("index.html"):
        text = html_file.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r'href="(/creatures\?[^"]+)"', text):
            creature_paths.add(match.group(1))

    print(f"Backfilling {len(creature_paths)} creature acquire pages...")
    for path_query in sorted(creature_paths):
        if fetch_page(path_query, root, prefer=args.prefer, timeout=args.timeout):
            ok += 1
            print(f"[ok] {path_query}")
        else:
            print(f"[skip] {path_query}")
        time.sleep(args.delay)

    print("Downloading images/icons referenced by mirrored pages...")
    saved, missed = download_missing_assets(
        root,
        prefer=args.prefer,
        delay=args.delay,
        wb_timeout=args.timeout,
    )
    print(f"Assets: downloaded {saved}, failed {missed}")

    print(f"Done. {ok} pages saved or already present.")


if __name__ == "__main__":
    main()
