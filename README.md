# favorites-manager

A 100% Python tool (no Node/PHP required) for managing **favorites/bookmarks**
exported from multiple browsers (Chrome, Edge, Firefox, Coc Coc, Brave,
Safari...) in the **Netscape Bookmark HTML** format — the standard format
every browser supports for both *export* and *re-import*.

## Features

- **Read** a `bookmarks.html` file (even a malformed/non-standard one — it
  self-normalizes the unclosed `<DT>`/`<DD>` structure).
- Preserves **notes (`<DD>`)** and **ICON_URI** (Firefox) when reading and
  writing back — no silent data loss like many other tools that only read
  `HREF`. Also reads/writes the `TAGS=` attribute if the source file has it
  (from services like del.icio.us or other tools) — note: Chrome and
  Firefox do **not** themselves write or read `TAGS=` on HTML import/export
  (verified directly in both browsers' source code, see "References"
  below), so this is purely data preservation for compatibility with other
  tools, not a "tag" feature Chrome/Firefox will display after import.
- **Merge** multiple files from multiple browsers into one bookmark tree.
- **Find & remove duplicates** by normalized URL (strips trailing `/`,
  fragment `#...`, case-insensitive scheme & host); when duplicates are
  found, the copy with the earliest `ADD_DATE` is kept.
- **Auto-organize into folders** by domain (e.g. all `github.com` links
  grouped into one folder).
- **Manually add URLs** via a `config.json` file (edit by hand or via the
  `add-url` command), supporting `folder`, `tags`, and `description`.
- **Check for broken links** (404, connection errors, timeouts...) running
  concurrently via a thread pool, with a JSON report and an option to
  auto-remove dead links.
- **Export one HTML file per browser** (Chrome/Edge/Firefox/Safari/Brave/
  Coc Coc) with the correct name/flag for each browser's "bookmarks bar"
  folder, so importing doesn't conflict or create an "Imported (date)"
  folder.

## Installation (using `uv`)

```bash
uv venv
uv pip install -e .
```

Requires Python **3.9+**. Dependencies: `beautifulsoup4`, `lxml`, `click`,
`rich`, `requests` (all pure Python, no complex native builds needed).

## Usage (CLI: `favorites`)

```bash
# Quick stats (bookmark count, folder count, duplicate count) for one or more files
favorites stats chrome.html firefox.html

# List duplicate groups in detail, without modifying a file
favorites list-duplicates chrome.html

# Merge multiple files + remove duplicates -> write a new file, re-import into a browser
favorites dedupe chrome.html firefox.html -o merged_clean.html

# Merge multiple files, keeping the original folder structure (no dedupe)
favorites merge chrome.html firefox.html -o merged.html

# Merge + remove duplicates + auto-organize into folders by domain
favorites organize chrome.html firefox.html -o organized.html \
    --min-group-size 3

# Print the existing folder tree for a file
favorites list-folders chrome.html
```

### Manually adding URLs via `config.json`

No code changes needed — just add a URL to `config.json` and let the
program read and merge it in at build time. There are two ways to add one:

