"""Download pages and assets via curl (live site, then Wayback fallback)."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from swgpets.config import UPSTREAM_BASE, USER_AGENT, WAYBACK_BASE

WAYBACK_PREFIX = re.compile(
    r"https?://web\.archive\.org/web/\d+(?:id_)?/",
    re.IGNORECASE,
)


def _curl_env() -> dict[str, str]:
    env = dict(os.environ)
    env["NO_PROXY"] = "*"
    env["no_proxy"] = "*"
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        env.pop(key, None)
    return env


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
        USER_AGENT,
        "-H",
        f"Referer: {UPSTREAM_BASE}/",
        "-o",
        str(dest),
        url,
    ]
    try:
        subprocess.run(cmd, check=True, env=_curl_env(), capture_output=True)
        if not dest.is_file() or dest.stat().st_size == 0:
            return False
        if not _looks_valid_asset(dest):
            dest.unlink(missing_ok=True)
            return False
        return True
    except (subprocess.CalledProcessError, OSError):
        if dest.exists():
            dest.unlink(missing_ok=True)
        return False


def _looks_valid_asset(dest: Path) -> bool:
    """Reject HTML error pages saved when upstream blocks or redirects."""
    size = dest.stat().st_size
    if size < 80:
        return False
    head = dest.read_bytes()[:512]
    lower = head.lstrip().lower()
    if lower.startswith(b"<!doctype") or lower.startswith(b"<html") or lower.startswith(b"<"):
        return False
    suffix = dest.suffix.lower()
    if suffix == ".png":
        return head[:4] == b"\x89PNG"
    if suffix in (".jpg", ".jpeg"):
        return head[:2] == b"\xff\xd8"
    if suffix == ".gif":
        return head[:6] in (b"GIF87a", b"GIF89a")
    if suffix == ".webp":
        return head[:4] == b"RIFF" and b"WEBP" in head[8:16]
    if suffix == ".ico":
        return head[:4] in (b"\x00\x00\x01\x00", b"\x89PNG")
    if suffix in (".css", ".js"):
        return True
    if suffix in (".woff", ".woff2", ".ttf", ".eot", ".svg"):
        return True
    return True


def strip_wayback_artifacts(body: bytes) -> bytes:
    text = body.decode("utf-8", errors="replace")
    text = WAYBACK_PREFIX.sub("/", text)
    text = text.replace("<!-- BEGIN WAYBACK TOOLBAR INSERT -->", "")
    text = text.replace("<!-- END WAYBACK TOOLBAR INSERT -->", "")
    return text.encode("utf-8")


def fetch_to_file(
    path: str,
    dest: Path,
    *,
    live_timeout: int = 30,
    wb_timeout: int = 120,
    prefer: str = "auto",
) -> str | None:
    """Download path into dest. Returns 'live', 'wayback', or None."""
    if path.startswith("http"):
        live_url = path
        wb_url = f"{WAYBACK_BASE}{path.replace(UPSTREAM_BASE, '')}"
    else:
        live_url = f"{UPSTREAM_BASE}{path}"
        wb_url = f"{WAYBACK_BASE}{path}"

    order: tuple[str, ...]
    if prefer == "live":
        order = ("live",)
    elif prefer == "wayback":
        order = ("wayback",)
    else:
        order = ("live", "wayback")

    for source in order:
        url = live_url if source == "live" else wb_url
        timeout = live_timeout if source == "live" else wb_timeout
        if curl_download(url, dest, timeout):
            if source == "wayback":
                dest.write_bytes(strip_wayback_artifacts(dest.read_bytes()))
            return source
    return None
