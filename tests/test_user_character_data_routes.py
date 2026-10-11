import pytest

UID = "route-test-user"
OTHER_UID = "route-test-other"
CHARACTER_NAME = "Joe Schmoe"
USER_NAME = "moobelle"
EXPECTED_RECORD = {"owner": USER_NAME, "name": CHARACTER_NAME}


def _headers(uid=UID):
    return {"X-User-Id": uid}


def _create(api_client, name=CHARACTER_NAME, owner=USER_NAME, uid=UID):
    resp = api_client.post(
        "/characters",
        headers=_headers(uid),
        json={"character_name": name, "user_name": owner},
    )
    assert resp.status_code == 201
    return resp.json()["character_id"]


@pytest.mark.integration
def test_create_detail_ids_list_count_roundtrip(api_client):
    cid = _create(api_client)
    assert len(cid) == 8 and int(cid, 16) >= 0

    detail = api_client.get(f"/characters/{cid}", headers=_headers())
    assert detail.status_code == 200
    assert detail.json() == EXPECTED_RECORD

    ids = api_client.get("/characters/ids", headers=_headers())
    assert ids.status_code == 200
    assert ids.json() == [cid]

    listing = api_client.get("/characters", headers=_headers())
    assert listing.status_code == 200
    assert listing.json() == [EXPECTED_RECORD]

    count = api_client.get("/characters/count", headers=_headers())
    assert count.status_code == 200
    assert count.json() == 1


@pytest.mark.integration
def test_empty_user_returns_empty_collections(api_client):
    assert api_client.get("/characters", headers=_headers()).json() == []
    assert api_client.get("/characters/ids", headers=_headers()).json() == []
    assert api_client.get("/characters/count", headers=_headers()).json() == 0


@pytest.mark.integration
def test_missing_detail_returns_404(api_client):
    resp = api_client.get("/characters/fakeID", headers=_headers())
    assert resp.status_code == 404
    assert resp.json() == {"detail": "character not found"}


@pytest.mark.integration
def test_other_uid_isolated(api_client, redis_conn):
    cid = _create(api_client)

    assert api_client.get("/characters", headers=_headers(OTHER_UID)).json() == []
    assert api_client.get("/characters/ids", headers=_headers(OTHER_UID)).json() == []
    assert api_client.get("/characters/count", headers=_headers(OTHER_UID)).json() == 0
    other_detail = api_client.get(f"/characters/{cid}", headers=_headers(OTHER_UID))
    assert other_detail.status_code == 404
    other_class = api_client.put(
        f"/characters/{cid}/class",
        headers=_headers(OTHER_UID),
        json={"class": "Wizard"},
    )
    assert other_class.status_code == 404
    assert api_client.get(f"/characters/{cid}", headers=_headers()).json() == EXPECTED_RECORD


@pytest.mark.integration
@pytest.mark.parametrize(
    "method,path,kwargs",
    [
        ("POST", "/characters", {"json": {"character_name": "A", "user_name": "B"}}),
        ("GET", "/characters", {}),
        ("GET", "/characters/ids", {}),
        ("GET", "/characters/count", {}),
        ("GET", "/characters/deadbeef", {}),
        ("PUT", "/characters/deadbeef/class", {"json": {"class": "Wizard"}}),
    ],
)
def test_missing_and_empty_headers_fail_all_operations(api_client, method, path, kwargs):
    for headers in ({}, {"X-User-Id": ""}):
        resp = api_client.request(method, path, headers=headers, **kwargs)
        assert resp.status_code == 422, (method, path, headers)
    assert api_client.get("/characters/count", headers=_headers()).json() == 0


@pytest.mark.integration
def test_legacy_user_id_body_rejected(api_client):
    resp = api_client.post(
        "/characters",
        headers=_headers(),
        json={"user_id": UID, "character_name": "A", "user_name": "B"},
    )
    assert resp.status_code == 422
    assert api_client.get("/characters", headers=_headers()).json() == []
    assert api_client.get("/characters", headers=_headers(OTHER_UID)).json() == []


@pytest.mark.integration
def test_persistence_collision_returns_409(api_client, redis_conn, monkeypatch):
    from forge_backend import storage, user_character_data_routes

    cid = _create(api_client)
    before_ids = api_client.get("/characters/ids", headers=_headers()).json()
    monkeypatch.setattr(
        user_character_data_routes._service, "generate_character_id", lambda uid: cid
    )
    resp = api_client.post(
        "/characters",
        headers=_headers(),
        json={"character_name": "Other", "user_name": "other"},
    )
    assert resp.status_code == 409
    assert resp.json() == {"detail": "Character ID collision, retry"}
    assert api_client.get(f"/characters/{cid}", headers=_headers()).json() == (EXPECTED_RECORD)
    assert api_client.get("/characters/ids", headers=_headers()).json() == before_ids
    assert storage.count_characters(redis_conn, UID) == 1


@pytest.mark.integration
def test_old_paths_removed(api_client):
    assert api_client.post("/user-character", json={}).status_code == 404
    assert api_client.get(f"/user-character/{UID}/list", headers=_headers()).status_code == 404
    assert api_client.get(f"/num-user-characters/{UID}").status_code == 404


@pytest.mark.integration
def test_extra_record_fields_retained(api_client, redis_conn):
    from forge_backend import storage

    cid = _create(api_client)
    storage.update_character(
        redis_conn, UID, cid, {"owner": USER_NAME, "name": CHARACTER_NAME, "notes": "retained"}
    )
    detail = api_client.get(f"/characters/{cid}", headers=_headers()).json()
    assert detail["notes"] == "retained"
    assert "class" not in detail
    listing = api_client.get("/characters", headers=_headers()).json()
    assert listing[0]["notes"] == "retained"
