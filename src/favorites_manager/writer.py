"""Write a Folder/Bookmark tree back out as a standard Netscape Bookmark
HTML file, importable into Chrome, Edge, Firefox, Brave, Coc Coc, Safari, ..."""
from __future__ import annotations

from html import escape
from pathlib import Path

from .models import Folder

_HEADER = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
<!-- This is an automatically generated file.
     It will be read and overwritten.
     DO NOT EDIT! -->
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks</H1>
"""


def write_file(root: Folder, path: str | Path) -> None:
    Path(path).write_text(to_html(root), encoding="utf-8")


def to_html(root: Folder) -> str:
    lines = [_HEADER.rstrip("\n"), "<DL><p>"]
    _write_dl(root, lines, indent=1)
    lines.append("</DL><p>")
    return "\n".join(lines) + "\n"


def _write_dl(folder: Folder, lines: list[str], indent: int) -> None:
    pad = "    " * indent
    for sub in folder.subfolders:
        attrs = []
        if sub.add_date:
            attrs.append(f'ADD_DATE="{escape(sub.add_date, quote=True)}"')
        attrs.append(f'LAST_MODIFIED="{escape(sub.last_modified or "0", quote=True)}"')
        if sub.personal_toolbar:
            attrs.append('PERSONAL_TOOLBAR_FOLDER="true"')
        lines.append(f'{pad}<DT><H3 {" ".join(attrs)}>{escape(sub.name)}</H3>')
        lines.append(f"{pad}<DL><p>")
        _write_dl(sub, lines, indent + 1)
        lines.append(f"{pad}</DL><p>")

    for bm in folder.bookmarks:
        attrs = []
        if bm.add_date:
            attrs.append(f'ADD_DATE="{escape(bm.add_date, quote=True)}"')
        if bm.last_modified:
            attrs.append(f'LAST_MODIFIED="{escape(bm.last_modified, quote=True)}"')
        attrs.append(f'HREF="{escape(bm.url, quote=True)}"')
        if bm.icon_uri:
            attrs.append(f'ICON_URI="{escape(bm.icon_uri, quote=True)}"')
        if bm.icon:
            attrs.append(f'ICON="{escape(bm.icon, quote=True)}"')
        if bm.tags:
            attrs.append(f'TAGS="{escape(",".join(bm.tags), quote=True)}"')
        lines.append(f'{pad}<DT><A {" ".join(attrs)}>{escape(bm.title)}</A>')
        if bm.description:
            lines.append(f"{pad}<DD>{escape(bm.description)}")
