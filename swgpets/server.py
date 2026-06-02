#!/usr/bin/env python3
"""Local HTTP server that proxies https://www.swgpets.com with optional disk cache."""

from __future__ import annotations

import argparse
import email.message
import hashlib
import http.client
import mimetypes
import re
import socketserver
import ssl
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from swgpets.backup import mirror_dest, query_slug
from swgpets.offline_forms import parse_post_fields, pets_query_fallbacks, redirect_path_for_post
from swgpets.config import (
    CACHE_DIR,
    DEFAULT_HOST,
    DEFAULT_PORT,
    HOP_BY_HOP,
    MIRROR_DIR,
    UPSTREAM_BASE,
    UPSTREAM_HOSTS,
    USER_AGENT,
)

from swgpets.rewrite_urls import rewrite_mirror_body

STATIC_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".webp",
    ".css",
    ".js",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
}


def is_static_path(path: str) -> bool:
    base = path.lower().split("?", 1)[0]
    return any(base.endswith(ext) for ext in STATIC_SUFFIXES)


def filter_headers(headers: email.message.Message) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    for key, value in headers.items():
        if key.lower() in HOP_BY_HOP:
            continue
        items.append((key, value))
    return items


def cache_path(url: str, root: Path) -> Path:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path or "/"
    if path.endswith("/"):
        path += "index.html"
    rel = Path(path.lstrip("/"))
    if parsed.query:
        digest = hashlib.sha256(parsed.query.encode()).hexdigest()[:12]
        rel = rel.parent / f"{rel.stem}_{digest}{rel.suffix or '.html'}"
    return root / rel


def rewrite_body(body: bytes, content_type: str | None, local_origin: str) -> bytes:
    if not content_type:
        return body
    lowered = content_type.lower()
    if "text/html" not in lowered and "text/css" not in lowered and "javascript" not in lowered:
        return body
    origin_bytes = local_origin.encode("ascii")
    body = rewrite_mirror_body(body, local_origin=origin_bytes)
    if "text/html" in lowered and b"search_specials[]" in body:
        # Single-select offline: avoids multi-select sending many ?specials= ids.
        body = body.replace(b"search_specials[]' MULTIPLE", b"search_specials[]'")
        body = body.replace(b'search_specials[]" MULTIPLE', b'search_specials[]"')
        body = body.replace(b"search_bonus[]' MULTIPLE", b"search_bonus[]'")
    return body


def path_variants(path: str) -> list[str]:
    """Return path aliases for mirror lookup (+ vs space vs _)."""
    decoded = urllib.parse.unquote(path)
    variants: set[str] = {path, decoded}
    for candidate in list(variants):
        variants.add(candidate.replace(" ", "+"))
        variants.add(candidate.replace(" ", "_"))
        variants.add(candidate.replace("+", " "))
        variants.add(candidate.replace("+", "_"))
        variants.add(candidate.replace("_", "+"))
        variants.add(candidate.replace("_", " "))
    return list(variants)


def request_path_query(raw_path: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(raw_path)
    return urllib.parse.unquote(parsed.path or "/"), parsed.query


def serve_mirror_404(handler: BaseHTTPRequestHandler, path: str, query: str = "") -> None:
    display = path + (f"?{query}" if query else "")
    message = f"""<!DOCTYPE html>
<html><head><title>Not in offline backup</title></head>
<body>
<h1>Not in offline backup</h1>
<p><code>{display}</code> was not mirrored. Offline backup includes <strong>/pets</strong>, <strong>/pet/*</strong>, <strong>/creatures</strong>, <strong>/special*</strong>, Tools pages, and creature acquire lists.</p>
<p>Run <code>./backfill-nav.sh</code> for Creatures + Tools, or <code>./backfill-specials.sh</code> for ability acquire lists.</p>
<p><a href="/pets">Go to Pet List</a></p>
</body></html>"""
    payload = message.encode("utf-8")
    handler.send_response(404, "Not found in local mirror")
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def serve_local_file(
    path: Path,
    handler: BaseHTTPRequestHandler,
    *,
    local_origin: str | None = None,
) -> bool:
    if not path.is_file():
        return False
    data = path.read_bytes()
    mime, _ = mimetypes.guess_type(str(path))
    if local_origin and mime and (
        mime.startswith("text/") or "javascript" in mime or "json" in mime
    ):
        data = rewrite_body(data, mime, local_origin)
    handler.send_response(200)
    handler.send_header("Content-Type", mime or "application/octet-stream")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)
    return True


