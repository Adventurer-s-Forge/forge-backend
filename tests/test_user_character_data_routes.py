from fastapi import HTTPException

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


class NewCharacterData:
    user_id: str
    character_name: str
    user_name: str

    def __init__(self, user_id, character_name, user_name):
        self.user_id = user_id
        self.character_name = character_name
        self.user_name = user_name


# Set the test data
test_user_id = "a12345"
test_character_name = "Joe Schmoe"
test_user_name = "moobelle"
NEW_CHARACTER_DATA = NewCharacterData(test_user_id, test_character_name, test_user_name)
# Set the expected result
EXPECTED_RESULT = {
    "owner": test_user_name,
    "name": test_character_name
}


def test_create_new_character_via_api_route_roundtrip():
    # Test creating a new character
    response = create_new_character(NEW_CHARACTER_DATA)
    assert response["status_code"] == 201
    character_id = response["detail"]["character_id"]
    result = response["detail"]["result"]
    assert int(character_id, 16) and len(character_id) == 8 # Verify that the output is a hexademcial [14] and is 8 characters
    assert result == 1
    # Test getting the newly created character by ID
    assert get_character_by_id(NEW_CHARACTER_DATA.user_id, character_id)["status_code"] == 200
    assert get_character_by_id(NEW_CHARACTER_DATA.user_id, character_id)["detail"] == EXPECTED_RESULT
    # Test getting the user's character IDs
    assert list_character_ids(NEW_CHARACTER_DATA.user_id)["status_code"] == 200
    assert list_character_ids(NEW_CHARACTER_DATA.user_id)["detail"] == [character_id]
    # Test getting a list of the user's characters
    assert list_characters(NEW_CHARACTER_DATA.user_id)["status_code"] == 200
    assert list_characters(NEW_CHARACTER_DATA.user_id)["detail"] == [EXPECTED_RESULT]
    # Test getting the number of characters for the user
    assert get_num_user_characters(NEW_CHARACTER_DATA.user_id)["status_code"] == 200
    assert get_num_user_characters(NEW_CHARACTER_DATA.user_id)["detail"] == 1
    # Clean up after the test
    userCharacterDataService = UserCharacterDataService()
    userCharacterDataService.redis_client.delete(char_key(NEW_CHARACTER_DATA.user_id, character_id)) # Delete the test character [7]
    userCharacterDataService.redis_client.delete(char_index_key(NEW_CHARACTER_DATA.user_id)) # Delete any existing character index key for the user (char:idx:uid) [7]


def test_no_character_found_via_api_route():
    """Use a TryCatch to catch the error and pass it to a variable, and assert that that the error type and its data are correct [16]."""
    testingError = None
    try:
        get_character_by_id(NEW_CHARACTER_DATA.user_id, "fakeID")
    except HTTPException as e:
        testingError = e
    assert type(testingError) == HTTPException
    assert testingError.status_code == 404
    assert testingError.detail == "Character not found!"