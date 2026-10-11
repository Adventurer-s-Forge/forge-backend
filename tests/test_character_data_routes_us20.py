import pytest

from forge_backend import user_character_data_routes
from forge_backend.storage import (
    char_key,
    get_user_character,
    refresh_reference_type,
    update_character,
)

pytestmark = pytest.mark.integration

UID = "us20-test-user"
OTHER_UID = "us20-other-user"
CHARID = "26957"


def _item_records():
    return [
        {
            "type": "item",
            "key": "srd_longsword",
            "name": "Longsword",
            "document": "srd-2024",
            "data": {},
        },
        {"type": "item", "key": "srd_dagger", "name": "Dagger", "document": "srd-2024", "data": {}},
        {"type": "item", "key": "srd_shield", "name": "Shield", "document": "srd-2024", "data": {}},
    ]


def _headers(uid=UID):
    return {"X-User-Id": uid}


@pytest.fixture
def client(api_client, redis_conn):
    refresh_reference_type(redis_conn, "item", _item_records())
    user_character_data_routes._service.create_user_character(UID, "Gandalf", "test-user", CHARID)
    return api_client


def _equipment_url(charid=CHARID):
    return f"/characters/{charid}/equipment"


@pytest.mark.test_id("ST-18")
def test_save_valid_equipment_persists_and_roundtrips(client, redis_conn):
    # Arrange a populated class through storage; the class value must survive.
    record = get_user_character(redis_conn, UID, CHARID)
    record["class"] = "Wizard"
    update_character(redis_conn, UID, CHARID, record)

    resp = client.put(
        _equipment_url(), json={"equipment": ["Longsword", "Shield"]}, headers=_headers()
    )
    assert resp.status_code == 200
    assert resp.json()["equipment"] == ["Longsword", "Shield"]

    fetched = client.get(f"/characters/{CHARID}", headers=_headers()).json()
    assert fetched["equipment"] == ["Longsword", "Shield"]
    assert fetched["owner"] == "test-user"
    assert fetched["name"] == "Gandalf"
    assert fetched["class"] == "Wizard"

    raw = get_user_character(redis_conn, UID, CHARID)
    assert raw["equipment"] == ["Longsword", "Shield"]

    listed = client.get("/characters", headers=_headers()).json()
    assert next(r for r in listed if r["name"] == "Gandalf")["equipment"] == ["Longsword", "Shield"]


def test_mixed_slug_and_name_persists_verbatim_in_order(client):
    resp = client.put(
        _equipment_url(), json={"equipment": ["srd_dagger", "Shield"]}, headers=_headers()
    )
    assert resp.status_code == 200
    assert resp.json()["equipment"] == ["srd_dagger", "Shield"]
    assert client.get(f"/characters/{CHARID}", headers=_headers()).json()["equipment"] == [
        "srd_dagger",
        "Shield",
    ]


@pytest.mark.test_id("ST-17")
def test_clear_saved_selection_with_empty_list(client, redis_conn):
    assert (
        client.put(
            _equipment_url(), json={"equipment": ["Longsword"]}, headers=_headers()
        ).status_code
        == 200
    )
    resp = client.put(_equipment_url(), json={"equipment": []}, headers=_headers())
    assert resp.status_code == 200
    assert resp.json()["equipment"] == []
    fetched = client.get(f"/characters/{CHARID}", headers=_headers()).json()
    assert fetched["equipment"] == []
    assert get_user_character(redis_conn, UID, CHARID)["equipment"] == []


@pytest.mark.test_id("ST-17")
def test_clear_with_empty_reference_set(client, redis_conn):
    assert (
        client.put(
            _equipment_url(), json={"equipment": ["Longsword"]}, headers=_headers()
        ).status_code
        == 200
    )
    refresh_reference_type(redis_conn, "item", [])
    resp = client.put(_equipment_url(), json={"equipment": []}, headers=_headers())
    assert resp.status_code == 200
    assert client.get(f"/characters/{CHARID}", headers=_headers()).json()["equipment"] == []
    assert get_user_character(redis_conn, UID, CHARID)["equipment"] == []


