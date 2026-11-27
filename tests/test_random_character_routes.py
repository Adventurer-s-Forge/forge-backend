"""US-39 API proof: an authenticated unsaved preview, nothing written, keep-through-CRUD.

The shared fixture is seeded into Redis through the ordinary reference writer, so these
tests exercise the real service, the real route and the real validator together.
"""

import copy
import json
from types import SimpleNamespace

import pytest
import redis
from conftest import UID, creation_cases
from fastapi.testclient import TestClient

RANDOMIZE = "/characters/randomize"
REFERENCE_TYPES = ("race", "class", "background", "equipment", "skill", "spell", "feat")
SERVER_FIELDS = ("schemaVersion", "ownerUid", "createdAt", "updatedAt")
UNAVAILABLE = "Random character generation is unavailable because reference data is incomplete."
SUBCLASS = "srd-2024_champion"


@pytest.fixture
def cases():
    return creation_cases()


@pytest.fixture
def seed_references(redis_conn, cases):
    """Seed the fixture's reference envelopes, optionally leaving a type out."""
    from forge_backend.storage import refresh_reference_type

    def seed(*, skip: tuple[str, ...] = ()):
        for ref_type in REFERENCE_TYPES:
            if ref_type in skip:
                continue
            refresh_reference_type(redis_conn, ref_type, cases["references"][ref_type])

    return seed


@pytest.fixture
def seeded(api_client, seed_references):
    seed_references()
    return api_client


def snapshot(redis_conn) -> dict[str, bytes]:
    """Every key with a type-aware dump, so a no-write claim covers strings and sets."""
    return {key: redis_conn.dump(key) for key in sorted(redis_conn.scan_iter())}


def preview(client) -> dict:
    response = client.post(RANDOMIZE, json={})
    assert response.status_code == 200, response.text
    return response.json()


def keep_payload(record: dict) -> dict:
    return {key: value for key, value in record.items() if key not in SERVER_FIELDS}


@pytest.mark.test_id("ST-47")
class TestPreview:
    @pytest.mark.integration
    def test_a_preview_is_complete_and_carries_no_server_fields(self, seeded, redis_conn):
        seen = snapshot(redis_conn)

        record = preview(seeded)

        assert set(record) == {
            "id",
            "name",
            "level",
            "raceId",
            "sizeChoice",
            "classId",
            "fightingStyleId",
            "toolChoiceId",
            "backgroundId",
            "equipmentChoice",
            "purchasedItemIds",
            "walletCp",
            "characterTypePresetChoice",
            "abilities",
            "proficientSkillIds",
            "expertiseIds",
            "spellIds",
            "featIds",
            "classFeatChoices",
            "completedSteps",
        }
        for field in SERVER_FIELDS:
            assert field not in record
        assert record["level"] == 1
        assert record["abilities"]["method"] == "pointbuy"
        assert set(record["abilities"]["base"]) == {"STR", "DEX", "CON", "INT", "WIS", "CHA"}
        assert record["classId"] != SUBCLASS
        assert record["purchasedItemIds"] == []
        # The whole database is untouched: no character, no index, no reference rewrite.
        assert snapshot(redis_conn) == seen

    @pytest.mark.integration
    def test_generation_leaves_a_nonempty_roster_alone(self, seeded, redis_conn):
        from test_character_contract import CHAR_ID, draft

        assert seeded.post("/characters", json=draft(name="Existing")).status_code == 201
        before = snapshot(redis_conn)
        roster = seeded.get("/characters").json()

        record = preview(seeded)

        assert snapshot(redis_conn) == before
        assert seeded.get("/characters").json() == roster
        assert seeded.get(f"/characters/{CHAR_ID}").json()["name"] == "Existing"
        assert record["id"] != CHAR_ID

    @pytest.mark.integration
    def test_repeated_generation_keeps_producing_legal_varied_characters(self, seeded):
        cost = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}

        records = [preview(seeded) for _ in range(12)]

        assert len({record["id"] for record in records}) == len(records)
        assert (
            len({json.dumps(record["abilities"]["base"], sort_keys=True) for record in records}) > 1
        )
        for record in records:
            assert len(record["proficientSkillIds"]) >= 2
            assert set(record["completedSteps"]) >= {
                "name",
                "race",
                "class",
                "background",
                "equipment",
                "attributes",
                "skills",
            }
            base = record["abilities"]["base"]
            assert all(8 <= score <= 15 for score in base.values())
            assert sum(cost[score] for score in base.values()) <= 27

    @pytest.mark.integration
    def test_no_outbound_http_is_needed_to_generate_or_keep(self, seeded, no_outbound_http):
        record = preview(seeded)

        assert seeded.post("/characters", json=keep_payload(record)).status_code == 201


