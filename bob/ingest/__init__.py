"""Ingest module for parsing various document types."""

from bob.ingest.base import ParsedDocument, Parser
from bob.ingest.registry import get_parser, register_parser

__all__ = [
    "ParsedDocument",
    "Parser",
    "get_parser",
    "register_parser",
]
