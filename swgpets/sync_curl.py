#!/usr/bin/env python3
"""Curl-based sync (subprocess) — avoids urllib proxy issues."""

from __future__ import annotations

import argparse
import re
import subprocess
import time
from pathlib import Path

from swgpets.config import CACHE_DIR
from swgpets.prefetch import ATTR_RE, extract_from_html, is_asset_path
from swgpets.server import cache_path
from swgpets.sync import CORE_PATHS, save_to_cache, _is_html_path

LIVE_BASE = "https://www.swgpets.com"
WB_BASE = f"https://web.archive.org/web/{LIVE_BASE}"


def curl_download(url: str, dest: Path, timeout: int) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "curl",
        "-sSL",
        "--max-time",
        str(timeout),
        "--noproxy",
        "*",
        "-A",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "-o",
        str(dest),
        url,
    ]
    env = {
        "NO_PROXY": "*",
        "no_proxy": "*",
        "HTTP_PROXY": "",
        "HTTPS_PROXY": "",
        "ALL_PROXY": "",
    }
    try:
        subprocess.run(cmd, check=True, env={**__import__("os").environ, **env})
        return dest.is_file() and dest.stat().st_size > 0
    except (subprocess.CalledProcessError, OSError):
        if dest.exists():
            dest.unlink()
        return False


def fetch_path(path: str, cache_dir: Path, live_timeout: int, wb_timeout: int) -> str | None:
    live_url = f"{LIVE_BASE}{path}"
    wb_url = f"{WB_BASE}{path}"
    if path == "/" or path == "":
        dest = cache_dir / "index.html"
    else:
        dest = cache_dir / path.lstrip("/")

    if curl_download(live_url, dest, live_timeout):
        return "live"
    if curl_download(wb_url, dest, wb_timeout):
        return "wayback"
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, default=CACHE_DIR)
    parser.add_argument("--live-timeout", type=int, default=15)
    parser.add_argument("--wb-timeout", type=int, default=120)
    parser.add_argument("--delay", type=float, default=0.12)
    parser.add_argument("--max-assets", type=int, default=800)
    args = parser.parse_args()

    args.cache.mkdir(parents=True, exist_ok=True)
    html_files: list[Path] = []

    for path in CORE_PATHS:
        source = fetch_path(path, args.cache, args.live_timeout, args.wb_timeout)
        if source:
            print(f"[{source}] {path}")
            dest = args.cache / "index.html" if path == "/" else args.cache / path.lstrip("/")
            if _is_html_path(path, dest):
                html_files.append(dest)
        else:
            print(f"[FAIL] {path}")
        time.sleep(args.delay)

    assets: set[str] = set()
    for html in html_files:
        text = html.read_text(encoding="utf-8", errors="replace")
        for match in ATTR_RE.finditer(text):
            raw = match.group(1)
            if raw.startswith("/") and is_asset_path(raw):
                assets.add(raw)

    saved = 0
    for asset in sorted(assets):
        if saved >= args.max_assets:
            break
        dest = args.cache / asset.lstrip("/")
        if dest.is_file() and dest.stat().st_size > 0:
            continue
        source = fetch_path(asset, args.cache, args.live_timeout, args.wb_timeout)
        if source:
            saved += 1
            print(f"[{source}] {asset}")
        time.sleep(args.delay)

    count = sum(1 for _ in args.cache.rglob("*") if _.is_file())
    print(f"Done. {count} files in {args.cache.resolve()}")


if __name__ == "__main__":
    main()
