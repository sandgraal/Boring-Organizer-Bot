"""Pydantic models for API requests and responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# === Ask Endpoint Models ===


class AskFilters(BaseModel):
    """Filters for search queries."""

    projects: list[str] | None = None
    types: list[str] | None = None
    date_after: datetime | None = None
    date_before: datetime | None = None
    language: str | None = None


class AskRequest(BaseModel):
    """Request body for POST /ask."""

    query: str = Field(..., description="Natural language query")
    filters: AskFilters | None = None
    top_k: int = Field(default=5, ge=1, le=20, description="Number of results to return")


class SourceLocator(BaseModel):
    """Locator information for a source chunk."""

    type: str
    heading: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    page: int | None = None
    total_pages: int | None = None
    paragraph_index: int | None = None
    sheet_name: str | None = None
    row_count: int | None = None
    section: str | None = None

    model_config = {"extra": "allow"}


class Source(BaseModel):
    """A source citation in search results."""

    id: int
    chunk_id: int
    file_path: str
    file_type: str
    locator: SourceLocator
    snippet: str = Field(..., description="Text content from the source")
    date: datetime | None = None
    date_confidence: str = Field(..., description="Confidence level: HIGH, MEDIUM, LOW, UNKNOWN")
    project: str
    may_be_outdated: bool = False
    similarity_score: float = Field(..., ge=0, le=1)
    git_repo: str | None = None
    git_commit: str | None = None


class AskFooter(BaseModel):
    """Footer information for ask response."""

    source_count: int
    date_confidence: str | None = None
    may_be_outdated: bool = False
    outdated_source_count: int = 0
    not_found: bool = False
    not_found_message: str | None = None


class AskResponse(BaseModel):
    """Response body for POST /ask."""

    answer: str | None = Field(None, description="Answer text, null if not found")
    sources: list[Source]
    footer: AskFooter
    query_time_ms: int


# === Index Endpoint Models ===


class IndexRequest(BaseModel):
    """Request body for POST /index."""

    path: str = Field(..., description="Path to index")
    project: str = Field(..., description="Project name")
    recursive: bool = Field(default=True, description="Index recursively")


class IndexError(BaseModel):
    """An error encountered during indexing."""

    file: str
    error: str


class IndexProgress(BaseModel):
    """Progress information for an indexing job."""

    total_files: int = 0
    processed_files: int = 0
    percent: int = 0
    current_file: str | None = None


class IndexResponse(BaseModel):
    """Response body for POST /index and GET /index/{job_id}."""

    job_id: str
    status: str = Field(..., description="Job status: started, running, completed, failed")
    path: str
    project: str
    started_at: datetime
    completed_at: datetime | None = None
    progress: IndexProgress
    errors: list[IndexError] = Field(default_factory=list)


class IndexAlreadyRunningError(BaseModel):
    """Error response when an index job is already running."""

    code: str = "INDEX_JOB_RUNNING"
    message: str = "An indexing job is already running. Wait for completion or cancel it."
    current_job_id: str


# === Project Endpoint Models ===


class ProjectStats(BaseModel):
    """Statistics for a project."""

    name: str
    document_count: int
    chunk_count: int
    source_types: dict[str, int]


class ProjectListResponse(BaseModel):
    """Response body for GET /projects."""

    projects: list[ProjectStats]
    total_projects: int


# === Document Endpoint Models ===


class DocumentInfo(BaseModel):
    """Information about an indexed document."""

    id: int
    source_path: str
    source_type: str
    project: str
    source_date: datetime | None = None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    """Response body for GET /documents."""

    documents: list[DocumentInfo]
    total: int
    page: int
    page_size: int


# === Error Models ===


class ErrorDetail(BaseModel):
    """RFC 7807 Problem Details error response."""

    type: str = Field(default="about:blank", description="Error type URI")
    title: str = Field(..., description="Short human-readable summary")
    status: int = Field(..., description="HTTP status code")
    detail: str | None = Field(None, description="Detailed explanation")
    instance: str | None = Field(None, description="URI of the specific occurrence")

    model_config = {"extra": "allow"}


# === Health Models ===


class HealthResponse(BaseModel):
    """Response body for GET /health."""

    status: str
    version: str
    database: str
    indexed_documents: int
