from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from .browsers import BROWSERS, build_for_browser
from .config import add_entry, apply_entries, load_config
from .dedupe import find_duplicates, remove_duplicates, remove_empty_folders
from .linkcheck import check_links, remove_broken as remove_broken_bookmarks
from .models import Folder
from .organize import merge_folders, organize_by_domain
from .parser import parse_file
from .writer import write_file

console = Console()


@click.group()
def main() -> None:
    """favorites: công cụ quản lý favorites/bookmarks đa trình duyệt."""


@main.command()
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
def stats(files: tuple[str, ...]) -> None:
    """Thống kê nhanh: tổng bookmark, số folder, số trùng lặp cho từng file."""
    table = Table(title="Thống kê favorites")
    table.add_column("File")
    table.add_column("Bookmarks", justify="right")
    table.add_column("Folders", justify="right")
    table.add_column("Trùng lặp", justify="right")
    for f in files:
        root = parse_file(f)
        n_folders = sum(1 for _ in root.walk_folders()) - 1
        n_dupes = sum(len(g.removed) for g in find_duplicates(root))
        table.add_row(f, str(root.count_bookmarks()), str(n_folders), str(n_dupes))
    console.print(table)


@main.command()
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("-o", "--output", required=True, type=click.Path(), help="File HTML kết quả.")
@click.option(
    "--keep-empty-folders", is_flag=True, help="Giữ lại folder rỗng sau khi xoá trùng lặp."
)
def dedupe(files: tuple[str, ...], output: str, keep_empty_folders: bool) -> None:
    """Gộp 1+ file bookmark, xoá trùng lặp theo URL, ghi ra file HTML mới."""
    roots = [parse_file(f) for f in files]
    names = [click.format_filename(f) for f in files]
    merged = merge_folders(roots, names) if len(roots) > 1 else roots[0]

    removed = remove_duplicates(merged)
    if not keep_empty_folders:
        remove_empty_folders(merged)

    write_file(merged, output)
    console.print(
        f"[green]Đã xoá {removed} bookmark trùng lặp.[/green] "
        f"Còn lại {merged.count_bookmarks()} bookmark -> [bold]{output}[/bold]"
    )


@main.command(name="list-duplicates")
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
def list_duplicates(files: tuple[str, ...]) -> None:
    """Liệt kê chi tiết các nhóm bookmark trùng lặp (không sửa file)."""
    roots = [parse_file(f) for f in files]
    names = [click.format_filename(f) for f in files]
    merged = merge_folders(roots, names) if len(roots) > 1 else roots[0]

    groups = find_duplicates(merged)
    if not groups:
        console.print("[green]Không có bookmark trùng lặp.[/green]")
        return
    for g in groups:
        console.print(f"\n[bold yellow]{g.normalized_url}[/bold yellow]")
        console.print(f"  giữ lại : {g.kept.title}")
        for r in g.removed:
            console.print(f"  bỏ      : {r.title}")
    console.print(f"\n[bold]Tổng: {len(groups)} nhóm, {sum(len(g.removed) for g in groups)} bookmark thừa.[/bold]")


@main.command()
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("-o", "--output", required=True, type=click.Path(), help="File HTML kết quả.")
@click.option("--min-group-size", default=2, show_default=True, help="Số bookmark tối thiểu để tách domain thành folder riêng.")
@click.option("--dedupe/--no-dedupe", default=True, show_default=True, help="Xoá trùng lặp trước khi phân loại.")
def organize(files: tuple[str, ...], output: str, min_group_size: int, dedupe: bool) -> None:
    """Gộp file, (tuỳ chọn) xoá trùng lặp, rồi phân loại bookmark theo domain
    thành từng folder, ghi ra file HTML mới."""
    roots = [parse_file(f) for f in files]
    names = [click.format_filename(f) for f in files]
    merged = merge_folders(roots, names) if len(roots) > 1 else roots[0]

    if dedupe:
        remove_duplicates(merged)

    organized = organize_by_domain(merged, min_group_size=min_group_size)
    write_file(organized, output)
    console.print(
        f"[green]Đã phân loại {organized.count_bookmarks()} bookmark thành "
        f"{len(organized.subfolders)} folder theo domain[/green] -> [bold]{output}[/bold]"
    )


