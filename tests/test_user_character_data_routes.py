from forge_backend.storage import (  # Used for the cleanup at the end of the test
    char_index_key,
    char_key,
)
from forge_backend.user_character_data_routes import (
    create_new_character,
    get_character_by_id,
    get_num_user_characters,
    list_character_ids,
    list_characters,
)
from forge_backend.user_character_data_service import (
    UserCharacterDataService,  # Used for the cleanup at the end of the test
)

# Set the test data
user_id = "a12345"
character_name = "Joe Schmoe"
user_name = "moobelle"
# Set the data for the test new character
NEW_CHARACTER_DATA = {
        "user_id": user_id,
        "character_name": character_name,
        "user_name": user_name
    }
# Set the expected result
EXPECTED_RESULT = {
    "owner": user_name,
    "name": character_name
}


def test_create_new_character_via_api_route_roundtrip():
    # Test creating a new character
    response = create_new_character(NEW_CHARACTER_DATA)
    character_id = response["character_id"]
    result = response["result"]
    assert character_id.isnumeric() and len(character_id) == 5 # Verify that the output is a number [6] and is 5 digits
    assert result == 1
    # Test getting the newly created character by ID
    assert get_character_by_id(NEW_CHARACTER_DATA["user_id"], character_id) == EXPECTED_RESULT
    # Test getting the user's character IDs
    assert list_character_ids(NEW_CHARACTER_DATA["user_id"]) == [character_id]
    # Test getting a list of the user's characters
    assert list_characters(NEW_CHARACTER_DATA["user_id"]) == [EXPECTED_RESULT]
    # Test getting the number of characters for the user
    assert get_num_user_characters(NEW_CHARACTER_DATA["user_id"]) == 1
    # Clean up after the test
    userCharacterDataService = UserCharacterDataService()
    userCharacterDataService.redis_client.delete(char_key(NEW_CHARACTER_DATA["user_id"], character_id)) # Delete the test character [7]
    userCharacterDataService.redis_client.delete(char_index_key(NEW_CHARACTER_DATA["user_id"])) # Delete any existing character index key for the user (char:idx:uid) [7]