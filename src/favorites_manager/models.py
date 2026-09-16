"""Cấu trúc dữ liệu cho bookmark/folder, dùng chung cho parser, dedupe, writer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlsplit, urlunsplit


@dataclass
class Bookmark:
    """Một bookmark (link) đơn lẻ."""

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
        """URL đã chuẩn hoá để so sánh trùng lặp.

        - bỏ khoảng trắng thừa
        - hạ thường scheme/host
        - bỏ dấu "/" cuối path (nếu path không rỗng)
        - bỏ fragment (#...)
        - giữ nguyên query string (vì có thể mang ý nghĩa khác nhau)
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
    """Một folder, có thể chứa bookmark con và folder con (đệ quy)."""

    name: str
    add_date: Optional[str] = None
    last_modified: Optional[str] = None
    personal_toolbar: bool = False
    bookmarks: list[Bookmark] = field(default_factory=list)
    subfolders: list["Folder"] = field(default_factory=list)

    def walk_bookmarks(self):
        """Duyệt đệ quy toàn bộ bookmark trong folder này và các folder con."""
        for bm in self.bookmarks:
            yield bm
        for sub in self.subfolders:
            yield from sub.walk_bookmarks()

    def walk_folders(self):
        """Duyệt đệ quy toàn bộ folder (bao gồm chính nó)."""
        yield self
        for sub in self.subfolders:
            yield from sub.walk_folders()

    def count_bookmarks(self) -> int:
        return sum(1 for _ in self.walk_bookmarks())