@pytest.mark.parametrize(
    "selection",
    [
        ["Vorpal Kumquat"],
        ["Longsword", "Vorpal Kumquat"],
        [""],
        ["Longsword", ""],
    ],
    ids=["unknown-only", "mixed-valid-unknown", "empty-string", "mixed-empty-string"],
)
def test_unknown_entries_rejected_without_write(client, redis_conn, selection):
    assert (
        client.put(
            _equipment_url(), json={"equipment": ["Longsword"]}, headers=_headers()
        ).status_code
        == 200
    )
    before = redis_conn.get(char_key(UID, CHARID))
    resp = client.put(_equipment_url(), json={"equipment": selection}, headers=_headers())
    assert resp.status_code == 400
    assert resp.json() == {"detail": "unknown item"}
    assert redis_conn.get(char_key(UID, CHARID)) == before


def test_nonempty_rejected_when_reference_set_empty(client, redis_conn):
    refresh_reference_type(redis_conn, "item", [])
    before = redis_conn.get(char_key(UID, CHARID))
    resp = client.put(_equipment_url(), json={"equipment": ["Longsword"]}, headers=_headers())
    assert resp.status_code == 400
    assert resp.json() == {"detail": "unknown item"}
    assert redis_conn.get(char_key(UID, CHARID)) == before


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"equipment": "Longsword"},
        {"equipment": None},
        {"equipment": ["Longsword", 42]},
        {"equipment": [None]},
    ],
    ids=["missing-field", "scalar", "null", "non-string-member", "null-member"],
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
            _equipment_url(), json={"equipment": ["Longsword", "Shield"]}, headers=_headers()
        ).status_code
        == 200
    )
    resp = client.put(_equipment_url(), json={"equipment": ["Dagger"]}, headers=_headers())
    assert resp.status_code == 200
    assert client.get(f"/characters/{CHARID}", headers=_headers()).json()["equipment"] == ["Dagger"]
    before = get_user_character(redis_conn, UID, CHARID)
    resp = client.put(_equipment_url(), json={"equipment": ["Dagger"]}, headers=_headers())
    assert resp.status_code == 200
    assert get_user_character(redis_conn, UID, CHARID) == before


@pytest.mark.test_id("ST-19")
def test_repeated_entries_preserved_verbatim(client):
    resp = client.put(
        _equipment_url(), json={"equipment": ["Shield", "Shield"]}, headers=_headers()
    )
    assert resp.status_code == 200
    assert client.get(f"/characters/{CHARID}", headers=_headers()).json()["equipment"] == [
        "Shield",
        "Shield",
    ]


def test_missing_character_returns_404(client):
    resp = client.put(
        "/characters/nonexistent/equipment",
        json={"equipment": ["Longsword"]},
        headers=_headers(),
    )
    assert resp.status_code == 404
    assert resp.json() == {"detail": "character not found"}
    assert client.get("/characters/nonexistent", headers=_headers()).status_code == 404


def test_other_user_cannot_write_and_index_unchanged(client, redis_conn):
    assert (
        client.put(
            _equipment_url(), json={"equipment": ["Longsword"]}, headers=_headers()
        ).status_code
        == 200
    )
    resp = client.put(_equipment_url(), json={"equipment": ["Dagger"]}, headers=_headers(OTHER_UID))
    assert resp.status_code == 404
    assert resp.json() == {"detail": "character not found"}
    assert get_user_character(redis_conn, UID, CHARID)["equipment"] == ["Longsword"]
    assert redis_conn.smembers(f"char:idx:{OTHER_UID}") == set()


def test_missing_character_takes_precedence_over_unknown_item(client):
    resp = client.put(
        "/characters/nonexistent/equipment",
        json={"equipment": ["Vorpal Kumquat"]},
        headers=_headers(),
    )
    assert resp.status_code == 404
    assert resp.json() == {"detail": "character not found"}


@pytest.mark.parametrize("headers", [{}, {"X-User-Id": ""}], ids=["missing", "blank"])
@pytest.mark.parametrize("method", ["put", "get"], ids=["PUT", "GET"])
def test_missing_or_blank_identity_returns_422(client, headers, method):
    if method == "put":
        resp = client.put(_equipment_url(), json={"equipment": ["Longsword"]}, headers=headers)
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
    names = sorted(r["name"] for r in resp.json())
    assert names == ["Dagger", "Longsword", "Shield"]

    chosen = resp.json()[0]["name"]
    put_resp = client.put(_equipment_url(), json={"equipment": [chosen]}, headers=_headers())
    assert put_resp.status_code == 200
    assert client.get(f"/characters/{CHARID}", headers=_headers()).json()["equipment"] == [chosen]
    assert attempts == []
