# SWG Pets — Offline Backup & Local Server

A local copy of [swgpets.com/pets](https://www.swgpets.com/pets) so you can browse the pet database even when the live site is down. The project downloads pages, images, and CSS to your disk, then serves them with a small Python web server — **no internet required** after the backup is done.

---

## Table of contents

1. [What this does](#what-this-does)
2. [Requirements](#requirements)
3. [First-time setup](#first-time-setup)
4. [Everyday usage](#everyday-usage)
5. [Server modes: offline vs live proxy](#server-modes-offline-vs-live-proxy)
6. [What is backed up (and what is not)](#what-is-backed-up-and-what-is-not)
7. [All commands](#all-commands)
8. [Project layout](#project-layout)
9. [Updating your backup](#updating-your-backup)
10. [Troubleshooting](#troubleshooting)
11. [Advanced options](#advanced-options)
12. [Legacy / optional tools](#legacy--optional-tools)

---

## What this does

| Step | Command | Needs network? |
|------|---------|----------------|
| **1. Download** | `./backup.sh` | Yes (or Wayback Machine) |
| **2. Browse** | `./start.sh` | **No** — reads from `./mirror` on disk |

When you run `./start.sh` and a backup already exists (`mirror/pets/`), the server runs in **offline mode**:

- Files are read from `~/git/swgPets/mirror/`
- **Nothing is fetched from swgpets.com**
- If a URL is not in the mirror, you get a 404 (no fallback to the live site)

The live site is only contacted when you run `./backup.sh` (or if you explicitly start in [proxy mode](#server-modes-offline-vs-live-proxy)).

---

## Requirements

- **macOS or Linux** (scripts use bash)
- **Python 3.10+** (stdlib only — no `pip install` needed)
- **`curl`** in your PATH (used for downloads)
- **`lsof`** (used by `./stop.sh` to find the server process)

Network is only required for `./backup.sh`, not for `./start.sh` in offline mode.

---

## First-time setup

```bash
cd ~/git/swgPets

chmod +x backup.sh backfill-specials.sh start.sh stop.sh mirror.sh

./backup.sh
```

The backup can take **20–40+ minutes** depending on connection speed. It prints progress as it saves pages and assets. When it finishes, you should see a summary like:

```text
Done. N pages, M assets, T files total under .../mirror
```

Then start the server:

```bash
./start.sh
```

Open in your browser:

**http://127.0.0.1:8765/pets**

Use `/pets` as the main entry point. The root URL (`/`) redirects to the pet list.

---

## Everyday usage

### Start browsing (offline)

```bash
cd ~/git/swgPets
./start.sh
```

You should see:

```text
Found ./mirror — starting in offline mode (no network required).
Starting SWG Pets at http://127.0.0.1:8765/pets
Serving static backup from ./mirror (offline — pets section only)
```

### Stop the server

```bash
./stop.sh
```

Or press **Ctrl+C** in the terminal where the server is running.

### Refresh the backup (when the live site is up)

```bash
./stop.sh          # optional but avoids port conflicts
./backup.sh        # re-download / merge new content
./start.sh
```

Re-running `./backup.sh` skips files that are already on disk and only fetches missing pages.

---

## Server modes: offline vs live proxy

`./start.sh` picks the mode automatically:

| Condition | Mode | Data source |
|-----------|------|-------------|
| `mirror/pets/` exists and you run `./start.sh` with no extra flags | **Offline (default)** | `./mirror` on disk only |
| You pass `--mirror-only` | **Offline** | `./mirror` on disk only |
| No `mirror/pets/`, or you pass `--no-cache` | **Live proxy** | Fetches from `www.swgpets.com` |

### Offline mode (recommended)

```bash
./start.sh
# same as:
./start.sh --mirror-only
```

- Serves static HTML, images, and CSS from `./mirror`
- Works with Wi‑Fi off
- Pet list, filters, and pet detail pages work
- Login, live search, and non-mirrored sections do **not** work

### Live proxy mode (legacy)

```bash
./start.sh --no-cache
```

- Proxies requests to `https://www.swgpets.com`
- Requires internet
- PHP features (login, search) may work
- Not a durable offline archive — use `./backup.sh` for that

### How to confirm you are offline

1. Check the startup message for `offline mode` / `Serving static backup from ./mirror`.
2. Disconnect from the network and reload **http://127.0.0.1:8765/pets** — it should still work.

---

## What is backed up (and what is not)

### Included

- **`/pets`** — main pet list
- **`/pets?letter=A` … `Z`** — alphabetical listings
- **`/pets?specials=N`** — pets filtered by ability (e.g. Damage Poison)
- **Filter variants** linked from the pet list (group, family, mount, mutation, etc.)
- **`/pet/Name`** — individual pet detail pages (including names with spaces, stored as `Name+With+Spaces`)
- **`/specials`** and **`/special/Name`** — ability list and detail (train ranks, effects)
- **`/creatures?specials=N-R`** — where to acquire abilities (linked from special pages)
- **`/templates/`** — site CSS and layout images
- **`/images/`** — icons, pet thumbnails, uploads referenced from pet pages
- **`/favicon.ico`**

**Offline search:** The pet list and specials search boxes use POST on the live site. The local server converts those to GET URLs (e.g. `POST /pets` with ability filter → `GET /pets?specials=3`).

Links inside saved HTML are rewritten so navigation stays on `http://127.0.0.1:8765`.

### Not included

These appear in the site navigation but are **outside the pets backup scope**:

- Full `/creatures` browser (only acquire lists linked from specials are mirrored)
- `/research`, `/planner`, `/wiki/`, etc.
- Login (`/login.php`), profiles, forums, external links

Other unmirrored links show a short page with a link back to `/pets`.

---

## All commands

### Main scripts

| Command | Description |
|---------|-------------|
| `./backup.sh` | Download / refresh offline mirror into `./mirror` |
| `./backfill-specials.sh` | Add specials, ability filters, and creature acquire pages |
| `./backfill-assets.sh` | Download creature thumbnails, ranked ability icons, and flags into `./mirror` |
| `./start.sh` | Start local server (offline if `mirror/pets` exists) |
| `./stop.sh` | Stop server on port 8765 (or `SWGPETS_PORT`) |
| `./mirror.sh` | Same as `./backup.sh` |

### Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `SWGPETS_PORT` | `8765` | TCP port for the local server |
| `SWGPETS_HOST` | `127.0.0.1` | Bind address |

Example — custom port:

```bash
SWGPETS_PORT=8080 ./start.sh
SWGPETS_PORT=8080 ./stop.sh
```

### `backup.sh` options

```bash
./backup.sh --help
```

| Option | Default | Description |
|--------|---------|-------------|
| `--prefer auto` | `auto` | Try live site first, then Wayback Machine |
| `--prefer live` | | Live site only |
| `--prefer wayback` | | Wayback Machine only (if live blocks automated access) |
| `--delay 0.35` | `0.35` | Seconds between requests (be polite to the server) |
| `--max-pages 5000` | `5000` | Max HTML pages to crawl |
| `--output ./mirror` | `./mirror` | Output directory |

Examples:

```bash
./backup.sh --prefer wayback          # archive.org only
./backup.sh --delay 0.5               # slower, gentler crawl
```

### `start.sh` / server options

```bash
python3 -m swgpets.server --help
```

| Flag | Description |
|------|-------------|
| `--mirror-only` | Force offline mode (disk only) |
| `--no-cache` | Live proxy mode (internet required) |
| `--host 127.0.0.1` | Listen address |
| `--port 8765` | Listen port |

Examples:

```bash
./start.sh --mirror-only              # explicit offline
./start.sh --no-cache                 # live proxy
python3 -m swgpets.server --port 9000 --mirror-only
```

---

## Project layout

```text
swgPets/
├── backup.sh          # Run full offline backup → ./mirror
├── start.sh           # Start local web server
├── stop.sh            # Stop local web server
├── mirror.sh          # Alias for backup.sh
├── README.md
├── mirror/            # Offline copy (gitignored, ~200+ MB)
│   ├── index.html     # Redirects to /pets
│   ├── pets/          # Pet list pages
│   ├── pet/           # Pet detail pages (e.g. pet/Bantha/index.html)
│   ├── images/        # Icons, thumbnails, uploads
│   └── templates/     # CSS and layout assets
├── cache/             # Legacy proxy cache (gitignored, optional)
└── swgpets/           # Python package
    ├── backup.py      # Crawler / downloader
    ├── server.py      # Local HTTP server
    ├── curl_fetch.py  # curl-based HTTP client
    └── config.py      # Paths, URLs, defaults
```

**Git:** `mirror/` and `cache/` are in `.gitignore`. Commit the scripts; keep the backup on your machine (or back it up separately).

---

## Updating your backup

Run while **www.swgpets.com** (or Wayback) is reachable:

```bash
./backup.sh
```

The crawler:

1. Starts from `/pets` and A–Z letter pages
2. Follows every `/pets` and `/pet/*` link it finds in saved HTML
3. Downloads referenced images and CSS
4. Skips files that already exist locally

There is no automatic schedule — re-run `./backup.sh` whenever you want a fresher snapshot.

---

## Troubleshooting

### “Not found in local mirror” (404)

**Use the pet list URL:**

```text
http://127.0.0.1:8765/pets
```

not only `http://127.0.0.1:8765/`.

**Common 404 causes:**

| URL | Why |
|-----|-----|
| `/creatures`, `/specials`, `/wiki/` | Not part of the pets backup |
| `/login.php` | Not mirrored |
| A pet name with odd encoding | Server tries `+`, space, and `_` variants; re-run `./backup.sh` if that pet was never downloaded |
| `/pets?sort1=...&specials=N` after ability search | **Restart the server** after updating code: `./stop.sh && ./start.sh`. The mirror stores filters as `/pets?specials=N` only. Run `./verify-filters.sh` to confirm all 28 abilities resolve. |

### Ability search shows “Not in offline backup” for Charge (or other abilities)

The filtered page **is** on disk (`mirror/pets/specials_N/`). The search form sends extra sort/show parameters; the server maps those to the mirrored filter URL.

1. Restart so you pick up the latest server code:

```bash
./stop.sh && ./start.sh
```

2. Verify every ability filter is present:

```bash
./verify-filters.sh
```

3. If any are missing, refresh from the live site:

```bash
./refresh-filters.sh
```

Some abilities (Provoke, Deflective Hide, Paralytic Poison, Preparation, Resource Scavenger) have **few pets** — their pages are much smaller than Charge but still valid.


```bash
./stop.sh
./start.sh
```

If that fails:

```bash
lsof -ti tcp:8765 | xargs kill -9
./start.sh
```

### Backup fails or many “skip page” lines

- Check internet access to `https://www.swgpets.com`
- Try Wayback: `./backup.sh --prefer wayback`
- Corporate proxy: scripts unset `HTTP_PROXY` for `curl`; ensure `curl` works:  
  `curl -I https://www.swgpets.com/pets`

### Images or CSS missing

Re-run a full backup:

```bash
./backup.sh
```

Creature acquire pages (`/creatures?specials=N-R`) often load **without icons** until assets are backfilled:

```bash
./backfill-assets.sh
```

Then restart the server.

### Creature acquire page has no creature thumbnails or ability icons

The HTML was mirrored but images under `/images/swgpets/` and ranked icons like `bm_defensive5.png` were not. Run:

```bash
./backfill-assets.sh
```

This scans all mirrored HTML and downloads missing PNG/CSS/JS into `./mirror/images/`.

### Am I hitting the live site or my disk?

Read the terminal when you run `./start.sh`:

- **Disk:** `offline mode`, `Serving static backup from ./mirror`
- **Live:** `Live proxy mode (needs network)`

Offline mode **never** contacts swgpets.com, even on 404.

### `wget` not used

Downloads use **Python + curl** (Homebrew `wget` is not required).

---

## Advanced options

### Run backup and server without shell wrappers

```bash
cd ~/git/swgPets
python3 -m swgpets.backup --output ./mirror
python3 -m swgpets.server --mirror-only --port 8765
```

### Serve mirror with another tool

The `mirror/` tree is plain static files. Any static server works, but paths like `/pet/Bantha` expect directory indexes or rewrite rules. The included `swgpets.server` handles SWG Pets URL quirks (query strings, `+` in names).

### Disk space

A full pets backup is typically **~200–300 MB** and **~2,500+ files**. Ensure you have space before running `./backup.sh`.

---

## Legacy / optional tools

These were part of an earlier **live proxy + cache** workflow. You do not need them for offline browsing.

| Script | Purpose |
|--------|---------|
| `./sync.sh` | Sync a fixed list of paths into `./cache` |
| `./sync-curl.sh` | Same, using curl |
| `./prefetch.sh` | Pull images/CSS from already-cached HTML |
| `python3 -m swgpets.mirror` | Older crawler (use `./backup.sh` instead) |

For a durable offline copy, use **`./backup.sh`** and **`./start.sh`** only.

---

## Quick reference

```bash
# One-time (or when refreshing)
./backup.sh

# Browse offline
./start.sh
# → http://127.0.0.1:8765/pets

# Stop
./stop.sh
```

**Offline = files in `mirror/` on your disk. Live site = only when running `./backup.sh` or `./start.sh --no-cache`.**
