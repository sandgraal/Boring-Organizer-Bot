"""Markdown document parser."""

from __future__ import annotations

import re
from pathlib import Path

from bob.ingest.base import DocumentSection, ParsedDocument, Parser


class MarkdownParser(Parser):
    """Parser for Markdown documents."""

    extensions = [".md", ".markdown"]

    def can_parse(self, path: Path) -> bool:
        """Check if this parser can handle the given file."""
        return path.suffix.lower() in self.extensions

    def parse(self, path: Path) -> ParsedDocument:
        """Parse a Markdown document into sections.

        Splits on headings to create logical sections with line-level locators.

        Raises:
            UnicodeDecodeError: If file cannot be decoded as UTF-8.
            OSError: If file cannot be read.
        """
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Try common fallback encodings
            for encoding in ["latin-1", "cp1252", "iso-8859-1"]:
                try:
                    content = path.read_text(encoding=encoding)
                    break
                except (UnicodeDecodeError, LookupError):
                    continue
            else:
                raise UnicodeDecodeError(
                    "utf-8",
                    b"",
                    0,
                    0,
                    f"Unable to decode {path} with UTF-8 or common fallback encodings",
                )

        lines = content.split("\n")

        sections: list[DocumentSection] = []
        current_section: list[str] = []
        current_heading: str | None = None
        current_heading_level: int = 0
        section_start_line: int = 1

        # Pattern for ATX headings (# Heading)
        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$")

        for i, line in enumerate(lines, start=1):
            match = heading_pattern.match(line)

            if match:
                # Save previous section
                if current_section:
                    sections.append(
                        DocumentSection(
                            content="\n".join(current_section).strip(),
                            locator_type="heading",
                            locator_value={
                                "heading": current_heading or "(document start)",
                                "heading_level": current_heading_level,
                                "start_line": section_start_line,
                                "end_line": i - 1,
                            },
                        )
                    )

                # Start new section
                current_heading_level = len(match.group(1))
                current_heading = match.group(2).strip()
                current_section = [line]
                section_start_line = i
            else:
                current_section.append(line)

        # Don't forget the last section
        if current_section:
            sections.append(
                DocumentSection(
                    content="\n".join(current_section).strip(),
                    locator_type="heading",
                    locator_value={
                        "heading": current_heading or "(document start)",
                        "heading_level": current_heading_level,
                        "start_line": section_start_line,
                        "end_line": len(lines),
                    },
                )
            )

        # Extract title from first H1 or filename
        title = None
        for section in sections:
            if section.locator_value.get("heading_level") == 1:
                title = section.locator_value.get("heading")
                break
        if not title:
            title = path.stem

        return ParsedDocument(
            source_path=str(path),
            source_type="markdown",
            content=content,
            sections=sections,
            title=title,
            source_date=self.get_source_date(path, content),
        )
