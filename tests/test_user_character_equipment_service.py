"""Redis-free unit tests for equipment selection (US-20 service slice)."""

from unittest.mock import patch

import pytest

from forge_backend.user_character_data_service import UserCharacterDataService

SEED = [
    {"key": "srd_longsword", "name": "Longsword"},
    {"key": "srd_dagger", "name": "Dagger"},
    {"key": "srd_shield", "name": "Shield"},
]


def _service():
    return UserCharacterDataService(redis_client=object())


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Longsword", True),
        ("srd_dagger", True),
        ("Shield", True),
        ("Vorpal Kumquat", False),
        ("longsword", False),
        ("SRD_DAGGER", False),
        ("", False),
    ],
)
def test_item_exists_resolves_names_slugs_case_sensitively(value, expected):
    svc = _service()
    with patch(
        "forge_backend.user_character_data_service.list_reference_records", return_value=list(SEED)
    ):
        assert svc.item_exists(value) is expected


def test_item_exists_with_no_seeded_records():
    svc = _service()
    with patch("forge_backend.user_character_data_service.list_reference_records", return_value=[]):
        assert svc.valid_item_values() == set()
        assert svc.item_exists("Longsword") is False


def _stub_storage(initial):
    state = {"record": dict(initial), "writes": 0}

    def _get_character(conn, uid, charid):
        return state["record"]

    def _update(conn, uid, charid, record):
        state["writes"] += 1
        state["record"] = dict(record)

    return state, _get_character, _update


def test_setter_rejects_mixed_valid_invalid_without_write():
    svc = _service()
    base = {"owner": "test-user", "name": "Gandalf", "class": "Wizard"}
    state, get_character, update = _stub_storage(base)
    with (
        patch(
            "forge_backend.user_character_data_service.list_reference_records",
            return_value=list(SEED),
        ),
        patch(
            "forge_backend.user_character_data_service.get_user_character",
            side_effect=get_character,
        ),
        patch("forge_backend.user_character_data_service.update_character", side_effect=update),
        pytest.raises(ValueError, match="unknown item"),
    ):
        svc.set_character_equipment("uid", "char", ["Longsword", "Vorpal Kumquat"])
    assert state["writes"] == 0
    assert state["record"] == base


def test_setter_missing_record_raises_key_error():
    svc = _service()
    with (
        patch("forge_backend.user_character_data_service.get_user_character", return_value=None),
        patch("forge_backend.user_character_data_service.list_reference_records") as refs,
    ):
        with pytest.raises(KeyError):
            svc.set_character_equipment("uid", "missing", ["Longsword"])
        refs.assert_not_called()


def test_setter_replaces_and_clears_preserving_unrelated_fields():
    svc = _service()
    base = {"owner": "test-user", "name": "Gandalf", "class": "Wizard"}
    state, get_character, update = _stub_storage(base)
    with (
        patch(
            "forge_backend.user_character_data_service.list_reference_records",
            return_value=list(SEED),
        ),
        patch(
            "forge_backend.user_character_data_service.get_user_character",
            side_effect=get_character,
        ),
        patch("forge_backend.user_character_data_service.update_character", side_effect=update),
    ):
        record = svc.set_character_equipment("uid", "char", ["srd_dagger", "Shield"])
        assert record["equipment"] == ["srd_dagger", "Shield"]
        assert record["class"] == "Wizard"
        assert record["owner"] == "test-user"
        cleared = svc.set_character_equipment("uid", "char", [])
        assert cleared["equipment"] == []
        assert cleared["class"] == "Wizard"
    assert state["writes"] == 2
    assert state["record"]["equipment"] == []


def test_setter_clear_skips_reference_lookup():
    svc = _service()
    base = {"owner": "test-user", "name": "Gandalf"}
    state, get_character, update = _stub_storage(base)
    with (
        patch(
            "forge_backend.user_character_data_service.get_user_character",
            side_effect=get_character,
        ),
        patch("forge_backend.user_character_data_service.update_character", side_effect=update),
        patch("forge_backend.user_character_data_service.list_reference_records") as refs,
    ):
        assert svc.set_character_equipment("uid", "char", [])["equipment"] == []
        refs.assert_not_called()
    assert state["writes"] == 1
