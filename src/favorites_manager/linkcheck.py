"""Check which bookmarks are dead (404, DNS failure, timeout, ...), running
concurrently via ThreadPoolExecutor (network I/O-bound, so no need for
asyncio here).

Strategy:
    - Try HEAD first (lightweight, saves bandwidth).
    - Some servers don't support HEAD (return 405) -> fall back to GET.
    - There's a timeout + concurrency cap to avoid getting blocked/rate-limited.
    - 2xx/3xx counts as "alive"; 4xx/5xx/connection errors count as "possibly dead".
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
    final_url: Optional[str] = None  # differs from the original url if redirected


def _check_one(url: str, timeout: float) -> tuple[bool, Optional[int], Optional[str], Optional[str]]:
    try:
        with requests.head(
            url, allow_redirects=True, timeout=timeout, headers=_DEFAULT_HEADERS
        ) as resp:
            status_code = resp.status_code
            final_url = resp.url
            needs_get_fallback = status_code == 405 or status_code >= 400

        if needs_get_fallback:
            # Many servers block/don't support HEAD -> retry with GET.
            # Use stream=True + a context manager so we don't download the
            # full body (we only need status/headers) and ALWAYS close the
            # connection, avoiding connection-pool leaks when scanning
            # hundreds/thousands of URLs.
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
    """Check every bookmark in `root` (recursively). Returns results for
    EVERY bookmark (alive and dead alike), in completion order."""
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
    """Remove bookmarks whose url is in `broken_urls` from the `root` tree.
    Returns the number removed."""
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
