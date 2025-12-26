"""Tests for MCP permission enforcement."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from bob.agents.mcp_server import create_app
from bob.config import Config, PathsConfig, PermissionsConfig


def _config_for_vault(vault_root: Path, scope: int) -> Config:
    return Config(
        paths=PathsConfig(vault=vault_root),
        permissions=PermissionsConfig(
            default_scope=scope,
            allowed_vault_paths=[str(vault_root)],
        ),
    )


def test_write_note_denied_when_scope_low(monkeypatch, tmp_path: Path) -> None:
    """Write requests are denied when scope is below template-write level."""
    vault_root = tmp_path / "vault"
    vault_root.mkdir()
    config = _config_for_vault(vault_root, scope=0)
    monkeypatch.setattr("bob.agents.mcp_server.get_config", lambda: config)
    monkeypatch.setattr(
        "bob.api.write_permissions.get_database", lambda: MagicMock(), raising=False
    )

    client = TestClient(create_app())
    response = client.post(
        "/",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "write_note",
                "arguments": {"path": "note.md", "content": "hi"},
            },
        },
    )

    payload = response.json()
    assert payload["error"]["message"] == "PERMISSION_DENIED"


def test_read_note_denied_outside_allowed_paths(monkeypatch, tmp_path: Path) -> None:
    """Read requests are denied outside allowed vault paths."""
    vault_root = tmp_path / "vault"
    vault_root.mkdir()
    config = _config_for_vault(vault_root, scope=3)
    monkeypatch.setattr("bob.agents.mcp_server.get_config", lambda: config)

    client = TestClient(create_app())
    response = client.post(
        "/",
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "read_note",
                "arguments": {"path": str(tmp_path / "outside.md")},
            },
        },
    )

    payload = response.json()
    assert payload["error"]["message"] == "PERMISSION_DENIED"


def test_write_note_dry_run(monkeypatch, tmp_path: Path) -> None:
    """Dry-run writes return metadata without writing files."""
    vault_root = tmp_path / "vault"
    vault_root.mkdir()
    config = _config_for_vault(vault_root, scope=3)
    monkeypatch.setattr("bob.agents.mcp_server.get_config", lambda: config)

    client = TestClient(create_app())
    response = client.post(
        "/",
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "write_note",
                "arguments": {"path": "note.md", "content": "hello", "dry_run": True},
            },
        },
    )

    payload = response.json()
    content = payload["result"]["content"][0]["text"]
    decoded = json.loads(content)
    assert decoded["tool"] == "write_note"
    assert decoded["data"]["dry_run"] is True
    assert (vault_root / "note.md").exists() is False
