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

