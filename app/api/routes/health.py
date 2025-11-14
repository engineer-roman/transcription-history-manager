"""Health check endpoints."""

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """
    Health check endpoint.

    Returns:
        dict: Status and application information
    """
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.app_version,
    }


@router.get("/ready")
async def readiness_check() -> dict[str, str]:
    """
    Readiness check endpoint.

    Returns:
        dict: Readiness status
    """
    return {"status": "ready"}


@router.get("/live")
async def liveness_check() -> dict[str, str]:
    """
    Liveness check endpoint.

    Returns:
        dict: Liveness status
    """
    return {"status": "alive"}
