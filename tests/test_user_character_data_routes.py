import pytest

UUID = "0f8c1a7e-3d52-4b91-a7c8-6e2f91b40d35"
UID = "route-test-user"
OTHER_UID = "route-test-other"


def _headers(uid=UID):
    return {"X-User-Id": uid}


def _payload(**overrides):
    payload = {"id": UUID, "name": "Joe Schmoe"}
    payload.update(overrides)
    return payload


def _create(api_client, payload=None, uid=UID):
    payload = payload if payload is not None else _payload()
    resp = api_client.post("/characters", json=payload, headers=_headers(uid))
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.mark.integration
def test_create_detail_ids_list_count_roundtrip(api_client):
    cid = _create(api_client)
    assert api_client.get(f"/characters/{cid}", headers=_headers()).json()["name"] == "Joe Schmoe"
    assert api_client.get("/characters/ids", headers=_headers()).json() == [cid]
    assert len(api_client.get("/characters", headers=_headers()).json()) == 1
    assert api_client.get("/characters/count", headers=_headers()).json() == 1


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
    assert api_client.get(f"/characters/{cid}", headers=_headers(OTHER_UID)).status_code == 404
    assert api_client.get(f"/characters/{cid}", headers=_headers()).status_code == 200


@pytest.mark.integration
@pytest.mark.parametrize(
    ("method", "path", "kwargs"),
    [
        ("post", "/characters", {"json": {"id": UUID, "name": "x"}}),
        ("get", "/characters", {}),
        ("get", "/characters/ids", {}),
        ("get", "/characters/count", {}),
        ("get", f"/characters/{UUID}", {}),
        ("put", f"/characters/{UUID}", {"json": {"id": UUID, "name": "x"}}),
        ("put", f"/characters/{UUID}/equipment", {"json": {"equipmentIds": []}}),
        ("put", f"/characters/{UUID}/spells", {"json": {"spellIds": []}}),
    ],
)
def test_missing_and_empty_headers_fail_all_operations(api_client, method, path, kwargs):
    for headers in ({}, {"X-User-Id": ""}):
        resp = getattr(api_client, method)(path, headers=headers, **kwargs)
        assert resp.status_code == 422
    assert api_client.get("/characters/count", headers=_headers()).json() == 0


@pytest.mark.integration
def test_legacy_create_body_rejected(api_client):
    resp = api_client.post(
        "/characters",
        json={"character_name": "Joe Schmoe", "user_name": "moobelle"},
        headers=_headers(),
    )
    assert resp.status_code == 422
    assert api_client.get("/characters", headers=_headers(OTHER_UID)).json() == []


@pytest.mark.integration
def test_persistence_collision_returns_409(api_client, redis_conn):
    _create(api_client)
    before = redis_conn.get(f"char:{UID}:{UUID}")
    resp = api_client.post("/characters", json=_payload(name="Other"), headers=_headers())
    assert resp.status_code == 409
    assert resp.json() == {"detail": "Character ID collision, retry"}
    assert redis_conn.get(f"char:{UID}:{UUID}") == before
    from forge_backend import storage

    assert storage.count_characters(redis_conn, UID) == 1


@pytest.mark.integration
def test_old_paths_removed(api_client):
    assert api_client.post("/user-character", json={}).status_code == 404
    assert api_client.get(f"/user-character/{UID}/list", headers=_headers()).status_code == 404
    assert api_client.get(f"/num-user-characters/{UID}").status_code == 404


@pytest.mark.integration
def test_unknown_fields_rejected(api_client):
    resp = api_client.post("/characters", json=_payload(owner="x"), headers=_headers())
    assert resp.status_code == 422
