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


def char_key(uid: str, charid: str) -> str:
    """
    Construct the prefix to use to reference the character in the database.

    Args:
        uid (str): The user's ID from Google Firebase Authentication
        charid (str): The unique ID of the user's character
    
    Returns:
        (str): The prefix to use to reference the character in the database
    """
    return f"char:{uid}:{charid}"


def ref_index_key(ref_type: str) -> str:
    return f"ref:idx:{ref_type}"


def char_index_key(uid: str) -> str:
    """
    Construct the index reference for a user's characters in the database.

    Args:
        uid (str): The user's ID from Google Firebase Authentication

    Returns:
        (str): The index reference for a user's characters in the database
    """
    return f"char:idx:{uid}"


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


def get_user_character(conn: redis.Redis, uid: str, charid: str) -> dct[str, Any] | None:
    """
    Retrieve a character for a certain user from the database.

    Args:
        conn (redis.Redis): the Redist database connection
        uid (str): The user's ID from Google Firebase Authentication
        charid (str): The unique ID of the user's character

    Returns:
        (dct[str, Any] | Any): The user's character as a Dictionary of String, Any; or None if there is no existing characters
    """
    raw = conn.get(char_key(uid, charid)) # Construct the prefix to get the user's character
    # If the user's character is empty, then return None.
    # Otherwise, continue.
    if raw is None:
        return None
    return json.loads(raw) # deserialize the retrieved JSON and return it


def list_reference_keys(conn: redis.Redis, ref_type: str) -> list[str]:
    return sorted(conn.smembers(ref_index_key(ref_type)))


def list_char_keys(conn: redis.Redis, uid: str) -> list[str]:
    """
    Consruct the index and then get the list of the index keys for a user's characters from the database.

    Args:
        conn (redis.Redis): the Redist database connection
        uid (str): The user's ID from Google Firebase Authentication

    Returns:
        (list[str]): The list of index keys for a user's characters
    """
    return sorted(conn.smembers(char_index_key(uid)))


def list_reference_records(conn: redis.Redis, ref_type: str) -> list[dict[str, Any]]:
    slugs = list_reference_keys(conn, ref_type)
    if not slugs:
        return []
    raws = conn.mget([ref_key(ref_type, slug) for slug in slugs])
    return [json.loads(raw) for raw in raws if raw is not None]


def list_character_records(conn: redis.Redis, uid: str) -> list[dict[str, Any]]:
    """
    Retrieve all characters for a certain user from the database.

    Args:
        conn (redis.Redis): the Redist database connection
        uid (str): The user's ID from Google Firebase Authentication

    Returns:
        (list[dict[str, Any]]): The list of a user's characters (including the data for each)
    """
    slugs = list_char_keys(conn, uid) # Get the keys for each of the user's characters
    # If there were no keys, then return an empty list.
    # Otherwise, continue.
    if not slugs:
        return []
    # Iterate through the slugs, construct the correct prefix for database retrieval, retrieve the character, and add it to the raws list
    raws = conn.mget([char_key(uid, slug) for slug in slugs])
    # Iterate through each raw, deserialize the JSON if data exists, and add the result to the list to return
    return [json.loads(raw) for raw in raws if raw is not None]


def count_reference(conn: redis.Redis, ref_type: str) -> int:
    return conn.scard(ref_index_key(ref_type))


def count_characters(conn: redis.Redis, uid: str) -> int:
    """
    Retrieve the count of characters for a certain user in the database.

    Args:
        conn (redis.Redis): the Redist database connection
        uid (str): The user's ID from Google Firebase Authentication
    """
    return conn.scard(char_index_key(uid))


def add_new_character(conn: redis.Redis, uid: str, charid: str, user_character: Mapping[str, str]) -> None:
    """
    Add a new character for a user to the database.

    Args:
        conn (redis.Redis): the Redist database connection
        uid (str): The user's ID from Google Firebase Authentication
        charid (str): The unique ID of the user's character
        user_character (Mapping[str, str]): The actual data for the user's character (e.g. {"name": "Joe Schmoe"})

    Returns:
        (int): The number of items added to the database (should only be 1 item)
    """
    pipe = conn.pipeline(transaction=True)
    pipe.set(
        char_key(uid, charid), # Construct the prefix to add the user's character to the database
        json.dumps(user_character, ensure_ascii=False, separators=(",", ":")) # Serialize incoming JSON into JSON String before adding to database
    )