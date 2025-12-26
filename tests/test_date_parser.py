"""Tests for content-based date parsing."""

from datetime import datetime

from bob.ingest.date_parser import extract_date_from_content, parse_date_hint


def test_extract_date_from_frontmatter():
    content = """---
title: Test
date: 2024-06-01
---
# Heading
Body text.
"""
    parsed = extract_date_from_content(content)
    assert parsed == datetime(2024, 6, 1)


def test_extract_date_from_iso_text():
    parsed = extract_date_from_content("Updated: 2025-01-15")
    assert parsed == datetime(2025, 1, 15)


def test_extract_date_from_month_name():
    parsed = extract_date_from_content("Published on January 15, 2025.")
    assert parsed == datetime(2025, 1, 15)


def test_extract_date_from_day_month():
    parsed = extract_date_from_content("Dated 15 January 2025.")
    assert parsed == datetime(2025, 1, 15)


def test_parse_date_hint_handles_iso_time():
    parsed = parse_date_hint("2025-01-15T10:00:00Z")
    assert parsed == datetime(2025, 1, 15, 10, 0, 0)


def test_parse_date_hint_ignores_ambiguous_numeric():
    assert parse_date_hint("03/04/2025") is None


def test_parse_date_hint_prefers_updated_line():
    parsed = parse_date_hint("Created 2024-01-01\nUpdated 2024-06-15")
    assert parsed == datetime(2024, 6, 15)


def test_parse_date_hint_handles_as_of():
    parsed = parse_date_hint("As of January 5, 2025 the plan was updated.")
    assert parsed == datetime(2025, 1, 5)
