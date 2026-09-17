from favorites_manager.config import ConfigError, load_config
from favorites_manager.dedupe import find_duplicates, remove_duplicates
from favorites_manager.parser import parse_html
from favorites_manager.writer import to_html

SAMPLE = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks</H1>
<DL><p>
    <DT><H3>Folder A</H3>
    <DL><p>
        <DT><A HREF="https://example.com/">Example</A>
        <DT><A HREF="https://example.com">Example (no trailing slash)</A>
        <DT><H3>Sub Folder</H3>
        <DL><p>
            <DT><A HREF="https://other.com/page">Other</A>
        </DL><p>
    </DL><p>
</DL><p>
"""


def test_parse_counts():
    root = parse_html(SAMPLE)
    assert root.count_bookmarks() == 3
    folder_a = root.subfolders[0]
    assert folder_a.name == "Folder A"
    assert len(folder_a.bookmarks) == 2
    assert len(folder_a.subfolders) == 1


def test_find_duplicates_normalizes_trailing_slash():
    root = parse_html(SAMPLE)
    groups = find_duplicates(root)
    assert len(groups) == 1
    assert groups[0].normalized_url == "https://example.com"


def test_remove_duplicates_and_roundtrip():
    root = parse_html(SAMPLE)
    removed = remove_duplicates(root)
    assert removed == 1
    assert root.count_bookmarks() == 2

    html = to_html(root)
    reparsed = parse_html(html)
    assert reparsed.count_bookmarks() == 2


def test_remove_duplicates_merges_tags_and_description():
    html = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
<DL><p>
    <DT><A HREF="https://example.com/" TAGS="a,b">Example</A>
    <DT><A HREF="https://example.com" TAGS="b,c">Example dup</A>
    <DD>description from the duplicate
</DL><p>
"""
    root = parse_html(html)
    removed = remove_duplicates(root)
    assert removed == 1
    kept = root.bookmarks[0]
    assert set(kept.tags) == {"a", "b", "c"}
    assert kept.description == "description from the duplicate"


def test_load_config_rejects_malformed_json(tmp_path):
    bad = tmp_path / "config.json"
    bad.write_text('{"bookmarks": [{"url": "https://x.com",}]}', encoding="utf-8")
    try:
        load_config(bad)
        assert False, "expected ConfigError"
    except ConfigError as exc:
        assert "invalid JSON" in str(exc)


def test_load_config_rejects_missing_url_field(tmp_path):
    bad = tmp_path / "config.json"
    bad.write_text('{"bookmarks": [{"title": "no url"}]}', encoding="utf-8")
    try:
        load_config(bad)
        assert False, "expected ConfigError"
    except ConfigError as exc:
        assert "bookmarks[0]" in str(exc)


def test_load_config_accepts_valid_entry(tmp_path):
    good = tmp_path / "config.json"
    good.write_text(
        '{"bookmarks": [{"url": "https://example.com", "title": "Ex", "folder": "A/B"}]}',
        encoding="utf-8",
    )
    entries = load_config(good)
    assert len(entries) == 1
    assert entries[0].url == "https://example.com"
    assert entries[0].folder == ("A", "B")
