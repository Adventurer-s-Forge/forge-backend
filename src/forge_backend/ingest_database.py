"""Deploy-time Open5e reference-data ingestion (seed script).

Fetches the five reference types from the Open5e API and full-replaces them in
Redis via :func:`storage.refresh_reference_type`. Importing this module has no
side effects; call :func:`run_ingestion` explicitly (FastAPI lifespan in
``forge_backend.main``) or via ``python -m forge_backend.ingest_database``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from forge_backend.open_5e_caller import Open5eCaller
from forge_backend.storage import REF_TYPES, get_redis, refresh_reference_type


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
    }
    counts: dict[str, int] = {}
    for ref_type in REF_TYPES:
        records = [
            {
                "type": ref_type,
                "key": raw.get("slug"),
                "name": raw.get("name"),
                "document": raw.get("document__slug"),
                "data": raw,
            }
            for raw in fetchers[ref_type]()
        ]
        counts[ref_type] = refresh_reference_type(redis_client, ref_type, records)
    return counts


if __name__ == "__main__":
    print(run_ingestion())
