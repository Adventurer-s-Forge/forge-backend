"""FastAPI application entrypoint with deploy-time reference-data seeding."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from forge_backend import config
from forge_backend.character_data_routes import router as reference_router
from forge_backend.ingest_database import run_ingestion
from forge_backend.user_character_data_routes import router as user_character_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: str
    seed_counts: dict[str, int] | None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Seed Redis reference data at startup; never fail startup over it."""
    logger.info("startup seeding: begin")
    try:
        counts = await asyncio.to_thread(run_ingestion)
    except Exception:
        logger.warning(
            "startup seeding: failed; serving without fresh seed",
            exc_info=True,
        )
        counts = None
    else:
        logger.info("startup seeding: complete counts=%s", counts)
    app.state.seed_counts = counts
    yield


app = FastAPI(
    title="Adventurer's Forge API",
    version="0.1.0",
    description=(
        "D&D reference content and player-character API. Character operations use a "
        "temporary X-User-Id header, not verified authentication."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Characters", "description": "Player-character records."},
        {"name": "Reference content", "description": "Seeded D&D reference lists."},
        {"name": "Health", "description": "Service liveness and seed outcome."},
    ],
)
app.include_router(reference_router)
app.include_router(user_character_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.get(
    "/health",
    tags=["Health"],
    operation_id="get_health",
    response_model=HealthResponse,
    summary="Health check",
)
def health() -> HealthResponse:
    """Liveness plus last seeding outcome (None when seeding failed)."""
    return HealthResponse(status="ok", seed_counts=getattr(app.state, "seed_counts", None))
