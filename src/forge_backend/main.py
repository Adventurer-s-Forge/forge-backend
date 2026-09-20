"""FastAPI application entrypoint with deploy-time reference-data seeding."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI

from forge_backend.ingest_database import run_ingestion

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Seed Redis reference data at startup; never fail startup over it."""
    try:
        counts = await asyncio.to_thread(run_ingestion)
    except Exception:
        logger.warning(
            "reference-data seeding failed; serving without fresh seed",
            exc_info=True,
        )
        counts = None
    app.state.seed_counts = counts
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, Any]:
    """Liveness plus last seeding outcome (None when seeding failed)."""
    return {"status": "ok", "seed_counts": getattr(app.state, "seed_counts", None)}
