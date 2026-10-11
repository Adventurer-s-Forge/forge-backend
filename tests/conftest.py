import os

import pytest
import redis
from fastapi.testclient import TestClient

TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15")


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
    from forge_backend import character_data_routes, user_character_data_routes
    from forge_backend.main import app

    monkeypatch.setattr(character_data_routes.service, "redis_client", redis_conn)
    monkeypatch.setattr(user_character_data_routes._service, "redis_client", redis_conn)
    return TestClient(app)
