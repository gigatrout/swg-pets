"""HTTP fetch helpers: live swgpets.com with Wayback fallback."""

from __future__ import annotations

import re
import ssl
import urllib.error
import urllib.parse
import urllib.request

from swgpets.config import UPSTREAM_BASE, USER_AGENT, WAYBACK_BASE, WAYBACK_SNAPSHOT

WAYBACK_PREFIX = re.compile(
    r"https?://web\.archive\.org/web/\d+(?:id_)?/",
    re.IGNORECASE,
)


def wayback_fetch_url(path: str, snapshot: str = WAYBACK_SNAPSHOT) -> str:
    if path.startswith("http"):
        target = path
    else:
        target = urllib.parse.urljoin(UPSTREAM_BASE + "/", path)
    if snapshot:
        return f"https://web.archive.org/web/{snapshot}id_/{target}"
    return f"{WAYBACK_BASE}{urllib.parse.urlparse(target).path}" + (
        f"?{urllib.parse.urlparse(target).query}" if urllib.parse.urlparse(target).query else ""
    )


def live_fetch_url(path: str) -> str:
    if path.startswith("http"):
        return path
    return urllib.parse.urljoin(UPSTREAM_BASE + "/", path)


def fetch_bytes(
    path: str,
    *,
    timeout: int = 90,
    prefer: str = "auto",
    live_timeout: int = 12,
) -> tuple[bytes, str]:
    """Return (body, source) where source is 'live' or 'wayback'."""
    errors: list[str] = []
    order = ("live", "wayback") if prefer == "auto" else (prefer,)

    for source in order:
        if source == "live":
            url = live_fetch_url(path)
            attempt_timeout = live_timeout
        elif source == "wayback":
            url = wayback_fetch_url(path)
            attempt_timeout = timeout
        else:
            raise ValueError(f"unknown source: {source}")

        try:
            body = _request(url, attempt_timeout)
            if source == "wayback":
                body = strip_wayback_artifacts(body)
            return body, source
        except (urllib.error.URLError, TimeoutError) as exc:
            errors.append(f"{source}: {exc}")

    raise RuntimeError("; ".join(errors))


def _no_proxy_opener() -> urllib.request.OpenerDirector:
    context = ssl.create_default_context()
    https = urllib.request.HTTPSHandler(context=context)
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), https)


def _request(url: str, timeout: int) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": f"{UPSTREAM_BASE}/",
        },
    )
    opener = _no_proxy_opener()
    with opener.open(request, timeout=timeout) as response:
        return response.read()


def strip_wayback_artifacts(body: bytes) -> bytes:
    text = body.decode("utf-8", errors="replace")
    text = WAYBACK_PREFIX.sub("/", text)
    text = text.replace("<!-- BEGIN WAYBACK TOOLBAR INSERT -->", "")
    text = text.replace("<!-- END WAYBACK TOOLBAR INSERT -->", "")
    return text.encode("utf-8")
