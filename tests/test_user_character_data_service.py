import pytest

from forge_backend.character_models import CharacterRecord
from forge_backend.user_character_data_service import UserCharacterDataService

pytestmark = pytest.mark.integration

UUID = "0f8c1a7e-3d52-4b91-a7c8-6e2f91b40d35"


def test_create_new_character_roundtrip(redis_conn):
    service = UserCharacterDataService(redis_conn)
    user_id = "4CIZQ94T3ncLcAAizmHcN62V6Q43"
    character = CharacterRecord.model_validate({"id": UUID, "name": "Bart Penelope"})

    expected = character.model_dump(mode="json")
    assert service.create_user_character(user_id, character) == 1
    assert service.get_num_user_characters(user_id) == 1
    assert service.get_character_by_id(user_id, UUID) == expected
    assert service.list_character_ids(user_id) == [UUID]
    assert service.list_characters(user_id) == [expected]
