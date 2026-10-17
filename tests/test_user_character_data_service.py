import pytest

from forge_backend.character_models import CharacterRecord
from forge_backend.user_character_data_service import UserCharacterDataService

pytestmark = pytest.mark.integration

UUID = "0f8c1a7e-3d52-4b91-a7c8-6e2f91b40d35"


def test_create_new_character_roundtrip(redis_conn):
    service = UserCharacterDataService(redis_conn)
    user_id = "4CIZQ94T3ncLcAAizmHcN62V6Q43"
    character = CharacterRecord.model_validate({"id": UUID, "name": "Bart Penelope"})

    record = service.create_user_character(user_id, character)
    assert record["ownerUid"] == user_id
    assert record["schemaVersion"] == 1
    assert record["createdAt"] == record["updatedAt"]



def test_validate_skills_no_skills(redis_conn):
    service = UserCharacterDataService(redis_conn)
    assert service._validate_skill_ids(None) == None


def test_validate_skills_invalid_skills(redis_conn):
    service = UserCharacterDataService(redis_conn)
    error_validating_skills = None # Initialize the result to validate
    expected_error_message = "unknown skill IDs"
    expected_error_type = ValueError

    try:
        service._validate_skill_ids(["arcana", "fakeSkill", "history"])
    except ValueError as error:
        error_validating_skills = error

    assert type(error_validating_skills) == expected_error_type
    assert error_validating_skills.args[0] == expected_error_message
