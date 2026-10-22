"""PUT /characters/{id} validation, equipment selection, and resave behaviour.

Covers the replacement-save contract: invalid bodies never mutate stored state,
equipment selections round-trip verbatim, clearing works (including when the
reference set is empty), and resaving the same body is idempotent.
"""

import json

import pytest
from conftest import UID
from test_character_contract import CHAR_ID, draft

from forge_backend.storage import refresh_reference_type

RECORD_KEY = f"char:{UID}:{CHAR_ID}"
INDEX_KEY = f"char:idx:{UID}"
EQUIPMENT = ["srd-2024_longsword", "srd-2024_shield", "srd-2024_dagger"]


@pytest.fixture
def seeded(api_client, redis_conn):
    refresh_reference_type(
        redis_conn,
        "class",
        [
            {
                "type": "class",
                "key": "test_warden",
                "name": "Warden",
                "document": "srd-2024",
                "data": {},
            }
        ],
    )
    refresh_reference_type(
        redis_conn,
        "spell",
        [
            {
                "type": "spell",
                "key": "draft_spell",
                "name": "Draft Spell",
                "document": "srd-2024",
                "data": {"classes": [{"key": "test_warden", "name": "Warden"}]},
            }
        ],
    )
    refresh_reference_type(
        redis_conn,
        "equipment",
        [
            {
                "type": "equipment",
                "key": key,
                "name": key.removeprefix("srd-2024_").title(),
                "document": "srd-2024",
                "data": {},
            }
            for key in EQUIPMENT
        ],
    )
    assert api_client.post("/characters", json=draft()).status_code == 201
    return api_client


def _stored(redis_conn) -> dict:
    return json.loads(redis_conn.get(RECORD_KEY))


def _without_timestamp(record: dict) -> dict:
    return {k: v for k, v in record.items() if k != "updatedAt"}


@pytest.mark.test_id("ST-15")
@pytest.mark.integration
@pytest.mark.parametrize(
    ("body", "status", "detail"),
    [
        # Structural rejections (FastAPI / pydantic, 422).
        (draft(name="   "), 422, None),
        (draft(level=True), 422, None),
        (draft(level="5"), 422, None),
        (draft(level=21), 422, None),
        (draft(raceId=""), 422, None),
        (draft(sizeChoice="Large"), 422, None),
        (draft(purchasedItemIds=[5]), 422, None),
        (draft(purchasedItemIds=[""]), 422, None),
        (draft(completedSteps=["bogus"]), 422, None),
        (draft(abilities={"method": "epic"}), 422, None),
        (draft(abilities={"base": {"FOO": 1}}), 422, None),
        (draft(equipmentChoice={"class": "A", "extra": 1}), 422, None),
        (draft() | {"owner": "someone-else"}, 422, None),
        (draft() | {"class": "Wizard"}, 422, None),
        # Reference and business-rule rejections (400).
        (draft(classId="nope"), 400, "unknown classId"),
        (draft(purchasedItemIds=["srd-2024_shield", "nope"]), 400, "unknown equipmentIds"),
        (draft(purchasedItemIds=["Shield"]), 400, "unknown equipmentIds"),
        (draft(classId="test_warden", spellIds=["nope"]), 400, "unknown spellIds"),
        (draft(spellIds=["draft_spell"]), 400, "Character has no class selected"),
        (
            draft(classId="test_warden", spellIds=["draft_spell", "nope"]),
            400,
            "unknown spellIds",
        ),
        (
            draft(id="11111111-2222-4333-8444-555555555555"),
            400,
            "id must match character_id",
        ),
    ],
)
def test_invalid_put_is_rejected_without_mutation(seeded, redis_conn, body, status, detail):
    before = redis_conn.get(RECORD_KEY)
    before_idx = redis_conn.smembers(INDEX_KEY)

    resp = seeded.put(f"/characters/{CHAR_ID}", json=body)

    assert resp.status_code == status, resp.text
    if detail is not None:
        assert resp.json() == {"detail": detail}
    assert redis_conn.get(RECORD_KEY) == before
    assert redis_conn.smembers(INDEX_KEY) == before_idx


@pytest.mark.test_id("ST-17")
@pytest.mark.integration
def test_clear_saved_equipment_with_empty_list(seeded, redis_conn):
    resp = seeded.put(f"/characters/{CHAR_ID}", json=draft(purchasedItemIds=["srd-2024_longsword"]))
    assert resp.status_code == 200, resp.text

    resp = seeded.put(f"/characters/{CHAR_ID}", json=draft(purchasedItemIds=[]))
    assert resp.status_code == 200, resp.text
    assert resp.json()["purchasedItemIds"] == []
    assert seeded.get(f"/characters/{CHAR_ID}").json()["purchasedItemIds"] == []
    assert _stored(redis_conn)["purchasedItemIds"] == []


@pytest.mark.test_id("ST-17")
@pytest.mark.integration
def test_clear_with_empty_equipment_reference_set(seeded, redis_conn):
    resp = seeded.put(f"/characters/{CHAR_ID}", json=draft(purchasedItemIds=["srd-2024_longsword"]))
    assert resp.status_code == 200, resp.text
    refresh_reference_type(redis_conn, "equipment", [])

    resp = seeded.put(f"/characters/{CHAR_ID}", json=draft(purchasedItemIds=[]))
    assert resp.status_code == 200, resp.text
    assert seeded.get(f"/characters/{CHAR_ID}").json()["purchasedItemIds"] == []
    assert _stored(redis_conn)["purchasedItemIds"] == []


