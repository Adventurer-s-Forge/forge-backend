import pytest

from forge_backend import user_character_data_routes
from forge_backend.character_models import CharacterRecord
from forge_backend.storage import (
    char_key,
    get_user_character,
    refresh_reference_type,
    update_character,
)

pytestmark = pytest.mark.integration

UID = "us20-test-user"
OTHER_UID = "us20-other-user"
CHARID = "0f8c1a7e-3d52-4b91-a7c8-6e2f91b40d35"


def _item_records():
    return [
        {
            "type": "item",
            "key": "srd-2024_longsword",
            "name": "Longsword",
            "document": "srd-2024",
            "data": {},
        },
        {
            "type": "item",
            "key": "srd-2024_dagger",
            "name": "Dagger",
            "document": "srd-2024",
            "data": {},
        },
        {
            "type": "item",
            "key": "srd-2024_shield",
            "name": "Shield",
            "document": "srd-2024",
            "data": {},
        },
    ]


def _headers(uid=UID):
    return {"X-User-Id": uid}


@pytest.fixture
def client(api_client, redis_conn):
    refresh_reference_type(redis_conn, "item", _item_records())
    user_character_data_routes._service.create_user_character(
        UID, CharacterRecord.model_validate({"id": CHARID, "name": "Gandalf"})
    )
    return api_client


def _equipment_url(charid=CHARID):
    return f"/characters/{charid}/equipment"


@pytest.mark.test_id("ST-18")
def test_save_valid_equipment_persists_and_roundtrips(client, redis_conn):
    # Arrange a populated classId through storage; it must survive.
    record = get_user_character(redis_conn, UID, CHARID)
    record["classId"] = "srd-2024_warden"
    update_character(redis_conn, UID, CHARID, record)

    resp = client.put(
        _equipment_url(),
        json={"equipmentIds": ["srd-2024_longsword", "srd-2024_shield"]},
        headers=_headers(),
    )
    assert resp.status_code == 200
    assert resp.json()["equipmentIds"] == ["srd-2024_longsword", "srd-2024_shield"]

    fetched = client.get(f"/characters/{CHARID}", headers=_headers()).json()
    assert fetched["equipmentIds"] == ["srd-2024_longsword", "srd-2024_shield"]
    assert fetched["name"] == "Gandalf"
    assert fetched["classId"] == "srd-2024_warden"

    raw = get_user_character(redis_conn, UID, CHARID)
    assert raw["equipmentIds"] == ["srd-2024_longsword", "srd-2024_shield"]

    listed = client.get("/characters", headers=_headers()).json()
    assert next(r for r in listed if r["name"] == "Gandalf")["equipmentIds"] == [
        "srd-2024_longsword",
        "srd-2024_shield",
    ]


def test_display_names_rejected(client):
    resp = client.put(
        _equipment_url(), json={"equipmentIds": ["srd-2024_dagger", "Shield"]}, headers=_headers()
    )
    assert resp.status_code == 400
    assert resp.json() == {"detail": "unknown equipmentIds"}


@pytest.mark.test_id("ST-17")
def test_clear_saved_selection_with_empty_list(client, redis_conn):
    assert (
        client.put(
            _equipment_url(), json={"equipmentIds": ["srd-2024_longsword"]}, headers=_headers()
        ).status_code
        == 200
    )
    resp = client.put(_equipment_url(), json={"equipmentIds": []}, headers=_headers())
    assert resp.status_code == 200
    assert resp.json()["equipmentIds"] == []
    fetched = client.get(f"/characters/{CHARID}", headers=_headers()).json()
    assert fetched["equipmentIds"] == []
    assert get_user_character(redis_conn, UID, CHARID)["equipmentIds"] == []


@pytest.mark.test_id("ST-17")
def test_clear_with_empty_reference_set(client, redis_conn):
    assert (
        client.put(
            _equipment_url(), json={"equipmentIds": ["srd-2024_longsword"]}, headers=_headers()
        ).status_code
        == 200
    )
    refresh_reference_type(redis_conn, "item", [])
    resp = client.put(_equipment_url(), json={"equipmentIds": []}, headers=_headers())
    assert resp.status_code == 200
    assert client.get(f"/characters/{CHARID}", headers=_headers()).json()["equipmentIds"] == []
    assert get_user_character(redis_conn, UID, CHARID)["equipmentIds"] == []


@pytest.mark.parametrize(
    "selection",
    [
        ["Vorpal Kumquat"],
        ["srd-2024_longsword", "Vorpal Kumquat"],
        [""],
        ["srd-2024_longsword", ""],
    ],
    ids=["unknown-only", "mixed-valid-unknown", "empty-string", "mixed-empty-string"],
)
def test_unknown_entries_rejected_without_write(client, redis_conn, selection):
    assert (
        client.put(
            _equipment_url(), json={"equipmentIds": ["srd-2024_longsword"]}, headers=_headers()
        ).status_code
        == 200
    )
    before = redis_conn.get(char_key(UID, CHARID))
    resp = client.put(_equipment_url(), json={"equipmentIds": selection}, headers=_headers())
    assert resp.status_code in (400, 422)
    if resp.status_code == 400:
        assert resp.json() == {"detail": "unknown equipmentIds"}
    assert redis_conn.get(char_key(UID, CHARID)) == before


