# forge-backend

Adventurer's Forge backend: Redis data-access layer, rules engine, FastAPI server.

## Stack

- Python 3.12 + [uv](https://docs.astral.sh/uv/) (dependency management)
- Redis 7 (local dev via Docker Compose; seeded reference content + character data)
- Pytest (tests), Ruff (lint)

## Setup

```sh
# Install uv (once per machine)
curl -LsSf https://astral.sh/uv/install.sh | sh
# Install dependencies (creates .venv; uv.lock is committed)
uv sync
# Start local Redis (port 6379) + RedisInsight (port 5540)
docker compose up -d
```

## Environment

| Variable        | Default                        | Purpose                                                  |
|-----------------|--------------------------------|----------------------------------------------------------|
| `REDIS_URL`     | `redis://localhost:6379/0`     | Runtime/seed Redis (production sets this)                |
| `TEST_REDIS_URL`| `redis://localhost:6379/15`    | Test-only Redis DB (flushed per test)                    |
| `CORS_ORIGINS`  | `http://localhost:5173`        | Comma-separated browser origins allowed to call the API  |


`TEST_REDIS_URL` is never derived from `REDIS_URL`, so the test suite cannot flush dev data.

## Run

```sh
uv run pytest        # unit + integration (integration skips if Redis unreachable)
uv run ruff check .  # lint
# Seed Redis at app startup (lifespan) and serve the API:
uv run uvicorn forge_backend.main:app
curl localhost:8000/health  # {"status":"ok","seed_counts":{...}} (null when seeding failed)
# Manual/deploy seed fallback (same run_ingestion the lifespan calls):
uv run python -m forge_backend.ingest_database
```

Startup never fails over seeding: if Open5e or Redis is unreachable, the lifespan logs a
warning and the app still serves (with `seed_counts: null`).

## API

Contract is the OpenAPI schema generated from the FastAPI app (`src/forge_backend/main.py`,
title "Adventurer's Forge API", version `0.1.0`), pinned by `tests/test_openapi_contract.py`.
With the server running (`uv run uvicorn forge_backend.main:app`):

- Interactive docs: `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc`
- Raw schema: `http://localhost:8000/openapi.json`

Identity is a temporary `X-User-Id` request header selecting the `char:{uid}:*` storage
namespace; it is not authentication (Firebase verification is a future story).

| Method | Path | operationId | Success | Errors |
|--------|------|-------------|---------|--------|
| `GET` | `/races` | `list_races` | `200 [ReferenceRecord]` | `422` |
| `GET` | `/classes` | `list_classes` | `200 [ReferenceRecord]` | `422` |
| `GET` | `/backgrounds` | `list_backgrounds` | `200 [ReferenceRecord]` | `422` |
| `GET` | `/items` | `list_items` | `200 [ReferenceRecord]` | `422` |
| `GET` | `/spells` | `list_spells` | `200 [ReferenceRecord]` | `422` |
| `POST` | `/characters` | `create_character` | `201 CreateCharacterResponse` | `409` (id collision), `422` |
| `GET` | `/characters` | `list_characters` | `200 [CharacterRecord]` | `422` |
| `GET` | `/characters/ids` | `list_character_ids` | `200 [string]` (sorted) | `422` |
| `GET` | `/characters/count` | `count_characters` | `200 int` | `422` |
| `GET` | `/characters/{character_id}` | `get_character` | `200 CharacterRecord` | `404`, `422` |
| `PUT` | `/characters/{character_id}/class` | `set_character_class` | `200 CharacterRecord` | `400` (unknown class), `404`, `422` |
| `GET` | `/health` | `get_health` | `200 HealthResponse` (`seed_counts` null when seeding failed) | N/A |

Request bodies:

```sh
# POST /characters (header X-User-Id: <uid>)
{"character_name": "Gandalf", "user_name": "test-user"}
# → 201 {"character_id": "1a2b3c4d", "result": 1}

# PUT /characters/{id}/class (header X-User-Id: <uid>)
{"class": "Wizard"}
```

Error bodies are `{"detail": "<message>"}` (`ErrorResponse`); validation failures are
FastAPI's `422 HTTPValidationError`.

## Redis Schema

All Redis access goes through `src/forge_backend/storage.py`; nothing else in the
codebase touches Redis. Keys are namespaced into two families: `ref:*` (seeded D&D reference
content, shared read-only by all users) and `char:*` (per-player character data). This allows a
re-seed of a reference type to never touch player data.

### Key layout

| Key pattern          | Redis type | Value                                                             |
|----------------------|------------|-------------------------------------------------------------------|
| `ref:{type}:{slug}`  | STRING     | One reference record, stored as a single compact JSON string      |
| `ref:idx:{type}`     | SET        | Slugs currently stored for `{type}`; source of truth for list/count |
| `char:{uid}:{id}`    | STRING     | One player character as JSON (owner, name, class)                  |
| `char:idx:{uid}`     | SET        | Character ids for that user; SADDed idempotently on every save, source of truth for list/count |

- `{type}` ∈ `race` | `class` | `background` | `item` | `spell` | `skill` (`storage.REF_TYPES`).
- `{slug}` is the Open5e v2 key, constrained to `^[a-z0-9_-]+$` (e.g. `srd_dragonborn`).
- No hashes, no TTLs: reference records are immutable between seeds and always read whole,
  so each is one JSON string and no key ever expires.

### Reference record envelope (`ref:{type}:{slug}` value)

Exactly five contract fields (extra keys ignored); every record is checked by
`validate_reference_record` before anything is written:

```json
{
  "type": "race",
  "key": "srd_dragonborn",
  "name": "Dragonborn",
  "document": "srd-2014",
  "data": { "...verbatim Open5e v2 record..." }
}
```

- `type` must equal the `{type}` in the key (envelope and key cannot disagree).
- `data` is the Open5e v2 record stored verbatim; the app never calls Open5e at runtime.
- Serialized with `json.dumps(..., ensure_ascii=False, separators=(",", ":"))`.

### Operations & invariants

| Function (storage.py)      | Behavior |
|----------------------------|----------|
| `refresh_reference_type`   | Full-replace of one type inside a single `MULTI/EXEC`: delete orphan keys, `SET` every record, rebuild the index (`DEL` + `SADD`). All records are validated before any write, so one bad record aborts the refresh with nothing persisted. Duplicate slugs: last wins. Empty input wipes the type. `char:*` is never touched. |
| `get_reference`            | `GET` + `json.loads`; `None` on miss. |
| `list_reference_keys`      | Sorted `SMEMBERS` of the index. |
| `list_reference_records`   | Sorted `SMEMBERS`, then `MGET` of all records; index entries whose key is gone are skipped. |
| `count_reference`          | `SCARD` of the index. |
| `get_user_character`       | `GET` + `json.loads` of `char:{uid}:{id}`; `None` on miss. |
| `add_new_character`        | Upsert in one MULTI/EXEC: `SET` record (NX: duplicate id returns 0, preserves original) + `SADD` id; returns 1 if created, 0 otherwise. |
| `list_char_keys`           | Sorted `SMEMBERS` of `char:idx:{uid}`. |
| `list_character_records`   | Sorted ids then `MGET` of the records. |
| `count_characters`         | `SCARD` of `char:idx:{uid}`. |

Invariants:

- The index is rebuilt from scratch on every refresh (never incrementally patched), so
  `ref:idx:{type}` cannot drift from the stored `ref:{type}:*` keys.
- Refreshes are idempotent: re-running the same seed produces the same state.
- Reference content is shared (no per-user prefix); character keys are per-player via `{uid}`.
- Production data lives in the logical DB from `REDIS_URL` (DB 0 locally); the test suite uses
  the separate logical DB from `TEST_REDIS_URL` (DB 15), flushed per test.

Schema behavior is pinned by tests: `test_storage.py` (key formats, envelope validation),
`test_storage_integration.py` (refresh roundtrip, idempotency, orphan cleanup,
`ref:*`/`char:*` isolation, wipe), and `test_startup_seed.py` (ingestion envelope/counts,
lifespan seed-once, seed-failure-is-nonfatal, seed-level idempotent rerun).

## Layout

```text
src/forge_backend/
  config.py                         # REDIS_URL (env, localhost default)
  storage.py                        # ONLY module allowed to import redis (NFR-16)
  open_5e_caller.py                 # sync Open5e API client (deploy-time only, never at runtime)
  ingest_database.py                # run_ingestion(): fetch six ref types, full-replace per type
  main.py                           # FastAPI app (OpenAPI title/version/tags); lifespan seeds via run_ingestion; GET /health
  character_data_routes.py          # reference-content router (/races, /classes, /backgrounds, /items, /spells)
  character_data_service.py         # read service over seeded content
  user_character_data_service.py    # Intermediary functions for retrieving/manipulating user characters
  user_character_data_routes.py     # sole /characters router (create/list/ids/count/detail/set-class)
tests/
  conftest.py                             # redis_conn fixture (dedicated DB 15 + flush) + api_client (in-process TestClient)
  test_storage.py                         # unit: key formats, record validation
  test_storage_integration.py             # integration: refresh roundtrip, idempotency,
                                          # orphan cleanup, type/player-data isolation, wipe
  test_startup_seed.py                    # ingestion formatting/counts, lifespan seed + failure,
                                          # seed-level idempotent rerun (integration)
  test_openapi_contract.py                # OpenAPI pin: 201 create, CharacterRecord wire key, ReferenceRecord shape, X-User-Id header, error schemas
  test_character_data_routes_us35.py      # reference routes + class-selection (US-35) via api_client
  test_user_character_data_service.py     # Unit testing of generating a character ID and Integration testing of the functions to create a new character
  test_user_character_data_routes.py      # Integration testing of character routes via the api_client fixture
```
