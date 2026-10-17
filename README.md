# forge-backend

Adventurer's Forge backend: Redis data-access layer, rules engine, FastAPI server.

## Stack

- Python 3.12 + [uv](https://docs.astral.sh/uv/) (dependency management)
- Redis 7 (local dev via Docker Compose; seeded reference content + character data)
- Firebase Authentication (ID-token verification only; no service-account credential)
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
| `FIREBASE_PROJECT_ID` | `adv-forge`              | Checked against each token's `aud` and `iss`             |


`TEST_REDIS_URL` is never derived from `REDIS_URL`, so the test suite cannot flush dev data.

`FIREBASE_PROJECT_ID` is **NOT** a secret -- it already ships in the frontend budle as 
`VITE_FIREBASE_PROJECT_ID`. It must match the project and client authenticates against, or
ever token is rejected with `Invalid audience`.

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
warning and the app still serves (with `seed_counts: null`). A failed seed leaves whatever
was last seeded in place, so the reference endpoints keep serving stale-but-valid content
rather than empty lists.

## Authentication
Character routes require a Firebase ID token:

```
Authorization: Bearer <firebase id token>
```

`src/forge_backend/auth.py` is the only pace a uid enters the application. Tokens are verified
agaisnt Google's published JWKS (signature, `aud`, `iss`, `exp`), and the owner uid is the verified
`sub` claim. **No endpoint accepts a uid as a path segment, query parameter or body field.** -- if 
the client could name the uid, it could name someone else's.

Verification needs no service-account credential, only `FIREBASE_PROJECT_ID`

| Condition | Response |
|-----------|----------|
| no `Authorization` header | `401 {"detail": "missing bearer token"}` |
| malformed, expired or wrong-project token | `401 {"detail": "invalid or expired token"}` |
| google JWKS unreachable | `503 {"detail": "auth temporarily unavailable"}` |

The `503` is deliberate: a JWKS outage is not an invalid token, and returning `401` would sign 
users out over a transient network failure.

Ownership is enforced by the key namespace rather than by a check: a caller can only address
`char:{uid}:*` for their own verified uid, so another user's character is simply not found.
`PUT` and `DELETE` on a character the caller does not own return **404, not 403** -- a `403` 
would confirm the id exists.

## API

Contract is the OpenAPI schema generated from the FastAPI app (`src/forge_backend/main.py`,
title "Adventurer's Forge API", version `0.1.0`), pinned by `tests/test_openapi_contract.py`.
With the server running (`uv run uvicorn forge_backend.main:app`):

- Interactive docs: `http://localhost:8000/docs` (Swagger UI) and `http://localhost:8000/redoc`
- Raw schema: `http://localhost:8000/openapi.json`

### Reference content

Read-only, unauthenticated, seeded from Open5e at startup.

| Method | Path | operationId | Success | Errors |
|--------|------|-------------|---------|--------|
| `GET` | `/races` | `list_races` | `200 [ReferenceRecord]` | `422` |
| `GET` | `/classes` | `list_classes` | `200 [ReferenceRecord]` | `422` |
| `GET` | `/backgrounds` | `list_backgrounds` | `200 [ReferenceRecord]` | `422` |
| `GET` | `/equipment` | `list_items` | `200 [ReferenceRecord]` | `422` |
| `GET` | `/spells` | `list_spells` | `200 [ReferenceRecord]` | `422` |
| `GET` | `/health` | `get_health` | `200 HealthResponse` (`seed_counts` null when seeding failed) | N/A |

### Characters

All require `Authorization: Bearer <token>`; all can return `401`.

| Method | Path | operationId | Success | Errors |
|--------|------|-------------|---------|--------|
| `POST` | `/characters` | `create_character` | `201 CharacterRecord` (caller-supplied UUID) | `400` (unknown classId/equipmentIds/spellIds/skillIds, spell ineligible for class), `409` (id collision), `422` |
| `GET` | `/characters` | `list_characters` | `200 [CharacterRecord]` | `422` |
| `GET` | `/characters/ids` | `list_character_ids` | `200 [string]` (sorted) | `422` |
| `GET` | `/characters/count` | `count_characters` | `200 int` | `422` |
| `GET` | `/characters/{character_id}` | `get_character` | `200 CharacterRecord` | `404`, `422` |
| `PUT` | `/characters/{character_id}` | `save_character` | `200 CharacterRecord` (full replacement) | `400` (ID mismatch, unknown classId/equipmentIds/spellIds/skillIds, spell ineligible for class), `404`, `422` |
| `DELETE` | `/characters/{character_id}` | `delete_character` | `204` no body | `404` |

The client makes exactly **two writes** down from **eight writes** per character: a `POST` when the name is entered, 
and one full `PUT` at the end of creation (or when the user chooses to save and exit mid-way). There are no per-field 
routes -- a class change also prunes skills and spells, so a single-field update would store an inconsistent record.
The client recomputes the whole document and replaces it.

Error bodies are `{"detail": "<message>"}` (`ErrorResponse`); validation failure are FastAPI's `422 HTTPValidationError`.

### Request and response shapes

`CharacterRecord` is the **request** body for both `POST` and `PUT` -- 14 fields, `extra="forbid"`. Omitted fields take
blank defaults:

```json
{
  "id": "0f8c1a7e-3d52-4b91-a7c8-6e2f91b40d35",
  "name": "Gandalf",
  "level": 1,
  "raceId": null,
  "sizeChoice": null,
  "classId": null,
  "backgroundId": null,
  "abilities": { "method": null, "base": {}, "rolled": [], "originBonuses": {} },
  "equipmentChoice": { "class": null, "background": null },
  "purchasedItemIds": [],
  "proficientSkillIds": [],
  "expertiseIds": [],
  "spellIds": [],
  "completedSteps": ["name"]
}
```

`CharacterDocument` is the **response** shape -- the same 14 fields plus 4 the server owns:

| Field | Notes |
|-------|-------|
| `schemaVersion` | `1`; stamped at write time so a future shape change stays migratable |
| `ownerUid` | from the verified token, never from the body |
| `createdAt` | ISO 8601 UTC, set on create, carried forward verbatim on every save |
| `updatedAt` | ISO 8601 UTC, re-stamped on every write (millisecond precision) |

All four are **rejected in request bodies** -- the client strips them before sending, and `extra="forbid"`
turns an attempt into a `422` naming the field rather than silently overwriting `createdAt`.

Validation checks *shape, not completeness*: `null` means "not chosen yet", `{}` and `[]` mean "nothing assigned yet", 
because the wizard saves mid-flow. D&D rules validation (legal skills for a class, ability spreads, spell counts) stays
on the client -- it governs the user's own data, so it is a UX aid rather than a trust boundary. The one exception is 
reference integrity: `classId`, `purchasedItemIds`, `spellIds`, and `skillIds` are checked against seeded content and `spellIds` 
against class eligibility (`spell_rules.py`).

Notes on individual fields:

- `id` is **client-generated** (`crypto.randomUUID()`), validated as a canonical lowercase v4 UUID. The server never
  mints one. This makes `POST` retry-safe: a resend after a lost response returns `409` rather than creating a duplicate.
- `sizeChoice` is `"Small"`, `"Medium"` or `null`. Only Human and Tiefling offer a choice in SRD-2024; for the other
  sever species, the size is derived from `raceId` client-side.
- `equipmentChoice` holds the option *letter* from a "Choose A or B" list, not item ids. The Fighter offers A, B, **or**
  C, so it is a free string rather than an enum. `class` is a Python keyword, so the model aliases it and dumps with 
`by_alias=True`.
- `proficientSkillIds` holds **class picks only** -- background-granted skills are derived from `backgroundId` on the
  client. Stored as given; gratnts are not merged in.
- `completedSteps` is not a completion flag. A finished non-caster has seven entries and no `"spells"`, so never require
  all eight.

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
| `char:{uid}:{id}`    | STRING     | One player character as JSON (18-field `CharacterDocument`)         |
| `char:idx:{uid}`     | SET        | Character ids for that user; `SADD`ed idempotently on every save, source of truth for list/count |

- `{type}` ∈ `race` | `class` | `background` | `equipment` | `spell` | `skill` (`storage.REF_TYPES`).
- `{slug}` is the Open5e v2 key, constrained to `^[a-z0-9_-]+$` (e.g. `srd-2024_barbarian`).
- `{uid}` is the Firebase uid from the verified token. Firebase uids are **mixed case**, so the 
  lowercase `_SLUG_RE` must not be reused to validate them.
- No hashes, no TTLs: reference records are immutable between seeds and always read whole,
  so each is one JSON string and no key ever expires.

> **Do note delete `char:idx:*` keys by hand.** RedisInsight renders `:` as a path separator, so
> they look like a folder of derived metadata. They are not: `list_character_records` builds its
> result from the index, so removing one leaves the character documents intact but invisible to 
> the API.

### Seed documents

SRD edition is pinned per resource category and never mixed within one
(`ingest_database.REF_DOCUMENTS`)

| Type | Document |
|------|----------|
| `race`, `class`, `background`, `equipment`, `spell`, | `srd-2024` |
| `skill` | `core` (edition-neutral; the 18-skill list is unchanged between SRD 2014 and 2024) |

Records from other documents are skipped at ingest. Subspecies are excluded.

### Reference record envelope (`ref:{type}:{slug}` value)

Exactly five contract fields (extra keys ignored); every record is checked by
`validate_reference_record` before anything is written:

```json
{
  "type": "race",
  "key": "srd_dragonborn",
  "name": "Dragonborn",
  "document": "srd-2024",
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
| `add_new_character`        | One MULTI/EXEC: `SET` record (`NX`, so a duplicate id returns 0 and preserves the original) + `SADD` id; returns 1 if created, 0 otherwise. |
| `update_character`         | One `MULTI/EXEC`: plain `SET` of the full record + idempotent `SADD`. For a record the caller has already fetched. |
| `delete_character`         | One `MULTI/EXEC`: `DEL` record + `SREM` that single id. Returns `False` when the record did not exist. |
| `list_char_keys`           | Sorted `SMEMBERS` of `char:idx:{uid}`. |
| `list_character_records`   | Sorted ids then `MGET` of the records. |
| `count_characters`         | `SCARD` of `char:idx:{uid}`. |

Invariants:

- The index is rebuilt from scratch on every refresh (never incrementally patched), so
  `ref:idx:{type}` cannot drift from the stored `ref:{type}:*` keys.
- Refreshes are idempotent: re-running the same seed produces the same state.
- Record and index are always written in the same `MULTI/EXEC`, so no code path leaves one without
  the other.
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
  auth.py                           # ONLY place a uid enters the app; Firebase ID-token verification
  storage.py                        # ONLY module allowed to import redis (NFR-16)
  open_5e_caller.py                 # sync Open5e API client (deploy-time only, never at runtime)
  ingest_database.py                # run_ingestion(): fetch six ref types, full-replace per type
  main.py                           # FastAPI app (OpenAPI title/version/tags); lifespan seeds via run_ingestion; GET /health
  character_data_routes.py          # reference-content router (/races, /classes, /backgrounds, /equipment, /spells)
  character_data_service.py         # read service over seeded content
  user_character_data_service.py    # character CRUD + reference/spell-eligibility validation
  spell_rules.py                    # pure spell class-eligibility validator (no I/O)
  character_models.py               # CharacterRecord (request) / CharacterDocument (response), strict, extra="forbid"
  user_character_data_routes.py     # sole /characters router (create/list/ids/count/detail/save/delete)
tests/
  conftest.py                              # redis_conn (DB 15 + flush), api_client (token
                                           # override), no_outbound_http, as_user helper
  test_storage.py                          # unit: key formats, record validation
  test_storage_integration.py              # integration: refresh roundtrip, idempotency,
                                           # orphan cleanup, ref/char isolation, wipe
  test_startup_seed.py                     # ingestion envelope/counts, lifespan seed + failure
  test_character_models.py                 # CharacterRecord/CharacterDocument validation
  test_character_contract.py               # character CRUD over HTTP
  test_character_ownership.py              # cross-user isolation: 404 not 403
  test_auth.py                             # token verification and rejection paths
  test_reference_routes.py                 # reference endpoints served from the seed
  test_no_outbound_http.py                 # the app never calls Open5e while serving
  test_character_data_routes.py            # reference-content service (mocked)
  test_character_data_service.py           # reference read service
  test_user_character_data_service.py      # character CRUD service
  test_openapi_contract.py                 # OpenAPI pin: status codes, wire keys, schemas
  test_cors.py                             # preflight + allowed/rejected origins
docker-compose.yml                  # local Redis + RedisInsight
```
