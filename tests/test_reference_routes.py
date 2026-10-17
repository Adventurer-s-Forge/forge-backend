"""The six reference endpoints, served from the seed."""

import pytest

REFERENCE_ROUTES = [
    ("/races", "race"),
    ("/classes", "class"),
    ("/backgrounds", "background"),
    ("/equipment", "equipment"),
    ("/spells", "spell"),
    ("/skills", "skill"),
]

ENVELOPE = {"type", "key", "name", "document", "data"}


@pytest.mark.integration
@pytest.mark.parametrize("path,ref_type", REFERENCE_ROUTES)
def test_served_from_seed_without_outbound_http(
    api_client, redis_conn, no_outbound_http, path, ref_type
):
    from forge_backend.storage import refresh_reference_type

    refresh_reference_type(
        redis_conn,
        ref_type,
        [
            {
                "type": ref_type,
                "key": "srd-2024_probe",
                "name": "Probe",
                "document": "srd-2024",
                "data": {"key": "srd-2024_probe"},
            }
        ],
    )

    response = api_client.get(path)
    assert response.status_code == 200
    assert [r["key"] for r in response.json()] == ["srd-2024_probe"]
    assert ENVELOPE <= set(response.json()[0])


@pytest.mark.integration
@pytest.mark.parametrize("path,_", REFERENCE_ROUTES)
def test_empty_seed_returns_empty_list(api_client, path, _):
    """An unseeded type  is 200 [], not 404 00 the client distinguishes
    "nothing seeded" from "endpoint missing".
    """
    assert api_client.get(path).json() == []


@pytest.mark.integration
@pytest.mark.parametrize("path,_", REFERENCE_ROUTES)
def test_reference_routes_need_no_token(api_client, path, _):
    """Reference content is public; only /characters require auth."""
    assert api_client.get(path).status_code == 200
