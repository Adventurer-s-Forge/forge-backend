"""Deploy-time Open5e reference-data ingestion (seed script).

Fetches the six reference types from the Open5e API and full-replaces them in
Redis via :func:`storage.refresh_reference_type`. Importing this module has no
side effects; call :func:`run_ingestion` explicitly (FastAPI lifespan in
``forge_backend.main``) or via ``python -m forge_backend.ingest_database``.

SRD edition policy: race, class, background, item, and spell seed from
``srd-2024`` (SRD 5.2, 2024 rules, CC BY 4.0); skill seeds from ``core`` with
only ``srd-2024`` description entries projected (edition-neutral skill
IDs/metadata; Open5e has no separate top-level 2024 skill records).
"""

import logging
import time
from collections.abc import Callable
from typing import Any

from forge_backend.open_5e_caller import Open5eCaller
from forge_backend.storage import REF_TYPES, get_redis, refresh_reference_type

logger = logging.getLogger(__name__)

REF_DOCUMENTS: dict[str, str] = {
    "race": "srd-2024",
    "class": "srd-2024",
    "background": "srd-2024",
    "equipment": "srd-2024",
    "spell": "srd-2024",
    "skill": "core",
    "feat": "srd-2024",
}


def _reference_data(raw: dict[str, Any], ref_type: str) -> dict[str, Any]:
    """Return the envelope payload; project skill descriptions to 2024 only."""
    if ref_type != "skill":
        return raw
    descriptions = raw.get("descriptions", [])
    if descriptions is None:
        return {**raw, "descriptions": []}
    if not isinstance(descriptions, list):
        raise ValueError("invalid skill descriptions")  # noqa: TRY004
    kept = []
    for entry in descriptions:
        if not isinstance(entry, dict):
            raise ValueError("invalid skill descriptions")  # noqa: TRY004
        if _document_key(entry) == "srd-2024":
            kept.append(entry)
    return {**raw, "descriptions": kept}


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
        "equipment": caller.get_equipment,
        "spell": caller.get_spells,
        "skill": caller.get_skills,
        "feat": caller.get_feats,
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
                "data": _reference_data(raw, ref_type),
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
