# Backend testing guide

This guide is for developers working in `forge-backend`. It describes the current
pytest setup and the patterns to follow when adding or changing tests. Run all commands
below from this directory.

## Setup and safe test execution

The backend uses Python 3.12+, uv, pytest, pytest-cov, and synchronous FastAPI
`TestClient` (with httpx). Development dependencies and pytest configuration live in
[`pyproject.toml`](pyproject.toml); uv resolves dependencies using `uv.lock`.

```sh
uv sync
# Start just Redis; RedisInsight is not needed for tests.
docker compose up -d redis

# Use a disposable database for BOTH connection paths.
export TEST_REDIS_URL=redis://localhost:6379/15
export REDIS_URL="$TEST_REDIS_URL"
uv run pytest
```

**These commands can delete data.** The `redis_conn` fixture calls `FLUSHDB` before
and after each test that uses it, including tests that depend on it indirectly through
`api_client`. Never point either URL at production, shared, or valuable development data.
Database 15 is only a convention, not a safety check: any database selected by
`TEST_REDIS_URL` will be flushed. Set the variables before starting pytest because
configuration is read at module import time.

`TEST_REDIS_URL` defaults to `redis://localhost:6379/15` and is independent of
`REDIS_URL`, whose runtime default is database 0. Every Redis-touching test now goes
through `redis_conn`: services accept an optional `redis_client` argument
(`UserCharacterDataService(redis_conn)`), and the legacy `cleanup_before_test()`
helper is gone because fixture flushes already isolate each test. Keep exporting both
variables: `REDIS_URL` still feeds `get_redis()` for services constructed without an
explicit client, the two module-level router services, and startup ingestion when a
test enters `TestClient` lifespan.

Run the suite serially against its dedicated database. Concurrent pytest processes
sharing it can flush each other's data. Parallel-worker execution is not configured;
adding it requires separate databases/connections per worker first.

## Useful commands

After exporting the safe URLs above:

```sh
# Full suite, with skip reasons visible
uv run pytest -ra

# Marked Redis integration tests
uv run pytest -m integration -ra

# Everything not marked integration (see the caveat below)
uv run pytest -m "not integration" -ra

# One module or one test
uv run pytest tests/test_storage.py
uv run pytest tests/test_storage_integration.py::test_roundtrip -v

# Select test names containing an expression
uv run pytest -k "invalid_class or reselecting_class" -v

# Stop on the first failure; enter the debugger at a failure
uv run pytest -x
uv run pytest tests/test_storage.py --pdb

# Inspect collection without executing tests
uv run pytest --collect-only -q

# Coverage of backend source, with missing lines shown
uv run pytest --cov=forge_backend --cov-report=term-missing

# Match the current CI test invocation and lint command
uv run pytest . --cov=.
uv run ruff check .
```

`-m "not integration"` excludes every Redis-dependent test: `test_storage_integration.py`
uses module-level `pytestmark`, and the service roundtrip tests take `redis_conn` and
are marked integration. For a targeted Redis-free run, `uv run pytest tests/test_storage.py`
exercises pure key/validation functions. Classify tests by dependencies and behavior, not
just filenames; for example, `test_character_data_routes.py` currently tests service
methods using mocks.

If Redis is unreachable, `redis_conn` skips dependent tests after a failed `PING`.
It does not turn Redis errors during the test into skips, and tests bypassing the
fixture do not receive this skip behavior. A green run with integration skips is not
proof of Redis behavior: check `-ra` output and run again with a reachable test database
before submitting storage or API changes.

CI is defined in [`.github/workflows/backend-ci.yaml`](.github/workflows/backend-ci.yaml).
It starts Docker Compose, sets both Redis URLs to database 15, runs
`uv run pytest . --cov=.`, then Ruff. The workflow targets pull requests to `main`;
its push branch list is currently empty. No coverage failure threshold is configured.
The source-focused coverage command above is useful locally; CI's broader `--cov=.`
command is the existing configuration, not an equivalent measurement scope.

## Organization and markers

Pytest discovers tests under `tests` (`testpaths` in `pyproject.toml`). Use
`test_<area>.py` modules and `test_<behavior>` functions, with names describing the
observable outcome. Keep related cases together; use module-local helpers or fixtures
for data specific to that area and `tests/conftest.py` for genuinely shared setup.

| Area | Examples to consult |
| --- | --- |
| Pure storage key and record validation | `tests/test_storage.py` |
| Redis persistence, refresh, idempotency, and namespace isolation | `tests/test_storage_integration.py` |
| Mocked service boundaries | `tests/test_character_data_service.py` |
| API persistence, identity namespaces, validation, and collisions | `tests/test_user_character_data_routes.py` |
| Reference routes and class-selection transitions | `tests/test_character_data_routes_us35.py` |
| Ingestion formatting and application lifespan | `tests/test_startup_seed.py` |
| Public API schema and browser CORS behavior | `tests/test_openapi_contract.py`, `tests/test_cors.py` |

Two custom markers are registered:

- `@pytest.mark.integration`: tests requiring reachable Redis. Apply it to individual
  tests in mixed modules, or use `pytestmark = pytest.mark.integration` when the whole
  module requires Redis. Fixture dependencies do not automatically apply this marker.
- `@pytest.mark.test_id("ST-5")`: links a test to a specification test-case ID. Examples
  use `ST-5` for invalid class selection and `ST-6` for re-selection. This is metadata,
  not a plugin that checks requirements coverage or updates documents automatically.

