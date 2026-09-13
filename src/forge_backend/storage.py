"""Single Redis data-access layer.

This module is the only file in the repo permitted to import ``redis``.
All callers (seed script, FastAPI handlers, tests) obtain a client
via `get_redis` or pass their own and call the functions below.

Key layout (``ref:*`` = reference content, ``char:*`` = player characters)::

    ref:{type}:{slug}  STRING (JSON)  one reference record
    ref:idx:{type}     SET             slugs currently stored for that type
    char:{uid}:{id}    STRING (JSON)  player character

Stored-record JSON contract (produced by the Open5e seed transform)::

    {"type": "race", "key": "srd_dragonborn", "name": "Dragonborn",
     "document": "srd-2014", "data": {...verbatim Open5e v2 record...}}
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from typing import Any, Final

import redis

from forge_backend import config

REF_TYPES: Final[tuple[str, ...]] = ("race", "class", "background", "item", "spell")

_SLUG_RE = re.compile(r"^[a-z0-9_-]+$")

_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """Return the module-level cached sync client for ``config.REDIS_URL``."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(
            config.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
    return _redis_client


def ref_key(ref_type: str, slug: str) -> str:
    return f"ref:{ref_type}:{slug}"


def ref_index_key(ref_type: str) -> str:
    return f"ref:idx:{ref_type}"


def validate_reference_record(record: Mapping[str, Any], ref_type: str) -> None:
    """Raise ``ValueError`` (naming the offending field) unless the envelope is valid.

    Extra keys beyond the five contract fields are ignored.
    """
    record_type = record.get("type") if isinstance(record, Mapping) else None
    if record_type not in REF_TYPES or record_type != ref_type:
        raise ValueError(f"invalid 'type': {record_type!r} (expected {ref_type!r})")
    slug = record.get("key")
    if not isinstance(slug, str) or not _SLUG_RE.match(slug):
        raise ValueError(f"invalid 'key': {slug!r} (must match ^[a-z0-9_-]+$)")
    name = record.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError(f"invalid 'name': {name!r} (must be a non-empty string)")
    document = record.get("document")
    if not isinstance(document, str) or not document:
        raise ValueError(f"invalid 'document': {document!r} (must be a non-empty string)")
    data = record.get("data")
    if not isinstance(data, Mapping):
        raise ValueError(f"invalid 'data': {type(data).__name__} (must be a Mapping)")  # noqa: TRY004


def refresh_reference_type(
    conn: redis.Redis, ref_type: str, records: Iterable[Mapping[str, Any]]
) -> int:
    """Full-replace of one content type; returns records written.

    Later duplicates of the same ``record["key"]`` win. An empty ``records``
    deliberately wipes the type. Orphan keys present from a previous seed
    but absent now are deleted; ``char:*`` keys are never touched.
    """
    old_slugs: set[str] = conn.smembers(ref_index_key(ref_type))
    collapsed: dict[str, Mapping[str, Any]] = {}
    for record in records:
        collapsed[record["key"]] = record
    for record in collapsed.values():
        validate_reference_record(record, ref_type)
    new_slugs = set(collapsed)
    orphans = old_slugs - new_slugs

    pipe = conn.pipeline(transaction=True)
    for slug in orphans:
        pipe.delete(ref_key(ref_type, slug))
    for slug, record in collapsed.items():
        pipe.set(
            ref_key(ref_type, slug),
            json.dumps(record, ensure_ascii=False, separators=(",", ":")),
        )
    pipe.delete(ref_index_key(ref_type))
    if new_slugs:
        pipe.sadd(ref_index_key(ref_type), *sorted(new_slugs))
    pipe.execute()
    return len(collapsed)


def get_reference(conn: redis.Redis, ref_type: str, slug: str) -> dict[str, Any] | None:
    raw = conn.get(ref_key(ref_type, slug))
    if raw is None:
        return None
    return json.loads(raw)


def list_reference_keys(conn: redis.Redis, ref_type: str) -> list[str]:
    return sorted(conn.smembers(ref_index_key(ref_type)))


def list_reference_records(conn: redis.Redis, ref_type: str) -> list[dict[str, Any]]:
    slugs = list_reference_keys(conn, ref_type)
    if not slugs:
        return []
    raws = conn.mget([ref_key(ref_type, slug) for slug in slugs])
    return [json.loads(raw) for raw in raws if raw is not None]


def count_reference(conn: redis.Redis, ref_type: str) -> int:
    return conn.scard(ref_index_key(ref_type))