@pytest.mark.test_id("ST-49")
class TestKeep:
    @pytest.mark.integration
    def test_keeping_the_preview_persists_it_unchanged(self, seeded):
        record = preview(seeded)

        created = seeded.post("/characters", json=keep_payload(record))

        assert created.status_code == 201, created.text
        stored = created.json()
        assert stored["ownerUid"] == UID
        assert stored["schemaVersion"] == 1
        assert stored["createdAt"] and stored["updatedAt"]
        assert keep_payload(stored) == record

        fetched = seeded.get(f"/characters/{record['id']}").json()
        assert keep_payload(fetched) == record
        listed = seeded.get("/characters").json()
        assert [entry["id"] for entry in listed] == [record["id"]]

        # Keeping survives the feats re-derivation the save path performs.
        assert stored["featIds"] == record["featIds"]

    @pytest.mark.integration
    def test_keeping_twice_conflicts_and_preserves_the_first_record(self, seeded, redis_conn):
        record = preview(seeded)
        assert seeded.post("/characters", json=keep_payload(record)).status_code == 201
        before = snapshot(redis_conn)

        again = seeded.post("/characters", json=keep_payload(record))

        assert again.status_code == 409
        assert snapshot(redis_conn) == before

    @pytest.mark.integration
    def test_a_kept_preview_is_an_ordinary_owned_character(self, seeded):
        from conftest import OTHER_UID, as_user
        from test_character_contract import draft

        record = preview(seeded)
        assert seeded.post("/characters", json=keep_payload(record)).status_code == 201

        assert (
            seeded.put(
                f"/characters/{record['id']}", json=keep_payload(record) | {"name": "Renamed"}
            ).status_code
            == 200
        )
        assert seeded.get(f"/characters/{record['id']}").json()["name"] == "Renamed"

        as_user(seeded, OTHER_UID)
        assert seeded.get(f"/characters/{record['id']}").status_code == 404
        assert seeded.put(f"/characters/{record['id']}", json=draft()).status_code == 404
        assert seeded.delete(f"/characters/{record['id']}").status_code == 404

        as_user(seeded, UID)
        assert seeded.delete(f"/characters/{record['id']}").status_code == 204


