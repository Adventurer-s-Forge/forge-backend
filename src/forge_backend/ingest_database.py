"""Deploy-time Open5e reference-data ingestion (seed script).

Fetches the six reference types from the Open5e API and full-replaces them in
Redis via :func:`storage.refresh_reference_type`. Importing this module has no
side effects; call :func:`run_ingestion` explicitly (FastAPI lifespan in
``forge_backend.main``) or via ``python -m forge_backend.ingest_database``.

SRD edition is pinned per resource category, never mixed within a category:
backgrounds and items seed from ``srd-2024``; races, classes, and spells seed
from ``srd-2014``; skills seed from ``core`` (the Open5e v2 edition-neutral
SRD skill set the 18-skill list is unchanged between the 2014 and 2024 SRDs).
"""

import logging
import time
from collections.abc import Callable
from typing import Any

from forge_backend.open_5e_caller import Open5eCaller
from forge_backend.storage import REF_TYPES, get_redis, refresh_reference_type

logger = logging.getLogger(__name__)

REF_DOCUMENTS: dict[str, str] = {
    "race": "srd-2014",
    "class": "srd-2014",
    "background": "srd-2024",
    "item": "srd-2024",
    "spell": "srd-2014",
    "skill": "core",
}


def _document_key(raw: dict[str, Any]) -> str | None:
    """Return the upstream document marker, handling both envelope shapes.

    Most v2 endpoints embed ``document`` as ``{"key": ...}``; ``/skills/``
    uses a bare string (``"core"`` for the SRD set).
    """
    document = raw.get("document", {})
    if isinstance(document, str):
        return document
    if isinstance(document, dict):
        key = document.get("key")
        return key if isinstance(key, str) else None
    return None


def run_ingestion() -> dict[str, int]:
    """Fetch all reference types from Open5e and full-replace them in Redis.

    Returns per-type record counts, e.g. ``{"race": n, "class": n, ...}``.
    Raises whatever the Open5e caller or Redis raises; callers that must stay
    up without a fresh seed (e.g. the app lifespan) catch everything.
    """
    caller = Open5eCaller()
    redis_client = get_redis()
    fetchers: dict[str, Callable[[], list[dict[str, Any]]]] = {
        "race": caller.get_races,
        "class": caller.get_classes,
        "background": caller.get_backgrounds,
        "item": caller.get_items,
        "spell": caller.get_spells,
        "skill": caller.get_skills,
    }
    counts: dict[str, int] = {}
    total_start = time.perf_counter()
    logger.info("reference-data seeding started for types=%s", list(REF_TYPES))
    for ref_type in REF_TYPES:
        expected_doc = REF_DOCUMENTS[ref_type]
        start = time.perf_counter()
        try:
            raw_records = fetchers[ref_type]()
        except Exception:
            logger.exception(
                "seeding %s: fetch failed (expected document=%s)", ref_type, expected_doc
            )
            raise
        fetched = len(raw_records)
        records = [
            {
                "type": ref_type,
                "key": raw["key"],
                "name": raw["name"],
                "document": _document_key(raw),
                "data": raw,
            }
            for raw in raw_records
            if _document_key(raw) == expected_doc and not raw.get("is_subspecies", False)
        ]
        skipped = fetched - len(records)
        written = refresh_reference_type(redis_client, ref_type, records)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "seeding %s: fetched=%d kept=%d skipped=%d written=%d expected_document=%s elapsed_ms=%.1f",
            ref_type,
            fetched,
            len(records),
            skipped,
            written,
            expected_doc,
            elapsed_ms,
        )
        counts[ref_type] = written
    total_ms = (time.perf_counter() - total_start) * 1000
    logger.info("reference-data seeding finished counts=%s elapsed_ms=%.1f", counts, total_ms)
    return counts


if __name__ == "__main__":
    print(run_ingestion())
