import json

import pytest

from forge_backend.storage import refresh_reference_type

UID = "us19-smoke-owner"
OTHER_UID = "us19-smoke-other"
UUID = "0f8c1a7e-3d52-4b91-a7c8-6e2f91b40d35"


def _headers(uid=UID):
    return {"X-User-Id": uid}


def _payload(**overrides):
    payload = {
        "id": UUID,
        "name": "Gandalf",
        "level": 1,
        "raceId": "draft_race",
        "classId": "test_warden",
        "backgroundId": "draft_background",
        "abilities": {
            "method": "roll",
            "base": {"STR": 15, "DEX": 14},
            "rolled": [15, 14, 13, 12, 10, 8],
            "originBonuses": {"STR": 2},
        },
        "proficientSkillIds": ["arcana"],
        "expertiseIds": ["arcana"],
        "spellIds": ["draft_spell"],
        "equipmentIds": ["srd_shield", "srd_shield"],
        "completedSteps": ["name", "class", "item"],
    }
    payload.update(overrides)
    return payload


@pytest.fixture
def seeded(api_client, redis_conn):
    refresh_reference_type(
        redis_conn,
        "class",
        [
            {
                "type": "class",
                "key": "test_warden",
                "name": "Warden",
                "document": "srd-2024",
                "data": {},
            }
        ],
    )
    refresh_reference_type(
        redis_conn,
        "item",
        [
            {
                "type": "item",
                "key": "srd_shield",
                "name": "Shield",
                "document": "srd-2024",
                "data": {},
            },
            {
                "type": "item",
                "key": "srd_dagger",
                "name": "Dagger",
                "document": "srd-2024",
                "data": {},
            },
        ],
    )
    return api_client


@pytest.mark.integration
def test_create_read_contract(seeded, redis_conn):
    payload = _payload()
    resp = seeded.post("/characters", json=payload, headers=_headers())
    assert resp.status_code == 201, resp.text
    assert resp.json() == payload
    raw = json.loads(redis_conn.get(f"char:{UID}:{UUID}"))
    assert raw == payload
    assert seeded.get(f"/characters/{UUID}", headers=_headers()).json() == payload
    assert seeded.get("/characters", headers=_headers()).json() == [payload]
    assert "owner" not in raw

    minimal = {"id": "11111111-2222-4333-8444-555555555555", "name": "Draft"}
    resp = seeded.post("/characters", json=minimal, headers=_headers())

    # duplicate preserves original
    dup = _payload(name="Other")
    resp = seeded.post("/characters", json=dup, headers=_headers())
    assert resp.status_code == 409
    assert resp.json() == {"detail": "Character ID collision, retry"}
    assert json.loads(redis_conn.get(f"char:{UID}:{UUID}")) == payload


@pytest.mark.integration
def test_save_reload_and_replace(seeded, redis_conn):
    from fastapi.testclient import TestClient

    from forge_backend import user_character_data_routes
    from forge_backend.main import app

    draft = {"id": UUID, "name": "Gandalf"}
    assert seeded.post("/characters", json=draft, headers=_headers()).status_code == 201
    payload = _payload(name="Gandalf the Grey")
    resp = seeded.put(f"/characters/{UUID}", json=payload, headers=_headers())
    assert resp.status_code == 200
    assert resp.json() == payload
    assert seeded.get(f"/characters/{UUID}", headers=_headers()).json() == payload
    assert seeded.get("/characters/ids", headers=_headers()).json() == [UUID]
    assert seeded.get("/characters/count", headers=_headers()).json() == 1

    # fresh client against same redis, no flush
    other = TestClient(app)
    from forge_backend import character_data_routes

    other_uid_service = user_character_data_routes._service
    old = other_uid_service.redis_client
    other_uid_service.redis_client = redis_conn
    character_data_routes.service.redis_client = redis_conn
    try:
        assert other.get(f"/characters/{UUID}", headers=_headers()).json() == payload
    finally:
        other_uid_service.redis_client = old
    # second save replaces, not merges
    replacement = _payload(
        name="Gandalf",
        classId=None,
        equipmentIds=[],
        proficientSkillIds=[],
        expertiseIds=[],
        spellIds=[],
        completedSteps=["name"],
        abilities={"method": None, "base": {}, "rolled": [], "originBonuses": {}},
        raceId=None,
        backgroundId=None,
    )
    resp = seeded.put(f"/characters/{UUID}", json=replacement, headers=_headers())
    assert resp.status_code == 200
    assert resp.json() == replacement
    assert seeded.get(f"/characters/{UUID}", headers=_headers()).json() == replacement
    assert seeded.get("/characters/ids", headers=_headers()).json() == [UUID]

    # minimal save resets to defaults
    minimal = {"id": UUID, "name": "Reset"}
    resp = seeded.put(f"/characters/{UUID}", json=minimal, headers=_headers())
    assert resp.status_code == 200
    assert resp.json()["classId"] is None
    assert resp.json()["equipmentIds"] == []
    assert resp.json()["completedSteps"] == []


