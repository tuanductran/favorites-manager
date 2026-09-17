"""Parse a Netscape Bookmark HTML file (the format exported by Chrome, Edge,
Firefox, Coc Coc, Brave, ...) into a Folder/Bookmark tree.

Rough shape of the source file:

    <DL><p>
        <DT><H3 ...>Folder name</H3>
        <DL><p>
            <DT><A HREF="...">Bookmark name</A>
            <DT><H3 ...>Subfolder</H3>
            <DL><p> ... </DL><p>
        </DL><p>
    </DL><p>

This isn't valid XHTML (tags are never closed), so we use BeautifulSoup with
the pure-Python "html.parser" backend, which repairs the DOM tree the same
way a browser would (no lxml dependency required — html.parser is fine for
this format and avoids pulling in a much larger native-code dependency).
"""
from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from .models import Bookmark, Folder

# Netscape Bookmark files never close <DT>/<DD> (much like <li>): browsers
# auto-close the currently open item whenever a new <DT>/<DD> appears, OR
# when the enclosing <DL> is closed — but a <DT> can still "contain" a
# nested <DL> (a subfolder). BeautifulSoup's html.parser doesn't know this
# rule, so we pre-process the text with a stack to insert the right closing
# tag at the right place, based on <DL>/</DL> nesting depth (which is
# already balanced in the source file).
_TOKEN_RE = re.compile(r"(?i)<DL>|</DL>|<DT>|<DD>")


def _normalize_netscape_html(html: str) -> str:
    out: list[str] = []
    # stack entries: ("dl",) or ("item", "dt"|"dd")
    stack: list[tuple] = []
    pos = 0
    for m in _TOKEN_RE.finditer(html):
        out.append(html[pos:m.start()])
        token = m.group(0).upper()
        if token in ("<DT>", "<DD>"):
            tag = "dt" if token == "<DT>" else "dd"
            if stack and stack[-1][0] == "item":
                out.append(f"</{stack[-1][1]}>")
                stack.pop()
            out.append(f"<{tag}>")
            stack.append(("item", tag))
        elif token == "<DL>":
            out.append("<dl>")
            stack.append(("dl",))
        elif token == "</DL>":
            if stack and stack[-1][0] == "item":
                out.append(f"</{stack[-1][1]}>")
                stack.pop()
            if stack and stack[-1][0] == "dl":
                stack.pop()
            out.append("</dl>")
        pos = m.end()
    out.append(html[pos:])
    return "".join(out)


def parse_file(path: str | Path) -> Folder:
    """Read a single bookmark HTML file and return the root Folder ("root")."""
    html = Path(path).read_text(encoding="utf-8", errors="replace")
    return parse_html(html)


def parse_html(html: str) -> Folder:
    html = _normalize_netscape_html(html)
    soup = BeautifulSoup(html, "html.parser")
    root = Folder(name="root")

    # Every bookmark/folder lives inside the top-level <DL>.
    top_dl = soup.find("dl")
    if top_dl is not None:
        _parse_dl(top_dl, root)
    return root


def _parse_dl(dl: Tag, parent: Folder) -> None:
    """Walk the direct <DT> children of a <DL>, filling in `parent`.

    Note: after normalization, nested <DL>s (containing a folder's
    children) end up as siblings of the <p> wrapper, but the folder's own
    <DL> is a child of the corresponding <dt>. Direct <dt> children may sit
    under an auto-inserted <p> wrapper, so check for that first.
    """
    container = dl.find("p", recursive=False) or dl
    for dt in container.find_all("dt", recursive=False):
        h3 = dt.find("h3", recursive=False)
        a = dt.find("a", recursive=False)

        if h3 is not None:
            folder = Folder(
                name=h3.get_text(strip=True) or "(untitled)",
                add_date=h3.get("add_date"),
                last_modified=h3.get("last_modified"),
                personal_toolbar=(h3.get("personal_toolbar_folder") == "true"),
            )
            parent.subfolders.append(folder)
            # After normalization, the child <DL> is nested inside this
            # same <dt> (try a sibling too, in case some exporter differs).
            child_dl = dt.find("dl", recursive=False) or dt.find_next_sibling("dl")
            if child_dl is not None:
                _parse_dl(child_dl, folder)

        elif a is not None:
            href = a.get("href")
            if not href:
                continue
            tags_raw = a.get("tags") or ""
            tags = tuple(t.strip() for t in tags_raw.split(",") if t.strip())

            # A <DD> note/description sits right after <DT><A>...</A>, as a
            # sibling <dt>/<dd> pair after normalization. Only attach it if
            # it really belongs to this bookmark, i.e. it directly follows
            # this <dt> with no other <dt> in between.
            description = None
            next_dd = dt.find_next_sibling("dd")
            if next_dd is not None and next_dd.find_previous_sibling("dt") is dt:
                text = next_dd.get_text(strip=True)
                description = text or None

            bookmark = Bookmark(
                title=a.get_text(strip=True) or href,
                url=href,
                add_date=a.get("add_date"),
                last_modified=a.get("last_modified"),
                icon=a.get("icon"),
                icon_uri=a.get("icon_uri"),
                tags=tags,
                description=description,
            )
            parent.bookmarks.append(bookmark)
