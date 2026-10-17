"""The /characters contract: CRUD, ownership, and the server-owned fields."""

import pytest
from conftest import UID

CHAR_ID = "0f8c1a7e-3d52-4b91-a7c8-6e2f91b40d35"
SERVER_FIELDS = ("schemaVersion", "ownerUid", "createdAt", "updatedAt")


def draft(character_id: str = CHAR_ID, **overrides) -> dict:
    """Exactly what the client's createDraft() sends, minus the stripped fields"""
    body = {
        "id": character_id,
        "name": "Thorin",
        "level": 1,
        "raceId": None,
        "sizeChoice": None,
        "classId": None,
        "backgroundId": None,
        "abilities": {
            "method": None,
            "base": {},
            "rolled": [],
            "originBonuses": {},
        },
        "equipmentChoice": {"class": None, "background": None},
        "purchasedItemIds": [],
        "proficientSkillIds": [],
        "expertiseIds": [],
        "spellIds": [],
        "completedSteps": ["name"],
    }
    return body | overrides


@pytest.mark.integration
def test_crud_roundtrip(api_client):
    assert api_client.get("/characters").json() == []

    created = api_client.post("/characters", json=draft())
    assert created.status_code == 201
    record = created.json()
    assert all(field in record for field in SERVER_FIELDS)
    assert record["ownerUid"] == UID
    assert record["schemaVersion"] == 1

    assert api_client.get("/characters").json() == [record]
    assert api_client.get(f"/characters/{CHAR_ID}").json() == record

    saved = api_client.put(f"/characters/{CHAR_ID}", json=draft(name="Thorin Fireforge"))
    assert saved.status_code == 200
    assert saved.json()["name"] == "Thorin Fireforge"

    assert api_client.delete(f"/characters/{CHAR_ID}").status_code == 204
    assert api_client.get("/characters").json() == []
    assert api_client.get(f"/characters/{CHAR_ID}").status_code == 404


@pytest.mark.integration
def test_empty_list_is_not_an_error(api_client):
    """A user with no characters get 200 [], never 404 -- the dashboard
    distinguishes "no characcters yet" from "request failed".
    """
    response = api_client.get("/characters")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.integration
def test_duplicate_id_is_409_and_preserves_the_original(api_client):
    created = api_client.post("/characters", json=draft()).json()
    saved = api_client.put(f"/characters/{CHAR_ID}", json=draft(name="Renamed")).json()

    assert saved["createdAt"] == created["createdAt"]
    assert saved["updatedAt"] >= created["updatedAt"]


@pytest.mark.integration
@pytest.mark.parametrize("field", SERVER_FIELDS)
def test_server_owned_fields_rejected_in_requests(api_client, field):
    """Never silently overwrite createdAt -- there is no other copy of it."""
    values = {
        "schemaVersion": 2,
        "ownerUid": "someone-else",
        "createdAt": "2020-01-01T00:00:00.000Z",
        "updatedAt": "2020-01-01T00:00:00.000Z",
    }
    response = api_client.post("/characters", json=draft(**{field: values[field]}))
    assert response.status_code == 422
    assert field in str(response.json())


@pytest.mark.integration
def test_put_requires_an_existing_record(api_client):
    """PUT is a replace, not an upsert."""
    assert api_client.put(f"/characters/{CHAR_ID}", json=draft()).status_code == 404


@pytest.mark.integration
def test_path_and_body_id_must_match(api_client):
    api_client.post("/characters", json=draft())
    other = "9c8b7a65-4321-4fed-8abc-0123456789ab"
    assert api_client.put(f"/characters/{CHAR_ID}", json=draft(other)).status_code == 400


@pytest.mark.integration
def test_second_delete_is_404(api_client):
    api_client.post("/characters", json=draft())
    assert api_client.delete(f"/characters/{CHAR_ID}").status_code == 204
    assert api_client.delete(f"/characters/{CHAR_ID}").status_code == 404
