"""Tests for the markdown parser."""

from bob.ingest.markdown import MarkdownParser


class TestMarkdownParser:
    """Tests for markdown parsing."""

    def test_can_parse_md(self, temp_dir):
        parser = MarkdownParser()
        md_file = temp_dir / "test.md"
        md_file.write_text("# Test")
        assert parser.can_parse(md_file)

    def test_cannot_parse_other(self, temp_dir):
        parser = MarkdownParser()
        txt_file = temp_dir / "test.txt"
        txt_file.write_text("test")
        assert not parser.can_parse(txt_file)

    def test_parse_simple_document(self, sample_markdown):
        parser = MarkdownParser()
        doc = parser.parse(sample_markdown)

        assert doc.source_type == "markdown"
        assert doc.title == "Test Document"
        assert len(doc.sections) > 0

    def test_sections_have_locators(self, sample_markdown):
        parser = MarkdownParser()
        doc = parser.parse(sample_markdown)

        for section in doc.sections:
            assert section.locator_type == "heading"
            assert "heading" in section.locator_value
            assert "start_line" in section.locator_value
            assert "end_line" in section.locator_value

    def test_preserves_heading_hierarchy(self, sample_markdown):
        parser = MarkdownParser()
        doc = parser.parse(sample_markdown)

        headings = [s.locator_value.get("heading") for s in doc.sections]
        assert "Test Document" in headings or "(document start)" in headings
        assert "Section One" in headings
        assert "Subsection 1.1" in headings

    def test_empty_file(self, temp_dir):
        parser = MarkdownParser()
        empty = temp_dir / "empty.md"
        empty.write_text("")

        doc = parser.parse(empty)
        assert doc.source_type == "markdown"
        # May have zero sections or one empty section

    def test_no_headings(self, temp_dir):
        parser = MarkdownParser()
        no_headings = temp_dir / "plain.md"
        no_headings.write_text("Just plain text.\n\nAnother paragraph.")

        doc = parser.parse(no_headings)
        assert len(doc.sections) >= 1
        # Should create a section for document start
