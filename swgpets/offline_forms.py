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


# POST form field -> GET query param (matches swgpets.com URL shape).
PET_SEARCH_FIELD_TO_PARAM: dict[str, str] = {
    "search_name": "search_name",
    "search_family": "family",
    "search_group": "group",
    "search_obtain": "obtain",
    "search_planet": "planet",
    "search_supplement": "supplement",
    "search_mission": "mission",
    "search_mount": "mount",
    "search_flying": "flying",
    "search_added": "added",
    "search_type": "type",
    "search_lyase": "lyase",
    "search_colors": "colors",
    "search_frog": "frog",
}

PET_QUERY_DISPLAY_KEYS = frozenset({"sort1", "sort2", "show", "page"})


def _pets_filter_params(parsed: dict[str, list[str]]) -> list[tuple[str, str]]:
    params: list[tuple[str, str]] = []
    for key in sorted(parsed):
        if key in PET_QUERY_DISPLAY_KEYS:
            continue
        for value in parsed[key]:
            if value:
                params.append((key, value))
    return params


def pets_search_query(fields: dict[str, list[str]]) -> str:
    """Build GET query for /pets — filter keys used by the offline mirror."""
    params: list[tuple[str, str]] = []
    seen: set[str] = set()

    special_ids: list[str] = []
    for key in ("search_specials[]", "search_specials"):
        special_ids.extend(v for v in fields.get(key, []) if v and v != "Any")
    if special_ids:
        params.append(("specials", special_ids[-1]))
        seen.add("specials")

    bonus_ids: list[str] = []
    for key in ("search_bonus[]", "search_bonus"):
        bonus_ids.extend(v for v in fields.get(key, []) if v)
    if bonus_ids:
        params.append(("bonus", bonus_ids[-1]))
        seen.add("bonus")

    for field, param in PET_SEARCH_FIELD_TO_PARAM.items():
        value = _first(fields, field)
        if value and value != "Any" and param not in seen:
            params.append((param, value))
            seen.add(param)

    # sort1/sort2/show are not mirrored as separate pages; omit them.
    return urllib.parse.urlencode(params)


def pets_query_fallbacks(query: str) -> list[str]:
    """Simpler /pets query strings to try when the full URL is not mirrored."""
    parsed = urllib.parse.parse_qs(query, keep_blank_values=True)
    fallbacks: list[str] = []

    filter_query = urllib.parse.urlencode(_pets_filter_params(parsed))
    if filter_query:
        fallbacks.append(filter_query)

    specials = parsed.get("specials", [])
    bonuses = parsed.get("bonus", [])
    if specials:
        simplified = f"specials={specials[-1]}"
        if simplified not in fallbacks:
            fallbacks.append(simplified)
    if bonuses:
        simplified = f"bonus={bonuses[-1]}"
        if simplified not in fallbacks:
            fallbacks.append(simplified)
    if specials and bonuses:
        combined = f"specials={specials[-1]}&bonus={bonuses[-1]}"
        if combined not in fallbacks:
            fallbacks.insert(0, combined)
    return fallbacks


def pets_canonical_filter_query(query: str) -> str | None:
    """Drop sort/show/page params; return filter-only query when it differs."""
    parsed = urllib.parse.parse_qs(query, keep_blank_values=True)
    if not parsed:
        return None
    if not any(key in parsed for key in PET_QUERY_DISPLAY_KEYS):
        return None
    canonical = urllib.parse.urlencode(_pets_filter_params(parsed))
    if not canonical or canonical == query:
        return None
    return canonical


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


def creatures_search_query(path: str, fields: dict[str, list[str]]) -> str:
    """Build GET query for /creatures from POST body + action URL query."""
    _, _, existing = path.partition("?")
    params: list[tuple[str, str]] = list(
        urllib.parse.parse_qsl(existing, keep_blank_values=True)
    )
    seen = {key for key, _ in params}
    skip = {"sort1", "sort2", "show"}
    for key, values in fields.items():
        if key in skip or not values or not values[0] or values[0] == "Any":
            continue
        if key not in seen:
            params.append((key, values[0]))
            seen.add(key)
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
    if base == "/creatures":
        query = creatures_search_query(path, fields)
        return f"/creatures?{query}" if query else "/creatures"
    return None
