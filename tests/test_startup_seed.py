import pytest
from fastapi.testclient import TestClient

from forge_backend import ingest_database, main
from forge_backend.storage import REF_TYPES, count_reference, get_reference


class StubCaller:
    @staticmethod
    def _rec(key, name, doc, **extra):
        return {"key": key, "name": name,
                "document": {"key": doc, "name": doc}, 
                "desc": "x", **extra}

    def get_races(self):
        return [
            self._rec("srd_elf", "Elf", "srd-2014", is_subspecies=False),
            self._rec("srd_elf_sub", "Elf (variant)", "srd-2014", is_subspecies=True),
            self._rec("toh_bugbear", "Bugbear", "toh", is_subspecies=False),
        ]

    def get_classes(self):
        return [self._rec("srd_class", "Class", "srd-2014")]

    def get_backgrounds(self):
        return [self._rec("srd_background", "Background", "srd-2014")]

    def get_items(self):
        return [
            self._rec("srd_item_1", "Item 1", "srd-2014"),
            self._rec("srd_item_2", "Item 2", "srd-2014"),
            self._rec("srd_item_3", "Item 3", "srd-2014"),
        ]

    def get_spells(self):
        return [self._rec("srd_spell", "Spell", "srd-2014")]


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
        "race": 1,
        "class": 1,
        "background": 1,
        "item": 3,
        "spell": 1,
    }
    assert [ref_type for _, ref_type, _ in calls] == list(REF_TYPES)
    for conn, ref_type, records in calls:
        assert conn == "fake-conn"
        for record in records:
            assert record["key"] == record["data"]["key"]
            assert record["name"] == record["data"]["name"]
            assert record["document"] == record["data"]["document"]["key"]


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
    assert get_reference(redis_conn, "race", "srd_elf")["name"] == "Elf"

    second = ingest_database.run_ingestion()
    assert second == first
    for ref_type in REF_TYPES:
        assert count_reference(redis_conn, ref_type) == first[ref_type]
