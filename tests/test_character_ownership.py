"""One user can never reach another user's characters.

Ownership is enforced by the `char:{uid}:` key namespace rather than by an explicit
check, so a non-owned character is *not found* rather than forbidden. Returning 403
would confirm the id exists.
"""

import pytest
from conftest import OTHER_UID, UID, as_user
from test_character_contract import CHAR_ID, draft


@pytest.fixture
def seeded(api_client):
    assert api_client.post("/characters", json=draft()).status_code == 201
    return api_client


@pytest.mark.integration
def test_other_user_sees_an_empty_roster(seeded):
    as_user(seeded, OTHER_UID)
    assert seeded.get("/characters").json() == []
    assert seeded.get("/characters/ids").json() == []
    assert seeded.get("/characters/count").json() == 0


@pytest.mark.integration
@pytest.mark.parametrize("method", ["get", "put", "delete"])
def test_other_user_gets_404_not_403(seeded, method):
    as_user(seeded, OTHER_UID)
    call = getattr(seeded, method)
    response = call(f"/characters/{CHAR_ID}", json=draft()) if method == "put" else call(
        f"/characters/{CHAR_ID}"
    )
    assert response.status_code == 404


@pytest.mark.integration
def test_other_users_write_does_not_touch_the_owner(seeded):
    as_user(seeded, OTHER_UID)
    seeded.put(f"/characters/{CHAR_ID}", json=draft(name="Hijacked"))
    seeded.delete(f"/characters/{CHAR_ID}")

    as_user(seeded, UID)
    record = seeded.get(f"/characters/{CHAR_ID}")
    assert record.status_code == 200
    assert record.json()["name"] == "Thorin"


@pytest.mark.integration
def test_same_character_id_can_exist_for_two_users(seeded, redis_conn):
    """Ids are namespaced, so a collision across users in not a collision."""
    as_user(seeded, OTHER_UID)
    assert seeded.post("/characters", json=draft(name="Also Thorin")).status_code == 201
    assert seeded.get(f"/characters/{CHAR_ID}").json()["name"] == "Also Thorin"

    as_user(seeded, UID)
    assert seeded.get(f"/characters/{CHAR_ID}").json()["name"] == "Thorin"