from forge_backend.storage import char_index_key, char_key
from forge_backend.user_character_data_service import UserCharacterDataService


def cleanup_before_test(user_id: str) -> None:
    """
    Helper function to clean up the database before running tests.

    Args:
        user_id (str): The user ID that needs test characters removed
    """
    userCharacterDataService = UserCharacterDataService()
    chars = userCharacterDataService.list_character_ids(user_id)
    for char in chars:
        userCharacterDataService.redis_client.delete(
            char_key(user_id, char)
        )  # Delete the test character [7]
        userCharacterDataService.redis_client.delete(char_index_key(user_id))
