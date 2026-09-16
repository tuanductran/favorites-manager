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
    """favorites: a tool for managing favorites/bookmarks across multiple browsers."""


@main.command()
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
def stats(files: tuple[str, ...]) -> None:
    """Quick stats: total bookmarks, folder count, and duplicate count for each file."""
    table = Table(title="Favorites stats")
    table.add_column("File")
    table.add_column("Bookmarks", justify="right")
    table.add_column("Folders", justify="right")
    table.add_column("Duplicates", justify="right")
    for f in files:
        root = parse_file(f)
        n_folders = sum(1 for _ in root.walk_folders()) - 1
        n_dupes = sum(len(g.removed) for g in find_duplicates(root))
        table.add_row(f, str(root.count_bookmarks()), str(n_folders), str(n_dupes))
    console.print(table)


@main.command()
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("-o", "--output", required=True, type=click.Path(), help="Output HTML file.")
@click.option(
    "--keep-empty-folders", is_flag=True, help="Keep empty folders after removing duplicates."
)
def dedupe(files: tuple[str, ...], output: str, keep_empty_folders: bool) -> None:
    """Merge one or more bookmark files, remove URL duplicates, and write the result to a new HTML file."""
    roots = [parse_file(f) for f in files]
    names = [click.format_filename(f) for f in files]
    merged = merge_folders(roots, names) if len(roots) > 1 else roots[0]

    removed = remove_duplicates(merged)
    if not keep_empty_folders:
        remove_empty_folders(merged)

    write_file(merged, output)
    console.print(
        f"[green]Removed {removed} duplicate bookmarks.[/green] "
        f"{merged.count_bookmarks()} bookmarks remain -> [bold]{output}[/bold]"
    )


@main.command(name="list-duplicates")
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
def list_duplicates(files: tuple[str, ...]) -> None:
    """List duplicate bookmark groups in detail (doesn't modify any file)."""
    roots = [parse_file(f) for f in files]
    names = [click.format_filename(f) for f in files]
    merged = merge_folders(roots, names) if len(roots) > 1 else roots[0]

    groups = find_duplicates(merged)
    if not groups:
        console.print("[green]No duplicate bookmarks found.[/green]")
        return
    for g in groups:
        console.print(f"\n[bold yellow]{g.normalized_url}[/bold yellow]")
        console.print(f"  kept   : {g.kept.title}")
        for r in g.removed:
            console.print(f"  dropped: {r.title}")
    console.print(f"\n[bold]Total: {len(groups)} group(s), {sum(len(g.removed) for g in groups)} redundant bookmark(s).[/bold]")


@main.command()
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("-o", "--output", required=True, type=click.Path(), help="Output HTML file.")
@click.option("--min-group-size", default=2, show_default=True, help="Minimum bookmark count for a domain to get its own folder.")
@click.option("--dedupe/--no-dedupe", default=True, show_default=True, help="Remove duplicates before organizing.")
def organize(files: tuple[str, ...], output: str, min_group_size: int, dedupe: bool) -> None:
    """Merge files, (optionally) remove duplicates, then group bookmarks by
    domain into folders, and write the result to a new HTML file."""
    roots = [parse_file(f) for f in files]
    names = [click.format_filename(f) for f in files]
    merged = merge_folders(roots, names) if len(roots) > 1 else roots[0]

    if dedupe:
        remove_duplicates(merged)

    organized = organize_by_domain(merged, min_group_size=min_group_size)
    write_file(organized, output)
    console.print(
        f"[green]Organized {organized.count_bookmarks()} bookmarks into "
        f"{len(organized.subfolders)} folder(s) by domain[/green] -> [bold]{output}[/bold]"
    )