Use existing specification IDs rather than inventing unrelated identifiers.
For story work, consult that story's acceptance criteria and the matching requirements
traceability row in the project architecture document. Keep the relevant
specification/traceability entries current;record preconditions, inputs, steps, and
expected results so cases are reproducible.

## Shared fixtures and API lifecycle

[`tests/conftest.py`](tests/conftest.py) provides function-scoped fixtures:

- `redis_conn`: creates a redis-py connection with `decode_responses=True`, checks
  connectivity, flushes the selected database, yields the connection, then flushes
  again and closes it. Each dependent test starts with an empty database; seed only
  the records needed for that test, preferably through storage functions such as
  `refresh_reference_type` and `add_new_character`. Never add per-test manual cleanup:
  the fixture flush covers it.
- `api_client`: depends on `redis_conn` and `monkeypatch`. It replaces the Redis
  connections on `character_data_routes.service` and
  `user_character_data_routes._service`, then returns `TestClient(app)`. It exercises
  in-process HTTP routing against real test Redis; no uvicorn process is required.
  Monkeypatch restores the replaced attributes after the test.

Services take an optional `redis_client` (`CharacterDataService(redis_conn)`,
`UserCharacterDataService(redis_conn)`) and default to the runtime `get_redis()`
connection when omitted. New Redis-touching tests take `redis_conn` directly or go
through `api_client`; they do not build services with implicit runtime connections.

The shared `api_client` is **not** entered as a context manager, so it does not run
application startup/shutdown lifespan. This keeps ordinary route tests from triggering
startup ingestion. For lifespan behavior, follow `test_startup_seed.py`: patch
`forge_backend.main.run_ingestion` first and use `with TestClient(main.app) as client:`.
Do not enter a client context without isolating ingestion; startup can access Redis
and the upstream content API.

Character requests currently use `headers={"X-User-Id": "test-user"}` to select an
owner namespace. This is temporary identity plumbing, not Firebase authentication.
Test missing/blank headers and cross-user isolation, but do not treat header-based
tests as proof of authenticated authorization.

## Writing focused, deterministic tests

Follow the existing plain-function style: arrange minimal input/setup, act through
the public function or HTTP endpoint, and assert the observable result. Comments or
a short docstring should explain a non-obvious invariant, not restate each line.

- **Assert behavior, not just execution.** Verify exact returned records, status codes,
  meaningful response fields, and state transitions. For rejected writes, compare
  persisted state before and after. The invalid-class test is a useful example.
- **Exercise boundaries and failure paths.** Cover invalid envelopes, missing records,
  duplicate IDs, empty refreshes, re-selection, orphan cleanup, idempotent reruns, and
  reference/player or user/user isolation where relevant to the change.
- **Parameterize cases sharing the same behavior.** `test_storage.py` uses
  `@pytest.mark.parametrize` for invalid records; route tests parameterize missing
  identity headers across endpoints. Keep different behaviors separate for useful
  failure messages; descriptive parameter IDs are helpful for larger tables.
- **Use `pytest.raises` for expected exceptions.** Assert the intended exception type;
  check message content only when it is part of the contract. Do not catch broad
  exceptions or suppress failures to make a test pass.
- **Keep inputs local and deterministic.** Use small record dictionaries and fixed
  user/character IDs. Do not depend on seeded developer data, test execution order,
  live Open5e responses, sleeps, or a particular random ID value. For generated IDs,
  check the required format; force collisions explicitly when testing rejection.
- **Preserve the architecture boundary.** Pure rules/validation tests need no I/O.
  Mock storage boundaries for isolated service tests; use real Redis for storage
  semantics and end-to-end route persistence. Direct fixture Redis access is useful
  for arranging exceptional states or independently checking persistence, not a
  pattern for application code to bypass the storage layer.

### Patching dependencies

Both pytest's `monkeypatch` and `unittest.mock.patch` are established in this suite.
Patch the name **where the tested code looks it up**, not merely where it was defined.
For example, service tests patch `forge_backend.character_data_service.get_reference`
and `get_redis`; lifespan tests patch `forge_backend.main.run_ingestion`.
Patch constructors' dependencies before constructing the service.

Prefer small controlled stubs when their outputs drive meaningful behavior.
`StubCaller` in `test_startup_seed.py` supplies deterministic upstream records while
integration coverage still uses real Redis. Use monkeypatch or scoped `patch` so
changes are restored automatically. Do not add permanent tests that only repeat a
mock's configured return value or assert incidental internal call sequences: verify
validation, filtering, persistence, or another consumer-visible contract instead.

## Before submitting a change

1. Derive cases from the affected behavior/story and reproduce a bug with a focused
   failing case before fixing it when practical.
2. Run the affected tests, then the full suite with both URLs targeting disposable
   Redis. Inspect failures **and skips**; do not weaken assertions or skip a failing
   test to obtain a green result.
3. Run `uv run ruff check .` and inspect source-focused coverage for unexercised
   branches relevant to the change. Coverage percentages alone do not establish
   correctness.
4. For behavioral changes, also exercise the changed public path (for example, an
   in-process API request followed by a persisted-record read). Document any limits
   of local verification; TestClient does not prove deployed networking or browser
   behavior.
5. Update affected test-case and traceability documentation in the same PR, and
   reference the story/issue. Passing local checks does not replace teammate review,
   green CI, or deployed verification.
