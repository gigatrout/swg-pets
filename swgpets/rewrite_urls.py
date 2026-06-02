"""Rewrite mirrored HTML/CSS so links work offline (strip Wayback + swgpets.com)."""

from __future__ import annotations

import re

REWRITE_HOSTS = re.compile(
    rb"https?://(?:www\.)?swgpets\.com|//(?:www\.)?swgpets\.com",
    re.IGNORECASE,
)

# /web/20230318150108cs_//templates/... or https://web.archive.org/web/123im_/...
WAYBACK_PREFIX = re.compile(
    rb"https?://web\.archive\.org/web/\d+(?:[a-z]{2}_)?/?",
    re.IGNORECASE,
)
WAYBACK_PATH = re.compile(
    rb"/web/\d+(?:[a-z]{2}_)?/*",
    re.IGNORECASE,
)

WAYBACK_TOOLBAR = re.compile(
    rb"<!-- BEGIN WAYBACK TOOLBAR INSERT -->.*?<!-- END WAYBACK TOOLBAR INSERT -->",
    re.DOTALL | re.IGNORECASE,
)
WAYBACK_SCRIPT = re.compile(
    rb"<script\b[^>]*\b(?:archive\.org|web-static\.archive\.org)\b[^>]*>.*?</script>",
    re.DOTALL | re.IGNORECASE,
)
WAYBACK_LINK = re.compile(
    rb"<link\b[^>]*\bweb-static\.archive\.org\b[^>]*>",
    re.IGNORECASE,
)
WAYBACK_DIV = re.compile(
    rb'<div\b[^>]*\bid="wm-ipp(?:-base)?"[^>]*>.*?</div>\s*(?=<div|<table|<form|<center|<a\s|<h|<p|<span|<script|<link|<table)',
    re.DOTALL | re.IGNORECASE,
)


def rewrite_mirror_body(body: bytes, *, local_origin: bytes = b"") -> bytes:
    """Normalize HTML/CSS/JS bodies saved from live site or Wayback."""
    if not body:
        return body

    head = body[:4096].lower()
    if b"<html" not in head and b"<!doctype" not in head and b"text/css" not in head and b"url(" not in head:
        if local_origin:
            return REWRITE_HOSTS.sub(local_origin, body)
        return REWRITE_HOSTS.sub(b"", body)

    body = WAYBACK_TOOLBAR.sub(b"", body)
    body = WAYBACK_SCRIPT.sub(b"", body)
    body = WAYBACK_LINK.sub(b"", body)
    body = WAYBACK_DIV.sub(b"", body)
    body = WAYBACK_PREFIX.sub(b"/", body)
    body = WAYBACK_PATH.sub(b"/", body)

    replacement = local_origin if local_origin else b""
    body = REWRITE_HOSTS.sub(replacement, body)
    body = re.sub(rb'(?<=["\'(=])/+', b'/', body)
    return body