**1. Edit the JSON file by hand** (create `config.json` if it doesn't exist yet):

```json
{
  "bookmarks": [
    { "url": "https://claude.ai", "title": "Claude", "folder": "AI Tools" },
    { "url": "https://github.com/tuanductran", "title": "My GitHub", "folder": "Dev/Profile" }
  ]
}
```

`folder` uses `/` to express nesting; leave it out or empty to add to the
root. Folders that don't exist yet are created automatically at build time.

**2. Use the CLI command** (writes to config.json for you, no need to open the file):

```bash
favorites add-url "https://claude.ai" --title "Claude" --folder "AI Tools" --config config.json
favorites add-url "https://github.com/tuanductran" --title "My GitHub" --folder "Dev/Profile" --config config.json
```

### Building per-browser output (avoiding import conflicts)

Every browser recognizes its "bookmarks bar" through the
`PERSONAL_TOOLBAR_FOLDER="true"` attribute rather than by name — but the
displayed name and merge behavior differ between browsers
(Chrome/Edge/Brave/Coc Coc call it "Bookmarks bar"/"Favorites bar", Firefox
calls it "Bookmarks Toolbar", Safari calls it "Favorites"). Importing one
shared file often makes the browser create an extra "Imported (date)"
folder instead of merging straight into the existing toolbar.

The `build` command handles this: it reads the source file(s) +
`config.json`, merges, removes duplicates, then exports **one HTML file per
browser**, each with the correct toolbar-folder name for that browser:

```bash
favorites build \
    -i chrome.html -i firefox.html \
    --config config.json \
    -o dist \
    --browsers chrome,firefox,edge,safari

# add --organize --min-group-size 3 if you also want domain-based organization
```

Result: `dist/chrome.html`, `dist/firefox.html`, `dist/edge.html`,
`dist/safari.html` — import the matching file into its target browser.

### Checking for broken links

```bash
# Just view the report, don't modify the file
favorites check-links bookmarks.html --workers 15 --timeout 8 --report dead-links.json

# Check and auto-remove broken links, writing the result to a new file
favorites check-links bookmarks.html --remove-broken -o cleaned.html
```

Mechanism: try `HEAD` first (lightweight); if the server doesn't support it
(405) or errors, fall back to `GET`; runs concurrently via a
`ThreadPoolExecutor` (10 threads by default) so it doesn't take hours on a
file with hundreds/thousands of bookmarks. **Known limitation** (shared by
any HTTP-status-based link checker): some sites block bots
(Cloudflare/Akamai) and may report an error even though the page is alive,
and SPA-style pages (client-side rendered) can return `200` even though the
actual content is gone — so treat the report as a lead for manual review,
not something to trust 100%.

## Using it as a Python library

```python
from favorites_manager.parser import parse_file
from favorites_manager.dedupe import remove_duplicates
from favorites_manager.organize import organize_by_domain
from favorites_manager.writer import write_file

root = parse_file("bookmarks.html")
remove_duplicates(root)
organized = organize_by_domain(root, min_group_size=3)
write_file(organized, "organized.html")
```

## Project structure

```
favorites-manager/
├── pyproject.toml
├── README.md
├── config.json          # example config: 493 bookmarks converted from a real export
├── src/favorites_manager/
│   ├── models.py     # Bookmark, Folder (dataclasses)
│   ├── parser.py      # parses Netscape Bookmark HTML -> a Folder tree
│   ├── writer.py       # writes a Folder tree -> Netscape Bookmark HTML
│   ├── dedupe.py       # find/remove duplicates, remove empty folders
│   ├── organize.py     # merge multiple sources, organize by domain
│   ├── config.py        # read/write config.json (manually-added URLs)
│   ├── browsers.py      # per-browser export
│   ├── linkcheck.py     # broken-link checking (concurrent)
│   └── cli.py            # CLI (click)
└── tests/
    └── test_roundtrip.py
```

## Technical notes

Netscape Bookmark files never close the `<DT>`/`<DD>` tags (much like `<li>`
inside a `<ul>`), so `BeautifulSoup` (html.parser) will nest the DOM tree
incorrectly by default. `parser.py` runs a pre-processing pass with a stack
to insert `</dt>`/`</dd>` at the right place (based on `<DL>`/`</DL>`
nesting, which is already balanced in the source file) before parsing.

## Audit history / bugs fixed

- **Multiple `PERSONAL_TOOLBAR_FOLDER="true"` when merging sources**: when
  `build` merges 2+ files (each with its own browser-specific toolbar
  folder), the per-browser build used to rename only the FIRST toolbar
  folder it found, leaving the others still flagged `true` — so the target
  browser has no defined choice of toolbar folder. Fixed in `browsers.py`
  to always clear the flag on every folder first, then set it on exactly
  one.
- **Lost `tags`/`description` when deduping**: a removed duplicate could
  carry tags/notes the kept copy didn't have. `dedupe.py` now merges
  (unions) tags and backfills a missing `description` from the removed
  copies before deleting them.
- **Connection leak in check-links**: the GET fallback branch
  (`stream=True`) used to never close the response, which could exhaust
  the connection pool when scanning many URLs that don't support HEAD.
  Fixed by wrapping it in a context manager (`with ... as resp`) so the
  connection is always closed.
- **`favorites build` running silently with no input**: added a check that
  requires at least one `-i/--input` or `--config`.
- Actually tested on Python **3.9.25** (not just 3.11) to confirm modern
  type-hint syntax (`str | None`, `tuple[str, ...]`) works correctly thanks
  to `from __future__ import annotations` in every module.

## References (cross-checked directly against browser source code)

Rather than relying only on third-party blog posts, the format assumptions
here were cross-checked directly against the open-source code of Chromium
and Firefox:

- **Chromium** — `chrome/browser/bookmarks/bookmark_html_writer.cc`
  ([chromium.googlesource.com](https://chromium.googlesource.com/chromium/src/+/lkgr/chrome/browser/bookmarks/bookmark_html_writer.cc)):
  confirms the file header matches `writer.py` exactly; confirms
  `PERSONAL_TOOLBAR_FOLDER="true"` is written by Chrome only for the
  Bookmarks Bar folder (it never writes `TAGS`/`ICON_URI`); confirms "Other
  bookmarks" and "Mobile bookmarks" content is exported by Chrome **flat at
  the root level**, not wrapped in their own folder — matching how
  `parser.py` handles bookmarks that sit directly at the root.
- **Firefox** — `toolkit/components/places/BookmarkHTMLUtils.sys.mjs`
  ([searchfox.org](https://searchfox.org/firefox-main/source/toolkit/components/places/BookmarkHTMLUtils.sys.mjs)):
  confirms `<DD>` is a note attached to the `<A>` bookmark immediately
  preceding it (matches the logic `parser.py` uses); confirms `ICON_URI` is
  a Firefox-specific attribute; confirms Firefox does **not** read `TAGS=`
  on HTML import (the imported attribute list is `HREF`, `ICON`,
  `ICON_URI`, `LAST_CHARSET` — no `TAGS`); confirms the "a new folder
  implicitly closes the previous sibling folder when the next `<H3>`
  appears" mechanism matches exactly how `parser.py` normalizes the file
  using a stack.
