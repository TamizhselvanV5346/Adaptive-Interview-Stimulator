from fastapi import FastAPI

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.api.routes.intake import router as intake_router


configure_logging()

logger = get_logger(__name__)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Adaptive Interview Simulator backend.",
)

app.include_router(
    intake_router,
    prefix=settings.api_prefix,
)

@app.on_event("startup")
async def startup_event() -> None:
    logger.info(
        "Starting %s in %s environment",
        settings.app_name,
        settings.environment,
    )


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "version": "0.1.0",
        "environment": settings.environment,
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
    }