"""Merge bookmarks from multiple browsers and organize them by domain into folders."""
from __future__ import annotations

from collections import defaultdict
from urllib.parse import urlsplit

from .models import Bookmark, Folder


def merge_folders(folders: list[Folder], names: list[str] | None = None) -> Folder:
    """Merge multiple Folder trees (from different files/browsers) into one
    tree, with each source kept under its own subfolder so it's clear where
    each bookmark came from."""
    root = Folder(name="root")
    for i, folder in enumerate(folders):
        label = names[i] if names and i < len(names) else f"Source {i + 1}"
        wrapper = Folder(name=label)
        wrapper.bookmarks = list(folder.bookmarks)
        wrapper.subfolders = list(folder.subfolders)
        root.subfolders.append(wrapper)
    return root


def _domain_of(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or "(other)"


def organize_by_domain(root: Folder, min_group_size: int = 2) -> Folder:
    """Return a NEW tree: every bookmark (walked recursively from `root`) is
    grouped into a folder by domain. Domains with fewer than
    `min_group_size` bookmarks are lumped together into a "Misc" folder."""
    by_domain: dict[str, list[Bookmark]] = defaultdict(list)
    for bm in root.walk_bookmarks():
        by_domain[_domain_of(bm.url)].append(bm)

    new_root = Folder(name="root")
    misc = Folder(name="Misc")
    for domain, items in sorted(by_domain.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if len(items) >= min_group_size:
            new_root.subfolders.append(Folder(name=domain, bookmarks=list(items)))
        else:
            misc.bookmarks.extend(items)
    if misc.bookmarks:
        new_root.subfolders.append(misc)
    return new_root
