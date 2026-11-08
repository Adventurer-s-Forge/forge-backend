import copy

import pytest
import requests
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

    def get_feats(self):
        return [self._rec("srd-2024_alert", "Alert", "srd-2024"),]

    def get_monsters(self):
        return [
            self._rec("srd-2024_aboleth", "Aboleth", "srd-2024"),
            self._rec("srd-2014_aboleth", "Aboleth", "srd-2014"),
        ]

    def get_magic_items(self):
        return [
            self._rec("srd-2024_magic-lens", "Magic Lens", "srd-2024"),
            self._rec("srd-2014_magic-lens", "Magic Lens", "srd-2014"),
        ]

    def get_conditions(self):
        return [
            {
                "key": "blinded",
                "name": "Blinded",
                "document": {"key": "core"},
                "descriptions": [
                    {"document": "srd-2024", "desc": "2024 blinded"},
                    {"document": "srd-2014", "desc": "2014 blinded"},
                ],
            },
            {
                "key": "charmed",
                "name": "Charmed",
                "document": "toh",
                "descriptions": [],
            },
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
        "feat": 1,
        "monster": 1,
        "magic_item": 1,
        "condition": 1,
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


@pytest.mark.test_id("ST-16")
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


@pytest.mark.parametrize("ref_type", ["skill", "condition"])
def test_projection_keeps_only_srd_2024_descriptions_without_mutation(ref_type):
    raw = {
        "key": "x",
        "name": "X",
        "document": "core",
        "descriptions": [_desc("srd-2024", "new"), _desc("srd-2014", "old")],
    }
    snapshot = copy.deepcopy(raw)
    out = ingest_database._reference_data(raw, ref_type)
    assert out["descriptions"] == [_desc("srd-2024", "new")]
    assert raw == snapshot


def test_condition_projection_retains_real_desc_fields():
    raw = {
        "key": "blinded",
        "name": "Blinded",
        "document": {"key": "core"},
        "descriptions": [
            {"document": "srd-2024", "desc": "2024 blinded"},
            {"document": "srd-2014", "desc": "2014 blinded"},
        ],
    }
    out = ingest_database._reference_data(raw, "condition")
    assert out["descriptions"] == [{"document": "srd-2024", "desc": "2024 blinded"}]


@pytest.mark.parametrize("ref_type", ["skill", "condition"])
@pytest.mark.parametrize("descriptions", [None, []])
def test_missing_or_empty_descriptions_project_to_empty(ref_type, descriptions):
    raw = {"key": "a", "document": "core", "descriptions": descriptions}
    assert ingest_database._reference_data(raw, ref_type)["descriptions"] == []
    assert (
        ingest_database._reference_data({"key": "a", "document": "core"}, ref_type)["descriptions"]
        == []
    )


def test_non_projected_type_passes_through_unchanged():
    other = {"key": "x", "descriptions": [_desc("srd-2014", "old")]}
    assert ingest_database._reference_data(other, "class") == other


@pytest.mark.parametrize("ref_type", ["skill", "condition"])
@pytest.mark.parametrize("bad", ["nope", ["nope"]])
def test_malformed_descriptions_fail(ref_type, bad):
    with pytest.raises(ValueError, match=f"invalid {ref_type} descriptions"):
        ingest_database._reference_data({"key": "a", "descriptions": bad}, ref_type)


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


@pytest.mark.integration
def test_malformed_condition_keeps_prior_cached_conditions(monkeypatch, redis_conn):
    _patch_caller(monkeypatch)
    monkeypatch.setattr(ingest_database, "get_redis", lambda: redis_conn)
    ingest_database.run_ingestion()
    assert count_reference(redis_conn, "condition") == 1

    class BadConditions(StubCaller):
        def get_conditions(self):
            return [
                {"key": "blinded", "name": "Blinded", "document": "core", "descriptions": "nope"}
            ]

    monkeypatch.setattr(ingest_database, "Open5eCaller", BadConditions)
    with pytest.raises(ValueError, match="invalid condition descriptions"):
        ingest_database.run_ingestion()
    assert count_reference(redis_conn, "condition") == 1
    assert get_reference(redis_conn, "condition", "blinded") is not None


@pytest.mark.integration
def test_failed_monster_fetch_keeps_prior_cache_and_lifespan_serves(monkeypatch, redis_conn):
    _patch_caller(monkeypatch)
    monkeypatch.setattr(ingest_database, "get_redis", lambda: redis_conn)
    ingest_database.run_ingestion()
    assert get_reference(redis_conn, "monster", "srd-2024_aboleth") is not None

    class FailingMonsters(StubCaller):
        def get_monsters(self):
            raise requests.ConnectionError("Open5e down")

    monkeypatch.setattr(ingest_database, "Open5eCaller", FailingMonsters)
    monkeypatch.setattr(main, "run_ingestion", ingest_database.run_ingestion)
    with pytest.raises(requests.ConnectionError):
        ingest_database.run_ingestion()
    assert get_reference(redis_conn, "monster", "srd-2024_aboleth") is not None

    with TestClient(main.app) as client:
        assert client.get("/health").json() == {"status": "ok", "seed_counts": None}


def _fake_pages(monkeypatch, pages):
    """Route requests.get by URL marker; ``pages`` maps a marker to (payload|Exception)."""
    from forge_backend import open_5e_caller

    def fake_get(url, **_kwargs):
        for marker, outcome in pages.items():
            if marker in url:
                if isinstance(outcome, Exception):
                    raise outcome
                return _FakeResponse(outcome)
        return _FakeResponse({"results": [], "next": None})

    monkeypatch.setattr(open_5e_caller.requests, "get", fake_get)


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


_CREATURES_PAGE_2 = "https://api.open5e.com/v2/creatures/?page=2&format=json"


@pytest.mark.integration
def test_monster_pagination_accepts_second_page_and_filters_documents(monkeypatch, redis_conn):
    def monster(key, doc):
        return {"key": key, "name": key, "document": {"key": doc}}

    _fake_pages(
        monkeypatch,
        {
            "creatures/?document__key": {
                "results": [monster("srd-2024_goblin", "srd-2024"), monster("x_wrong", "srd-2014")],
                "next": _CREATURES_PAGE_2,
            },
            "creatures/?page=2": {
                "results": [monster("srd-2024_ogre", "srd-2024"), monster("y_wrong", "other")],
                "next": None,
            },
        },
    )
    monkeypatch.setattr(ingest_database, "get_redis", lambda: redis_conn)
    assert ingest_database.run_ingestion()["monster"] == 2
    assert get_reference(redis_conn, "monster", "srd-2024_ogre") is not None
    assert get_reference(redis_conn, "monster", "x_wrong") is None


@pytest.mark.integration
def test_second_page_failure_keeps_prior_monsters(monkeypatch, redis_conn):
    import requests as _requests

    monster = {"key": "srd-2024_goblin", "name": "Goblin", "document": {"key": "srd-2024"}}
    _fake_pages(
        monkeypatch,
        {
            "creatures/?document__key": {"results": [monster], "next": _CREATURES_PAGE_2},
            "creatures/?page=2": {"results": [], "next": None},
        },
    )
    monkeypatch.setattr(ingest_database, "get_redis", lambda: redis_conn)
    ingest_database.run_ingestion()
    assert count_reference(redis_conn, "monster") == 1

    _fake_pages(
        monkeypatch,
        {
            "creatures/?document__key": {"results": [monster], "next": _CREATURES_PAGE_2},
            "creatures/?page=2": _requests.HTTPError("502"),
        },
    )
    with pytest.raises(_requests.HTTPError):
        ingest_database.run_ingestion()
    assert get_reference(redis_conn, "monster", "srd-2024_goblin") is not None
    assert count_reference(redis_conn, "monster") == 1
