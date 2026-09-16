# favorites-manager

Công cụ Python 100% (không cần Node/PHP...) để quản lý **favorites/bookmarks**
xuất ra từ nhiều trình duyệt (Chrome, Edge, Firefox, Cốc Cốc, Brave, Safari...)
ở định dạng **Netscape Bookmark HTML** — định dạng chuẩn mà mọi trình duyệt
đều hỗ trợ *xuất* và *import lại*.

## Tính năng

- **Đọc** file `bookmarks.html` (kể cả file lỗi/không chuẩn, tự chuẩn hoá lại
  cấu trúc `<DT>`/`<DD>` không đóng thẻ).
- Giữ nguyên **ghi chú (`<DD>`)** và **ICON_URI** (Firefox) khi đọc/ghi lại —
  không bị mất dữ liệu như nhiều tool khác chỉ đọc `HREF`. Cũng đọc/ghi được
  thuộc tính `TAGS=` nếu file nguồn có sẵn (từ các dịch vụ như del.icio.us
  hoặc tool khác) — lưu ý: Chrome và Firefox **không** tự ghi hay đọc
  `TAGS=` khi import/export qua HTML (đã xác minh trực tiếp trong mã nguồn
  của cả hai, xem mục "Nguồn tham khảo" bên dưới), nên đây chỉ là bảo toàn
  dữ liệu cho khả năng tương thích với các tool khác, không phải tính năng
  "tag" mà Chrome/Firefox sẽ hiển thị sau khi import.
- **Gộp** nhiều file từ nhiều trình duyệt thành 1 cây bookmark.
- **Tìm & xoá trùng lặp** theo URL đã chuẩn hoá (bỏ `/` cuối, fragment `#...`,
  không phân biệt hoa/thường ở scheme & host); khi trùng, giữ lại bản có
  `ADD_DATE` sớm nhất.
- **Phân loại theo folder** tự động dựa trên domain (ví dụ toàn bộ
  `github.com` gom vào 1 folder).
- **Tự thêm URL thủ công** qua file `config.json` (sửa tay hoặc qua lệnh
  `add-url`), hỗ trợ cả `folder`, `tags`, `description`.
- **Kiểm tra link chết** (404, lỗi kết nối, timeout...) chạy song song bằng
  thread pool, xuất báo cáo JSON, tuỳ chọn tự xoá link chết.
- **Xuất riêng file HTML cho từng trình duyệt** (Chrome/Edge/Firefox/Safari/
  Brave/Cốc Cốc) với đúng tên/flag folder "thanh bookmark" của từng trình
  duyệt, để import không bị conflict/tạo folder "Imported (ngày)".

## Cài đặt (dùng `uv`)

```bash
uv venv
uv pip install -e .
```

Yêu cầu Python **3.9+**. Thư viện dùng: `beautifulsoup4`, `lxml`, `click`,
`rich`, `requests` (đều thuần Python, không cần build native phức tạp).

## Sử dụng (CLI: `favorites`)

```bash
# Xem thống kê (số bookmark, số folder, số trùng lặp) cho 1 hoặc nhiều file
favorites stats chrome.html firefox.html

# Xem chi tiết từng nhóm trùng lặp, không sửa file
favorites list-duplicates chrome.html

# Gộp nhiều file + xoá trùng lặp -> ghi ra file mới, import lại vào trình duyệt
favorites dedupe chrome.html firefox.html -o merged_clean.html

# Gộp nhiều file, giữ nguyên cấu trúc folder gốc (không xoá trùng lặp)
favorites merge chrome.html firefox.html -o merged.html

# Gộp + xoá trùng lặp + tự phân loại folder theo domain
favorites organize chrome.html firefox.html -o organized.html \
    --min-group-size 3

# In cây folder hiện có của 1 file
favorites list-folders chrome.html
```

### Tự thêm URL qua file `config.json`

Không cần sửa code, chỉ cần thêm URL vào `config.json` rồi để chương trình
đọc và chèn vào lúc build. Có 2 cách thêm:

**1. Sửa tay file JSON** (tạo `config.json` nếu chưa có):

```json
{
  "bookmarks": [
    { "url": "https://claude.ai", "title": "Claude", "folder": "AI Tools" },
    { "url": "https://github.com/tuanductran", "title": "My GitHub", "folder": "Dev/Profile" }
  ]
}
```

