"""MCP-compatible JSON-RPC server for agent interoperability."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from bob.agents.tools import ask
from bob.api.write_permissions import (
    ensure_allowed_write_path,
    ensure_scope_level,
    resolve_allowed_directories,
)
from bob.config import Config, get_config
from bob.db.database import get_database


@dataclass(frozen=True)
class MCPError(Exception):
    """Structured error for JSON-RPC responses."""

    code: int
    message: str
    data: dict[str, Any] | None = None


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


TOOLS: list[dict[str, Any]] = [
    {
        "name": "ask",
        "description": "Run a grounded question against indexed sources.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {"type": "string"},
                "project": {"type": "string"},
                "top_k": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "required": ["question"],
        },
    },
    {
        "name": "list_projects",
        "description": "List indexed projects and document counts.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "index_status",
        "description": "Return indexing stats for a project or overall corpus.",
        "inputSchema": {
            "type": "object",
            "properties": {"project": {"type": "string"}},
        },
    },
    {
        "name": "read_note",
        "description": "Read a note from the vault (paths are scope-limited).",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_note",
        "description": "Write a note to the vault (honors scopes and dry-run).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "dry_run": {"type": "boolean"},
                "project": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
]


def _jsonrpc_error(
    request_id: Any, code: int, message: str, data: dict[str, Any] | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }
    if data is not None:
        payload["error"]["data"] = data
    return payload


def _jsonrpc_result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _require_str(params: dict[str, Any], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise MCPError(code=-32602, message=f"Missing or invalid '{key}' parameter.")
    return value.strip()


def _optional_str(params: dict[str, Any], key: str) -> str | None:
    value = params.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise MCPError(code=-32602, message=f"Invalid '{key}' parameter.")
    return value.strip()


def _optional_int(
    params: dict[str, Any], key: str, *, minimum: int | None = None, maximum: int | None = None
) -> int | None:
    value = params.get(key)
    if value is None:
        return None
    if not isinstance(value, int):
        raise MCPError(code=-32602, message=f"Invalid '{key}' parameter.")
    if minimum is not None and value < minimum:
        raise MCPError(code=-32602, message=f"'{key}' must be >= {minimum}.")
    if maximum is not None and value > maximum:
        raise MCPError(code=-32602, message=f"'{key}' must be <= {maximum}.")
    return value


def _resolve_target_path(raw_path: str, vault_root: Path) -> Path:
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate
    return vault_root / candidate


def _ensure_allowed_read_path(target_path: Path, config: Config) -> None:
    resolved_target = target_path.resolve()
    allowed_dirs = resolve_allowed_directories(config)
    if any(resolved_target.is_relative_to(dir_path) for dir_path in allowed_dirs):
        return
    raise MCPError(
        code=-32000,
        message="PERMISSION_DENIED",
        data={
            "message": "Target path is outside allowed vault directories.",
            "target_path": str(target_path),
            "allowed_paths": [str(path) for path in allowed_dirs],
        },
    )


def _tool_ask(params: dict[str, Any]) -> dict[str, Any]:
    question = _require_str(params, "question")
    project = _optional_str(params, "project")
    top_k = _optional_int(params, "top_k", minimum=1, maximum=20)
    config = get_config()
    result = ask(question=question, project=project, top_k=top_k or config.defaults.top_k)
    return result.to_dict()


def _tool_list_projects(_: dict[str, Any]) -> dict[str, Any]:
    db = get_database()
    stats = db.get_stats()
    counts = db.get_project_document_counts()
    return {
        "projects": stats.get("projects", []),
        "document_count": stats.get("document_count", 0),
        "chunk_count": stats.get("chunk_count", 0),
        "source_types": stats.get("source_types", {}),
        "project_counts": counts,
    }


def _tool_index_status(params: dict[str, Any]) -> dict[str, Any]:
    project = _optional_str(params, "project")
    db = get_database()
    return db.get_stats(project)


def _tool_read_note(params: dict[str, Any]) -> dict[str, Any]:
    raw_path = _require_str(params, "path")
    config = get_config()
    target_path = _resolve_target_path(raw_path, config.paths.vault)
    _ensure_allowed_read_path(target_path, config)
    if not target_path.exists():
        raise MCPError(
            code=-32000,
            message="NOT_FOUND",
            data={"message": "File does not exist.", "target_path": str(target_path)},
        )
    content = target_path.read_text(encoding="utf-8")
    return {"path": str(target_path), "content": content, "bytes": len(content)}


def _tool_write_note(params: dict[str, Any]) -> dict[str, Any]:
    raw_path = _require_str(params, "path")
    content = _require_str(params, "content")
    dry_run = bool(params.get("dry_run", False))
    project = _optional_str(params, "project")
    config = get_config()
    target_path = _resolve_target_path(raw_path, config.paths.vault)
    try:
        ensure_allowed_write_path("mcp-write-note", project, target_path, config)
        ensure_scope_level("mcp-write-note", project, target_path, config)
    except Exception as exc:  # noqa: BLE001
        detail = getattr(exc, "detail", None)
        payload = detail if isinstance(detail, dict) else {"message": str(exc)}
        raise MCPError(code=-32000, message="PERMISSION_DENIED", data=payload) from exc

    overwrote = target_path.exists()
    payload = {
        "path": str(target_path),
        "dry_run": dry_run,
        "bytes": len(content),
        "overwrote": overwrote,
    }
    if dry_run:
        return payload

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding="utf-8")
    return payload


TOOL_HANDLERS: dict[str, ToolHandler] = {
    "ask": _tool_ask,
    "list_projects": _tool_list_projects,
    "index_status": _tool_index_status,
    "read_note": _tool_read_note,
    "write_note": _tool_write_note,
}


def _handle_request(payload: dict[str, Any]) -> dict[str, Any] | None:
    request_id = payload.get("id")
    if payload.get("jsonrpc") != "2.0" or "method" not in payload:
        return _jsonrpc_error(request_id, -32600, "Invalid Request")

    method = payload.get("method")
    params = payload.get("params") or {}
    if method == "initialize":
        return _jsonrpc_result(
            request_id,
            {
                "serverInfo": {"name": "bob-mcp", "version": "0.1.0"},
                "capabilities": {"tools": {}},
            },
        )
    if method == "tools/list":
        return _jsonrpc_result(request_id, {"tools": TOOLS})
    if method == "tools/call":
        if not isinstance(params, dict):
            return _jsonrpc_error(request_id, -32602, "Invalid params")
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(tool_name, str) or tool_name not in TOOL_HANDLERS:
            return _jsonrpc_error(request_id, -32602, "Unknown tool")
        if not isinstance(arguments, dict):
            return _jsonrpc_error(request_id, -32602, "Invalid tool arguments")
        try:
            result_payload = TOOL_HANDLERS[tool_name](arguments)
        except MCPError as exc:
            return _jsonrpc_error(request_id, exc.code, exc.message, exc.data)
        except Exception as exc:  # noqa: BLE001
            return _jsonrpc_error(
                request_id, -32000, "Tool execution failed", {"message": str(exc)}
            )
        return _jsonrpc_result(
            request_id,
            {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {"tool": tool_name, "data": result_payload}, ensure_ascii=True
                        ),
                    }
                ]
            },
        )
    if method == "ping":
        return _jsonrpc_result(request_id, {"status": "ok"})
    return _jsonrpc_error(request_id, -32601, "Method not found")


async def _handle_mcp(request: Request) -> Response:
    payload = await request.json()
    if isinstance(payload, list):
        responses = [_handle_request(item) for item in payload if isinstance(item, dict)]
        responses = [resp for resp in responses if resp is not None]
        return JSONResponse(responses)
    if isinstance(payload, dict):
        response = _handle_request(payload)
        if response is None:
            return Response(status_code=204)
        return JSONResponse(response)
    return JSONResponse(_jsonrpc_error(None, -32600, "Invalid Request"))


def create_app() -> FastAPI:
    """Create the MCP JSON-RPC app."""
    app = FastAPI(title="B.O.B MCP", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_api_route("/", _handle_mcp, methods=["POST"])
    return app


def run_server(host: str | None = None, port: int | None = None) -> None:
    """Run the MCP server with uvicorn."""
    import uvicorn

    config = get_config()
    target_host = host or config.mcp.host
    target_port = port or config.mcp.port
    uvicorn.run(create_app(), host=target_host, port=target_port, log_level="info")