@main.command()
@click.argument("files", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("-o", "--output", required=True, type=click.Path(), help="Output HTML file.")
def merge(files: tuple[str, ...], output: str) -> None:
    """Just merge multiple bookmark files (from different browsers) into
    one file, keeping each file's original folder structure (no dedupe)."""
    roots = [parse_file(f) for f in files]
    names = [click.format_filename(f) for f in files]
    merged = merge_folders(roots, names)
    write_file(merged, output)
    console.print(f"[green]Merged {merged.count_bookmarks()} bookmarks[/green] -> [bold]{output}[/bold]")


@main.command(name="list-folders")
@click.argument("file", type=click.Path(exists=True))
def list_folders(file: str) -> None:
    """Print the folder tree along with the bookmark count in each folder."""
    root = parse_file(file)

    def show(folder: Folder, depth: int = 0) -> None:
        if folder.name != "root":
            console.print("  " * depth + f"[cyan]{folder.name}[/cyan] ({len(folder.bookmarks)})")
        for sub in folder.subfolders:
            show(sub, depth + (0 if folder.name == "root" else 1))

    show(root)


@main.command(name="add-url")
@click.argument("url")
@click.option("--title", default=None, help="Display title. Defaults to the URL.")
@click.option("--folder", default="", help='Folder path, "/"-separated, e.g. "Dev/APIs".')
@click.option("--tags", default="", help='Comma-separated list of tags.')
@click.option("--description", default=None, help="Note/description (exported as a <DD> tag).")
@click.option("--config", "config_path", default="config.json", show_default=True, type=click.Path())
def add_url(url: str, title: str | None, folder: str, tags: str, description: str | None, config_path: str) -> None:
    """Add a URL to config.json (creating the file if needed)."""
    entry = add_entry(config_path, url=url, title=title, folder=folder, tags=tags, description=description)
    console.print(
        f"[green]Added[/green] {entry.title} -> {entry.url} "
        f"(folder: {'/'.join(entry.folder) or '(root)'}) to [bold]{config_path}[/bold]"
    )


@main.command()
@click.option("-i", "--input", "input_files", multiple=True, type=click.Path(exists=True), help="Source bookmark file(s) (repeat -i for multiple).")
@click.option("--config", "config_path", default=None, type=click.Path(exists=True), help="config.json file containing manually-added URLs.")
@click.option("-o", "--output-dir", required=True, type=click.Path(), help="Directory to write the output HTML files into.")
@click.option("--browsers", default=",".join(BROWSERS), show_default=True, help="Comma-separated list of target browsers.")
@click.option("--organize/--no-organize", default=False, show_default=True, help="Re-organize by domain before exporting.")
@click.option("--min-group-size", default=2, show_default=True, help="Used with --organize: minimum bookmark count for a domain to get its own folder.")
def build(
    input_files: tuple[str, ...],
    config_path: str | None,
    output_dir: str,
    browsers: str,
    organize: bool,
    min_group_size: int,
) -> None:
    """Full pipeline: read source file(s) (+ config.json) -> merge -> remove
    duplicates -> (optionally) organize by domain -> write ONE HTML file PER
    BROWSER (so importing doesn't conflict/create an "Imported" folder)."""
    if not input_files and not config_path:
        raise click.UsageError("Need at least one -i/--input file or --config.")

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
    table = Table(title="Exported per browser")
    table.add_column("Browser")
    table.add_column("File")
    table.add_column("Bookmarks", justify="right")
    for b in browser_list:
        per_browser = build_for_browser(merged, b)
        out_path = out_dir / f"{b}.html"
        write_file(per_browser, out_path)
        table.add_row(b, str(out_path), str(per_browser.count_bookmarks()))

    console.print(
        f"Source: {merged.count_bookmarks() + n_dupes} bookmarks, "
        f"added {n_manual} from config, removed {n_dupes} duplicate(s)."
    )
    console.print(table)


@main.command(name="check-links")
@click.argument("file", type=click.Path(exists=True))
@click.option("--workers", default=10, show_default=True, help="Number of concurrent connections.")
@click.option("--timeout", default=10.0, show_default=True, help="Per-request timeout (seconds).")
@click.option("--remove-broken/--no-remove-broken", default=False, show_default=True, help="Also remove broken links and write the result to --output.")
@click.option("-o", "--output", default=None, type=click.Path(), help="HTML file to write after removing broken links (required with --remove-broken).")
@click.option("--report", default=None, type=click.Path(), help="Write a detailed report (JSON) to this file.")
def check_links_cmd(
    file: str, workers: int, timeout: float, remove_broken: bool, output: str | None, report: str | None
) -> None:
    """Check whether every bookmark in FILE is alive or dead (404/connection
    error/...). Runs concurrently via a thread pool; large files (a few
    hundred bookmarks) can take a couple of minutes."""
    root = parse_file(file)
    total = root.count_bookmarks()

    with click.progressbar(length=total, label="Checking links") as bar:
        def _progress(done: int, _total: int) -> None:
            bar.update(done - bar.pos)

        results = check_links(root, max_workers=workers, timeout=timeout, progress_cb=_progress)

    broken = [r for r in results if not r.ok]
    table = Table(title=f"Broken links ({len(broken)}/{total})")
    table.add_column("Status")
    table.add_column("Title")
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
        console.print(f"Wrote the full report -> [bold]{report}[/bold]")

    if remove_broken:
        if not output:
            raise click.UsageError("--output is required with --remove-broken.")
        broken_urls = {r.bookmark.url for r in broken}
        n = remove_broken_bookmarks(root, broken_urls)
        remove_empty_folders(root)
        write_file(root, output)
        console.print(f"[green]Removed {n} broken link(s)[/green] -> [bold]{output}[/bold]")


if __name__ == "__main__":
    main()
