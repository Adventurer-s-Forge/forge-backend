"""Key-only equipment validation tests (US-20 service slice)."""

from unittest.mock import patch

import pytest

from forge_backend.user_character_data_service import UserCharacterDataService

SEED_KEYS = ["srd-2024_longsword", "srd-2024_dagger", "srd-2024_shield"]


def _service():
    return UserCharacterDataService(redis_client=object())


def _stub_storage(initial):
    state = {"record": dict(initial), "writes": 0}

    def _get_character(conn, uid, charid):
        return state["record"]

    def _update(conn, uid, charid, record):
        state["writes"] += 1
        state["record"] = dict(record)

    return state, _get_character, _update


def _patch_refs(keys):
    return patch(
        "forge_backend.user_character_data_service.list_reference_keys",
        return_value=list(keys),
    )


def test_validate_equipment_rejects_unknown_without_write():
    svc = _service()
    base = {"name": "Gandalf", "classId": "srd-2024_warden"}
    state, get_character, update = _stub_storage(base)
    with (
        _patch_refs(SEED_KEYS),
        patch(
            "forge_backend.user_character_data_service.get_user_character",
            side_effect=get_character,
        ),
        patch("forge_backend.user_character_data_service.update_character", side_effect=update),
        pytest.raises(ValueError, match="unknown equipmentIds"),
    ):
        svc.set_character_equipment("uid", "char", ["srd-2024_longsword", "Vorpal Kumquat"])
    assert state["writes"] == 0
    assert state["record"] == base


def test_setter_missing_record_raises_key_error():
    svc = _service()
    with (
        patch("forge_backend.user_character_data_service.get_user_character", return_value=None),
        patch("forge_backend.user_character_data_service.list_reference_keys") as refs,
    ):
        with pytest.raises(KeyError):
            svc.set_character_equipment("uid", "missing", ["srd-2024_longsword"])
        refs.assert_not_called()


def test_setter_replaces_and_clears_preserving_unrelated_fields():
    svc = _service()
    base = {"name": "Gandalf", "classId": "srd-2024_warden"}
    state, get_character, update = _stub_storage(base)
    with (
        _patch_refs(SEED_KEYS),
        patch(
            "forge_backend.user_character_data_service.get_user_character",
            side_effect=get_character,
        ),
        patch("forge_backend.user_character_data_service.update_character", side_effect=update),
    ):
        record = svc.set_character_equipment("uid", "char", ["srd-2024_dagger", "srd-2024_shield"])
        assert record["equipmentIds"] == ["srd-2024_dagger", "srd-2024_shield"]
        assert record["classId"] == "srd-2024_warden"
        cleared = svc.set_character_equipment("uid", "char", [])
        assert cleared["equipmentIds"] == []
        assert cleared["classId"] == "srd-2024_warden"
    assert state["writes"] == 2
    assert state["record"]["equipmentIds"] == []


def test_setter_clear_skips_reference_lookup():
    svc = _service()
    base = {"name": "Gandalf"}
    state, get_character, update = _stub_storage(base)
    with (
        patch(
            "forge_backend.user_character_data_service.get_user_character",
            side_effect=get_character,
        ),
        patch("forge_backend.user_character_data_service.update_character", side_effect=update),
        patch("forge_backend.user_character_data_service.list_reference_keys") as refs,
    ):
        assert svc.set_character_equipment("uid", "char", [])["equipmentIds"] == []
        refs.assert_not_called()
    assert state["writes"] == 1
