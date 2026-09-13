import pytest

from forge_backend.storage import (
    count_reference,
    get_reference,
    list_reference_keys,
    list_reference_records,
    ref_key,
    refresh_reference_type,
)

pytestmark = pytest.mark.integration

DRAGONBORN = {
    "type": "race",
    "key": "srd_dragonborn",
    "name": "Dragonborn",
    "document": "srd-2014",
    "data": {"speed": "30 ft", "creature_type": "dragonborn"},
}

ELF = {
    "type": "race",
    "key": "srd_elf",
    "name": "Elf",
    "document": "srd-2014",
    "data": {"speed": "30 ft", "creature_type": "humanoid"},
}


def test_roundtrip(redis_conn):
    assert refresh_reference_type(redis_conn, "race", [DRAGONBORN]) == 1
    assert count_reference(redis_conn, "race") == 1
    assert get_reference(redis_conn, "race", "srd_dragonborn") == DRAGONBORN
    assert list_reference_keys(redis_conn, "race") == ["srd_dragonborn"]
    assert list_reference_records(redis_conn, "race") == [DRAGONBORN]


def test_idempotent_rerun(redis_conn):
    refresh_reference_type(redis_conn, "race", [DRAGONBORN, ELF])
    refresh_reference_type(redis_conn, "race", [DRAGONBORN, ELF])
    assert count_reference(redis_conn, "race") == 2
    assert list_reference_keys(redis_conn, "race") == ["srd_dragonborn", "srd_elf"]


def test_orphan_cleanup(redis_conn):
    refresh_reference_type(redis_conn, "race", [DRAGONBORN, ELF])
    refresh_reference_type(redis_conn, "race", [DRAGONBORN])
    assert count_reference(redis_conn, "race") == 1
    assert redis_conn.exists(ref_key("race", "srd_elf")) == 0
    assert list_reference_keys(redis_conn, "race") == ["srd_dragonborn"]


def test_type_isolation(redis_conn):
    refresh_reference_type(redis_conn, "race", [DRAGONBORN])
    assert count_reference(redis_conn, "spell") == 0
    assert list_reference_keys(redis_conn, "spell") == []


def test_player_data_untouched(redis_conn):
    redis_conn.set("char:test:1", '{"owner":"test-user","name":"Do Not Touch"}')
    refresh_reference_type(redis_conn, "race", [DRAGONBORN])
    assert redis_conn.get("char:test:1") == '{"owner":"test-user","name":"Do Not Touch"}'
    assert redis_conn.keys("char:*") == ["char:test:1"]


def test_empty_refresh_wipes_type(redis_conn):
    refresh_reference_type(redis_conn, "race", [DRAGONBORN, ELF])
    assert refresh_reference_type(redis_conn, "race", []) == 0
    assert count_reference(redis_conn, "race") == 0
    assert get_reference(redis_conn, "race", "srd_dragonborn") is None
