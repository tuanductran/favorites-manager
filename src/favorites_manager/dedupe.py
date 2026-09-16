"""Find & remove duplicate bookmarks in a Folder tree, based on normalized URL.

Which copy is kept when duplicates are found:
    - Prefer the bookmark with the earlier ADD_DATE (added first = the
      original).
    - If there's no ADD_DATE, keep whichever copy is encountered first
      while walking the tree (parent folder -> child folders, left to right).
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import Bookmark, Folder


@dataclass
class DuplicateGroup:
    normalized_url: str
    kept: Bookmark
    removed: list[Bookmark]


def _add_date_key(bm: Bookmark) -> int:
    try:
        return int(bm.add_date) if bm.add_date else 2**63 - 1
    except ValueError:
        return 2**63 - 1


def find_duplicates(root: Folder) -> list[DuplicateGroup]:
    """Group bookmarks that share the same normalized_url, without mutating the tree."""
    groups: dict[str, list[Bookmark]] = {}
    for bm in root.walk_bookmarks():
        groups.setdefault(bm.normalized_url, []).append(bm)

    result = []
    for url, items in groups.items():
        if len(items) <= 1:
            continue
        items_sorted = sorted(items, key=_add_date_key)
        kept, *removed = items_sorted
        result.append(DuplicateGroup(normalized_url=url, kept=kept, removed=removed))
    return result


def remove_duplicates(root: Folder) -> int:
    """Remove duplicate bookmarks directly on the `root` tree (in-place).

    Before removing, MERGE `tags`/`description` from the removed copies
    into the kept copy (if the kept copy is missing them), so data the user
    attached to a duplicate isn't silently lost.

    Returns the number of bookmarks removed.
    """
    duplicate_groups = find_duplicates(root)
    to_remove_ids = set()
    for group in duplicate_groups:
        merged_tags = list(group.kept.tags)
        for bm in group.removed:
            to_remove_ids.add(id(bm))
            for t in bm.tags:
                if t not in merged_tags:
                    merged_tags.append(t)
            if not group.kept.description and bm.description:
                group.kept.description = bm.description
        group.kept.tags = tuple(merged_tags)

    removed_count = 0

    def _clean(folder: Folder) -> None:
        nonlocal removed_count
        kept_bookmarks = []
        for bm in folder.bookmarks:
            if id(bm) in to_remove_ids:
                removed_count += 1
            else:
                kept_bookmarks.append(bm)
        folder.bookmarks = kept_bookmarks
        for sub in folder.subfolders:
            _clean(sub)

    _clean(root)
    return removed_count


def remove_empty_folders(root: Folder) -> int:
    """Recursively remove empty folders (no bookmarks, no subfolders).
    Returns the number of folders removed. Never removes the `root` object
    itself, even if it ends up empty."""
    removed_count = 0

    def _clean(folder: Folder) -> None:
        nonlocal removed_count
        kept = []
        for sub in folder.subfolders:
            _clean(sub)
            if sub.bookmarks or sub.subfolders:
                kept.append(sub)
            else:
                removed_count += 1
        folder.subfolders = kept

    _clean(root)
    return removed_count
