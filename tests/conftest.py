import os

import pytest
import redis

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
