import uuid

from forge_backend.storage import add_new_character, get_redis, list_character_records, list_char_keys, get_user_character, count_characters
from typing import Any


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
        result = add_new_character(self.redis_client, user_id, character_id, user_character) # Try to add the new character to the database
        if (result == 0):
            result = add_new_character(self.redis_client, user_id, character_id, user_character) # Adding the character again seems to succeed on the 2nd try if the 1st try fails
        return result


    def generate_character_id(self) -> str:
        """
        Generate the unique ID for the new character [3] [4] [5]

        Args:
            self (redis.Redis): The Redis database connection

        Returns:
            (str): The character ID as a 5 digit number
        """
        return str(uuid.uuid1().fields[0])[:5]


    def list_character_ids(self, user_id) -> list[str]:
        """
        Helper function to retrieve all the keys for the user's characters in database.

        Args:
            self (redis.Redis): The Redis database connection
            user_id (str): The user's ID from Google Firebase Authentication

        Returns:
            (list[str]): The list of index keys for a user's characters
        """
        return list_char_keys(self.redis_client, user_id)

    
    def list_characters(self, user_id: str) -> list[dict[str, Any]]:
        """
        Helper function to retrieve all characters for a certain user from the database.

        Args:
            self (redis.Redis): The Redis database connection
            user_id (str): The user's ID from Google Firebase Authentication

        Returns:
            (list[dict[str, Any]]): The list of a user's characters (including the data for each)
        """
        return list_character_records(self.redis_client, user_id)


    def get_a_character_by_id(self, user_id, character_id) -> dict[str, Any] | None:
        """
        Helper function to retrieve a character for a certain user from the database.

        Args:
            self (redis.Redis): The Redis database connection
            user_id (str): The user's ID from Google Firebase Authentication
            character_id (str): The unique ID of the user's character

        Returns:
            (dict[str, Any] | Any): The user's character as a Dictionary of String, Any; or None if there is no existing characters
        """
        return get_user_character(self.redis_client, user_id, character_id)


    def get_num_user_characters(self, user_id) -> int:
        """
        Helper function to retrieve the count of characters for a certain user in the database.

        Args:
            self (redis.Redis): The Redis database connection
            user_id (str): The user's ID from Google Firebase Authentication
        """
        return count_characters(self.redis_client, user_id)