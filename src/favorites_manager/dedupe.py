"""Tìm & loại bỏ bookmark trùng lặp trong cây Folder, theo URL đã chuẩn hoá.

Chiến lược giữ lại bản ghi nào khi có trùng lặp:
    - Ưu tiên bookmark có ADD_DATE nhỏ hơn (thêm sớm hơn = bản gốc).
    - Nếu không có ADD_DATE, giữ bookmark gặp đầu tiên khi duyệt cây
      (duyệt theo thứ tự folder cha -> folder con, trái sang phải).
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
    """Gom nhóm các bookmark có cùng normalized_url, không sửa cây gốc."""
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
    """Xoá bookmark trùng lặp trực tiếp trên cây `root` (in-place).

    Trước khi xoá, GỘP `tags`/`description` từ các bản bị xoá vào bản được
    giữ lại (nếu bản giữ lại đang thiếu) để không mất dữ liệu người dùng đã
    gắn cho bookmark trùng.

    Trả về số lượng bookmark đã bị xoá.
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
    """Xoá đệ quy các folder rỗng (không bookmark, không folder con).
    Trả về số lượng folder đã xoá. Không xoá folder gốc/personal-toolbar
    nếu nó là root truyền vào trực tiếp."""
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
