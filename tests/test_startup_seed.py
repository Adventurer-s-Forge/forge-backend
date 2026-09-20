import pytest
from fastapi.testclient import TestClient

from forge_backend import ingest_database, main
from forge_backend.storage import REF_TYPES, count_reference, get_reference


class StubCaller:
    @staticmethod
    def _rec(prefix, i):
        return {
            "slug": f"{prefix}-{i}",
            "name": f"{prefix} {i}",
            "document__slug": "srd-2014",
            "extra": True,
        }

    def get_races(self):
        return [self._rec("race", 1), self._rec("race", 2)]

    def get_classes(self):
        return [self._rec("class", 1)]

    def get_backgrounds(self):
        return [self._rec("background", 1)]

    def get_items(self):
        return [self._rec("item", 1), self._rec("item", 2), self._rec("item", 3)]

    def get_spells(self):
        return [self._rec("spell", 1)]


def _patch_caller(monkeypatch):
    monkeypatch.setattr(ingest_database, "Open5eCaller", StubCaller)


def test_run_ingestion_formats_and_counts(monkeypatch):
    _patch_caller(monkeypatch)
    monkeypatch.setattr(ingest_database, "get_redis", lambda: "fake-conn")
    calls = []

    def fake_refresh(conn, ref_type, records):
        records = list(records)
        calls.append((conn, ref_type, records))
        return len(records)

    monkeypatch.setattr(ingest_database, "refresh_reference_type", fake_refresh)

    assert ingest_database.run_ingestion() == {
        "race": 2,
        "class": 1,
        "background": 1,
        "item": 3,
        "spell": 1,
    }
    assert [ref_type for _, ref_type, _ in calls] == list(REF_TYPES)
    for conn, ref_type, records in calls:
        assert conn == "fake-conn"
        for record in records:
            assert record["type"] == ref_type
            assert record["key"] == record["data"]["slug"]
            assert record["name"] == record["data"]["name"]
            assert record["document"] == record["data"]["document__slug"]


def test_lifespan_seeds_and_health_reports_counts(monkeypatch):
    monkeypatch.setattr(main, "run_ingestion", lambda: {"race": 2, "spell": 1})
    with TestClient(main.app) as client:
        assert client.get("/health").json() == {
            "status": "ok",
            "seed_counts": {"race": 2, "spell": 1},
        }


def test_lifespan_seed_failure_is_nonfatal(monkeypatch):
    def boom():
        raise RuntimeError("Open5e down")

    monkeypatch.setattr(main, "run_ingestion", boom)
    with TestClient(main.app) as client:
        assert client.get("/health").json() == {"status": "ok", "seed_counts": None}


@pytest.mark.integration
def test_run_ingestion_idempotent_against_redis(monkeypatch, redis_conn):
    _patch_caller(monkeypatch)
    monkeypatch.setattr(ingest_database, "get_redis", lambda: redis_conn)

    first = ingest_database.run_ingestion()
    assert set(first) == set(REF_TYPES)
    assert all(n > 0 for n in first.values())
    for ref_type in REF_TYPES:
        assert count_reference(redis_conn, ref_type) == first[ref_type]
    assert get_reference(redis_conn, "race", "race-1")["name"] == "race 1"

    second = ingest_database.run_ingestion()
    assert second == first
    for ref_type in REF_TYPES:
        assert count_reference(redis_conn, ref_type) == first[ref_type]
