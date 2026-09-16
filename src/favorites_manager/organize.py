"""Gộp bookmark từ nhiều trình duyệt và phân loại theo domain thành folder."""
from __future__ import annotations

from collections import defaultdict
from urllib.parse import urlsplit

from .models import Bookmark, Folder


def merge_folders(folders: list[Folder], names: list[str] | None = None) -> Folder:
    """Gộp nhiều cây Folder (từ nhiều file/trình duyệt khác nhau) thành 1 cây,
    mỗi nguồn nằm trong 1 folder con để biết bookmark đến từ đâu."""
    root = Folder(name="root")
    for i, folder in enumerate(folders):
        label = names[i] if names and i < len(names) else f"Nguồn {i + 1}"
        wrapper = Folder(name=label)
        wrapper.bookmarks = list(folder.bookmarks)
        wrapper.subfolders = list(folder.subfolders)
        root.subfolders.append(wrapper)
    return root


def _domain_of(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or "(khác)"


def organize_by_domain(root: Folder, min_group_size: int = 2) -> Folder:
    """Trả về 1 cây MỚI: toàn bộ bookmark (duyệt đệ quy từ `root`) được gom
    vào folder theo domain. Domain có ít hơn `min_group_size` bookmark sẽ bị
    gom chung vào folder "Khác"."""
    by_domain: dict[str, list[Bookmark]] = defaultdict(list)
    for bm in root.walk_bookmarks():
        by_domain[_domain_of(bm.url)].append(bm)

    new_root = Folder(name="root")
    misc = Folder(name="Khác")
    for domain, items in sorted(by_domain.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if len(items) >= min_group_size:
            new_root.subfolders.append(Folder(name=domain, bookmarks=list(items)))
        else:
            misc.bookmarks.extend(items)
    if misc.bookmarks:
        new_root.subfolders.append(misc)
    return new_root
