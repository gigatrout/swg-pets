#!/usr/bin/env python3
"""Re-download /pets?specials=N pages so ability filters match the live site."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from swgpets.backup import SPECIAL_IDS, mirror_dest, rewrite_body
from swgpets.config import MIRROR_DIR
from swgpets.curl_fetch import fetch_to_file


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh pets?specials=* filter pages")
    parser.add_argument("--output", type=Path, default=MIRROR_DIR)
    parser.add_argument("--prefer", choices=("auto", "live", "wayback"), default="auto")
    parser.add_argument("--delay", type=float, default=0.25)
    args = parser.parse_args()

    ok = 0
    for sid in SPECIAL_IDS:
        path_query = f"/pets?specials={sid}"
        dest = mirror_dest(path_query, args.output)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_file() and dest.stat().st_size > 1000:
            ok += 1
            print(f"[cached] {path_query}")
            time.sleep(args.delay)
            continue
        source = fetch_to_file(path_query, dest, prefer=args.prefer)
        if source and dest.is_file() and dest.stat().st_size > 1000:
            dest.write_bytes(rewrite_body(dest.read_bytes()))
            ok += 1
            print(f"[{source}] {path_query}")
        else:
            if dest.exists():
                dest.unlink(missing_ok=True)
            print(f"[skip] {path_query}")
        time.sleep(args.delay)

    print(f"Refreshed {ok}/{len(SPECIAL_IDS)} ability filter pages.")


if __name__ == "__main__":
    main()
