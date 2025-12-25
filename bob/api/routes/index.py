"""Index endpoint for document indexing jobs."""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from bob.api.schemas import (
    IndexAlreadyRunningError,
    IndexError,
    IndexProgress,
    IndexRequest,
    IndexResponse,
    IndexStats,
)

router = APIRouter()


class IndexJobManager:
    """Manages indexing jobs (in-memory, single-user)."""

    def __init__(self) -> None:
        """Initialize the job manager."""
        self._current_job: dict[str, Any] | None = None
        self._lock = threading.Lock()

    def get_current_job(self) -> dict[str, Any] | None:
        """Get the current running job, if any."""
        with self._lock:
            return self._current_job

    def is_busy(self) -> bool:
        """Check if an indexing job is currently running."""
        with self._lock:
            return self._current_job is not None and self._current_job.get("status") == "running"

    def start_job(self, path: str, project: str, recursive: bool) -> dict[str, Any]:
        """Start a new indexing job.

        Args:
            path: Path to index.
            project: Project name.
            recursive: Whether to index recursively.

        Returns:
            Job information dict.

        Raises:
            ValueError: If a job is already running.
        """
        with self._lock:
            if self._current_job and self._current_job.get("status") == "running":
                raise ValueError(self._current_job["job_id"])

            job_id = f"idx_{uuid.uuid4().hex[:8]}"
            self._current_job = {
                "job_id": job_id,
                "status": "running",
                "path": path,
                "project": project,
                "recursive": recursive,
                "started_at": datetime.now(UTC),
                "completed_at": None,
                "progress": {
                    "total_files": 0,
                    "processed_files": 0,
                    "percent": 0,
                    "current_file": None,
                },
                "stats": {"documents": 0, "chunks": 0, "skipped": 0, "errors": 0},
                "errors": [],
            }
            return self._current_job.copy()

    def update_progress(
        self,
        total_files: int | None = None,
        processed_files: int | None = None,
        current_file: str | None = None,
    ) -> None:
        """Update job progress.

        Args:
            total_files: Total number of files.
            processed_files: Number of processed files.
            current_file: Currently processing file.
        """
        with self._lock:
        if not self._current_job:
            return
        if total_files is not None:
            self._current_job["progress"]["total_files"] = total_files
            if processed_files is not None:
                self._current_job["progress"]["processed_files"] = processed_files
            if current_file is not None:
                self._current_job["progress"]["current_file"] = current_file

            # Recalculate percent
            total = self._current_job["progress"]["total_files"]
            processed = self._current_job["progress"]["processed_files"]
            if total > 0:
            self._current_job["progress"]["percent"] = int((processed / total) * 100)

    def set_stats(self, stats: dict[str, int]) -> None:
        """Store cumulative stats for the job."""

        with self._lock:
            if self._current_job:
                self._current_job["stats"] = stats

    def add_error(self, file: str, error: str) -> None:
        """Add an error to the job.

        Args:
            file: File that caused the error.
            error: Error message.
        """
        with self._lock:
            if self._current_job:
                self._current_job["errors"].append({"file": file, "error": error})

    def complete_job(self, status: str = "completed") -> None:
        """Mark the job as complete.

        Args:
            status: Final status (completed or failed).
        """
        with self._lock:
            if self._current_job:
                self._current_job["status"] = status
                self._current_job["completed_at"] = datetime.now(UTC)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Get a job by ID.

        Args:
            job_id: Job ID to look up.

        Returns:
            Job information or None.
        """
        with self._lock:
            if self._current_job and self._current_job["job_id"] == job_id:
                return self._current_job.copy()
            return None


# Global job manager instance
_job_manager = IndexJobManager()


def get_job_manager() -> IndexJobManager:
    """Get the global job manager."""
    return _job_manager


def _run_index_job(path: str, project: str, recursive: bool) -> None:  # noqa: ARG001
    """Run the actual indexing job in a background thread.

    Args:
        path: Path to index.
        project: Project name.
        recursive: Whether to index recursively (currently always True).
    """
    from bob.index.indexer import count_indexable_targets, index_paths, is_git_url

    manager = get_job_manager()

    try:
        target_path = Path(path)
        if not is_git_url(path) and not target_path.exists():
            manager.add_error(path, f"Path does not exist: {path}")
            manager.complete_job("failed")
            return

        total_files = count_indexable_targets([target_path])
        manager.update_progress(total_files=total_files)

        processed_files = 0

        def report_progress(file_path: Path) -> None:
            nonlocal processed_files
            processed_files += 1
            manager.update_progress(
                processed_files=processed_files,
                current_file=str(file_path),
            )

        stats = index_paths(
            [target_path],
            project=project,
            language="en",
            progress_callback=report_progress,
        )
        manager.set_stats(stats)
        manager.complete_job("completed")
    except Exception as e:
        manager.add_error(path, str(e))
        manager.complete_job("failed")


@router.post("/index", response_model=IndexResponse)
def start_index_job(request: IndexRequest) -> IndexResponse:
    """Start a new indexing job.

    Args:
        request: Index request with path and project.

    Returns:
        Job information.

    Raises:
        HTTPException: If a job is already running.
    """
    manager = get_job_manager()

    try:
        job = manager.start_job(request.path, request.project, request.recursive)
    except ValueError as e:
        # Job already running
        raise HTTPException(
            status_code=409,
            detail={"error": IndexAlreadyRunningError(current_job_id=str(e)).model_dump()},
        ) from e

    # Start background indexing
    thread = threading.Thread(
        target=_run_index_job,
        args=(request.path, request.project, request.recursive),
        daemon=True,
    )
    thread.start()

    return IndexResponse(
        job_id=job["job_id"],
        status="started",
        path=job["path"],
        project=job["project"],
        started_at=job["started_at"],
        progress=IndexProgress(**job["progress"]),
        errors=[],
        stats=IndexStats(**job.get("stats", {})),
    )


@router.get("/index/{job_id}", response_model=IndexResponse)
def get_index_job(job_id: str) -> IndexResponse:
    """Get the status of an indexing job.

    Args:
        job_id: Job ID to look up.

    Returns:
        Job status and progress.

    Raises:
        HTTPException: If job not found.
    """
    manager = get_job_manager()
    job = manager.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return IndexResponse(
        job_id=job["job_id"],
        status=job["status"],
        path=job["path"],
        project=job["project"],
        started_at=job["started_at"],
        completed_at=job.get("completed_at"),
        progress=IndexProgress(**job["progress"]),
        errors=[IndexError(**e) for e in job.get("errors", [])],
        stats=IndexStats(**job.get("stats", {})),
    )
