"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from bob.db.database import get_database

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str | int]:
    """Health check endpoint.

    Returns server status, version, and basic database stats.
    """
    try:
        db = get_database()
        stats = db.get_stats()
        db_status = "connected"
    except Exception:
        db_status = "error"
        stats = {"document_count": 0}

    return {
        "status": "healthy",
        "version": "1.0.0",
        "database": db_status,
        "indexed_documents": stats.get("document_count", 0),
    }
