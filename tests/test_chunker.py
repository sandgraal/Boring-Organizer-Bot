"""Tests for the chunking module."""

from bob.index.chunker import (
    Chunk,
    chunk_text,
    estimate_tokens,
    has_minimal_content,
    is_boilerplate,
    validate_chunk,
)


class TestEstimateTokens:
    """Tests for token estimation."""

    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_short_string(self):
        # ~4 chars per token
        result = estimate_tokens("hello world")  # 11 chars
        assert result == 2  # 11 // 4

    def test_longer_string(self):
        text = "a" * 100
        assert estimate_tokens(text) == 25


class TestChunkText:
    """Tests for text chunking."""

    def test_short_text_single_chunk(self):
        text = "Short paragraph."
        chunks = chunk_text(text, target_size=100)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_multiple_paragraphs(self):
        text = "Paragraph one.\n\nParagraph two.\n\nParagraph three."
        chunks = chunk_text(text, target_size=20, overlap=5)
        assert len(chunks) >= 1

    def test_preserves_content(self):
        text = "Important content that should not be lost."
        chunks = chunk_text(text, target_size=100)
        assert text in chunks[0]

    def test_respects_paragraph_boundaries(self):
        text = "Para one.\n\nPara two.\n\nPara three."
        chunks = chunk_text(text, target_size=50, min_size=5)
        # Content should be preserved across chunks
        full_content = "\n\n".join(chunks)
        assert "Para one" in full_content
        assert "Para three" in full_content


class TestChunkLocators:
    """Tests for chunk locator formatting."""

    def test_chunk_has_locator_info(self):
        chunk = Chunk(
            content="Test content",
            locator_type="heading",
            locator_value={"heading": "Test", "start_line": 1, "end_line": 5},
            token_count=10,
        )
        assert chunk.locator_type == "heading"
        assert chunk.locator_value["heading"] == "Test"
        assert chunk.locator_value["start_line"] == 1
        assert chunk.locator_value["end_line"] == 5


class TestIsBoilerplate:
    """Tests for boilerplate detection."""

    def test_copyright_notice(self):
        assert is_boilerplate("Copyright 2024 Some Company")

    def test_all_rights_reserved(self):
        assert is_boilerplate("All rights reserved")

    def test_table_of_contents(self):
        assert is_boilerplate("Table of Contents")

    def test_page_number(self):
        assert is_boilerplate("Page 5 of 10")
        assert is_boilerplate("page 12")

    def test_slide_number(self):
        assert is_boilerplate("1/10")
        assert is_boilerplate("5 / 20")

    def test_navigation_text(self):
        assert is_boilerplate("Click here")
        assert is_boilerplate("Back to top")

    def test_normal_text_not_boilerplate(self):
        assert not is_boilerplate("This is normal content about the topic.")
        assert not is_boilerplate("The implementation uses a database.")


class TestHasMinimalContent:
    """Tests for minimal content validation."""

    def test_sufficient_content(self):
        text = "This is a sentence with enough words to pass the minimum threshold."
        assert has_minimal_content(text)

    def test_too_few_words(self):
        text = "Too short."
        assert not has_minimal_content(text)

    def test_too_few_unique_words(self):
        # Repetitive content
        text = "the the the the the the the the the the"
        assert not has_minimal_content(text)

    def test_mostly_numbers(self):
        # Low alpha ratio
        text = "123 456 789 012 345 678 901 234 567 890 ab cd"
        assert not has_minimal_content(text)

    def test_real_content_passes(self):
        text = (
            "B.O.B is a local-first knowledge assistant that helps you organize "
            "documents, extract decisions, and search with citations."
        )
        assert has_minimal_content(text)


class TestValidateChunk:
    """Tests for complete chunk validation."""

    def test_valid_chunk_passes(self):
        chunk = Chunk(
            content="This is meaningful content with enough words to be useful for search.",
            locator_type="heading",
            locator_value={"heading": "Test"},
            token_count=15,
        )
        assert validate_chunk(chunk)

    def test_empty_chunk_fails(self):
        chunk = Chunk(
            content="",
            locator_type="heading",
            locator_value={"heading": "Test"},
            token_count=0,
        )
        assert not validate_chunk(chunk)

    def test_whitespace_chunk_fails(self):
        chunk = Chunk(
            content="   \n\t  ",
            locator_type="heading",
            locator_value={"heading": "Test"},
            token_count=1,
        )
        assert not validate_chunk(chunk)

    def test_too_short_chunk_fails(self):
        chunk = Chunk(
            content="Hi",
            locator_type="heading",
            locator_value={"heading": "Test"},
            token_count=1,
        )
        assert not validate_chunk(chunk)

    def test_boilerplate_chunk_fails(self):
        chunk = Chunk(
            content="Copyright 2024 All Rights Reserved",
            locator_type="heading",
            locator_value={"heading": "Test"},
            token_count=6,
        )
        assert not validate_chunk(chunk)
