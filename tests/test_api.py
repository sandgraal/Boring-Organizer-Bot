"""Tests for API endpoints."""

from __future__ import annotations

from datetime import datetime, date, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from bob.api.app import create_app
from bob.config import Config
from bob.retrieval.search import SearchResult


@pytest.fixture
def client():
    """Create a test client for the API."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def mock_database():
    """Create a mock database for testing."""
    mock_db = MagicMock()
    mock_db.get_stats.return_value = {
        "document_count": 10,
        "chunk_count": 50,
        "source_types": {"markdown": 5, "pdf": 5},
        "projects": ["test"],
        "has_vec": True,
    }
    return mock_db


@pytest.fixture
def mock_coach_db():
    """Create a mock database with Coach Mode helpers."""
    mock_db = MagicMock()
    mock_db.get_user_settings.return_value = {
        "global_mode_default": "boring",
        "coach_mode_default": "boring",
        "per_project_mode": {},
        "coach_cooldown_days": 7,
    }
    mock_db.is_suggestion_type_in_cooldown.return_value = False
    mock_db.log_coach_suggestion = MagicMock()
    mock_db.get_suggestion_context.return_value = None
    return mock_db


class TestHealthEndpoint:
    """Tests for GET /health endpoint."""

    def test_health_returns_status(self, client: TestClient, mock_database: MagicMock):
        """Health check returns healthy status."""
        with patch("bob.api.routes.health.get_database", return_value=mock_database):
            response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"
        assert data["database"] == "connected"
        assert data["indexed_documents"] == 10

    def test_health_handles_db_error(self, client: TestClient):
        """Health check handles database errors gracefully."""
        with patch(
            "bob.api.routes.health.get_database",
            side_effect=Exception("DB connection failed"),
        ):
            response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "error"
        assert data["indexed_documents"] == 0


class TestAskEndpoint:
    """Tests for POST /ask endpoint."""

    @pytest.fixture
    def mock_search_results(self):
        """Create mock search results."""
        from datetime import datetime

        from bob.retrieval.search import SearchResult

        return [
            SearchResult(
                chunk_id=1,
                content="This is the answer content from the document.",
                score=0.92,
                source_path="/docs/test.md",
                source_type="markdown",
                locator_type="heading",
                locator_value={
                    "heading": "Test Section",
                    "start_line": 10,
                    "end_line": 20,
                },
                project="test",
                source_date=datetime(2024, 12, 1),
                git_repo=None,
                git_commit=None,
            ),
            SearchResult(
                chunk_id=2,
                content="Another relevant passage.",
                score=0.85,
                source_path="/docs/other.md",
                source_type="markdown",
                locator_type="heading",
                locator_value={
                    "heading": "Other Section",
                    "start_line": 5,
                    "end_line": 15,
                },
                project="test",
                source_date=datetime(2024, 6, 1),
                git_repo=None,
                git_commit=None,
            ),
        ]

    def test_ask_returns_sources(
        self, client: TestClient, mock_search_results: list, mock_coach_db: MagicMock
    ):
        """Ask endpoint returns sources with citations."""
        with patch("bob.api.routes.ask.search", return_value=mock_search_results), patch(
            "bob.api.routes.ask.get_database", return_value=mock_coach_db
        ):
            response = client.post(
                "/ask",
                json={"query": "test question", "top_k": 5},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] is not None
        assert data["coach_mode_enabled"] is False
        assert data["suggestions"] == []
        assert len(data["sources"]) == 2
        assert data["footer"]["source_count"] == 2
        assert data["footer"]["not_found"] is False
        assert "query_time_ms" in data

    def test_ask_returns_not_found_when_empty(
        self, client: TestClient, mock_coach_db: MagicMock
    ):
        """Ask endpoint returns not_found when no results."""
        with patch("bob.api.routes.ask.search", return_value=[]), patch(
            "bob.api.routes.ask.get_database", return_value=mock_coach_db
        ):
            response = client.post(
                "/ask",
                json={"query": "nonexistent topic"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] is None
        assert data["coach_mode_enabled"] is False
        assert data["sources"] == []
        assert data["footer"]["not_found"] is True
        assert data["footer"]["not_found_message"] is not None
        assert data["suggestions"] == []

    def test_ask_not_found_with_coach_enabled_returns_coverage_suggestion(
        self, client: TestClient, mock_coach_db: MagicMock
    ):
        """Ask endpoint returns coverage suggestion when Coach Mode is enabled."""
        with patch("bob.api.routes.ask.search", return_value=[]), patch(
            "bob.api.routes.ask.get_database", return_value=mock_coach_db
        ):
            response = client.post(
                "/ask",
                json={"query": "nonexistent topic", "coach_mode_enabled": True},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["coach_mode_enabled"] is True
        assert data["footer"]["not_found"] is True
        assert len(data["suggestions"]) == 1
        assert data["suggestions"][0]["type"] == "coverage_gaps"

    def test_ask_low_confidence_with_coach_enabled_returns_staleness_suggestion(
        self, client: TestClient, mock_coach_db: MagicMock
    ):
        """Ask endpoint returns staleness suggestion when confidence is LOW."""
        from datetime import datetime

        from bob.retrieval.search import SearchResult

        old_date = datetime(2000, 1, 1)
        results = [
            SearchResult(
                chunk_id=1,
                content="Decision: Use legacy system.",
                score=0.92,
                source_path="/docs/old.md",
                source_type="markdown",
                locator_type="heading",
                locator_value={
                    "heading": "Old Section",
                    "start_line": 10,
                    "end_line": 20,
                },
                project="test",
                source_date=old_date,
                git_repo=None,
                git_commit=None,
            ),
            SearchResult(
                chunk_id=2,
                content="Some older passage.",
                score=0.85,
                source_path="/docs/older.md",
                source_type="markdown",
                locator_type="heading",
                locator_value={
                    "heading": "Older Section",
                    "start_line": 5,
                    "end_line": 15,
                },
                project="test",
                source_date=old_date,
                git_repo=None,
                git_commit=None,
            ),
        ]

        with patch("bob.api.routes.ask.search", return_value=results), patch(
            "bob.api.routes.ask.get_database", return_value=mock_coach_db
        ):
            response = client.post(
                "/ask",
                json={"query": "test question", "coach_mode_enabled": True},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["coach_mode_enabled"] is True
        assert data["footer"]["not_found"] is False
        assert len(data["suggestions"]) == 1
        assert data["suggestions"][0]["type"] == "staleness"

    def test_ask_validates_top_k(self, client: TestClient, mock_coach_db: MagicMock):
        """Ask endpoint validates top_k parameter."""
        with patch("bob.api.routes.ask.get_database", return_value=mock_coach_db):
            response = client.post(
                "/ask",
                json={"query": "test", "top_k": 0},
            )
        assert response.status_code == 422  # Validation error

        with patch("bob.api.routes.ask.get_database", return_value=mock_coach_db):
            response = client.post(
                "/ask",
                json={"query": "test", "top_k": 100},
            )
        assert response.status_code == 422  # Validation error

    def test_ask_accepts_filters(
        self, client: TestClient, mock_search_results: list, mock_coach_db: MagicMock
    ):
        """Ask endpoint accepts filter parameters."""
        with patch("bob.api.routes.ask.search", return_value=mock_search_results), patch(
            "bob.api.routes.ask.get_database", return_value=mock_coach_db
        ):
            response = client.post(
                "/ask",
                json={
                    "query": "test question",
                    "filters": {
                        "projects": ["test"],
                        "types": ["markdown"],
                    },
                },
            )

        assert response.status_code == 200

    def test_ask_source_includes_required_fields(
        self, client: TestClient, mock_search_results: list, mock_coach_db: MagicMock
    ):
        """Ask response sources include all required fields."""
        with patch("bob.api.routes.ask.search", return_value=mock_search_results), patch(
            "bob.api.routes.ask.get_database", return_value=mock_coach_db
        ):
            response = client.post(
                "/ask",
                json={"query": "test question"},
            )

        data = response.json()
        source = data["sources"][0]

        # Check required fields
        assert "id" in source
        assert "chunk_id" in source
        assert "file_path" in source
        assert "file_type" in source
        assert "locator" in source
        assert "snippet" in source
        assert "date_confidence" in source
        assert "project" in source
        assert "similarity_score" in source


class TestIndexEndpoint:
    """Tests for indexing endpoints."""

    @pytest.fixture(autouse=True)
    def reset_job_manager(self):
        """Reset the job manager before each test."""
        from bob.api.routes.index import _job_manager

        _job_manager._current_job = None
        yield
        _job_manager._current_job = None

    def test_index_starts_job(self, client: TestClient, tmp_path):
        """POST /index starts an indexing job."""
        # Create a test file
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test\n\nContent here.")

        with patch("bob.api.routes.index._run_index_job"):
            response = client.post(
                "/index",
                json={
                    "path": str(tmp_path),
                    "project": "test",
                    "recursive": True,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert "job_id" in data
        assert data["project"] == "test"


    def test_index_rejects_concurrent_jobs(self, client: TestClient, tmp_path):
        """POST /index rejects when a job is already running."""
        # Create a test file
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test\n\nContent here.")

        # Start a job first
        with patch("bob.api.routes.index._run_index_job"):
            first_response = client.post(
                "/index",
                json={
                    "path": str(tmp_path),
                    "project": "test",
                    "recursive": True,
                },
            )
            assert first_response.status_code == 200

        # Try to start another job
        response = client.post(
            "/index",
            json={
                "path": str(tmp_path),
                "project": "test2",
            },
        )

        assert response.status_code == 409  # Conflict

    def test_get_index_job(self, client: TestClient, tmp_path):
        """GET /index/{job_id} returns job status."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test\n\nContent here.")

        with patch("bob.api.routes.index._run_index_job"):
            start_response = client.post(
                "/index",
                json={
                    "path": str(tmp_path),
                    "project": "test",
                },
            )

        assert start_response.status_code == 200
        job_id = start_response.json()["job_id"]

        response = client.get(f"/index/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id


class TestRoutinesEndpoint:
    """Tests for the routines endpoints."""

    def test_daily_checkin_creates_note_and_returns_retrievals(
        self, client: TestClient, tmp_path
    ):
        """POST /routines/daily-checkin writes a note and returns citations."""
        from datetime import datetime as dt

        config = Config()
        config.paths.vault = tmp_path

        sample_result = SearchResult(
            chunk_id=1,
            content="Sample context for the routine.",
            score=0.9,
            source_path="/docs/routine.md",
            source_type="markdown",
            locator_type="heading",
            locator_value={
                "heading": "Routine Section",
                "start_line": 1,
                "end_line": 5,
            },
            project="test",
            source_date=dt(2025, 1, 1),
            git_repo=None,
            git_commit=None,
        )

        results_by_query = {
            "open loop": [sample_result],
            "recent context": [sample_result],
        }

        def fake_search(*, query, project, top_k, **kwargs):
            return results_by_query.get(query, [])

        with patch("bob.api.routes.routines.get_config", return_value=config), patch(
            "bob.api.routes.routines.search", side_effect=fake_search
        ):
            response = client.post(
                "/routines/daily-checkin",
                json={
                    "project": "test",
                    "date": "2025-01-01",
                    "top_k": 1,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["routine"] == "daily-checkin"
        assert data["template"].endswith("docs/templates/daily.md")
        assert len(data["retrievals"]) == 2
        assert data["warnings"] == []

        target_path = tmp_path / "routines" / "daily" / "2025-01-01.md"
        assert target_path.exists()
        body = target_path.read_text()
        assert 'project: "test"' in body
        assert 'source: "routine/daily-checkin"' in body

    def test_weekly_review_creates_note_and_returns_retrievals(
        self, client: TestClient, tmp_path
    ):
        """POST /routines/weekly-review writes a note with week range metadata."""
        config = Config()
        config.paths.vault = tmp_path

        sample_result = SearchResult(
            chunk_id=1,
            content="Sample context for the routine.",
            score=0.9,
            source_path="/docs/routine.md",
            source_type="markdown",
            locator_type="heading",
            locator_value={
                "heading": "Routine Section",
                "start_line": 1,
                "end_line": 5,
            },
            project="test",
            source_date=datetime(2025, 1, 1),
            git_repo=None,
            git_commit=None,
        )

        results_by_query = {
            "weekly highlights": [sample_result],
            "stale decisions": [sample_result],
            "missing metadata": [sample_result],
        }

        def fake_search(*, query, project, top_k, **kwargs):
            return results_by_query.get(query, [])

        with patch("bob.api.routes.routines.get_config", return_value=config), patch(
            "bob.api.routes.routines.search", side_effect=fake_search
        ):
            response = client.post(
                "/routines/weekly-review",
                json={
                    "project": "test",
                    "date": "2025-01-01",
                    "top_k": 1,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["routine"] == "weekly-review"
        assert data["template"].endswith("docs/templates/weekly.md")
        assert len(data["retrievals"]) == 3
        assert data["warnings"] == []

        target_path = tmp_path / "routines" / "weekly" / "2025-W01.md"
        assert target_path.exists()
        body = target_path.read_text()
        week_start = date(2025, 1, 1) - timedelta(days=date(2025, 1, 1).weekday())
        week_end = week_start + timedelta(days=6)
        expected_range = f'{week_start.isoformat()} - {week_end.isoformat()}'
        assert f'week_range: "{expected_range}"' in body
    def test_get_nonexistent_job(self, client: TestClient):
        """GET /index/{job_id} returns 404 for unknown job."""
        response = client.get("/index/idx_nonexistent")
        assert response.status_code == 404


class TestSettingsEndpoint:
    """Tests for settings endpoints."""

    def test_get_settings(self, client: TestClient, mock_coach_db: MagicMock):
        """GET /settings returns persisted settings."""
        with patch("bob.api.routes.settings.get_database", return_value=mock_coach_db):
            response = client.get("/settings")

        assert response.status_code == 200
        data = response.json()
        assert data["coach_mode_default"] == "boring"
        assert data["coach_cooldown_days"] == 7

    def test_put_settings(self, client: TestClient, mock_coach_db: MagicMock):
        """PUT /settings updates settings."""
        with patch("bob.api.routes.settings.get_database", return_value=mock_coach_db):
            response = client.put(
                "/settings",
                json={
                    "coach_mode_default": "coach",
                    "per_project_mode": {"docs": "coach"},
                    "coach_cooldown_days": 14,
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_coach_db.update_user_settings.assert_called_once()

    def test_dismiss_suggestion(self, client: TestClient, mock_coach_db: MagicMock):
        """POST /suggestions/{id}/dismiss logs a dismissal."""
        with patch("bob.api.routes.settings.get_database", return_value=mock_coach_db):
            response = client.post(
                "/suggestions/test_fingerprint/dismiss",
                json={"suggestion_type": "coverage_gaps", "project": "docs"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "cooldown_until" in data


class TestProjectsEndpoint:
    """Tests for GET /projects endpoint."""

    def test_projects_returns_list(self, client: TestClient, mock_database: MagicMock):
        """Projects endpoint returns list of projects."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("project1",), ("project2",)]
        mock_database.conn.execute.return_value = mock_cursor

        with patch("bob.api.routes.projects.get_database", return_value=mock_database):
            response = client.get("/projects")

        assert response.status_code == 200
        data = response.json()
        assert "projects" in data
        assert "total_projects" in data

    def test_projects_empty_list(self, client: TestClient, mock_database: MagicMock):
        """Projects endpoint handles empty list."""
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_database.conn.execute.return_value = mock_cursor

        with patch("bob.api.routes.projects.get_database", return_value=mock_database):
            response = client.get("/projects")

        assert response.status_code == 200
        data = response.json()
        assert data["projects"] == []
        assert data["total_projects"] == 0


class TestCORS:
    """Tests for CORS configuration."""

    def test_cors_allows_localhost(self, client: TestClient):
        """CORS allows localhost origins."""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:8080",
                "Access-Control-Request-Method": "GET",
            },
        )
        # FastAPI/Starlette returns 200 for OPTIONS
        assert response.status_code in (200, 400)

    def test_cors_headers_present(self, client: TestClient, mock_database: MagicMock):
        """CORS headers are present in responses."""
        with patch("bob.api.routes.health.get_database", return_value=mock_database):
            response = client.get(
                "/health",
                headers={"Origin": "http://localhost:8080"},
            )

        assert "access-control-allow-origin" in response.headers


class TestDocumentsEndpoint:
    """Tests for GET /documents endpoint."""

    def test_documents_returns_list(self, client: TestClient, mock_database: MagicMock):
        """Documents endpoint returns list of documents."""
        mock_count_cursor = MagicMock()
        mock_count_cursor.fetchone.return_value = (5,)

        mock_docs_cursor = MagicMock()
        mock_docs_cursor.fetchall.return_value = [
            {
                "id": 1,
                "source_path": "/docs/test.md",
                "source_type": "markdown",
                "project": "test",
                "source_date": "2024-12-01T00:00:00",
                "created_at": "2024-12-01T00:00:00",
                "updated_at": "2024-12-01T00:00:00",
            }
        ]

        mock_database.conn.execute.side_effect = [mock_count_cursor, mock_docs_cursor]

        with patch("bob.api.routes.documents.get_database", return_value=mock_database):
            response = client.get("/documents")

        assert response.status_code == 200
        data = response.json()
        assert "documents" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data

    def test_documents_filters_by_project(self, client: TestClient, mock_database: MagicMock):
        """Documents endpoint filters by project."""
        mock_count_cursor = MagicMock()
        mock_count_cursor.fetchone.return_value = (0,)

        mock_docs_cursor = MagicMock()
        mock_docs_cursor.fetchall.return_value = []

        mock_database.conn.execute.side_effect = [mock_count_cursor, mock_docs_cursor]

        with patch("bob.api.routes.documents.get_database", return_value=mock_database):
            response = client.get("/documents?project=test")

        assert response.status_code == 200

    def test_documents_pagination(self, client: TestClient, mock_database: MagicMock):
        """Documents endpoint supports pagination."""
        mock_count_cursor = MagicMock()
        mock_count_cursor.fetchone.return_value = (100,)

        mock_docs_cursor = MagicMock()
        mock_docs_cursor.fetchall.return_value = []

        mock_database.conn.execute.side_effect = [mock_count_cursor, mock_docs_cursor]

        with patch("bob.api.routes.documents.get_database", return_value=mock_database):
            response = client.get("/documents?page=2&page_size=10")

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 10


class TestOpenEndpoint:
    """Tests for POST /open endpoint."""

    def test_open_nonexistent_file(self, client: TestClient):
        """Open endpoint returns 404 for nonexistent file."""
        response = client.post(
            "/open",
            json={"file_path": "/nonexistent/file.md"},
        )
        assert response.status_code == 404

    def test_open_existing_file(self, client: TestClient, tmp_path):
        """Open endpoint handles existing file."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        with patch("bob.api.routes.open.subprocess.Popen"):
            response = client.post(
                "/open",
                json={"file_path": str(test_file)},
            )

        assert response.status_code == 200
        data = response.json()
        # Either succeeds or gives instructions
        assert "success" in data
        assert "message" in data

    def test_open_with_line_number(self, client: TestClient, tmp_path):
        """Open endpoint accepts line number."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test\n\nLine 3")

        with patch("bob.api.routes.open.subprocess.Popen"):
            response = client.post(
                "/open",
                json={"file_path": str(test_file), "line": 3},
            )

        assert response.status_code == 200

    def test_open_with_editor_preference(self, client: TestClient, tmp_path):
        """Open endpoint accepts editor preference."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test")

        with patch("bob.api.routes.open.subprocess.Popen"):
            response = client.post(
                "/open",
                json={"file_path": str(test_file), "editor": "vscode"},
            )

        assert response.status_code == 200


class TestUIEndpoint:
    """Tests for root UI endpoint."""

    def test_root_serves_ui(self, client: TestClient):
        """Root endpoint serves the UI HTML page."""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert b"B.O.B" in response.content

    def test_static_css_served(self, client: TestClient):
        """Static CSS files are served."""
        response = client.get("/static/css/main.css")
        assert response.status_code == 200
        assert "text/css" in response.headers["content-type"]

    def test_static_js_served(self, client: TestClient):
        """Static JS files are served."""
        response = client.get("/static/js/app.js")
        assert response.status_code == 200
        assert "javascript" in response.headers["content-type"]
