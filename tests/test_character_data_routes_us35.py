import pytest

from forge_backend import user_character_data_routes
from forge_backend.storage import refresh_reference_type

UID = "us35-test-user"
CHARID = "26957"

CLASS_NAMES = [
    "Barbarian",
    "Bard",
    "Cleric",
    "Druid",
    "Fighter",
    "Monk",
    "Paladin",
    "Ranger",
    "Rogue",
    "Sorcerer",
    "Warlock",
    "Wizard",
]


def _class_records():
    return [
        {
            "type": "class",
            "key": f"srd_{name.lower()}",
            "name": name,
            "document": "srd-2014",
            "data": {},
        }
        for name in CLASS_NAMES
    ]


def _headers():
    return {"X-User-Id": UID}


@pytest.fixture
def client(api_client, redis_conn):
    refresh_reference_type(redis_conn, "class", _class_records())
    user_character_data_routes._service.create_user_character(UID, "Gandalf", "test-user", CHARID)
    return api_client


@pytest.mark.integration
def test_save_valid_class_persists(client):
    """Selecting a valid class persists it on the character record."""
    resp = client.put(f"/characters/{CHARID}/class", json={"class": "Wizard"}, headers=_headers())
    assert resp.status_code == 200
    record = client.get(f"/characters/{CHARID}", headers=_headers()).json()
    assert record["class"] == "Wizard"


@pytest.mark.integration
def test_save_class_by_slug_persists(client):
    """The seeded slug form is accepted and persisted verbatim."""
    resp = client.put(
        f"/characters/{CHARID}/class", json={"class": "srd_rogue"}, headers=_headers()
    )
    assert resp.status_code == 200
    record = client.get(f"/characters/{CHARID}", headers=_headers()).json()
    assert record["class"] == "srd_rogue"


@pytest.mark.test_id("ST-5")
@pytest.mark.integration
def test_invalid_class_rejected_without_write(client):
    """Unknown class is rejected and the record is unchanged."""
    before = client.get(f"/characters/{CHARID}", headers=_headers()).json()
    assert "class" not in before
    resp = client.put(
        f"/characters/{CHARID}/class", json={"class": "Illiudicor"}, headers=_headers()
    )
    assert resp.status_code == 400
    after = client.get(f"/characters/{CHARID}", headers=_headers()).json()
    assert after == before


@pytest.mark.test_id("ST-5")
@pytest.mark.integration
def test_missing_class_rejected(client):
    """Absent/null class fails body validation."""
    assert client.put(f"/characters/{CHARID}/class", json={}, headers=_headers()).status_code == 422
    assert (
        client.put(
            f"/characters/{CHARID}/class", json={"class": None}, headers=_headers()
        ).status_code
        == 422
    )


@pytest.mark.test_id("ST-5")
@pytest.mark.integration
def test_empty_class_rejected(client):
    """Empty class fails body validation."""
    assert (
        client.put(
            f"/characters/{CHARID}/class", json={"class": ""}, headers=_headers()
        ).status_code
        == 422
    )


@pytest.mark.test_id("ST-6")
@pytest.mark.integration
def test_reselecting_class_replaces(client):
    """Exactly one class value exists after re-selection."""
    assert (
        client.put(
            f"/characters/{CHARID}/class", json={"class": "Rogue"}, headers=_headers()
        ).status_code
        == 200
    )
    assert (
        client.put(
            f"/characters/{CHARID}/class", json={"class": "Cleric"}, headers=_headers()
        ).status_code
        == 200
    )
    record = client.get(f"/characters/{CHARID}", headers=_headers()).json()
    assert record["class"] == "Cleric"
    assert "classes" not in record


@pytest.mark.integration
def test_class_list_served_from_seed(client):
    """GET /classes returns the seeded records from Redis."""
    resp = client.get("/classes")
    assert resp.status_code == 200
    names = sorted(r["name"] for r in resp.json())
    assert names == sorted(CLASS_NAMES)


@pytest.mark.integration
def test_unknown_character_returns_404(client):
    assert client.get("/characters/nonexistent", headers=_headers()).status_code == 404
    resp = client.put("/characters/nonexistent/class", json={"class": "Wizard"}, headers=_headers())
    assert resp.status_code == 404


def test_missing_uid_header_returns_422():
    from fastapi.testclient import TestClient

    from forge_backend.main import app

    client = TestClient(app)
    assert client.get(f"/characters/{CHARID}").status_code == 422
    resp = client.put(f"/characters/{CHARID}/class", json={"class": "Wizard"})
    assert resp.status_code == 422


def test_blank_uid_header_returns_422():
    from fastapi.testclient import TestClient

    from forge_backend.main import app

    client = TestClient(app)
    headers = {"X-User-Id": ""}
    assert client.get(f"/characters/{CHARID}", headers=headers).status_code == 422
    resp = client.put(f"/characters/{CHARID}/class", json={"class": "Wizard"}, headers=headers)
    assert resp.status_code == 422
