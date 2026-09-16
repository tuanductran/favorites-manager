"""Core data structures for bookmarks/folders, shared by the parser, dedupe,
and writer modules."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlsplit, urlunsplit


@dataclass
class Bookmark:
    """A single bookmark (link)."""

    title: str
    url: str
    add_date: Optional[str] = None
    last_modified: Optional[str] = None
    icon: Optional[str] = None
    icon_uri: Optional[str] = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    description: Optional[str] = None
    folder_path: tuple[str, ...] = field(default_factory=tuple)

    @property
    def normalized_url(self) -> str:
        """Normalized URL used for duplicate comparison.

        - strips surrounding whitespace
        - lowercases scheme/host
        - drops a trailing "/" on the path (treating "" and "/" as equal)
        - drops the fragment (#...)
        - keeps the query string (it can carry distinct meaning)
        """
        raw = self.url.strip()
        parts = urlsplit(raw)
        scheme = parts.scheme.lower()
        netloc = parts.netloc.lower()
        path = parts.path
        if path in ("", "/"):
            path = ""
        elif path.endswith("/"):
            path = path[:-1]
        return urlunsplit((scheme, netloc, path, parts.query, ""))


@dataclass
class Folder:
    """A folder, which may contain child bookmarks and child folders (recursively)."""

    name: str
    add_date: Optional[str] = None
    last_modified: Optional[str] = None
    personal_toolbar: bool = False
    bookmarks: list[Bookmark] = field(default_factory=list)
    subfolders: list["Folder"] = field(default_factory=list)

    def walk_bookmarks(self):
        """Recursively yield every bookmark in this folder and its subfolders."""
        for bm in self.bookmarks:
            yield bm
        for sub in self.subfolders:
            yield from sub.walk_bookmarks()

    def walk_folders(self):
        """Recursively yield every folder (including this one)."""
        yield self
        for sub in self.subfolders:
            yield from sub.walk_folders()

    def count_bookmarks(self) -> int:
        return sum(1 for _ in self.walk_bookmarks())
