"""Parser for browser bookmarks export files."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from bob.ingest.base import DocumentSection, ParsedDocument, Parser

BOOKMARKS_SIGNATURE = "NETSCAPE-Bookmark-file-1"


@dataclass(frozen=True)
class BookmarkEntry:
    """Represents a bookmark entry from an export file."""

    title: str
    url: str
    folder: list[str]
    added_at: datetime | None


class _BookmarkHTMLParser(HTMLParser):
    """HTML parser for Netscape bookmark exports."""

    def __init__(self) -> None:
        super().__init__()
        self.entries: list[BookmarkEntry] = []
        self._folder_stack: list[str] = []
        self._dl_stack: list[bool] = []
        self._pending_folder: str | None = None
        self._in_h3 = False
        self._in_a = False
        self._text_parts: list[str] = []
        self._current_link: dict[str, Any] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs_dict = {key.lower(): value for key, value in attrs}
        if tag == "h3":
            self._in_h3 = True
            self._text_parts = []
        elif tag == "a":
            href = attrs_dict.get("href") or ""
            if href:
                self._in_a = True
                self._text_parts = []
                self._current_link = {
                    "url": href,
                    "add_date": attrs_dict.get("add_date"),
                }
        elif tag == "dl":
            if self._pending_folder:
                self._folder_stack.append(self._pending_folder)
                self._dl_stack.append(True)
                self._pending_folder = None
            else:
                self._dl_stack.append(False)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "h3":
            self._in_h3 = False
            title = "".join(self._text_parts).strip()
            if title:
                self._pending_folder = title
        elif tag == "a":
            if not self._in_a:
                return
            self._in_a = False
            title = "".join(self._text_parts).strip()
            url = self._current_link.get("url") or ""
            added_at = _parse_add_date(self._current_link.get("add_date"))
            if url:
                entry = BookmarkEntry(
                    title=title or url,
                    url=url,
                    folder=list(self._folder_stack),
                    added_at=added_at,
                )
                self.entries.append(entry)
            self._current_link = {}
        elif tag == "dl":
            if not self._dl_stack:
                return
            had_folder = self._dl_stack.pop()
            if had_folder and self._folder_stack:
                self._folder_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._in_h3 or self._in_a:
            self._text_parts.append(data)


def _parse_add_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return None
    try:
        return datetime.fromtimestamp(timestamp)
    except (OSError, OverflowError, ValueError):
        return None


def parse_bookmarks_html(content: str) -> list[BookmarkEntry]:
    """Parse bookmarks export HTML into entries."""
    if BOOKMARKS_SIGNATURE not in content and "<a" not in content.lower():
        raise ValueError("Not a bookmarks export file.")

    parser = _BookmarkHTMLParser()
    parser.feed(content)
    entries = parser.entries
    if not entries:
        raise ValueError("No bookmark entries found.")
    return entries


def parse_bookmarks_file(path: Path) -> list[BookmarkEntry]:
    """Read and parse a bookmarks export file."""
    content = path.read_text(encoding="utf-8", errors="ignore")
    return parse_bookmarks_html(content)


class BookmarksParser(Parser):
    """Parser for bookmarks export files."""

    extensions = [".html", ".htm"]

    def parse(self, path: Path) -> ParsedDocument:
        """Parse a bookmarks HTML export file into a structured document.

        Args:
            path: Path to the bookmarks HTML file.

        Returns:
            ParsedDocument with each bookmark as a section.
        """
        content = path.read_text(encoding="utf-8", errors="ignore")
        entries = parse_bookmarks_html(content)

        sections: list[DocumentSection] = []
        for entry in entries:
            folder_label = " / ".join(entry.folder) if entry.folder else "Unfiled"
            title = entry.title or entry.url
            section_content = f"[{title}]({entry.url})"
            if folder_label:
                section_content = f"{section_content}\nFolder: {folder_label}"
            locator_value = {"section": title}
            if entry.folder:
                locator_value["folder"] = folder_label
            if entry.added_at:
                locator_value["added_at"] = entry.added_at.isoformat()
            sections.append(
                DocumentSection(
                    content=section_content,
                    locator_type="section",
                    locator_value=locator_value,
                    metadata={"url": entry.url, "folder": folder_label},
                )
            )

        return ParsedDocument(
            source_path=str(path),
            source_type="bookmarks",
            content=content,
            sections=sections,
            title=path.stem,
            source_date=self.get_source_date(path, content),
            language="en",
        )

    def can_parse(self, path: Path) -> bool:
        """Check if a file is a parseable bookmarks export.

        Args:
            path: Path to check.

        Returns:
            True if the file appears to be a bookmarks HTML export.
        """
        if path.suffix.lower() not in self.extensions:
            return False
        try:
            with path.open(encoding="utf-8", errors="ignore") as handle:
                snippet = handle.read(4096)
        except OSError:
            return False
        lowered = snippet.lower()
        return BOOKMARKS_SIGNATURE in snippet or (
            "bookmark" in lowered and "<dl" in lowered and "<a" in lowered
        )
