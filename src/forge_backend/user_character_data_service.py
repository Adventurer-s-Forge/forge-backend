from forge_backend.storage import get_redis, add_new_character


"""This class provides functions to manipulate the user's character in the database."""
class UserCharacterDataService:
    
    def __init__(self):
        self.redis_client = get_redis()

    def create_users_character(self: redis.Redis, user_id: str, character_name: str) -> None:
        """
        Create the user's character as an object and add it to the database.

        Args:
            user_id (str): The user's ID from Google Firebase Authentication
            character_name (str): The name that the user provides for their character
        """
        user_character = {"name": character_name}; # Construct the JSON for the new character
        # Generate the unique ID for the new character
        add_new_character(self.redis_client, user_id, character_id, user_character) # Add the new character to the database