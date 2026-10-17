"""The app never calls Open5e while serving.

Ingestion is deploy-time only. If a route reaches for live reference data,
a slow or down Open5e becomes a slow or down API.
"""

import pytest

ALL_GET_ROUTES = [
    "/health",
    "/races",
    "/classes",
    "/backgrounds",
    "/equipment",
    "/spells",
    "/skills",
    "/characters",
    "/characters/ids",
    "characters/count",
]


@pytest.mark.integration
@pytest.mark.parametrize("path", ALL_GET_ROUTES)
def test_get_routes_make_no_outbound_http(api_client, no_outbound_http, path):
    assert api_client.get(path).status_code == 200


@pytest.mark.integration
def test_writes_make_no_outbound_http(api_client, no_outbound_http):
    from test_character_contract import CHAR_ID, draft

    assert api_client.post("/characters", json=draft()).status_code == 201
    assert api_client.put(f"/characters/{CHAR_ID}", json=draft(name="X")).status_code == 200
    assert api_client.delete(f"/characters/{CHAR_ID}").status_code == 204
