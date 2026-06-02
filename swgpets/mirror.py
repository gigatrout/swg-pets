#!/usr/bin/env python3
"""Mirror www.swgpets.com into ./mirror for offline browsing."""

from __future__ import annotations

import argparse
import hashlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from html.parser import HTMLParser
from pathlib import Path

from swgpets.config import MIRROR_DIR, UPSTREAM_BASE, UPSTREAM_HOSTS, USER_AGENT

ASSET_EXTENSIONS = {
    ".css",
    ".js",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
}


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {k: v for k, v in attrs if k and v}
        for key in ("href", "src", "action"):
            value = attr_map.get(key)
            if value:
                self.links.add(value)


def normalize_url(url: str, base: str) -> str | None:
    joined = urllib.parse.urljoin(base, url)
    parsed = urllib.parse.urlparse(joined)
    if parsed.scheme not in ("http", "https"):
        return None
    if parsed.netloc and parsed.netloc not in UPSTREAM_HOSTS:
        return None
    path = parsed.path or "/"
    if parsed.netloc in ("",) + UPSTREAM_HOSTS or not parsed.netloc:
        netloc = urllib.parse.urlparse(UPSTREAM_BASE).netloc
        parsed = parsed._replace(netloc=netloc, scheme="https")
    clean = parsed._replace(fragment="")
    return urllib.parse.urlunparse(clean)


def local_path_for_url(url: str, root: Path) -> Path:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path or "/"
    if path.endswith("/"):
        path = path + "index.html"
    rel = path.lstrip("/")
    if parsed.query:
        digest = hashlib.sha256(parsed.query.encode()).hexdigest()[:12]
        stem = Path(rel)
        rel = str(stem.parent / f"{stem.name}_{digest}{stem.suffix or '.html'}")
    target = root / rel
    if not target.suffix and not target.exists():
        target = target.with_suffix(".html")
    return target


def fetch(url: str, timeout: int) -> tuple[bytes, str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type")
        return response.read(), content_type


def extract_links(html: bytes, base_url: str) -> set[str]:
    parser = LinkParser()
    try:
        parser.feed(html.decode("utf-8", errors="replace"))
    except Exception:
        return set()
    out: set[str] = set()
    for link in parser.links:
        normalized = normalize_url(link, base_url)
        if normalized:
            out.add(normalized)
    return out


def mirror_site(
    *,
    root: Path,
    max_pages: int,
    delay: float,
    timeout: int,
) -> None:
    root.mkdir(parents=True, exist_ok=True)
    start = f"{UPSTREAM_BASE}/"
    queue: deque[str] = deque([start])
    seen: set[str] = set()
    saved = 0

    while queue and saved < max_pages:
        url = queue.popleft()
        if url in seen:
            continue
        seen.add(url)

        try:
            body, _ = fetch(url, timeout)
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"skip {url}: {exc}")
            continue

        dest = local_path_for_url(url, root)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(body)
        saved += 1
        print(f"[{saved}/{max_pages}] {url} -> {dest}")

        if dest.suffix in (".html", "") or "html" in dest.name:
            for link in extract_links(body, url):
                if link not in seen:
                    queue.append(link)

        time.sleep(delay)

    print(f"Done. Saved {saved} resources under {root}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Mirror swgpets.com for offline use")
    parser.add_argument("--output", type=Path, default=MIRROR_DIR)
    parser.add_argument("--max-pages", type=int, default=500)
    parser.add_argument("--delay", type=float, default=0.75)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    mirror_site(
        root=args.output,
        max_pages=args.max_pages,
        delay=args.delay,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    main()