@pytest.mark.test_id("ST-15")
@pytest.mark.integration
@pytest.mark.parametrize(
    ("body", "status", "detail"),
    [
        ({"id": UUID, "name": "   "}, 422, None),
        ({"id": UUID, "name": "G", "level": True}, 422, None),
        ({"id": UUID, "name": "G", "level": "5"}, 422, None),
        ({"id": UUID, "name": "G", "owner": "x"}, 422, None),
        ({"id": UUID, "name": "G", "abilities": {"nope": 1}}, 422, None),
        ({"id": UUID, "name": "G", "class": "Wizard"}, 422, None),
        ({"id": UUID, "name": "G", "equipment": ["Shield"]}, 422, None),
        ({"id": UUID, "name": "G", "equipmentIds": [5]}, 422, None),
        ({"id": UUID, "name": "G", "completedSteps": ["equipment"]}, 422, None),
        ({"id": UUID, "name": "G", "abilities": {"method": "epic"}}, 422, None),
        ({"id": UUID, "name": "G", "abilities": {"base": {"FOO": 1}}}, 422, None),
        ({"id": UUID, "name": "G", "classId": "nope"}, 400, "unknown classId"),
        (
            {"id": UUID, "name": "G", "equipmentIds": ["srd_shield", "nope"]},
            400,
            "unknown equipmentIds",
        ),
        (
            {"id": "11111111-2222-4333-8444-555555555555", "name": "G"},
            400,
            "id must match character_id",
        ),
    ],
)
def test_no_mutation_on_invalid_input(seeded, redis_conn, body, status, detail):
    assert (
        seeded.post(
            "/characters", json={"id": UUID, "name": "Gandalf"}, headers=_headers()
        ).status_code
        == 201
    )

    before = redis_conn.get(f"char:{UID}:{UUID}")
    before_idx = redis_conn.smembers(f"char:idx:{UID}")
    other_before = redis_conn.smembers(f"char:idx:{OTHER_UID}")
    resp = seeded.put(f"/characters/{UUID}", json=body, headers=_headers())
    assert resp.status_code == status, resp.text
    if detail:
        assert resp.json() == {"detail": detail}
    assert redis_conn.get(f"char:{UID}:{UUID}") == before
    assert redis_conn.smembers(f"char:idx:{UID}") == before_idx
    assert redis_conn.smembers(f"char:idx:{OTHER_UID}") == other_before


@pytest.mark.integration
def test_save_missing_record_404_without_create(seeded, redis_conn):
    resp = seeded.put(f"/characters/{UUID}", json={"id": UUID, "name": "G"}, headers=_headers())
    assert resp.status_code == 404
    assert resp.json() == {"detail": "character not found"}
    assert redis_conn.get(f"char:{UID}:{UUID}") is None


@pytest.mark.integration
def test_empty_seed_rejects_selections_allows_empty(seeded, redis_conn):
    from forge_backend.storage import refresh_reference_type

    refresh_reference_type(redis_conn, "class", [])
    refresh_reference_type(redis_conn, "item", [])
    assert (
        seeded.post("/characters", json={"id": UUID, "name": "G"}, headers=_headers()).status_code
        == 201
    )
    resp = seeded.put(
        f"/characters/{UUID}",
        json={"id": UUID, "name": "G", "classId": "test_warden"},
        headers=_headers(),
    )
    assert resp.status_code == 400
    resp = seeded.put(
        f"/characters/{UUID}",
        json={"id": UUID, "name": "G", "equipmentIds": ["srd_shield"]},
        headers=_headers(),
    )
    assert resp.status_code == 400
    resp = seeded.put(f"/characters/{UUID}", json={"id": UUID, "name": "G"}, headers=_headers())
    assert resp.status_code == 200


