"""Permissions endpoint for UI visibility."""

from __future__ import annotations

from fastapi import APIRouter

from bob.api.schemas import PermissionsResponse
from bob.config import get_config

router = APIRouter()


@router.get("/permissions", response_model=PermissionsResponse)
def permissions_status() -> PermissionsResponse:
    """Return current permission scope and vault path configuration."""
    config = get_config()
    return PermissionsResponse(
        default_scope=config.permissions.default_scope,
        enabled_connectors=config.permissions.enabled_connectors,
        allowed_vault_paths=config.permissions.allowed_vault_paths,
        vault_root=str(config.paths.vault),
    )
