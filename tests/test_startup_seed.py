import pytest
from fastapi.testclient import TestClient

from forge_backend import ingest_database, main
from forge_backend.storage import REF_TYPES, count_reference, get_reference


def _desc(doc, text):
    return {"document": {"key": doc}, "text": text}


class StubCaller:
    @staticmethod
    def _rec(key, name, doc, **extra):
        return {
            "key": key,
            "name": name,
            "document": {"key": doc, "name": doc},
            "desc": "x",
            **extra,
        }

    def get_races(self):
        return [
            self._rec("srd-2024_elf", "Elf", "srd-2024", is_subspecies=False),
            self._rec("srd_elf", "Elf", "srd-2014", is_subspecies=False),
            self._rec("srd-2024_elf_sub", "Elf (variant)", "srd-2024", is_subspecies=True),
            self._rec("toh_bugbear", "Bugbear", "toh", is_subspecies=False),
        ]

    def get_classes(self):
        return [
            self._rec("srd-2024_class", "Class", "srd-2024"),
            self._rec("srd_class", "Class", "srd-2014"),
        ]

    def get_backgrounds(self):
        return [
            self._rec("srd-2024_background", "Background", "srd-2024"),
            self._rec("srd_background", "Background", "srd-2014"),
        ]

    def get_equipment(self):
        return [
            self._rec("srd-2024_item_1", "Item 1", "srd-2024"),
            self._rec("srd-2024_item_2", "Item 2", "srd-2024"),
            self._rec("srd-2024_item_3", "Item 3", "srd-2024"),
            self._rec("srd_item_1", "Item 1", "srd-2014"),
        ]

    def get_spells(self):
        return [
            self._rec("srd-2024_spell", "Spell", "srd-2024"),
            self._rec("srd_spell", "Spell", "srd-2014"),
        ]

    def get_skills(self):
        return [
            {
                "key": "acrobatics",
                "name": "Acrobatics",
                "document": "core",
                "ability": "dex",
                "descriptions": [
                    _desc("srd-2024", "2024 acro"),
                    _desc("srd-2014", "2014 acro"),
                    _desc("a5e-ag", "a5e acro"),
                ],
            },
            {
                "key": "arcana",
                "name": "Arcana",
                "document": "core",
                "ability": "int",
                "descriptions": [_desc("srd-2024", "2024 arcana")],
            },
            self._rec("a5e-ag_culture", "Culture", "a5e-ag"),
        ]


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
        "equipment": 3,
        "spell": 1,
        "skill": 2,
    }
    assert [ref_type for _, ref_type, _ in calls] == list(REF_TYPES)
    by_type = {ref_type: records for _, ref_type, records in calls}
    assert [r["key"] for r in by_type["race"]] == ["srd-2024_elf"]
    assert [r["key"] for r in by_type["class"]] == ["srd-2024_class"]
    assert [r["key"] for r in by_type["background"]] == ["srd-2024_background"]
    assert [r["key"] for r in by_type["equipment"]] == [
        "srd-2024_item_1",
        "srd-2024_item_2",
        "srd-2024_item_3",
    ]
    assert [r["key"] for r in by_type["spell"]] == ["srd-2024_spell"]
    assert [r["key"] for r in by_type["skill"]] == ["acrobatics", "arcana"]
    for conn, ref_type, records in calls:
        assert conn == "fake-conn"
        for record in records:
            assert record["key"] == record["data"]["key"]
            raw_doc = record["data"]["document"]
            expected_raw = raw_doc["key"] if isinstance(raw_doc, dict) else raw_doc
            assert record["document"] == expected_raw
            assert record["document"] == ingest_database.REF_DOCUMENTS[ref_type]
    acro = next(r for r in by_type["skill"] if r["key"] == "acrobatics")
    assert acro["data"]["descriptions"] == [_desc("srd-2024", "2024 acro")]
    assert acro["data"]["ability"] == "dex"


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
    assert get_reference(redis_conn, "race", "srd-2024_elf")["name"] == "Elf"

    second = ingest_database.run_ingestion()
    assert second == first
    for ref_type in REF_TYPES:
        assert count_reference(redis_conn, ref_type) == first[ref_type]


