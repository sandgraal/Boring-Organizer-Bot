"""Tests for connector endpoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from bob.api.app import create_app
from bob.config import Config, DefaultsConfig, PathsConfig, PermissionsConfig

BOOKMARKS_HTML = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
<DL><p>
  <DT><A HREF="https://example.com">Example</A>
  <DT><A HREF="https://openai.com">OpenAI</A>
</DL><p>
"""


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app)


def _make_config(tmp_path: Path, *, enabled: bool, scope: int) -> Config:
    return Config(
        defaults=DefaultsConfig(project="main", language="en"),
        paths=PathsConfig(vault=tmp_path / "vault"),
        permissions=PermissionsConfig(
            default_scope=scope,
            enabled_connectors={"browser_saves": enabled, "calendar_import": False},
            allowed_vault_paths=["vault/manual-saves"],
        ),
    )


def test_bookmarks_import_creates_notes(tmp_path: Path, client: TestClient) -> None:
    bookmarks_path = tmp_path / "bookmarks.html"
    bookmarks_path.write_text(BOOKMARKS_HTML, encoding="utf-8")

    config = _make_config(tmp_path, enabled=True, scope=2)
    payload = {
        "source_path": str(bookmarks_path),
        "project": "docs",
        "language": "en",
    }

    with patch("bob.api.routes.connectors.get_config", return_value=config):
        response = client.post("/connectors/bookmarks/import", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 2
    assert len(data["created_paths"]) == 2
    for path_str in data["created_paths"]:
        note_path = Path(path_str)
        assert note_path.exists()
        content = note_path.read_text(encoding="utf-8")
        assert "connector/bookmarks" in content


def test_highlight_creates_note(tmp_path: Path, client: TestClient) -> None:
    config = _make_config(tmp_path, enabled=True, scope=2)
    payload = {
        "text": "Important highlight text",
        "source_url": "https://example.com",
        "project": "notes",
        "language": "en",
    }

    with patch("bob.api.routes.connectors.get_config", return_value=config):
        response = client.post("/connectors/highlights", json=payload)

    assert response.status_code == 200
    data = response.json()
    note_path = Path(data["file_path"])
    assert note_path.exists()
    content = note_path.read_text(encoding="utf-8")
    assert "Important highlight text" in content
    assert "connector/highlight" in content


def test_connectors_blocked_when_disabled(tmp_path: Path, client: TestClient) -> None:
    config = _make_config(tmp_path, enabled=False, scope=2)
    payload = {
        "text": "Blocked highlight",
        "source_url": "https://example.com",
    }

    with patch("bob.api.routes.connectors.get_config", return_value=config):
        response = client.post("/connectors/highlights", json=payload)

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "CONNECTOR_DISABLED"
