"""Parser registry for document types."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bob.ingest.base import Parser

# Registry of parsers by extension
_parsers: dict[str, "Parser"] = {}


def register_parser(parser: "Parser") -> None:
    """Register a parser for its extensions.

    Args:
        parser: Parser instance to register.
    """
    for ext in parser.extensions:
        _parsers[ext.lower()] = parser


def get_parser(path: Path) -> "Parser | None":
    """Get a parser for the given file path.

    Args:
        path: Path to the file.

    Returns:
        Parser instance or None if no parser found.
    """
    ext = path.suffix.lower()
    return _parsers.get(ext)


def init_parsers() -> None:
    """Initialize and register all built-in parsers."""
    from bob.ingest.markdown import MarkdownParser
    from bob.ingest.pdf import PDFParser
    from bob.ingest.word import WordParser
    from bob.ingest.excel import ExcelParser
    from bob.ingest.recipe import RecipeParser

    register_parser(MarkdownParser())
    register_parser(PDFParser())
    register_parser(WordParser())
    register_parser(ExcelParser())
    register_parser(RecipeParser())


# Auto-initialize on import
init_parsers()
