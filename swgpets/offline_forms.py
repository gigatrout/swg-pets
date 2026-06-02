"""Convert swgpets.com POST search forms to GET URLs for offline mirror lookup."""

from __future__ import annotations

import re
import urllib.parse
from http.server import BaseHTTPRequestHandler

# search_sid / search_specials[] option values on /pets and /specials
SPECIAL_ID_TO_NAME: dict[str, str] = {
    "1": "Provoke",
    "2": "Bite",
    "3": "Damage Poison",
    "4": "Puncture",
    "6": "Charge",
    "7": "Stomp",
    "8": "Dampen Pain",
    "9": "Enfeeble",
    "10": "Bolster Armor",
    "11": "Disease",
    "12": "Flank",
    "13": "Claw",
    "14": "Slash",
    "15": "Hamstring",
    "16": "Shaken",
    "17": "Wind Buffet",
    "18": "Health Leech",
    "19": "Defensive",
    "20": "Trample",
    "21": "Helper Monkey",
    "22": "Deflective Hide",
    "25": "Paralytic Poison",
    "26": "Preparation",
    "28": "Kick",
    "29": "Spit",
    "31": "Dancing Pet",
    "32": "Resource Scavenger",
    "33": "Truffle Pig",
}


def special_name_to_path(name: str) -> str:
    return name.replace(" ", "+")


def _parse_multipart(body: bytes, boundary: str) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}
    token = b"--" + boundary.encode("ascii", errors="replace")
    for part in body.split(token):
        if b"Content-Disposition" not in part:
            continue
        header_end = part.find(b"\r\n\r\n")
        if header_end < 0:
            continue
        headers = part[:header_end].decode("utf-8", errors="replace")
        content = part[header_end + 4 :].strip(b"\r\n-")
        name_match = re.search(r"name=(?:'|\")([^'\"]+)(?:'|\")", headers)
        if not name_match:
            continue
        value = content.decode("utf-8", errors="replace")
        if value:
            fields.setdefault(name_match.group(1), []).append(value)
    return fields


def parse_post_fields(handler: BaseHTTPRequestHandler) -> dict[str, list[str]]:
    """Parse application/x-www-form-urlencoded or multipart POST body."""
    length = int(handler.headers.get("Content-Length", "0") or 0)
    raw = handler.rfile.read(length) if length else b""
    content_type = handler.headers.get("Content-Type", "")

    if "multipart/form-data" in content_type:
        match = re.search(r"boundary=([^;\s]+)", content_type)
        if not match:
            return {}
        return _parse_multipart(raw, match.group(1).strip('"'))

    if raw:
        fields: dict[str, list[str]] = {}
        for key, value in urllib.parse.parse_qsl(raw.decode("utf-8", errors="replace")):
            fields.setdefault(key, []).append(value)
        return fields
    return {}


def _first(fields: dict[str, list[str]], *keys: str) -> str | None:
    for key in keys:
        values = fields.get(key)
        if values and values[0]:
            return values[0]
    return None


def pets_search_query(fields: dict[str, list[str]]) -> str:
    """Build GET query for /pets — only filter keys we mirror offline."""
    params: list[tuple[str, str]] = []

    special_ids: list[str] = []
    for key in ("search_specials[]", "search_specials"):
        special_ids.extend(v for v in fields.get(key, []) if v and v != "Any")
    if special_ids:
        params.append(("specials", special_ids[-1]))

    bonus_ids: list[str] = []
    for key in ("search_bonus[]", "search_bonus"):
        bonus_ids.extend(v for v in fields.get(key, []) if v)
    if bonus_ids:
        params.append(("bonus", bonus_ids[-1]))

    # sort1/sort2/show are not mirrored as separate pages; omit them.
    return urllib.parse.urlencode(params)


def pets_query_fallbacks(query: str) -> list[str]:
    """Simpler /pets query strings to try when the full URL is not mirrored."""
    parsed = urllib.parse.parse_qs(query, keep_blank_values=True)
    fallbacks: list[str] = []
    specials = parsed.get("specials", [])
    bonuses = parsed.get("bonus", [])
    if specials:
        fallbacks.append(f"specials={specials[-1]}")
    if bonuses:
        fallbacks.append(f"bonus={bonuses[-1]}")
    if specials and bonuses:
        fallbacks.insert(0, f"specials={specials[-1]}&bonus={bonuses[-1]}")
    return fallbacks


def special_search_query(fields: dict[str, list[str]]) -> str:
    """Build GET query string for /special from the specials search form."""
    params: list[tuple[str, str]] = []

    name = _first(fields, "search_name")
    if name:
        params.append(("name", name))

    sid = _first(fields, "search_sid")
    if sid and sid != "Any":
        # Numeric sid -> name= URL used by mirrored special pages
        name = SPECIAL_ID_TO_NAME.get(sid)
        if name:
            params.append(("name", special_name_to_path(name)))
        else:
            params.append(("search_sid", sid))

    for key in ("search_type", "search_rank", "search_universal", "letter"):
        value = _first(fields, key)
        if value and value != "Any":
            params.append((key, value))

    return urllib.parse.urlencode(params)


def redirect_path_for_post(path: str, fields: dict[str, list[str]]) -> str | None:
    """Return local redirect path (with query) for a POST, or None if unsupported."""
    base = path.split("?", 1)[0]
    if base == "/pets":
        query = pets_search_query(fields)
        return f"/pets?{query}" if query else "/pets"
    if base == "/special":
        query = special_search_query(fields)
        return f"/special?{query}" if query else "/special"
    return None