`folder` dùng `/` để phân cấp; để trống hoặc bỏ qua nếu muốn thêm vào gốc.
Folder chưa tồn tại sẽ tự được tạo khi build.

**2. Dùng lệnh CLI** (tự ghi vào config.json, không cần mở file):

```bash
favorites add-url "https://claude.ai" --title "Claude" --folder "AI Tools" --config config.json
favorites add-url "https://github.com/tuanductran" --title "My GitHub" --folder "Dev/Profile" --config config.json
```

### Build ra output riêng cho từng trình duyệt (tránh conflict khi import)

Mỗi trình duyệt nhận diện "thanh bookmark" (bookmarks bar) qua thuộc tính
`PERSONAL_TOOLBAR_FOLDER="true"` trên `<H3>`, chứ không phải theo tên —
nhưng tên hiển thị và cách gộp khi import lại khác nhau giữa các trình
duyệt (Chrome/Edge/Brave/Cốc Cốc gọi là "Bookmarks bar"/"Favorites bar",
Firefox gọi là "Bookmarks Toolbar", Safari gọi là "Favorites"). Import 1
file dùng chung dễ khiến trình duyệt tạo thêm folder "Imported (ngày)"
thay vì gộp thẳng vào thanh bookmark có sẵn.

Lệnh `build` giải quyết việc này: đọc file nguồn + `config.json`, gộp, xoá
trùng lặp, rồi xuất **1 file HTML riêng cho mỗi trình duyệt**, mỗi file có
tên folder thanh công cụ đúng quy ước của trình duyệt đó:

```bash
favorites build \
    -i chrome.html -i firefox.html \
    --config config.json \
    -o dist \
    --browsers chrome,firefox,edge,safari

# thêm --organize --min-group-size 3 nếu muốn phân loại theo domain luôn
```

Kết quả: `dist/chrome.html`, `dist/firefox.html`, `dist/edge.html`,
`dist/safari.html` — import file tương ứng vào đúng trình duyệt đó.

### Kiểm tra link chết

```bash
# Chỉ xem báo cáo, không sửa file
favorites check-links bookmarks.html --workers 15 --timeout 8 --report dead-links.json

# Kiểm tra rồi tự xoá link chết, ghi ra file mới
favorites check-links bookmarks.html --remove-broken -o cleaned.html
```

Cơ chế: thử `HEAD` trước (nhẹ), nếu server không hỗ trợ (405) hoặc lỗi thì
fallback sang `GET`; chạy song song bằng `ThreadPoolExecutor` (mặc định 10
luồng) để không mất hàng giờ với file vài trăm/nghìn bookmark. **Lưu ý hạn
chế** (giống mọi tool check-link dựa trên HTTP status): một số trang chặn
bot (Cloudflare/Akamai) có thể báo lỗi dù trang vẫn sống, và trang dạng SPA
(JS render phía client) có thể trả về `200` dù nội dung thực tế đã mất — nên
xem báo cáo là gợi ý để rà tay, không tự động tin 100%.


Sau khi có file `.html` kết quả, vào trình duyệt đích:

- **Chrome/Edge/Brave/Cốc Cốc**: `chrome://bookmarks` (hoặc `edge://favorites`)
  → menu (⋮) → *Import bookmarks* → chọn file `.html`.
- **Firefox**: `about:preferences` → *Bookmarks* (Thư viện) → *Import and
  Backup* → *Import Bookmarks from HTML...*.
- **Safari**: File → Import From → Bookmarks HTML File...

## Dùng như thư viện Python

```python
from favorites_manager.parser import parse_file
from favorites_manager.dedupe import remove_duplicates
from favorites_manager.organize import organize_by_domain
from favorites_manager.writer import write_file

root = parse_file("bookmarks.html")
remove_duplicates(root)
organized = organize_by_domain(root, min_group_size=3)
write_file(organized, "organized.html")
```

## Cấu trúc project

```
favorites-manager/
├── pyproject.toml
├── README.md
├── src/favorites_manager/
│   ├── models.py     # Bookmark, Folder (dataclass)
│   ├── parser.py      # đọc Netscape Bookmark HTML -> cây Folder
│   ├── writer.py       # cây Folder -> Netscape Bookmark HTML
│   ├── dedupe.py       # tìm/xoá trùng lặp, xoá folder rỗng
│   ├── organize.py     # gộp nhiều nguồn, phân loại theo domain
│   ├── config.py        # đọc/ghi config.json (URL tự thêm)
│   ├── browsers.py      # xuất riêng theo từng trình duyệt
│   ├── linkcheck.py     # kiểm tra link chết (song song)
│   └── cli.py           # CLI (click)
└── tests/
    └── test_roundtrip.py
```