@pytest.mark.test_id("ST-48")
class TestCompletedSaveValidation:
    @pytest.mark.integration
    def test_a_tampered_completed_character_is_rejected_on_create(self, seeded, redis_conn):
        record = preview(seeded)
        picks = record["proficientSkillIds"]
        broken = keep_payload(record) | {"proficientSkillIds": [picks[0], *picks[:-1]]}
        before = snapshot(redis_conn)

        response = seeded.post("/characters", json=broken)

        assert response.status_code == 400
        assert "unique" in response.json()["detail"]
        assert snapshot(redis_conn) == before

    @pytest.mark.integration
    def test_a_tampered_completed_character_is_rejected_on_save(self, seeded, redis_conn):
        record = preview(seeded)
        assert seeded.post("/characters", json=keep_payload(record)).status_code == 201
        before = snapshot(redis_conn)
        broken = keep_payload(record) | {
            "abilities": record["abilities"] | {"base": record["abilities"]["base"] | {"STR": 16}}
        }

        response = seeded.put(f"/characters/{record['id']}", json=broken)

        assert response.status_code == 400
        assert "8-15" in response.json()["detail"]
        assert snapshot(redis_conn) == before

    @pytest.mark.integration
    def test_an_overspent_finished_character_is_rejected_on_create(self, seeded, cases, redis_conn):
        """A record that breaks the rules is the caller's fault, not the seed's."""
        broken = copy.deepcopy(cases["validCharacters"]["fighter_soldier"])
        broken["abilities"]["base"]["STR"] = 15
        broken["abilities"]["base"]["DEX"] = 15
        broken["abilities"]["base"]["CON"] = 15
        broken["abilities"]["base"]["INT"] = 14
        before = snapshot(redis_conn)

        response = seeded.post("/characters", json=broken)

        assert response.status_code == 400
        assert "point-buy cost" in response.json()["detail"]
        assert snapshot(redis_conn) == before

    @pytest.mark.integration
    def test_a_partial_draft_still_saves_under_the_existing_contract(self, seeded, redis_conn):
        from test_character_contract import draft

        response = seeded.post("/characters", json=draft(name="Unfinished"))

        assert response.status_code == 201
        assert seeded.get("/characters").json()[0]["name"] == "Unfinished"

        # An unfinished point-buy draft (no completion markers) is not held to the full
        # contract either.
        partial = draft(name="Draft") | {
            "id": "9c8b7a65-4321-4fed-8abc-0123456789ab",
            "abilities": {
                "method": "pointbuy",
                "base": {"STR": 8},
                "rolled": [],
                "originBonuses": {},
            },
        }
        assert seeded.post("/characters", json=partial).status_code == 201
        assert len(seeded.get("/characters").json()) == 2


class TestReferenceUnavailable:
    @pytest.mark.integration
    def test_an_unseeded_database_is_a_503_with_no_writes(self, api_client, redis_conn):
        before = snapshot(redis_conn)

        response = api_client.post(RANDOMIZE, json={})

        assert response.status_code == 503
        assert response.json() == {"detail": UNAVAILABLE}
        assert snapshot(redis_conn) == before

    @pytest.mark.integration
    def test_a_malformed_seed_is_a_503_with_no_writes(
        self, api_client, seed_references, redis_conn
    ):
        seed_references(skip=("feat",))
        before = snapshot(redis_conn)

        response = api_client.post(RANDOMIZE, json={})

        assert response.status_code == 503
        assert response.json() == {"detail": UNAVAILABLE}
        assert snapshot(redis_conn) == before

    @pytest.mark.integration
    def test_a_datastore_failure_is_a_503(self, api_client, monkeypatch):
        from forge_backend import user_character_data_routes

        class BrokenConnection:
            def smembers(self, _key):
                raise redis.exceptions.ConnectionError("connection refused")

        monkeypatch.setattr(user_character_data_routes._service, "redis_client", BrokenConnection())

        response = api_client.post(RANDOMIZE, json={})

        assert response.status_code == 503
        assert response.json() == {"detail": UNAVAILABLE}

    @pytest.mark.integration
    def test_a_completed_keep_with_an_incomplete_seed_is_a_503(
        self, api_client, seed_references, cases
    ):
        seed_references(skip=("feat",))

        response = api_client.post("/characters", json=cases["validCharacters"]["fighter_soldier"])

        assert response.status_code == 503
        assert response.json() == {"detail": UNAVAILABLE}


class TestAuthentication:
    def test_a_missing_or_malformed_token_is_a_401(self, redis_conn, monkeypatch):
        from forge_backend import auth, main, user_character_data_routes

        monkeypatch.setattr(main, "run_ingestion", dict)
        monkeypatch.setattr(user_character_data_routes._service, "redis_client", redis_conn)
        # The dependency is left in place: only the JWKS lookup is stubbed, so the real
        # verification path (and its 401) is what answers.
        monkeypatch.setattr(
            auth._jwk_client,
            "get_signing_key_from_jwt",
            lambda _token: SimpleNamespace(key="not-a-key"),
        )
        client = TestClient(main.app)

        assert client.post(RANDOMIZE, json={}).status_code == 401
        rejected = client.post(RANDOMIZE, json={}, headers={"Authorization": "Bearer not-a-token"})
        assert rejected.status_code == 401
        assert rejected.json() == {"detail": "invalid or expired token"}
