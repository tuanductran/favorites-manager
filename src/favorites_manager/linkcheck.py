"""Kiểm tra bookmark nào đã chết (404, DNS lỗi, timeout, ...), chạy song
song bằng ThreadPoolExecutor (network I/O-bound nên không cần asyncio).

Chiến lược:
    - Thử HEAD trước (nhẹ, tiết kiệm băng thông).
    - Một số server không hỗ trợ HEAD (trả 405) -> fallback sang GET.
    - Có timeout + giới hạn concurrency để tránh bị chặn/rate-limit.
    - Coi 2xx/3xx là "sống"; 4xx/5xx/lỗi kết nối là "nghi vấn chết".
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Optional

import requests

from .models import Bookmark, Folder

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; favorites-manager-link-checker/1.0; "
        "+https://github.com/tuanductran/favorites-manager)"
    )
}


@dataclass
class LinkCheckResult:
    bookmark: Bookmark
    ok: bool
    status_code: Optional[int]
    error: Optional[str]
    final_url: Optional[str] = None  # khác url gốc nếu bị redirect


def _check_one(url: str, timeout: float) -> tuple[bool, Optional[int], Optional[str], Optional[str]]:
    try:
        with requests.head(
            url, allow_redirects=True, timeout=timeout, headers=_DEFAULT_HEADERS
        ) as resp:
            status_code = resp.status_code
            final_url = resp.url
            needs_get_fallback = status_code == 405 or status_code >= 400

        if needs_get_fallback:
            # Nhiều server chặn/không hỗ trợ HEAD -> thử lại bằng GET.
            # Dùng stream=True + context manager để không tải hết nội dung
            # về (chỉ cần status/headers) và LUÔN đóng kết nối, tránh rò rỉ
            # connection pool khi quét hàng trăm/nghìn URL.
            with requests.get(
                url, allow_redirects=True, timeout=timeout, headers=_DEFAULT_HEADERS,
                stream=True,
            ) as resp:
                status_code = resp.status_code
                final_url = resp.url

        return status_code < 400, status_code, None, final_url
    except requests.RequestException as exc:
        return False, None, type(exc).__name__ + ": " + str(exc), None


def check_links(
    root: Folder,
    max_workers: int = 10,
    timeout: float = 10.0,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> list[LinkCheckResult]:
    """Kiểm tra toàn bộ bookmark trong `root` (đệ quy). Trả về danh sách kết
    quả cho MỌI bookmark (cả sống lẫn chết) theo thứ tự hoàn thành."""
    bookmarks = list(root.walk_bookmarks())
    results: list[LinkCheckResult] = []
    total = len(bookmarks)
    done = 0

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_to_bm = {
            pool.submit(_check_one, bm.url, timeout): bm for bm in bookmarks
        }
        for future in as_completed(future_to_bm):
            bm = future_to_bm[future]
            ok, status, error, final_url = future.result()
            results.append(
                LinkCheckResult(
                    bookmark=bm, ok=ok, status_code=status, error=error,
                    final_url=final_url,
                )
            )
            done += 1
            if progress_cb:
                progress_cb(done, total)
    return results


def remove_broken(root: Folder, broken_urls: set[str]) -> int:
    """Xoá khỏi cây `root` các bookmark có url nằm trong `broken_urls`.
    Trả về số lượng đã xoá."""
    removed = 0

    def _clean(folder: Folder) -> None:
        nonlocal removed
        kept = []
        for bm in folder.bookmarks:
            if bm.url in broken_urls:
                removed += 1
            else:
                kept.append(bm)
        folder.bookmarks = kept
        for sub in folder.subfolders:
            _clean(sub)

    _clean(root)
    return removed
