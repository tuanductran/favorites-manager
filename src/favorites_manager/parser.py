"""Parse file favorites/bookmarks dạng Netscape Bookmark HTML (chuẩn xuất ra
từ Chrome, Edge, Firefox, Cốc Cốc, Brave, ...) thành cây Folder/Bookmark.

Cấu trúc file gốc (đơn giản hoá):

    <DL><p>
        <DT><H3 ...>Tên folder</H3>
        <DL><p>
            <DT><A HREF="...">Tên bookmark</A>
            <DT><H3 ...>Folder con</H3>
            <DL><p> ... </DL><p>
        </DL><p>
    </DL><p>

Vì đây không phải XHTML hợp lệ (thẻ không đóng), ta dùng BeautifulSoup với
parser "html.parser"/"lxml" để nó tự sửa cây DOM tương tự trình duyệt.
"""
from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from .models import Bookmark, Folder

# File Netscape Bookmark không đóng thẻ <DT>/<DD> (giống <li>): trình duyệt
# tự "auto-close" mục đang mở khi gặp <DT>/<DD> mới HOẶC khi gặp </DL> đóng
# chính cấp <DL> đang chứa nó — nhưng <DT> vẫn có thể "bao" một <DL> lồng
# bên trong nó (folder con). html.parser của BeautifulSoup không hiểu luật
# này nên cần tiền xử lý: dùng một stack để chèn thẻ đóng đúng chỗ, dựa
# theo độ sâu <DL>/</DL> (vốn đã được đóng mở cân bằng sẵn trong file gốc).
_TOKEN_RE = re.compile(r"(?i)<DL>|</DL>|<DT>|<DD>")


def _normalize_netscape_html(html: str) -> str:
    out: list[str] = []
    # phần tử: ("dl",) hoặc ("item", "dt"|"dd")
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
    """Đọc 1 file HTML bookmark và trả về Folder gốc ("root")."""
    html = Path(path).read_text(encoding="utf-8", errors="replace")
    return parse_html(html)


def parse_html(html: str) -> Folder:
    html = _normalize_netscape_html(html)
    soup = BeautifulSoup(html, "html.parser")
    root = Folder(name="root")

    # Toàn bộ bookmark/folder nằm trong <DL> đầu tiên ở cấp cao nhất.
    top_dl = soup.find("dl")
    if top_dl is not None:
        _parse_dl(top_dl, root)
    return root


def _parse_dl(dl: Tag, parent: Folder) -> None:
    """Duyệt các <DT> trực tiếp bên trong 1 thẻ <DL>, đổ vào `parent`.

    Lưu ý: BeautifulSoup (html.parser) tự động bọc nội dung <DL><p> thành
    <dl><p>...</p></dl>, và vì <DT> không có thẻ đóng, <DL> con lại lồng
    *bên trong* <dt> cha thay vì là sibling. Nên ta duyệt qua toàn bộ
    <dt> con cháu ở "độ sâu gần nhất" bằng cách xét container <p> nếu có.
    """
    container = dl.find("p", recursive=False) or dl
    for dt in container.find_all("dt", recursive=False):
        h3 = dt.find("h3", recursive=False)
        a = dt.find("a", recursive=False)

        if h3 is not None:
            folder = Folder(
                name=h3.get_text(strip=True) or "(Không tên)",
                add_date=h3.get("add_date"),
                last_modified=h3.get("last_modified"),
                personal_toolbar=(h3.get("personal_toolbar_folder") == "true"),
            )
            parent.subfolders.append(folder)
            # Sau khi chuẩn hoá, <DL> con nằm lồng bên trong chính <dt> này
            # (thử thêm sibling để phòng trường hợp trình duyệt xuất khác).
            child_dl = dt.find("dl", recursive=False) or dt.find_next_sibling("dl")
            if child_dl is not None:
                _parse_dl(child_dl, folder)

        elif a is not None:
            href = a.get("href")
            if not href:
                continue
            tags_raw = a.get("tags") or ""
            tags = tuple(t.strip() for t in tags_raw.split(",") if t.strip())

            # <DD> ghi chú/mô tả nằm ngay sau <DT><A>...</A>, là 1 <dt> sibling
            # riêng theo cấu trúc gốc (không lồng trong <a>). Sau khi chuẩn
            # hoá, nó thường xuất hiện làm sibling của <dt> hiện tại.
            description = None
            next_dd = dt.find_next_sibling("dd")
            # Chỉ nhận <dd> nếu nó thực sự "thuộc về" bookmark này, tức nằm
            # ngay trước <dt> kế tiếp (nếu có) trong cùng container.
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
