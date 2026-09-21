import uuid

from forge_backend.storage import add_new_character, get_redis


class UserCharacterDataService:
    """This class provides functions to manipulate the user's character in the database."""
    
    def __init__(self):
        self.redis_client = get_redis()

    def create_user_character(self, user_id: str, character_name: str, user_name: str, character_id: str) -> int:
        """
        Create the user's character as an object and add it to the database.

        Args:
            self (redis.Redis): The Redis database connection
            user_id (str): The user's ID from Google Firebase Authentication
            character_name (str): The name that the user provides for their character
            user_name (str): The username of the user that is creating the character
            character_id (str): The character's ID

        Returns:
            (int): The number of items added to the database (should only be 1)
        """
        user_character = {"owner": user_name, "name": character_name}; # Construct the JSON for the new character
        return add_new_character(self.redis_client, user_id, character_id, user_character) # Add the new character to the database


    def generate_character_id(self) -> str:
        """
        Generate the unique ID for the new character [3] [4] [5]

        Args:
            self (redis.Redis): The Redis database connection
            
        Returns:
            (str): The character ID as a 5 digit number
        """
        return str(uuid.uuid1().fields[0])[:5]

        #test success add