@pytest.mark.integration
def test_reseed_removes_old_edition_preserves_character(monkeypatch, redis_conn):
    import json

    from forge_backend.storage import add_new_character, refresh_reference_type

    _patch_caller(monkeypatch)
    monkeypatch.setattr(ingest_database, "get_redis", lambda: redis_conn)
    refresh_reference_type(
        redis_conn,
        "class",
        [
            {
                "type": "class",
                "key": "srd_wizard",
                "name": "Wizard",
                "document": "srd-2014",
                "data": {},
            }
        ],
    )
    character = {
        "id": "0f8c1a7e-3d52-4b91-a7c8-6e2f91b40d35",
        "name": "Gandalf",
        "level": 1,
        "raceId": None,
        "classId": None,
        "backgroundId": None,
        "abilities": {"method": None, "base": {}, "rolled": [], "originBonuses": {}},
        "proficientSkillIds": [],
        "expertiseIds": [],
        "spellIds": [],
        "equipmentIds": [],
        "completedSteps": [],
    }
    uid = "seed-cutover-user"
    assert add_new_character(redis_conn, uid, character["id"], character) == 1
    before = redis_conn.get(f"char:{uid}:{character['id']}")
    before_idx = redis_conn.smembers(f"char:idx:{uid}")

    ingest_database.run_ingestion()
    assert get_reference(redis_conn, "class", "srd_wizard") is None
    assert get_reference(redis_conn, "class", "srd-2024_class") is not None
    assert redis_conn.get(f"char:{uid}:{character['id']}") == before
    assert json.loads(before) == character
    assert redis_conn.smembers(f"char:idx:{uid}") == before_idx


def test_skill_projection_boundaries():
    raw = {
        "key": "acrobatics",
        "name": "Acrobatics",
        "document": "core",
        "ability": "dex",
        "descriptions": [_desc("srd-2024", "new")],
    }
    out = ingest_database._reference_data(dict(raw), "skill")
    assert out["descriptions"] == [_desc("srd-2024", "new")]
    assert raw["descriptions"] == [_desc("srd-2024", "new")]

    assert (
        ingest_database._reference_data({"key": "a", "document": "core"}, "skill")["descriptions"]
        == []
    )
    assert (
        ingest_database._reference_data(
            {"key": "a", "document": "core", "descriptions": []}, "skill"
        )["descriptions"]
        == []
    )
    # non-skill passes through unchanged (identity)
    other = {"key": "x", "descriptions": [_desc("srd-2014", "old")]}
    assert ingest_database._reference_data(other, "class") is other


def test_malformed_skill_descriptions_fail():
    with pytest.raises(ValueError, match="invalid skill descriptions"):
        ingest_database._reference_data({"key": "a", "descriptions": "nope"}, "skill")
    with pytest.raises(ValueError, match="invalid skill descriptions"):
        ingest_database._reference_data({"key": "a", "descriptions": ["nope"]}, "skill")


@pytest.mark.integration
def test_malformed_skill_blocks_refresh(monkeypatch, redis_conn):
    class BadSkills(StubCaller):
        def get_skills(self):
            return [
                {
                    "key": "acrobatics",
                    "name": "Acrobatics",
                    "document": "core",
                    "descriptions": "nope",
                }
            ]

        def get_races(self):
            return []

        def get_classes(self):
            return []

        def get_backgrounds(self):
            return []

        def get_equipment(self):
            return []

        def get_spells(self):
            return []

    monkeypatch.setattr(ingest_database, "Open5eCaller", BadSkills)
    monkeypatch.setattr(ingest_database, "get_redis", lambda: redis_conn)
    with pytest.raises(ValueError, match="invalid skill descriptions"):
        ingest_database.run_ingestion()
    assert count_reference(redis_conn, "skill") == 0
