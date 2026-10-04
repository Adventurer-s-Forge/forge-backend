import pytest

from forge_backend.user_character_data_service import UserCharacterDataService

pytestmark = pytest.mark.integration


def test_generate_character_id(redis_conn):
    service = UserCharacterDataService(redis_conn)
    charid = service.generate_character_id("m12345")
    assert len(charid) == 8
    assert int(charid, 16) >= 0


def test_create_new_character_roundtrip(redis_conn):
    service = UserCharacterDataService(redis_conn)
    user_id = "4CIZQ94T3ncLcAAizmHcN62V6Q43"
    user_name = "iLoveSourCream"
    character_name = "Bart Penelope"
    character_id = "12345"

    expected = {"owner": user_name, "name": character_name}
    assert service.create_user_character(user_id, character_name, user_name, character_id) == 1
    assert service.get_num_user_characters(user_id) == 1
    assert service.get_character_by_id(user_id, character_id) == expected
    assert service.list_character_ids(user_id) == [character_id]
    assert service.list_characters(user_id) == [expected]
