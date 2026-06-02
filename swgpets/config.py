"""Configuration for the local SWG Pets server."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "cache"
MIRROR_DIR = ROOT / "mirror"

UPSTREAM_HOSTS = ("www.swgpets.com", "swgpets.com")
UPSTREAM_BASE = "https://www.swgpets.com"

# Wayback: empty snapshot = redirect to latest archived copy.
WAYBACK_SNAPSHOT = ""
WAYBACK_BASE = f"https://web.archive.org/web/{UPSTREAM_BASE}"
WAYBACK_CALENDAR = "https://web.archive.org/web/*/https://www.swgpets.com/"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Headers not forwarded to upstream or back to the client.
HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
    }
)
