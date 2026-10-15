import os

import pytest
import redis
from fastapi.testclient import TestClient

TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")

UID = "testUserAAA"
OTHER_UID = "testUserBBB"


@pytest.fixture
def redis_conn():
    r = redis.Redis.from_url(TEST_REDIS_URL, decode_responses=True)
    try:
        r.ping()
    except redis.exceptions.RedisError:
        pytest.skip(f"Redis not reachable at {TEST_REDIS_URL}")
    r.flushdb()
    yield r
    r.flushdb()
    r.close()


@pytest.fixture
def api_client(redis_conn, monkeypatch):
    """In-process client with auth stubbed to `UID`
    
    Real Firebase tokens cannot be minted in tests, so `current_uid` is overridden.
    `auth.py`'s own verification is covered separately in `test_auth.py`, which
    exercises the dependency directly rather than through a route.
    
    Use `as_user(client, OTHER_UID)` to switch identity mid-test.
    """
    from forge_backend import character_data_routes, user_character_data_routes
    from forge_backend.auth import current_uid
    from forge_backend.main import app

    monkeypatch.setattr(character_data_routes.service, "redis_client", redis_conn)
    monkeypatch.setattr(user_character_data_routes._service, "redis_client", redis_conn)
    monkeypatch.setattr("forge_backend.main.run_ingestion", dict)

    app.dependency_overrides[current_uid] = lambda: UID
    yield TestClient(app)
    app.dependency_overrides.clear()


def as_user(client: TestClient, uid: str) -> TestClient:
    """Repoint the stubbed identity. Returns the same client for chaining."""
    from forge_backend.auth import current_uid

    client.app.dependency_overrides[current_uid] = lambda: uid
    return client


@pytest.fixture
def no_outbound_http(monkeypatch):
    """Fail any outbound HTTP. Open5e is a deploy-time dependency only; the app must
    never call it while serving a request."""
    import requests.sessions

    def _blocked(self, method, url, *args, **kwargs):
        raise AssertionError(f"unexpected outbound HTTP: {method} {url}")

    monkeypatch.setattr(requests.sessions.Session, "request", _blocked)