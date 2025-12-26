"""Parser registry for document types."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bob.ingest.base import Parser

# Registry of parsers by extension
_parsers: dict[str, Parser] = {}


def register_parser(parser: Parser) -> None:
    """Register a parser for its extensions.

    Args:
        parser: Parser instance to register.
    """
    for ext in parser.extensions:
        _parsers[ext.lower()] = parser


def get_parser(path: Path) -> Parser | None:
    """Get a parser for the given file path.

    Args:
        path: Path to the file.

    Returns:
        Parser instance or None if no parser found.
    """
    ext = path.suffix.lower()
    parser = _parsers.get(ext)
    if parser is not None:
        if parser.can_parse(path):
            return parser
    for candidate in set(_parsers.values()):
        if candidate.can_parse(path):
            return candidate
    return None


def init_parsers() -> None:
    """Initialize and register all built-in parsers."""
    from bob.ingest.bookmarks import BookmarksParser
    from bob.ingest.excel import ExcelParser
    from bob.ingest.markdown import MarkdownParser
    from bob.ingest.pdf import PDFParser
    from bob.ingest.recipe import RecipeParser
    from bob.ingest.word import WordParser

    register_parser(MarkdownParser())
    register_parser(PDFParser())
    register_parser(WordParser())
    register_parser(ExcelParser())
    register_parser(RecipeParser())
    register_parser(BookmarksParser())


# Auto-initialize on import
init_parsers()
