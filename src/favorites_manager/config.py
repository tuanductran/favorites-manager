"""Let the user add URLs manually to a JSON file (config.json), which the
program reads and merges into the bookmark tree before exporting.

config.json format:

    {
      "bookmarks": [
        {
          "url": "https://example.com",
          "title": "Example",
          "folder": "Dev Tools/APIs",
          "add_date": "1737000000"
        }
      ]
    }

- "folder": a "/"-separated folder path. If omitted, the bookmark is added
  to the root folder. Folders that don't exist yet are created automatically.
- "add_date": optional, epoch seconds (Netscape-style). Leave it out if not
  needed — the browser will assign one on import.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from .models import Bookmark, Folder

_FOLDER_SEP = "/"


@dataclass
class ManualEntry:
    url: str
    title: str
    folder: tuple[str, ...] = ()
    add_date: str | None = None
    tags: tuple[str, ...] = ()
    description: str | None = None

    @staticmethod
    def from_dict(d: dict) -> "ManualEntry":
        url = d["url"]
        title = d.get("title") or url
        raw_folder = d.get("folder") or ""
        folder = tuple(p.strip() for p in raw_folder.split(_FOLDER_SEP) if p.strip())
        add_date = str(d["add_date"]) if d.get("add_date") else None
        tags_raw = d.get("tags") or []
        tags = tuple(str(t).strip() for t in tags_raw if str(t).strip())
        description = d.get("description") or None
        return ManualEntry(
            url=url, title=title, folder=folder, add_date=add_date,
            tags=tags, description=description,
        )

    def to_dict(self) -> dict:
        d: dict = {"url": self.url, "title": self.title}
        if self.folder:
            d["folder"] = _FOLDER_SEP.join(self.folder)
        if self.add_date:
            d["add_date"] = self.add_date
        if self.tags:
            d["tags"] = list(self.tags)
        if self.description:
            d["description"] = self.description
        return d


def load_config(path: str | Path) -> list[ManualEntry]:
    p = Path(path)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8") or "{}")
    return [ManualEntry.from_dict(item) for item in data.get("bookmarks", [])]


def save_config(path: str | Path, entries: list[ManualEntry]) -> None:
    data = {"bookmarks": [e.to_dict() for e in entries]}
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def add_entry(
    path: str | Path,
    url: str,
    title: str | None = None,
    folder: str = "",
    tags: str = "",
    description: str | None = None,
) -> ManualEntry:
    """Add a URL to config.json (creating the file if needed), saving immediately."""
    entries = load_config(path)
    entry = ManualEntry(
        url=url,
        title=title or url,
        folder=tuple(p.strip() for p in folder.split(_FOLDER_SEP) if p.strip()),
        add_date=str(int(time.time())),
        tags=tuple(t.strip() for t in tags.split(",") if t.strip()),
        description=description or None,
    )
    entries.append(entry)
    save_config(path, entries)
    return entry


def _get_or_create_folder(root: Folder, path: tuple[str, ...]) -> Folder:
    current = root
    for name in path:
        match = next((f for f in current.subfolders if f.name == name), None)
        if match is None:
            match = Folder(name=name)
            current.subfolders.append(match)
        current = match
    return current


def apply_entries(root: Folder, entries: list[ManualEntry]) -> int:
    """Insert ManualEntry items into the `root` tree (in-place). Returns the count added."""
    for entry in entries:
        target = _get_or_create_folder(root, entry.folder)
        target.bookmarks.append(
            Bookmark(
                title=entry.title,
                url=entry.url,
                add_date=entry.add_date,
                tags=entry.tags,
                description=entry.description,
            )
        )
    return len(entries)
