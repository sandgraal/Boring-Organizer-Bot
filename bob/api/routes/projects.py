"""Projects endpoint for listing and managing projects."""

from __future__ import annotations

from fastapi import APIRouter

from bob.api.schemas import ProjectListResponse, ProjectStats
from bob.db.database import get_database

router = APIRouter()


@router.get("/projects", response_model=ProjectListResponse)
def list_projects() -> ProjectListResponse:
    """List all projects with their statistics.

    Returns:
        List of projects with document/chunk counts.
    """
    db = get_database()

    # Get all projects
    cursor = db.conn.execute("SELECT DISTINCT project FROM documents ORDER BY project")
    project_names = [row[0] for row in cursor.fetchall()]

    projects = []
    for name in project_names:
        # Get stats for this project
        stats = db.get_stats(project=name)

        projects.append(
            ProjectStats(
                name=name,
                document_count=stats.get("document_count", 0),
                chunk_count=stats.get("chunk_count", 0),
                source_types=stats.get("source_types", {}),
            )
        )

    return ProjectListResponse(
        projects=projects,
        total_projects=len(projects),
    )
