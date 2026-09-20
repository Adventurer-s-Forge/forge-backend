import uuid

from forge_backend.storage import add_new_character, get_redis


class UserCharacterDataService:
    """This class provides functions to manipulate the user's character in the database."""
    
    def __init__(self):
        self.redis_client = get_redis()

    def create_user_character(self, user_id: str, character_name: str) -> None:
        """
        Create the user's character as an object and add it to the database.

        Args:
            self (redis.Redis): The Redis database connection
            user_id (str): The user's ID from Google Firebase Authentication
            character_name (str): The name that the user provides for their character
        """
        user_character = {"name": character_name}; # Construct the JSON for the new character
        character_id = str(uuid.uuid1().fields[0])[:5] # Generate the unique ID for the new character [3] [4] [5]
        add_new_character(self.redis_client, user_id, character_id, user_character) # Add the new character to the database