@pytest.mark.integration
def test_identity_and_isolation(seeded, redis_conn):
    payload = _payload()
    assert seeded.post("/characters", json=payload, headers=_headers()).status_code == 201
    # missing/empty header on all eight operations
    ops = [
        ("post", "/characters", {"json": payload}),
        ("get", "/characters", {}),
        ("get", "/characters/ids", {}),
        ("get", "/characters/count", {}),
        ("get", f"/characters/{UUID}", {}),
        ("put", f"/characters/{UUID}", {"json": payload}),
        ("put", f"/characters/{UUID}/class", {"json": {"classId": "test_warden"}}),
        ("put", f"/characters/{UUID}/equipment", {"json": {"equipmentIds": []}}),
    ]
    for method, path, kw in ops:
        for headers in ({}, {"X-User-Id": ""}):
            resp = getattr(seeded, method)(path, headers=headers, **kw)
            assert resp.status_code == 422, (method, path, headers, resp.text)
    # Bearer without header does not substitute
    resp = seeded.get("/characters", headers={"Authorization": "Bearer x"})
    assert resp.status_code == 422
    # other UID isolated
    assert seeded.get("/characters", headers=_headers(OTHER_UID)).json() == []
    assert seeded.get("/characters/ids", headers=_headers(OTHER_UID)).json() == []
    assert seeded.get("/characters/count", headers=_headers(OTHER_UID)).json() == 0
    assert seeded.get(f"/characters/{UUID}", headers=_headers(OTHER_UID)).status_code == 404
    assert (
        seeded.put(f"/characters/{UUID}", json=payload, headers=_headers(OTHER_UID)).status_code
        == 404
    )
    assert (
        seeded.put(
            f"/characters/{UUID}/class",
            json={"classId": "test_warden"},
            headers=_headers(OTHER_UID),
        ).status_code
        == 404
    )
    assert (
        seeded.put(
            f"/characters/{UUID}/equipment", json={"equipmentIds": []}, headers=_headers(OTHER_UID)
        ).status_code
        == 404
    )
    # original unchanged
    assert seeded.get(f"/characters/{UUID}", headers=_headers()).json() == payload


@pytest.mark.integration
def test_no_runtime_outbound_http(seeded, monkeypatch):
    import requests.sessions

    attempts = []

    def guarded(self, *a, **k):
        attempts.append((a, k))
        raise AssertionError("outbound HTTP blocked")

    monkeypatch.setattr(requests.sessions.Session, "request", guarded)
    payload = _payload()
    assert seeded.post("/characters", json=payload, headers=_headers()).status_code == 201
    assert seeded.put(f"/characters/{UUID}", json=payload, headers=_headers()).status_code == 200
    assert seeded.get("/classes").status_code == 200
    assert attempts == []


@pytest.mark.test_id("ST-16")
@pytest.mark.integration
def test_reseed_preserves_characters(seeded, redis_conn, monkeypatch):
    from forge_backend import ingest_database

    payload = _payload()
    assert seeded.post("/characters", json=payload, headers=_headers()).status_code == 201
    before = redis_conn.get(f"char:{UID}:{UUID}")
    before_idx = redis_conn.smembers(f"char:idx:{UID}")

    class Caller:
        def get_races(self):
            return []

        def get_classes(self):
            return [
                {
                    "key": "test_warden",
                    "name": "Warden",
                    "document": {"key": "srd-2024"},
                    "data": {},
                }
            ]

        def get_backgrounds(self):
            return []

        def get_items(self):
            return []

        def get_spells(self):
            return []

        def get_skills(self):
            return []

    monkeypatch.setattr(ingest_database, "Open5eCaller", Caller)
    monkeypatch.setattr(ingest_database, "get_redis", lambda: redis_conn)
    ingest_database.run_ingestion()
    assert redis_conn.get(f"char:{UID}:{UUID}") == before
    assert json.loads(before) == payload
    assert redis_conn.smembers(f"char:idx:{UID}") == before_idx