## Ghi chú kỹ thuật

File Netscape Bookmark không đóng thẻ `<DT>` (giống `<li>` trong `<ul>`), nên
`BeautifulSoup` (html.parser) mặc định sẽ lồng sai cây DOM. `parser.py` có 1
bước tiền xử lý bằng stack để chèn `</dt>`/`</dd>` đúng vị trí (dựa theo độ
sâu `<DL>`/`</DL>` vốn đã cân bằng sẵn trong file gốc) trước khi parse.

## Đã audit / các lỗi đã vá

- **Nhiều `PERSONAL_TOOLBAR_FOLDER="true"` khi gộp nhiều nguồn**: khi
  `build` gộp 2+ file (mỗi file có 1 folder toolbar riêng của trình duyệt
  gốc), bản build-per-browser trước đây chỉ đổi tên folder toolbar ĐẦU
  TIÊN tìm thấy, để sót các folder toolbar khác vẫn mang cờ `true` ->
  browser đích không biết chọn folder nào làm thanh bookmark. Đã sửa
  `browsers.py` để luôn tắt cờ ở MỌI folder trước, chỉ bật lại đúng 1.
- **Mất `tags`/`description` khi xoá trùng lặp**: bản bị xoá trong 1 nhóm
  trùng lặp có thể có tag/ghi chú riêng mà bản được giữ lại không có ->
  `dedupe.py` giờ gộp (union) tags và điền `description` còn thiếu từ các
  bản bị xoá vào bản được giữ lại trước khi xoá.
- **Rò rỉ kết nối khi check-links**: nhánh fallback GET (`stream=True`)
  trước đây không đóng response -> có thể cạn connection pool khi quét
  nhiều URL không hỗ trợ HEAD. Đã bọc bằng context manager (`with ... as
  resp`) để luôn đóng kết nối.
- **`favorites build` chạy im lặng khi không có input**: đã thêm kiểm tra
  bắt buộc phải có ít nhất `-i/--input` hoặc `--config`.
- Đã test thực tế trên Python **3.9.25** (không chỉ 3.11) để đảm bảo cú
  pháp type hint hiện đại (`str | None`, `tuple[str, ...]`) hoạt động đúng
  nhờ `from __future__ import annotations` ở mọi module.

## Nguồn tham khảo (đối chiếu trực tiếp với mã nguồn trình duyệt)

Thay vì chỉ dựa vào blog/bài viết thứ ba, các giả định về định dạng đã được
đối chiếu trực tiếp với mã nguồn mở của Chromium và Firefox:

- **Chromium** — `chrome/browser/bookmarks/bookmark_html_writer.cc`
  ([chromium.googlesource.com](https://chromium.googlesource.com/chromium/src/+/lkgr/chrome/browser/bookmarks/bookmark_html_writer.cc)):
  xác nhận phần header file khớp chính xác với `writer.py`; xác nhận
  `PERSONAL_TOOLBAR_FOLDER="true"` chỉ được Chrome ghi cho folder Bookmarks
  Bar (không ghi `TAGS`/`ICON_URI`); xác nhận nội dung "Other bookmarks" và
  "Mobile bookmarks" được Chrome xuất **phẳng ở cấp gốc**, không bọc trong
  folder riêng — đúng với cách `parser.py` đang xử lý các bookmark nằm trực
  tiếp ở root.
- **Firefox** — `toolkit/components/places/BookmarkHTMLUtils.sys.mjs`
  ([searchfox.org](https://searchfox.org/firefox-main/source/toolkit/components/places/BookmarkHTMLUtils.sys.mjs)):
  xác nhận `<DD>` là ghi chú gắn với bookmark `<A>` ngay trước đó (đúng
  logic `parser.py` đang dùng); xác nhận `ICON_URI` là thuộc tính riêng của
  Firefox; xác nhận Firefox **không** đọc `TAGS=` khi import HTML (danh
  sách thuộc tính được import: `HREF`, `ICON`, `ICON_URI`, `LAST_CHARSET` —
  không có `TAGS`); xác nhận cơ chế "folder mới tự động đóng folder cũ
  cùng cấp khi gặp `<H3>` tiếp theo" giống hệt cách `parser.py` chuẩn hoá
  bằng stack.
