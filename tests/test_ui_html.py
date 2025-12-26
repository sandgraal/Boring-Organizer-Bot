"""Basic HTML smoke tests for UI scaffolding."""

from __future__ import annotations

from pathlib import Path


def test_new_note_modal_markup_exists() -> None:
    """UI includes the new note action and modal scaffolding."""
    html = Path("bob/ui/index.html").read_text(encoding="utf-8")
    assert 'id="new-note-btn"' in html
    assert 'id="note-modal"' in html
    assert 'id="note-form"' in html
    assert 'id="note-template"' in html
    assert 'id="note-target-path"' in html
    assert 'id="note-project-options"' in html
    assert 'id="permissions-scope"' in html
    assert 'id="permissions-vault-root"' in html
    assert 'id="permissions-paths"' in html
    assert 'id="permissions-connectors"' in html


def test_fix_queue_query_action_hook_exists() -> None:
    """Fix Queue supports rerunning repeated question tasks."""
    js = Path("bob/ui/static/js/app.js").read_text(encoding="utf-8")
    assert "data-fixqueue-query" in js
    assert "handleFixQueueQuery" in js


def test_fix_queue_project_filter_exists() -> None:
    """Health view exposes a Fix Queue project filter."""
    html = Path("bob/ui/index.html").read_text(encoding="utf-8")
    assert 'id="fixqueue-project-filter"' in html


def test_language_filter_markup_exists() -> None:
    """Ask filters include a language input."""
    html = Path("bob/ui/index.html").read_text(encoding="utf-8")
    assert 'id="language-filter"' in html


def test_locator_format_handles_section_and_line() -> None:
    """Source locator formatting includes section and line support."""
    js = Path("bob/ui/static/js/app.js").read_text(encoding="utf-8")
    assert 'case "section"' in js
    assert 'case "line"' in js


def test_connectors_controls_exist() -> None:
    """Settings include connector import controls."""
    html = Path("bob/ui/index.html").read_text(encoding="utf-8")
    assert 'id="connectors-bookmarks-path"' in html
    assert 'id="connectors-bookmarks-import-btn"' in html
    assert 'id="connectors-highlight-text"' in html
    assert 'id="connectors-highlight-save-btn"' in html
