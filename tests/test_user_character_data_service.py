import pytest

from forge_backend.user_character_data_service import UserCharacterDataService
from forge_backend.storage import char_key, char_index_key # Used for the cleanup at the end of the test

userCharacterDataService = UserCharacterDataService()


def test_generate_character_id():  
    charid = userCharacterDataService.generate_character_id()
    assert charid.isnumeric() and len(charid) == 5 # Verify that the output is a number [6] and is 5 digits


def test_create_new_character_roundtrip():
    # Set the test data
    user_id = "4CIZQ94T3ncLcAAizmHcN62V6Q43"
    user_name = "iLoveSourCream"
    character_name = "Bart Penelope"
    character_id = "12345"

    EXPECTED_RESULT = {
        "owner": user_name,
        "name": character_name
    }

    # Run the tests
    assert userCharacterDataService.create_user_character(user_id, character_name, user_name, character_id) == 1 # Verify that the new character was successfully created
    assert userCharacterDataService.get_num_user_characters(user_id) == 1
    assert userCharacterDataService.get_a_character_by_id(user_id, character_id) == EXPECTED_RESULT
    assert userCharacterDataService.list_character_ids(user_id) == [character_id]
    assert userCharacterDataService.list_characters(user_id) == [EXPECTED_RESULT]
    # Clean up after the test
    userCharacterDataService.redis_client.delete(char_key(user_id, character_id))
    userCharacterDataService.redis_client.delete(char_index_key(user_id)) # Delete any existing character index key for the user (char:idx:uid)