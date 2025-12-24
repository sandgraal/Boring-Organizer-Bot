"""FastAPI application factory for B.O.B API server."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from bob.api.routes import ask, documents, health, index, open, projects


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

    # Include routers
    app.include_router(health.router, tags=["Health"])
    app.include_router(ask.router, tags=["Query"])
    app.include_router(index.router, tags=["Indexing"])
    app.include_router(projects.router, tags=["Projects"])
    app.include_router(documents.router, tags=["Documents"])
    app.include_router(open.router, tags=["Files"])

    return app
