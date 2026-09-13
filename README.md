# forge-backenda

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

| Variable        | Default                        | Purpose                                  |
|-----------------|--------------------------------|------------------------------------------|
| `REDIS_URL`     | `redis://localhost:6379/0`     | Runtime/seed Redis (production sets this)|
| `TEST_REDIS_URL`| `redis://localhost:6379/15`    | Test-only Redis DB (flushed per test)    |

`TEST_REDIS_URL` is never derived from `REDIS_URL`, so the test suite cannot flush dev data.

## Run

```sh
uv run pytest        # unit + integration (integration skips if Redis unreachable)
uv run ruff check .  # lint
```

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
| `char:{uid}:{id}`    | STRING     | One player character as JSON *(reserved, CRUD not implemented yet)* |

- `{type}` ∈ `race` | `class` | `background` | `item` | `spell` (`storage.REF_TYPES`).
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

Invariants:

- The index is rebuilt from scratch on every refresh (never incrementally patched), so
  `ref:idx:{type}` cannot drift from the stored `ref:{type}:*` keys.
- Refreshes are idempotent: re-running the same seed produces the same state.
- Reference content is shared (no per-user prefix); character keys are per-player via `{uid}`.
- Production data lives in the logical DB from `REDIS_URL` (DB 0 locally); the test suite uses
  the separate logical DB from `TEST_REDIS_URL` (DB 15), flushed per test.

Schema behavior is pinned by tests: `test_storage.py` (key formats, envelope validation) and
`test_storage_integration.py` (refresh roundtrip, idempotency, orphan cleanup,
`ref:*`/`char:*` isolation, wipe).

## Layout

```text
src/forge_backend/
  config.py    # REDIS_URL (env, localhost default)
  storage.py   # ONLY module allowed to import redis (NFR-16)
tests/
  conftest.py                # redis_conn fixture (dedicated DB 15 + flush)
  test_storage.py            # unit: key formats, record validation
  test_storage_integration.py# integration: refresh roundtrip, idempotency,
                             # orphan cleanup, type/player-data isolation, wipe
docker-compose.yml  # local Redis + RedisInsight
```

