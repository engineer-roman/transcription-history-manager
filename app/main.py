"""Main FastAPI application."""

from logly import logger

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import conversations, health
from app.core.config import settings
from app.db import init_db
from app.repositories.superwhisper import SuperwhisperRepository
from app.services.indexing_service import IndexingService


logger.configure(
    level="INFO",
    color=False,
    show_function=False,
    show_module=False,
    show_filename=False,
    show_lineno=False,
)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
)

# Global indexing service instance
indexing_service: IndexingService | None = None


@app.on_event("startup")
async def startup_event():
    """Initialize database and start background indexing on application startup."""
    global indexing_service

    # Initialize database schema
    logger.info("Initializing database schema...")
    init_db()

    # Start background indexing
    logger.info("Starting background transcription indexing...")
    repository = SuperwhisperRepository(base_directory=Path(settings.superwhisper_directory))
    indexing_service = IndexingService(transcription_repo=repository)

    # Start sync in background (non-blocking)
    await indexing_service.start_background_sync()
    logger.info("Background indexing started")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# Include routers
app.include_router(health.router, prefix=settings.api_prefix, tags=["health"])
app.include_router(conversations.router, prefix=settings.api_prefix, tags=["conversations"])

# Mount static files directory
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root() -> FileResponse:
    """Serve the main application page."""
    index_path = Path(__file__).parent / "static" / "index.html"
    if index_path.exists():
        return FileResponse(index_path)

    # Fallback if static files not found
    from fastapi.responses import JSONResponse

    return JSONResponse(
        {
            "message": f"Welcome to {settings.app_name}",
            "version": settings.app_version,
            "docs": "/docs",
        }
    )
