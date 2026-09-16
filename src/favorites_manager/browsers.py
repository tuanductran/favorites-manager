"""Mỗi trình duyệt gọi tên folder "thanh bookmark" khác nhau, và chỉ NHẬN
DIỆN nó qua thuộc tính PERSONAL_TOOLBAR_FOLDER="true" trên thẻ <H3> (không
phải qua tên folder). Nếu xuất 1 file HTML dùng chung cho mọi trình duyệt:

- Tên folder hiển thị có thể lạ (vd Firefox thấy folder tên "Bookmarks bar"
  của Chrome nằm trong "Bookmarks Menu" thay vì trên thanh công cụ).
- Import nhiều lần vào cùng trình duyệt dễ tạo folder trùng kiểu
  "Imported (ngày)" thay vì gộp thẳng vào thanh bookmark.

`build_for_browser()` tạo 1 bản sao cây bookmark, đổi tên + đánh dấu đúng
folder "thanh công cụ" theo quy ước từng trình duyệt, để import vào đúng
trình duyệt đó sạch sẽ nhất, hạn chế trùng lặp/conflict.

Nguồn quy ước tên (theo tài liệu & thực nghiệm phổ biến):
- Chrome / Edge / Brave / Cốc Cốc (Chromium-based): "Bookmarks bar"
  (Edge/IE gọi là "Favorites bar" nhưng cũng nhận PERSONAL_TOOLBAR_FOLDER).
- Firefox: "Bookmarks Toolbar" (thanh công cụ) và "Bookmarks Menu" (menu).
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
    "coccoc": BrowserProfile("coccoc", "Cốc Cốc", "Bookmarks bar"),
    "firefox": BrowserProfile("firefox", "Mozilla Firefox", "Bookmarks Toolbar"),
    "safari": BrowserProfile("safari", "Safari", "Favorites"),
}


def _find_toolbar_folder(root: Folder) -> Folder | None:
    for f in root.walk_folders():
        if f.personal_toolbar:
            return f
    return None


def build_for_browser(root: Folder, browser: str) -> Folder:
    """Trả về 1 bản CLONE của `root`, đổi tên + gắn cờ folder thanh công cụ
    đúng quy ước của `browser`. Không sửa `root` gốc.

    Lưu ý: nếu `root` được gộp từ NHIỀU nguồn (nhiều trình duyệt), có thể có
    NHIỀU folder cùng mang cờ personal_toolbar=True (mỗi nguồn 1 cái) —
    xuất file với >1 PERSONAL_TOOLBAR_FOLDER="true" khiến trình duyệt xác
    định thanh bookmark không rõ ràng (undefined). Nên ta luôn tắt cờ này
    ở MỌI folder trước, rồi chỉ bật lại đúng 1 folder duy nhất.
    """
    if browser not in PROFILES:
        raise ValueError(f"Không hỗ trợ trình duyệt: {browser!r}. Chọn trong {BROWSERS}")
    profile = PROFILES[browser]
    clone = copy.deepcopy(root)

    for f in clone.walk_folders():
        f.personal_toolbar = False

    toolbar = _find_toolbar_folder(root)  # tìm trên bản gốc để lấy đúng vị trí đầu tiên theo thứ tự duyệt
    if toolbar is not None:
        # map sang folder tương ứng trong `clone` bằng cách duyệt song song
        toolbar = next(
            (f for f, orig in zip(clone.walk_folders(), root.walk_folders()) if orig is toolbar),
            None,
        )
    if toolbar is None:
        # Không có folder nào được đánh dấu là thanh công cụ trong nguồn ->
        # dùng folder đầu tiên ở cấp cao nhất (nếu có) làm thanh công cụ,
        # để tránh mọi thứ rơi hết vào "Other bookmarks"/"Imported".
        toolbar = clone.subfolders[0] if clone.subfolders else None

    if toolbar is not None:
        toolbar.personal_toolbar = True
        toolbar.name = profile.toolbar_folder_name

    return clone


def build_all(root: Folder, browsers: list[str] | None = None) -> dict[str, Folder]:
    targets = browsers or list(BROWSERS)
    return {b: build_for_browser(root, b) for b in targets}
