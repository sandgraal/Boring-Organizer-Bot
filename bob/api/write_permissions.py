"""Shared permission checks for template-based writes."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from bob.config import Config
from bob.db.database import get_database

TEMPLATE_WRITE_SCOPE = 3
CONNECTOR_WRITE_SCOPE = 2


def resolve_allowed_directories(config: Config) -> list[Path]:
    """Resolve configured allowed vault paths into absolute directories."""
    cwd = Path.cwd()
    vault_root = config.paths.vault.resolve()
    allowed_dirs: set[Path] = set()

    for entry in config.permissions.allowed_vault_paths:
        candidate = Path(entry)
        if candidate.is_absolute():
            allowed_dirs.add(candidate.resolve())
            continue

        parts = list(candidate.parts)
        if parts and parts[0] in {vault_root.name, "vault"}:
            parts = parts[1:]

        relative = Path(*parts) if parts else Path(".")
        allowed_dirs.add((vault_root / relative).resolve())
        allowed_dirs.add((cwd / candidate).resolve())

    return list(allowed_dirs)


def _log_permission_denial(
    *,
    action_name: str,
    project: str | None,
    target_path: Path,
    reason_code: str,
    scope_level: int | None = None,
    required_scope_level: int | None = None,
    allowed_paths: list[str] | None = None,
) -> None:
    """Persist permission denials without blocking the caller."""
    try:
        db = get_database()
        db.log_permission_denial(
            action_name=action_name,
            project=project,
            target_path=str(target_path),
            reason_code=reason_code,
            scope_level=scope_level,
            required_scope_level=required_scope_level,
            allowed_paths=allowed_paths,
        )
    except Exception:
        return


def ensure_allowed_write_path(
    action_name: str,
    project: str | None,
    target_path: Path,
    config: Config,
    *,
    required_scope_level: int = TEMPLATE_WRITE_SCOPE,
) -> None:
    """Validate that a write stays within allowed vault directories."""
    resolved_target = target_path.resolve()
    allowed_dirs = resolve_allowed_directories(config)
    if any(resolved_target.is_relative_to(dir_path) for dir_path in allowed_dirs):
        return

    allowed_paths = [str(dir_path) for dir_path in allowed_dirs]
    _log_permission_denial(
        action_name=action_name,
        project=project,
        target_path=target_path,
        reason_code="path",
        scope_level=config.permissions.default_scope,
        required_scope_level=required_scope_level,
        allowed_paths=allowed_paths,
    )

    raise HTTPException(
        status_code=403,
        detail={
            "code": "PERMISSION_DENIED",
            "message": "Target path is outside allowed vault directories.",
            "target_path": str(target_path),
            "allowed_paths": allowed_paths,
        },
    )


def ensure_scope_level(
    action_name: str,
    project: str | None,
    target_path: Path,
    config: Config,
    *,
    required_scope_level: int = TEMPLATE_WRITE_SCOPE,
) -> None:
    """Ensure the configured scope level permits scoped writes."""
    current = config.permissions.default_scope
    if current >= required_scope_level:
        return

    _log_permission_denial(
        action_name=action_name,
        project=project,
        target_path=target_path,
        reason_code="scope",
        scope_level=current,
        required_scope_level=required_scope_level,
    )

    raise HTTPException(
        status_code=403,
        detail={
            "code": "PERMISSION_DENIED",
            "message": f"Permission level {required_scope_level} required for {action_name}.",
            "scope_level": current,
            "required_scope_level": required_scope_level,
            "target_path": str(target_path),
        },
    )


def ensure_connector_enabled(
    connector_name: str,
    action_name: str,
    project: str | None,
    target_path: Path,
    config: Config,
    *,
    required_scope_level: int = CONNECTOR_WRITE_SCOPE,
) -> None:
    """Ensure a connector toggle is enabled before performing writes."""
    enabled = config.permissions.enabled_connectors.get(connector_name, False)
    if enabled:
        return

    allowed_dirs = resolve_allowed_directories(config)
    allowed_paths = [str(dir_path) for dir_path in allowed_dirs]
    _log_permission_denial(
        action_name=action_name,
        project=project,
        target_path=target_path,
        reason_code="connector",
        scope_level=config.permissions.default_scope,
        required_scope_level=required_scope_level,
        allowed_paths=allowed_paths,
    )

    raise HTTPException(
        status_code=403,
        detail={
            "code": "CONNECTOR_DISABLED",
            "message": f"Connector '{connector_name}' is disabled.",
            "target_path": str(target_path),
        },
    )
