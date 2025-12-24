"""Base classes for document parsing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class DocumentSection:
    """A section within a document with location information."""

    content: str
    locator_type: str  # 'heading', 'page', 'paragraph', 'sheet', 'section', 'line'
    locator_value: dict[str, Any]  # e.g., {"heading": "...", "start_line": 1, "end_line": 10}
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """A parsed document with sections and metadata."""

    source_path: str
    source_type: str
    content: str  # Full content for hashing
    sections: list[DocumentSection]
    title: str | None = None
    source_date: datetime | None = None
    language: str = "en"
    metadata: dict[str, Any] = field(default_factory=dict)


class Parser(ABC):
    """Base class for document parsers."""

    # File extensions this parser handles
    extensions: list[str] = []

    @abstractmethod
    def parse(self, path: Path) -> ParsedDocument:
        """Parse a document and return structured sections.

        Args:
            path: Path to the document.

        Returns:
            ParsedDocument with sections and metadata.
        """
        pass

    @abstractmethod
    def can_parse(self, path: Path) -> bool:
        """Check if this parser can handle the given file.

        Args:
            path: Path to check.

        Returns:
            True if this parser can handle the file.
        """
        pass

    def get_file_date(self, path: Path) -> datetime | None:
        """Get the modification date of a file.

        Args:
            path: Path to the file.

        Returns:
            Modification datetime or None.
        """
        try:
            stat = path.stat()
            return datetime.fromtimestamp(stat.st_mtime)
        except OSError:
            return None