@main.command()
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("-o", "--output", required=True, type=click.Path(), help="File HTML kết quả.")
def merge(files: tuple[str, ...], output: str) -> None:
    """Chỉ gộp nhiều file bookmark (từ nhiều trình duyệt) thành 1 file,
    giữ nguyên cấu trúc folder gốc của từng file (không dedupe)."""
    roots = [parse_file(f) for f in files]
    names = [click.format_filename(f) for f in files]
    merged = merge_folders(roots, names)
    write_file(merged, output)
    console.print(f"[green]Đã gộp {merged.count_bookmarks()} bookmark[/green] -> [bold]{output}[/bold]")


@main.command(name="list-folders")
@click.argument("file", type=click.Path(exists=True))
def list_folders(file: str) -> None:
    """In cây folder + số bookmark trong mỗi folder."""
    root = parse_file(file)

    def show(folder: Folder, depth: int = 0) -> None:
        if folder.name != "root":
            console.print("  " * depth + f"[cyan]{folder.name}[/cyan] ({len(folder.bookmarks)})")
        for sub in folder.subfolders:
            show(sub, depth + (0 if folder.name == "root" else 1))

    show(root)


@main.command(name="add-url")
@click.argument("url")
@click.option("--title", default=None, help="Tiêu đề hiển thị. Mặc định dùng URL.")
@click.option("--folder", default="", help='Đường dẫn folder, cách nhau bằng "/", vd "Dev/APIs".')
@click.option("--tags", default="", help='Danh sách tag, cách nhau bằng dấu phẩy.')
@click.option("--description", default=None, help="Ghi chú/mô tả (xuất thành thẻ <DD>).")
@click.option("--config", "config_path", default="config.json", show_default=True, type=click.Path())
def add_url(url: str, title: str | None, folder: str, tags: str, description: str | None, config_path: str) -> None:
    """Thêm 1 URL vào file config.json (tự tạo file nếu chưa có)."""
    entry = add_entry(config_path, url=url, title=title, folder=folder, tags=tags, description=description)
    console.print(
        f"[green]Đã thêm[/green] {entry.title} -> {entry.url} "
        f"(folder: {'/'.join(entry.folder) or '(gốc)'}) vào [bold]{config_path}[/bold]"
    )


@main.command()
@click.option("-i", "--input", "input_files", multiple=True, type=click.Path(exists=True), help="File(s) bookmark nguồn (có thể lặp -i nhiều lần).")
@click.option("--config", "config_path", default=None, type=click.Path(exists=True), help="File config.json chứa URL tự thêm.")
@click.option("-o", "--output-dir", required=True, type=click.Path(), help="Thư mục ghi các file HTML kết quả.")
@click.option("--browsers", default=",".join(BROWSERS), show_default=True, help="Danh sách trình duyệt cần xuất, cách nhau bằng dấu phẩy.")
@click.option("--organize/--no-organize", default=False, show_default=True, help="Phân loại lại theo domain trước khi xuất.")
@click.option("--min-group-size", default=2, show_default=True, help="Dùng cùng --organize: số bookmark tối thiểu để tách domain riêng.")
def build(
    input_files: tuple[str, ...],
    config_path: str | None,
    output_dir: str,
    browsers: str,
    organize: bool,
    min_group_size: int,
) -> None:
    """Pipeline đầy đủ: đọc file nguồn (+ config.json) -> gộp -> xoá trùng
    lặp -> (tuỳ chọn) phân loại theo domain -> xuất 1 file HTML RIÊNG cho
    mỗi trình duyệt (để import không bị conflict/tạo folder "Imported")."""
    if not input_files and not config_path:
        raise click.UsageError("Cần ít nhất 1 file -i/--input hoặc --config.")

    roots = [parse_file(f) for f in input_files]
    names = [click.format_filename(f) for f in input_files]
    merged = merge_folders(roots, names) if len(roots) > 1 else (roots[0] if roots else Folder(name="root"))

    n_manual = 0
    if config_path:
        entries = load_config(config_path)
        n_manual = apply_entries(merged, entries)

    n_dupes = remove_duplicates(merged)
    remove_empty_folders(merged)

    if organize:
        merged = organize_by_domain(merged, min_group_size=min_group_size)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    browser_list = [b.strip() for b in browsers.split(",") if b.strip()]
    table = Table(title="Đã xuất theo từng trình duyệt")
    table.add_column("Trình duyệt")
    table.add_column("File")
    table.add_column("Bookmarks", justify="right")
    for b in browser_list:
        per_browser = build_for_browser(merged, b)
        out_path = out_dir / f"{b}.html"
        write_file(per_browser, out_path)
        table.add_row(b, str(out_path), str(per_browser.count_bookmarks()))

    console.print(
        f"Nguồn: {merged.count_bookmarks() + n_dupes} bookmark, "
        f"đã thêm {n_manual} từ config, xoá {n_dupes} trùng lặp."
    )
    console.print(table)