def test_nonempty_rejected_when_reference_set_empty(client, redis_conn):
    refresh_reference_type(redis_conn, "item", [])
    before = redis_conn.get(char_key(UID, CHARID))
    resp = client.put(
        _equipment_url(), json={"equipmentIds": ["srd-2024_longsword"]}, headers=_headers()
    )
    assert resp.status_code == 400
    assert resp.json() == {"detail": "unknown equipmentIds"}
    assert redis_conn.get(char_key(UID, CHARID)) == before


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"equipmentIds": "Longsword"},
        {"equipmentIds": None},
        {"equipmentIds": ["srd-2024_longsword", 42]},
        {"equipmentIds": [None]},
        {"equipment": ["srd-2024_longsword"]},
    ],
    ids=["missing-field", "scalar", "null", "non-string-member", "null-member", "old-alias"],
)
def test_malformed_bodies_rejected_without_write(client, redis_conn, body):
    before = redis_conn.get(char_key(UID, CHARID))
    resp = client.put(_equipment_url(), json=body, headers=_headers())
    assert resp.status_code == 422
    assert redis_conn.get(char_key(UID, CHARID)) == before


@pytest.mark.test_id("ST-19")
def test_replace_and_resave_is_idempotent(client, redis_conn):
    assert (
        client.put(
            _equipment_url(),
            json={"equipmentIds": ["srd-2024_longsword", "srd-2024_shield"]},
            headers=_headers(),
        ).status_code
        == 200
    )
    resp = client.put(
        _equipment_url(), json={"equipmentIds": ["srd-2024_dagger"]}, headers=_headers()
    )
    assert resp.status_code == 200
    assert client.get(f"/characters/{CHARID}", headers=_headers()).json()["equipmentIds"] == [
        "srd-2024_dagger"
    ]
    before = get_user_character(redis_conn, UID, CHARID)
    resp = client.put(
        _equipment_url(), json={"equipmentIds": ["srd-2024_dagger"]}, headers=_headers()
    )
    assert resp.status_code == 200
    assert get_user_character(redis_conn, UID, CHARID) == before


@pytest.mark.test_id("ST-19")
def test_repeated_entries_preserved_verbatim(client):
    resp = client.put(
        _equipment_url(),
        json={"equipmentIds": ["srd-2024_shield", "srd-2024_shield"]},
        headers=_headers(),
    )
    assert resp.status_code == 200
    assert client.get(f"/characters/{CHARID}", headers=_headers()).json()["equipmentIds"] == [
        "srd-2024_shield",
        "srd-2024_shield",
    ]


def test_missing_character_returns_404(client):
    resp = client.put(
        "/characters/nonexistent/equipment",
        json={"equipmentIds": ["srd-2024_longsword"]},
        headers=_headers(),
    )
    assert resp.status_code == 404
    assert resp.json() == {"detail": "character not found"}
    assert client.get("/characters/nonexistent", headers=_headers()).status_code == 404


def test_other_user_cannot_write_and_index_unchanged(client, redis_conn):
    assert (
        client.put(
            _equipment_url(), json={"equipmentIds": ["srd-2024_longsword"]}, headers=_headers()
        ).status_code
        == 200
    )
    resp = client.put(
        _equipment_url(), json={"equipmentIds": ["srd-2024_dagger"]}, headers=_headers(OTHER_UID)
    )
    assert resp.status_code == 404
    assert resp.json() == {"detail": "character not found"}
    assert get_user_character(redis_conn, UID, CHARID)["equipmentIds"] == ["srd-2024_longsword"]
    assert redis_conn.smembers(f"char:idx:{OTHER_UID}") == set()


def test_missing_character_takes_precedence_over_unknown_item(client):
    resp = client.put(
        "/characters/nonexistent/equipment",
        json={"equipmentIds": ["Vorpal Kumquat"]},
        headers=_headers(),
    )
    assert resp.status_code == 404
    assert resp.json() == {"detail": "character not found"}


@pytest.mark.parametrize("headers", [{}, {"X-User-Id": ""}], ids=["missing", "blank"])
@pytest.mark.parametrize("method", ["put", "get"], ids=["PUT", "GET"])
def test_missing_or_blank_identity_returns_422(client, headers, method):
    if method == "put":
        resp = client.put(
            _equipment_url(), json={"equipmentIds": ["srd-2024_longsword"]}, headers=headers
        )
    else:
        resp = client.get(f"/characters/{CHARID}", headers=headers)
    assert resp.status_code == 422


def test_items_served_from_seed_with_no_outbound_http(client, redis_conn, monkeypatch):
    import requests.sessions

    attempts = []
    real_request = requests.sessions.Session.request

    def _blocked(self, *args, **kwargs):
        attempts.append(args)
        raise AssertionError("unexpected outbound HTTP")

    monkeypatch.setattr(requests.sessions.Session, "request", _blocked)
    assert real_request is not None  # keep linters honest about the saved reference

    resp = client.get("/items")
    assert resp.status_code == 200
    keys = sorted(r["key"] for r in resp.json())
    assert keys == ["srd-2024_dagger", "srd-2024_longsword", "srd-2024_shield"]

    chosen = resp.json()[0]["key"]
    put_resp = client.put(_equipment_url(), json={"equipmentIds": [chosen]}, headers=_headers())
    assert put_resp.status_code == 200
    assert client.get(f"/characters/{CHARID}", headers=_headers()).json()["equipmentIds"] == [
        chosen
    ]
    assert attempts == []