@pytest.mark.test_id("ST-17")
@pytest.mark.integration
def test_nonempty_equipment_rejected_when_reference_set_empty(seeded, redis_conn):
    refresh_reference_type(redis_conn, "equipment", [])
    before = redis_conn.get(RECORD_KEY)

    resp = seeded.put(f"/characters/{CHAR_ID}", json=draft(purchasedItemIds=["srd-2024_shield"]))
    assert resp.status_code == 400
    assert resp.json() == {"detail": "unknown equipmentIds"}
    assert redis_conn.get(RECORD_KEY) == before


PICK_A = {
    "key": "A",
    "label": "Chain Mail, Greatsword, Dungeoneer's Pack",
    "goldCp": 400,
    "grants": [
        {"text": "Chain Mail", "quantity": 1, "itemId": "srd-2024_chain-mail", "choosableFrom": None},
    ],
}

PICK_B = {
    "key": "B",
    "label": "50 GP",
    "goldCp": 5000,
    "grants": [],
}

@pytest.mark.test_id("ST-18")
@pytest.mark.integration
def test_save_valid_equipment_persists_and_roundtrips(seeded, redis_conn):
    body = draft(
        classId="test_warden",
        purchasedItemIds=["srd-2024_longsword", "srd-2024_shield"],
        equipmentChoice={"class": PICK_A, "background": PICK_B},
    )
    resp = seeded.put(f"/characters/{CHAR_ID}", json=body)
    assert resp.status_code == 200, resp.text
    expected = ["srd-2024_longsword", "srd-2024_shield"]
    assert resp.json()["purchasedItemIds"] == expected
    assert resp.json()["equipmentChoice"] == {"class": PICK_A, "background": PICK_B}

    fetched = seeded.get(f"/characters/{CHAR_ID}").json()
    assert fetched["purchasedItemIds"] == expected
    assert fetched["equipmentChoice"] == {"class": PICK_A, "background": PICK_B}
    assert fetched["classId"] == "test_warden"

    raw = _stored(redis_conn)
    assert raw["purchasedItemIds"] == expected
    assert raw["equipmentChoice"] == {"class": PICK_A, "background": PICK_B}

    listed = seeded.get("/characters").json()
    assert next(r for r in listed if r["id"] == CHAR_ID)["purchasedItemIds"] == expected


@pytest.mark.test_id("ST-19")
@pytest.mark.integration
def test_replace_and_resave_is_idempotent(seeded, redis_conn):
    assert (
        seeded.put(
            f"/characters/{CHAR_ID}",
            json=draft(purchasedItemIds=["srd-2024_longsword", "srd-2024_shield"]),
        ).status_code
        == 200
    )
    replacement = draft(purchasedItemIds=["srd-2024_dagger"])
    resp = seeded.put(f"/characters/{CHAR_ID}", json=replacement)
    assert resp.status_code == 200, resp.text
    assert seeded.get(f"/characters/{CHAR_ID}").json()["purchasedItemIds"] == ["srd-2024_dagger"]

    # Resaving the identical body changes nothing but the server-owned timestamp.
    assert seeded.put(f"/characters/{CHAR_ID}", json=replacement).status_code == 200
    first = _stored(redis_conn)
    assert seeded.put(f"/characters/{CHAR_ID}", json=replacement).status_code == 200
    second = _stored(redis_conn)
    assert _without_timestamp(second) == _without_timestamp(first)
    assert second["purchasedItemIds"] == ["srd-2024_dagger"]


@pytest.mark.test_id("ST-19")
@pytest.mark.integration
def test_repeated_equipment_entries_preserved_verbatim(seeded, redis_conn):
    repeated = ["srd-2024_shield", "srd-2024_shield"]
    resp = seeded.put(f"/characters/{CHAR_ID}", json=draft(purchasedItemIds=repeated))
    assert resp.status_code == 200, resp.text
    assert resp.json()["purchasedItemIds"] == repeated
    assert seeded.get(f"/characters/{CHAR_ID}").json()["purchasedItemIds"] == repeated
    assert _stored(redis_conn)["purchasedItemIds"] == repeated


@pytest.mark.test_id("ST-5")
@pytest.mark.integration
@pytest.mark.parametrize(
    ("class_id", "status", "detail"),
    [
        ("Warden", 400, "unknown classId"),
        ("nope", 400, "unknown classId"),
        ("", 422, None),
        (5, 422, None),
    ],
    ids=["display-name", "unknown-key", "empty-string", "non-string"],
)
def test_invalid_class_rejected_without_write(seeded, redis_conn, class_id, status, detail):
    before = redis_conn.get(RECORD_KEY)

    resp = seeded.put(f"/characters/{CHAR_ID}", json=draft(classId=class_id))

    assert resp.status_code == status, resp.text
    if detail is not None:
        assert resp.json() == {"detail": detail}
    assert redis_conn.get(RECORD_KEY) == before


@pytest.mark.test_id("ST-6")
@pytest.mark.integration
def test_reselecting_class_replaces(seeded, redis_conn):
    refresh_reference_type(
        redis_conn,
        "class",
        [
            {"type": "class", "key": key, "name": key, "document": "srd-2024", "data": {}}
            for key in ("test_warden", "test_rogue")
        ],
    )
    assert (
        seeded.put(f"/characters/{CHAR_ID}", json=draft(classId="test_warden")).status_code == 200
    )

    resp = seeded.put(f"/characters/{CHAR_ID}", json=draft(classId="test_rogue"))
    assert resp.status_code == 200, resp.text
    assert seeded.get(f"/characters/{CHAR_ID}").json()["classId"] == "test_rogue"

    stored = _stored(redis_conn)
    assert stored["classId"] == "test_rogue"
    assert "class" not in stored