class SwgPetsHandler(BaseHTTPRequestHandler):
    upstream_base = UPSTREAM_BASE
    cache_dir = CACHE_DIR
    mirror_dir = MIRROR_DIR
    use_cache = True
    prefer_mirror = False
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}")

    @property
    def local_origin(self) -> str:
        host = self.headers.get("Host", f"127.0.0.1:{DEFAULT_PORT}")
        return f"http://{host}"

    def _upstream_url(self) -> str:
        parsed = urllib.parse.urlparse(self.path)
        return urllib.parse.urlunparse(
            (
                "https",
                urllib.parse.urlparse(self.upstream_base).netloc,
                parsed.path or "/",
                "",
                parsed.query,
                "",
            )
        )

    def _mirror_candidates(self) -> list[Path]:
        path, query = request_path_query(self.path)

        if path in ("/", "/index.php"):
            return [
                self.mirror_dir / "index.html",
                self.mirror_dir / "pets" / "index.html",
            ]

        candidates: list[Path] = []

        # Try simplified /pets filter URLs first (mirrored as pets/specials_N/).
        if path.rstrip("/") == "/pets" and query:
            for simpler in pets_query_fallbacks(query):
                candidates.append(mirror_dest(f"/pets?{simpler}", self.mirror_dir))
                candidates.append(
                    self.mirror_dir / "pets" / query_slug(simpler) / "index.html"
                )

        for variant in path_variants(path):
            path_query = variant + (f"?{query}" if query else "")
            candidates.append(mirror_dest(path_query, self.mirror_dir))

            rel = variant.lstrip("/")
            if not rel:
                continue
            if query:
                slug = query_slug(query)
                segments = [s for s in rel.split("/") if s]
                if segments:
                    candidates.append(self.mirror_dir.joinpath(*segments, slug, "index.html"))
            else:
                candidates.extend(
                    [
                        self.mirror_dir / rel,
                        self.mirror_dir / f"{rel}.html",
                        self.mirror_dir / rel / "index.html",
                    ]
                )

        # /creatures?specials=3-1 (acquire lists from special detail pages)
        if path.startswith("/creatures") and query:
            for variant in path_variants(path):
                path_query = variant + f"?{query}"
                candidates.append(mirror_dest(path_query, self.mirror_dir))
                slug = query_slug(query)
                segments = [s for s in variant.lstrip("/").split("/") if s]
                if segments:
                    candidates.append(self.mirror_dir.joinpath(*segments, slug, "index.html"))

        # /special/Damage+Poison (icon links) vs /special?name=Damage+Poison (perm links)
        if path.startswith("/special/") and not query:
            name = path[len("/special/") :].strip("/")
            if name:
                for variant in path_variants(name):
                    candidates.append(self.mirror_dir / "special" / variant / "index.html")
                candidates.append(
                    self.mirror_dir / "special" / query_slug(f"name={name}") / "index.html"
                )

        seen: set[Path] = set()
        unique: list[Path] = []
        for candidate in candidates:
            if candidate not in seen:
                seen.add(candidate)
                unique.append(candidate)
        return unique

    def _try_mirror(self) -> bool:
        if not self.prefer_mirror:
            return False
        for candidate in self._mirror_candidates():
            if serve_local_file(candidate, self, local_origin=self.local_origin):
                return True
        return False

    def _try_cache(self) -> bool:
        if not self.use_cache:
            return False
        cached = cache_path(self._upstream_url(), self.cache_dir)
        return serve_local_file(cached, self, local_origin=self.local_origin)

    def _canonical_pets_redirect(self) -> bool:
        """Redirect /pets?sort1=...&specials=N to /pets?specials=N when mirrored."""
        path, query = request_path_query(self.path)
        if path.rstrip("/") != "/pets" or not query:
            return False
        fallbacks = pets_query_fallbacks(query)
        if not fallbacks:
            return False
        canonical = fallbacks[-1] if len(fallbacks) == 1 else fallbacks[0]
        # Prefer specials-only URL when an ability filter is present.
        parsed = urllib.parse.parse_qs(query, keep_blank_values=True)
        if parsed.get("specials"):
            canonical = f"specials={parsed['specials'][-1]}"
            if parsed.get("bonus"):
                canonical += f"&bonus={parsed['bonus'][-1]}"
        if canonical == query:
            return False
        dest = mirror_dest(f"/pets?{canonical}", self.mirror_dir)
        if not dest.is_file():
            return False
        print(f"GET {path}?{query} -> /pets?{canonical}")
        self.send_response(302, "Found")
        self.send_header("Location", f"/pets?{canonical}")
        self.end_headers()
        return True

    def _mirror_post_redirect(self) -> bool:
        """Handle search forms: POST /pets or POST /special -> GET mirror page."""
        path, _ = request_path_query(self.path)
        if path not in ("/pets", "/special", "/creatures"):
            return False
        fields = parse_post_fields(self)
        target = redirect_path_for_post(path, fields)
        if not target:
            return False
        print(f"POST {path} -> GET {target}")
        self.send_response(302, "Found")
        self.send_header("Location", target)
        self.end_headers()
        return True

    def _proxy(self, method: str) -> None:
        if method == "POST" and self.prefer_mirror and self._mirror_post_redirect():
            return

        if method == "GET" and self.prefer_mirror and self._canonical_pets_redirect():
            return

        if self._try_mirror():
            return

        if self.prefer_mirror:
            path, query = request_path_query(self.path)
            serve_mirror_404(self, path, query)
            return

        url = self._upstream_url()
        parsed = urllib.parse.urlparse(url)

        if method == "GET" and is_static_path(parsed.path or "/") and self._try_cache():
            return

        body = None
        if method in ("POST", "PUT", "PATCH"):
            length = int(self.headers.get("Content-Length", "0") or 0)
            body = self.rfile.read(length) if length else b""

        context = ssl.create_default_context()
        conn = http.client.HTTPSConnection(
            parsed.hostname,
            parsed.port or 443,
            context=context,
            timeout=120,
        )
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in HOP_BY_HOP
            and key.lower() != "accept-encoding"
        }
        headers["User-Agent"] = USER_AGENT
        headers["Host"] = parsed.hostname
        headers["Referer"] = f"{self.upstream_base}/"
        try:
            conn.request(
                method,
                parsed.path + (f"?{parsed.query}" if parsed.query else ""),
                body=body,
                headers=headers,
            )
            upstream = conn.getresponse()
            payload = upstream.read()
            content_type = upstream.getheader("Content-Type")
            payload = rewrite_body(payload, content_type, self.local_origin)

            if method == "GET" and upstream.status == 200:
                dest = cache_path(url, self.cache_dir)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(payload)

            self.send_response(upstream.status, upstream.reason)
            for key, value in filter_headers(upstream.msg):
                if key.lower() == "location":
                    for host in UPSTREAM_HOSTS:
                        value = value.replace(f"https://{host}", self.local_origin)
                        value = value.replace(f"http://{host}", self.local_origin)
                if key.lower() == "content-length":
                    continue
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except OSError as exc:
            print(f"upstream error for {url}: {exc}")
            if method == "GET" and self._try_cache():
                return
            message = b"Bad Gateway: could not reach www.swgpets.com"
            self.send_response(502, "Bad Gateway")
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(message)))
            self.end_headers()
            self.wfile.write(message)
        finally:
            conn.close()

    def do_GET(self) -> None:
        self._proxy("GET")

    def do_HEAD(self) -> None:
        self._proxy("HEAD")

    def do_POST(self) -> None:
        self._proxy("POST")

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.end_headers()


def run_server(
    host: str,
    port: int,
    *,
    cache: bool,
    mirror_only: bool,
) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    handler = SwgPetsHandler
    handler.use_cache = cache
    handler.prefer_mirror = mirror_only

    with ThreadingHTTPServer((host, port), handler) as httpd:
        mode = "mirror files" if mirror_only else "live proxy (with cache)"
        print(f"SWG Pets local server: http://{host}:{port}")
        print(f"Upstream: {UPSTREAM_BASE}")
        print(f"Mode: {mode}")
        print("Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local SWG Pets web server")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-cache", action="store_true", help="Do not read/write disk cache")
    parser.add_argument(
        "--mirror-only",
        action="store_true",
        help="Serve only ./mirror (run mirror.py first); no live upstream",
    )
    args = parser.parse_args()
    run_server(args.host, args.port, cache=not args.no_cache, mirror_only=args.mirror_only)


if __name__ == "__main__":
    main()
