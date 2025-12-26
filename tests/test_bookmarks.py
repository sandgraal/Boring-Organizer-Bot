"""Tests for bookmarks parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from bob.ingest.bookmarks import BookmarksParser, parse_bookmarks_html

SAMPLE_HTML = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks</H1>
<DL><p>
  <DT><H3 ADD_DATE="1700000000">Folder One</H3>
  <DL><p>
    <DT><A HREF="https://example.com" ADD_DATE="1700000001">Example</A>
  </DL><p>
  <DT><A HREF="https://openai.com">OpenAI</A>
</DL><p>
"""


def test_parse_bookmarks_html_extracts_entries() -> None:
    entries = parse_bookmarks_html(SAMPLE_HTML)
    assert len(entries) == 2
    assert entries[0].title == "Example"
    assert entries[0].url == "https://example.com"
    assert entries[0].folder == ["Folder One"]
    assert entries[1].title == "OpenAI"


def test_bookmarks_parser_builds_sections(tmp_path: Path) -> None:
    path = tmp_path / "bookmarks.html"
    path.write_text(SAMPLE_HTML, encoding="utf-8")

    parser = BookmarksParser()
    document = parser.parse(path)

    assert document.source_type == "bookmarks"
    assert len(document.sections) == 2
    assert document.sections[0].locator_type == "section"
    assert "Example" in document.sections[0].content
    assert "Folder One" in document.sections[0].content


def test_parse_bookmarks_html_rejects_invalid_input() -> None:
    with pytest.raises(ValueError):
        parse_bookmarks_html("Not a bookmarks export")
