from forge_backend.storage import (  # Used for the cleanup at the end of the test
    char_index_key,
    char_key,
)
from forge_backend.user_character_data_service import UserCharacterDataService

userCharacterDataService = UserCharacterDataService()


def test_generate_character_id():  
    # Set the test data
    user_id = "m12345"
    charid = userCharacterDataService.generate_character_id(user_id)
    assert int(charid, 16) and len(charid) == 8 # Verify that the output is a hexademcial [14] and is 8 characters


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
    assert userCharacterDataService.get_character_by_id(user_id, character_id) == EXPECTED_RESULT
    assert userCharacterDataService.list_character_ids(user_id) == [character_id]
    assert userCharacterDataService.list_characters(user_id) == [EXPECTED_RESULT]
    # Clean up after the test
    userCharacterDataService.redis_client.delete(char_key(user_id, character_id)) # Delete the test character [7]
    userCharacterDataService.redis_client.delete(char_index_key(user_id)) # Delete any existing character index key for the user (char:idx:uid) [7]