from fastapi import FastAPI

from app.core.config import settings


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Adaptive Interview Simulator backend.",
)


@app.get("/Landing_Page")
async def root():
    return {
        "service": settings.app_name,
        "version": "0.1.0",
    }


@app.get("/health")
async def health():
    return {
        "status": "ok"
    }