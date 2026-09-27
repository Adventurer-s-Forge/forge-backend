import requests

from forge_backend.storage import (  # Used for the cleanup at the end of the test
    char_index_key,
    char_key,
)
from forge_backend.user_character_data_service import (
    UserCharacterDataService,  # Used for the cleanup at the end of the test
)

# Set the test data
test_user_id = "f12345"
test_character_name = "Robert Robertson"
test_user_name = "MashedPotatoTime"
NEW_CHARACTER_DATA = {
    "user_id": test_user_id,
    "character_name": test_character_name,
    "user_name": test_user_name
}
# Set the expected result
EXPECTED_RESULT = {
    "owner": test_user_name,
    "name": test_character_name
}


def test_user_character_post_api_route_roundtrip():
    # # Test creating the character via API call
    response = requests.post("http://127.0.0.1:8000/user-character", json=NEW_CHARACTER_DATA)
    character_id = response.json()["character_id"]
    result = response.json()["result"]
    assert character_id.isnumeric() and len(character_id) == 5 # Verify that the output is a number [6] and is 5 digits
    assert result == 1
    # Test getting the created character via API call
    assert requests.get("http://127.0.0.1:8000/user-character/" + test_user_id + "/" + character_id).json() == EXPECTED_RESULT
    # Test getting the list of character IDs via API call
    assert requests.get("http://127.0.0.1:8000/user-character/" + test_user_id + "/ids").json() == [character_id]
    # Test getting the list of characters via API call
    assert requests.get("http://127.0.0.1:8000/user-character/" + test_user_id + "/list").json() == [EXPECTED_RESULT]
    assert requests.get("http://127.0.0.1:8000/num-user-characters/" + test_user_id).json() == 1
    # Clean up after the test
    userCharacterDataService = UserCharacterDataService()
    userCharacterDataService.redis_client.delete(char_key(test_user_id, character_id)) # Delete the test character [7]
    userCharacterDataService.redis_client.delete(char_index_key(test_user_id)) # Delete any existing character index key for the user (char:idx:uid) [7]