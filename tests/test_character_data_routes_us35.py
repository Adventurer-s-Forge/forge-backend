import pytest

from forge_backend import user_character_data_routes
from forge_backend.storage import refresh_reference_type

UID = "us35-test-user"
CHARID = "0f8c1a7e-3d52-4b91-a7c8-6e2f91b40d35"


def _class_records():
    return [
        {
            "type": "class",
            "key": "srd-2024_warden",
            "name": "Warden",
            "document": "srd-2024",
            "data": {},
        },
        {
            "type": "class",
            "key": "srd-2024_rogue",
            "name": "Rogue",
            "document": "srd-2024",
            "data": {},
        },
    ]


def _headers():
    return {"X-User-Id": UID}


@pytest.fixture
def client(api_client, redis_conn):
    refresh_reference_type(redis_conn, "class", _class_records())
    user_character_data_routes._service.create_user_character(
        UID, CharacterRecord.model_validate({"id": CHARID, "name": "Gandalf"})
    )
    return api_client


@pytest.mark.integration
def test_save_valid_class_persists(client):
    """Selecting a valid class key persists it on the character record."""
    resp = client.put(
        f"/characters/{CHARID}/class", json={"classId": "srd-2024_warden"}, headers=_headers()
    )
    assert resp.status_code == 200
    record = client.get(f"/characters/{CHARID}", headers=_headers()).json()
    assert record["classId"] == "srd-2024_warden"


@pytest.mark.integration
def test_display_name_rejected(client):
    """Display names are not accepted; only reference keys validate."""
    resp = client.put(f"/characters/{CHARID}/class", json={"classId": "Warden"}, headers=_headers())
    assert resp.status_code == 400
    assert resp.json() == {"detail": "unknown classId"}


@pytest.mark.test_id("ST-5")
@pytest.mark.integration
def test_invalid_class_rejected_without_write(client, redis_conn):
    """Unknown class is rejected and the record is unchanged."""
    before = redis_conn.get(f"char:{UID}:{CHARID}")
    resp = client.put(f"/characters/{CHARID}/class", json={"classId": "nope"}, headers=_headers())
    assert resp.status_code == 400
    assert resp.json() == {"detail": "unknown classId"}
    assert redis_conn.get(f"char:{UID}:{CHARID}") == before


@pytest.mark.test_id("ST-5")
@pytest.mark.integration
def test_missing_class_rejected(client):
    """Absent classId fails body validation."""
    assert client.put(f"/characters/{CHARID}/class", json={}, headers=_headers()).status_code == 422


@pytest.mark.test_id("ST-5")
@pytest.mark.integration
def test_empty_class_rejected(client):
    """Empty classId fails body validation."""
    assert (
        client.put(
            f"/characters/{CHARID}/class", json={"classId": ""}, headers=_headers()
        ).status_code
        == 422
    )


@pytest.mark.test_id("ST-5")
@pytest.mark.integration
def test_old_alias_rejected(client):
    assert (
        client.put(
            f"/characters/{CHARID}/class", json={"class": "srd-2024_warden"}, headers=_headers()
        ).status_code
        == 422
    )


@pytest.mark.test_id("ST-6")
@pytest.mark.integration
def test_reselecting_class_replaces(client):
    """Exactly one classId value exists after re-selection."""
    client.put(
        f"/characters/{CHARID}/class", json={"classId": "srd-2024_warden"}, headers=_headers()
    )
    resp = client.put(
        f"/characters/{CHARID}/class", json={"classId": "srd-2024_rogue"}, headers=_headers()
    )
    assert resp.status_code == 200
    record = client.get(f"/characters/{CHARID}", headers=_headers()).json()
    assert record["classId"] == "srd-2024_rogue"
    assert "class" not in record


@pytest.mark.integration
def test_class_list_served_from_seed(client):
    """GET /classes returns the seeded records from Redis."""
    resp = client.get("/classes")
    assert resp.status_code == 200
    keys = sorted(r["key"] for r in resp.json())
    assert keys == ["srd-2024_rogue", "srd-2024_warden"]


@pytest.mark.integration
def test_unknown_character_returns_404(client):
    assert client.get("/characters/nonexistent", headers=_headers()).status_code == 404
    resp = client.put(
        "/characters/nonexistent/class", json={"classId": "srd-2024_warden"}, headers=_headers()
    )
    assert resp.status_code == 404


def test_missing_uid_header_returns_422():
    from fastapi.testclient import TestClient

    from forge_backend.main import app

    resp = TestClient(app).put("/characters/x/class", json={"classId": "srd-2024_warden"})
    assert resp.status_code == 422


def test_blank_uid_header_returns_422():
    from fastapi.testclient import TestClient

    from forge_backend.main import app

    resp = TestClient(app).put(
        "/characters/x/class",
        json={"classId": "srd-2024_warden"},
        headers={"X-User-Id": ""},
    )
    assert resp.status_code == 422
