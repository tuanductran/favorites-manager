"""Each browser calls its "bookmarks bar" folder something different, and it
only ever RECOGNIZES it via the PERSONAL_TOOLBAR_FOLDER="true" attribute on
the <H3> tag (never by folder name). If you export one HTML file shared
across browsers:

- The displayed folder name can look odd (e.g. Firefox seeing Chrome's
  "Bookmarks bar" folder nested inside "Bookmarks Menu" instead of on the
  toolbar).
- Re-importing into the same browser repeatedly tends to create duplicate
  "Imported (date)" folders instead of merging straight into the toolbar.

`build_for_browser()` produces a copy of the bookmark tree with the correct
"toolbar folder" renamed and flagged per that browser's convention, so an
import into that specific browser stays as clean as possible and avoids
duplication/conflicts.

Naming conventions (per common documentation & observed behavior):
- Chrome / Edge / Brave / Coc Coc (Chromium-based): "Bookmarks bar"
  (Edge/IE calls it "Favorites bar" but still recognizes
  PERSONAL_TOOLBAR_FOLDER).
- Firefox: "Bookmarks Toolbar" (the toolbar) and "Bookmarks Menu" (the menu).
- Safari: "Favorites".
"""
from __future__ import annotations

import copy
from dataclasses import dataclass

from .models import Folder

BROWSERS = ("chrome", "edge", "brave", "coccoc", "firefox", "safari")


@dataclass
class BrowserProfile:
    key: str
    display_name: str
    toolbar_folder_name: str


PROFILES: dict[str, BrowserProfile] = {
    "chrome": BrowserProfile("chrome", "Google Chrome", "Bookmarks bar"),
    "edge": BrowserProfile("edge", "Microsoft Edge", "Favorites bar"),
    "brave": BrowserProfile("brave", "Brave", "Bookmarks bar"),
    "coccoc": BrowserProfile("coccoc", "Coc Coc", "Bookmarks bar"),
    "firefox": BrowserProfile("firefox", "Mozilla Firefox", "Bookmarks Toolbar"),
    "safari": BrowserProfile("safari", "Safari", "Favorites"),
}


def _find_toolbar_folder(root: Folder) -> Folder | None:
    for f in root.walk_folders():
        if f.personal_toolbar:
            return f
    return None


def build_for_browser(root: Folder, browser: str) -> Folder:
    """Return a CLONE of `root`, renamed and flagged for `browser`'s toolbar
    folder convention. Never mutates `root` itself.

    Note: if `root` was merged from MULTIPLE sources (multiple browsers),
    there may be SEVERAL folders carrying personal_toolbar=True (one per
    source) — exporting a file with more than one
    PERSONAL_TOOLBAR_FOLDER="true" leaves the target browser's choice of
    toolbar folder undefined. So we always clear the flag on EVERY folder
    first, then set it back on exactly one.
    """
    if browser not in PROFILES:
        raise ValueError(f"Unsupported browser: {browser!r}. Choose one of {BROWSERS}")
    profile = PROFILES[browser]
    clone = copy.deepcopy(root)

    for f in clone.walk_folders():
        f.personal_toolbar = False

    toolbar = _find_toolbar_folder(root)  # locate on the original tree first, to get the first match in traversal order
    if toolbar is not None:
        # map it to the corresponding folder in `clone` by walking both trees in lockstep
        toolbar = next(
            (f for f, orig in zip(clone.walk_folders(), root.walk_folders()) if orig is toolbar),
            None,
        )
    if toolbar is None:
        # No folder in the source was flagged as the toolbar folder -> fall
        # back to the first top-level folder (if any), so everything
        # doesn't end up dumped into "Other bookmarks"/"Imported".
        toolbar = clone.subfolders[0] if clone.subfolders else None

    if toolbar is not None:
        toolbar.personal_toolbar = True
        toolbar.name = profile.toolbar_folder_name

    return clone


def build_all(root: Folder, browsers: list[str] | None = None) -> dict[str, Folder]:
    targets = browsers or list(BROWSERS)
    return {b: build_for_browser(root, b) for b in targets}
