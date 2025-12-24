"""PDF document parser."""

from __future__ import annotations

from pathlib import Path

from bob.ingest.base import DocumentSection, ParsedDocument, Parser


class PDFParser(Parser):
    """Parser for PDF documents."""

    extensions = [".pdf"]

    def can_parse(self, path: Path) -> bool:
        """Check if this parser can handle the given file."""
        return path.suffix.lower() in self.extensions

    def parse(self, path: Path) -> ParsedDocument:
        """Parse a PDF document into page-based sections."""
        from pypdf import PdfReader

        reader = PdfReader(path)
        sections: list[DocumentSection] = []
        full_content: list[str] = []

        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            full_content.append(text)

            if text.strip():
                sections.append(
                    DocumentSection(
                        content=text.strip(),
                        locator_type="page",
                        locator_value={
                            "page": page_num,
                            "total_pages": len(reader.pages),
                        },
                    )
                )

        # Try to extract title from metadata or first page
        title = None
        if reader.metadata and reader.metadata.title:
            title = reader.metadata.title
        elif sections:
            # Use first non-empty line as title
            first_lines = sections[0].content.split("\n")
            for line in first_lines:
                if line.strip():
                    title = line.strip()[:100]  # Limit title length
                    break

        return ParsedDocument(
            source_path=str(path),
            source_type="pdf",
            content="\n\n".join(full_content),
            sections=sections,
            title=title or path.stem,
            source_date=self.get_file_date(path),
        )
