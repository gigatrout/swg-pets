"""Top-nav and tool pages to mirror for offline browsing."""

from __future__ import annotations

# Main nav + Tools dropdown (from site header).
NAV_PAGES: tuple[str, ...] = (
    "/creatures",
    "/research",
    "/planner",
    "/spots",
    "/lyase",
    "/known",
    "/sheet",
    "/exp",
    "/statcalc",
    "/hydro",
    "/oekevo",
    "/family",
    "/unknown",
    "/about",
)

# Creature browser letter tabs (linked from /creatures).
CREATURE_LETTERS: tuple[str, ...] = tuple(
    f"/creatures?letter={letter}" for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
)

# Shared template assets used on every page.
TEMPLATE_ASSETS: tuple[str, ...] = (
    "/templates/swgpets/swgpets.css",
    "/templates/swgpets/swgpetsmenu.css",
    "/templates/swgpets/images/swgpets_header.png",
    "/templates/swgpets/images/spacer.png",
    "/templates/swgpets/images/tail_top.png",
    "/templates/swgpets/images/tail_left.png",
    "/templates/swgpets/images/tail_right.png",
    "/favicon.ico",
)


def nav_seed_paths(*, include_creature_letters: bool = True) -> list[str]:
    seeds = list(NAV_PAGES)
    if include_creature_letters:
        seeds.extend(CREATURE_LETTERS)
    return seeds
