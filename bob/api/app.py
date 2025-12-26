"""FastAPI application factory for B.O.B API server."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from bob.api.routes import (
    ask,
    documents,
    feedback,
    health,
    index,
    notes,
    open,
    permissions,
    projects,
    routines,
    settings,
)

# Path to UI static files
UI_DIR = Path(__file__).parent.parent / "ui"
STATIC_DIR = UI_DIR / "static"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI app instance.
    """
    app = FastAPI(
        title="B.O.B API",
        description="Local-only API for B.O.B - Boring Organizer Bot",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # CORS configuration for local development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:3000",  # Common dev server port
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routers
    app.include_router(health.router, tags=["Health"])
    app.include_router(ask.router, tags=["Query"])
    app.include_router(feedback.router, tags=["Feedback"])
    app.include_router(index.router, tags=["Indexing"])
    app.include_router(projects.router, tags=["Projects"])
    app.include_router(documents.router, tags=["Documents"])
    app.include_router(settings.router, tags=["Settings"])
    app.include_router(permissions.router, tags=["Permissions"])
    app.include_router(open.router, tags=["Files"])
    app.include_router(routines.router, tags=["Routines"])
    app.include_router(notes.router, tags=["Notes"])

    # Mount static files for UI
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Serve index.html at root
    @app.get("/", include_in_schema=False, response_model=None)
    async def serve_ui() -> FileResponse | RedirectResponse:
        """Serve the main UI HTML page."""
        index_path = UI_DIR / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path), media_type="text/html")
        # Fallback: redirect to API docs if UI not available
        return RedirectResponse(url="/docs")

    return app
