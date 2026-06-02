#!/usr/bin/env python3
"""Download static assets (images, CSS, JS) into ./cache for offline use."""

from __future__ import annotations

import argparse
import re
import time
import urllib.parse
from pathlib import Path

from swgpets.config import CACHE_DIR, UPSTREAM_BASE, UPSTREAM_HOSTS
from swgpets.fetch import fetch_bytes
from swgpets.server import cache_path

ASSET_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".css",
    ".js",
    ".woff",
    ".woff2",
    ".ttf",
}

URL_IN_CSS = re.compile(r"url\(['\"]?([^'\"\)]+)['\"]?\)", re.IGNORECASE)
ATTR_RE = re.compile(
    r"""(?:src|href|background)\s*=\s*['"]([^'"]+)['"]""",
    re.IGNORECASE,
)


def is_asset_path(path: str) -> bool:
    lower = path.lower().split("?", 1)[0]
    return any(lower.endswith(ext) for ext in ASSET_SUFFIXES)


def normalize_asset(url: str, base: str) -> str | None:
    joined = urllib.parse.urljoin(base, url)
    parsed = urllib.parse.urlparse(joined)
    if parsed.scheme not in ("http", "https"):
        if url.startswith("/"):
            parsed = urllib.parse.urlparse(UPSTREAM_BASE + url)
        else:
            return None
    if parsed.netloc and parsed.netloc not in UPSTREAM_HOSTS:
        return None
    path = parsed.path or "/"
    if not is_asset_path(path):
        return None
    return urllib.parse.urlunparse(
        ("https", urllib.parse.urlparse(UPSTREAM_BASE).netloc, path, "", parsed.query, "")
    )


def extract_from_html(html: str, base: str) -> set[str]:
    found: set[str] = set()
    for match in ATTR_RE.finditer(html):
        normalized = normalize_asset(match.group(1), base)
        if normalized:
            found.add(normalized)
    return found


def extract_from_css(css: str, base: str) -> set[str]:
    found: set[str] = set()
    for match in URL_IN_CSS.finditer(css):
        normalized = normalize_asset(match.group(1), base)
        if normalized:
            found.add(normalized)
    return found


def prefetch(
    *,
    cache_dir: Path,
    prefer: str = "auto",
    seeds: list[Path],
    max_assets: int,
    delay: float,
    timeout: int,
) -> None:
    queue: list[str] = []

    for seed in seeds:
        if not seed.is_file():
            continue
        html = seed.read_text(encoding="utf-8", errors="replace")
        queue.extend(extract_from_html(html, UPSTREAM_BASE + "/"))

    pending = deque_unique(queue)
    saved = 0
    css_pending: list[str] = []

    while pending and saved < max_assets:
        url = pending.pop(0)
        dest = cache_path(url, cache_dir)
        if dest.is_file():
            continue
        try:
            parsed = urllib.parse.urlparse(url)
            body, source = fetch_bytes(parsed.path + (f"?{parsed.query}" if parsed.query else ""), timeout=timeout, prefer=prefer)
        except RuntimeError as exc:
            print(f"skip {url}: {exc}")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
        saved += 1
        print(f"[{saved}] [{source}] {url}")

        if dest.suffix.lower() == ".css":
            css_pending.append(url)
        time.sleep(delay)

    for css_url in css_pending:
        if saved >= max_assets:
            break
        css_path = cache_path(css_url, cache_dir)
        if not css_path.is_file():
            continue
        css = css_path.read_text(encoding="utf-8", errors="replace")
        for asset in extract_from_css(css, css_url):
            dest = cache_path(asset, cache_dir)
            if dest.is_file():
                continue
            if saved >= max_assets:
                break
            try:
                parsed = urllib.parse.urlparse(asset)
                body, source = fetch_bytes(
                    parsed.path + (f"?{parsed.query}" if parsed.query else ""),
                    timeout=timeout,
                    prefer=prefer,
                )
            except RuntimeError as exc:
                print(f"skip {asset}: {exc}")
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(body)
            saved += 1
            print(f"[{saved}] [{source}] {asset} (from css)")
            time.sleep(delay)

    print(f"Prefetched {saved} assets into {cache_dir}")


def deque_unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Prefetch SWG Pets static assets")
    parser.add_argument("--cache", type=Path, default=CACHE_DIR)
    parser.add_argument("--max-assets", type=int, default=2000)
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--prefer", choices=("auto", "live", "wayback"), default="auto")
    parser.add_argument(
        "seeds",
        nargs="*",
        type=Path,
        help="HTML files to scan (default: cache/index.html)",
    )
    args = parser.parse_args()
    seeds = args.seeds or [args.cache / "index.html"]
    args.cache.mkdir(parents=True, exist_ok=True)
    prefetch(
        cache_dir=args.cache,
        seeds=seeds,
        max_assets=args.max_assets,
        delay=args.delay,
        timeout=args.timeout,
        prefer=args.prefer,
    )


if __name__ == "__main__":
    main()
