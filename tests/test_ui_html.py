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


def test_fix_queue_query_action_hook_exists() -> None:
    """Fix Queue supports rerunning repeated question tasks."""
    js = Path("bob/ui/static/js/app.js").read_text(encoding="utf-8")
    assert "data-fixqueue-query" in js
    assert "handleFixQueueQuery" in js
