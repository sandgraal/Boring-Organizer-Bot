"""Tests for the MCP JSON-RPC server."""

from __future__ import annotations

import json
from unittest.mock import patch

from fastapi.testclient import TestClient

from bob.agents.mcp_server import create_app
from bob.agents.tools import AgentResult


def test_tools_list_includes_expected_tools() -> None:
    """Tools list includes core MCP tools."""
    client = TestClient(create_app())
    response = client.post(
        "/",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
    )

    assert response.status_code == 200
    payload = response.json()
    tools = payload["result"]["tools"]
    names = {tool["name"] for tool in tools}
    assert {"ask", "list_projects", "index_status", "read_note", "write_note"} <= names


def test_tools_call_ask_returns_agent_result() -> None:
    """Ask tool returns serialized AgentResult."""
    client = TestClient(create_app())
    fake_result = AgentResult(success=True, message="ok", data={"answer": "hi"})

    with patch("bob.agents.mcp_server.ask", return_value=fake_result):
        response = client.post(
            "/",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "ask", "arguments": {"question": "hi"}},
            },
        )

    assert response.status_code == 200
    payload = response.json()
    content = payload["result"]["content"][0]["text"]
    decoded = json.loads(content)
    assert decoded["tool"] == "ask"
    assert decoded["data"]["success"] is True
    assert decoded["data"]["message"] == "ok"
