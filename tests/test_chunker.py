"""Tests for the chunking module."""

from bob.index.chunker import Chunk, chunk_text, estimate_tokens


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
