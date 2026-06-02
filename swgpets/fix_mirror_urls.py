#!/usr/bin/env python3
"""Rewrite all mirrored HTML/CSS to strip Wayback URLs (fixes Tools page styling/images)."""

from __future__ import annotations

import argparse
from pathlib import Path

from swgpets.config import MIRROR_DIR
from swgpets.rewrite_urls import rewrite_mirror_body


def rewrite_mirror_tree(root: Path) -> int:
    updated = 0
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in (".html", ".htm", ".css", ".php") and path.name != "index.html":
            continue
        original = path.read_bytes()
        fixed = rewrite_mirror_body(original)
        if fixed != original:
            path.write_bytes(fixed)
            updated += 1
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Fix Wayback URLs in ./mirror HTML/CSS")
    parser.add_argument("--output", type=Path, default=MIRROR_DIR)
    args = parser.parse_args()

    updated = rewrite_mirror_tree(args.output)
    print(f"Rewrote {updated} files under {args.output.resolve()}")


if __name__ == "__main__":
    main()
