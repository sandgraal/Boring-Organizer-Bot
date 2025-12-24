"""Documents endpoint for listing indexed documents."""

from __future__ import annotations

from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Query

from bob.api.schemas import DocumentInfo, DocumentListResponse
from bob.db.database import get_database

router = APIRouter()


@router.get("/documents", response_model=DocumentListResponse)
def list_documents(
    project: str | None = Query(None, description="Filter by project"),
    source_type: str | None = Query(None, description="Filter by source type"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
) -> DocumentListResponse:
    """List indexed documents with optional filters.

    Args:
        project: Filter by project name.
        source_type: Filter by document type (markdown, pdf, etc).
        page: Page number (1-based).
        page_size: Number of results per page.

    Returns:
        Paginated list of documents.
    """
    db = get_database()

    # Build query
    conditions = []
    params: list[Any] = []

    if project:
        conditions.append("project = ?")
        params.append(project)

    if source_type:
        conditions.append("source_type = ?")
        params.append(source_type)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Get total count
    count_cursor = db.conn.execute(
        f"SELECT COUNT(*) FROM documents WHERE {where_clause}",
        params,
    )
    total = count_cursor.fetchone()[0]

    # Get paginated results
    offset = (page - 1) * page_size
    cursor = db.conn.execute(
        f"""
        SELECT id, source_path, source_type, project, source_date,
               created_at, updated_at
        FROM documents
        WHERE {where_clause}
        ORDER BY updated_at DESC
        LIMIT ? OFFSET ?
        """,
        (*params, page_size, offset),
    )

    documents = []
    for row in cursor.fetchall():
        row_dict = dict(row)

        # Parse dates with contextlib.suppress
        source_date = None
        with suppress(ValueError, TypeError):
            if row_dict.get("source_date"):
                source_date = datetime.fromisoformat(row_dict["source_date"])

        created_at = datetime.now(UTC)
        with suppress(ValueError, TypeError):
            if row_dict.get("created_at"):
                created_at = datetime.fromisoformat(row_dict["created_at"])

        updated_at = datetime.now(UTC)
        with suppress(ValueError, TypeError):
            if row_dict.get("updated_at"):
                updated_at = datetime.fromisoformat(row_dict["updated_at"])

        documents.append(
            DocumentInfo(
                id=row_dict["id"],
                source_path=row_dict["source_path"],
                source_type=row_dict["source_type"],
                project=row_dict["project"],
                source_date=source_date,
                created_at=created_at,
                updated_at=updated_at,
            )
        )

    return DocumentListResponse(
        documents=documents,
        total=total,
        page=page,
        page_size=page_size,
    )