@main.command(name="check-links")
@click.argument("file", type=click.Path(exists=True))
@click.option("--workers", default=10, show_default=True, help="Số kết nối chạy song song.")
@click.option("--timeout", default=10.0, show_default=True, help="Timeout mỗi request (giây).")
@click.option("--remove-broken/--no-remove-broken", default=False, show_default=True, help="Xoá luôn link chết và ghi ra --output.")
@click.option("-o", "--output", default=None, type=click.Path(), help="File HTML ghi lại sau khi xoá link chết (bắt buộc nếu dùng --remove-broken).")
@click.option("--report", default=None, type=click.Path(), help="Ghi báo cáo chi tiết (JSON) ra file này.")
def check_links_cmd(
    file: str, workers: int, timeout: float, remove_broken: bool, output: str | None, report: str | None
) -> None:
    """Kiểm tra từng bookmark trong FILE còn sống hay đã chết (404/lỗi kết
    nối/...). Chạy song song bằng thread pool, có thể mất vài phút với file
    lớn (khoảng vài trăm bookmark)."""
    root = parse_file(file)
    total = root.count_bookmarks()

    with click.progressbar(length=total, label="Đang kiểm tra link") as bar:
        def _progress(done: int, _total: int) -> None:
            bar.update(done - bar.pos)

        results = check_links(root, max_workers=workers, timeout=timeout, progress_cb=_progress)

    broken = [r for r in results if not r.ok]
    table = Table(title=f"Link chết ({len(broken)}/{total})")
    table.add_column("Status")
    table.add_column("Tiêu đề")
    table.add_column("URL")
    for r in sorted(broken, key=lambda r: (r.status_code or 0)):
        status_str = str(r.status_code) if r.status_code else (r.error or "?")
        table.add_row(status_str, r.bookmark.title[:40], r.bookmark.url)
    console.print(table)

    if report:
        import json as _json

        data = [
            {
                "url": r.bookmark.url,
                "title": r.bookmark.title,
                "ok": r.ok,
                "status_code": r.status_code,
                "error": r.error,
                "final_url": r.final_url,
            }
            for r in results
        ]
        Path(report).write_text(_json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        console.print(f"Đã ghi báo cáo đầy đủ -> [bold]{report}[/bold]")

    if remove_broken:
        if not output:
            raise click.UsageError("Cần --output khi dùng --remove-broken.")
        broken_urls = {r.bookmark.url for r in broken}
        n = remove_broken_bookmarks(root, broken_urls)
        remove_empty_folders(root)
        write_file(root, output)
        console.print(f"[green]Đã xoá {n} link chết[/green] -> [bold]{output}[/bold]")


if __name__ == "__main__":
    main()
