from fastapi import APIRouter
from pydantic import BaseModel

from forge_backend.user_character_data_service import UserCharacterDataService


class NewCharacterData(BaseModel):
    """Class to set the expected schema for new characters being created - provided via the imported pydantic BaseModel [10]."""
    user_id: str
    character_name: str
    user_name: str


router = APIRouter()
userCharacterDataService = UserCharacterDataService()


# Set the API routes for retrieving/manipulating user characters [9] [10]
@router.post("/user-character")
def create_new_character(newCharacterData: NewCharacterData):
    """
    API route for creating a new character [9] [10].

    Args:
        newCharacterData (NewCharacterData): The JSON Object/Python dictionary that contains the user ID, character name, and username

    Returns:
        (dict[str, Any]): JSON Object/Python dictionary containing the new character's ID and the result of adding the character to the database
    """
    # Generate the new character's ID
    character_id = userCharacterDataService.generate_character_id()
    result = userCharacterDataService.create_user_character(newCharacterData.user_id, newCharacterData.character_name, newCharacterData.user_name, character_id)
    # Ensure that the new character's ID is passed back out, along with the result of adding the character to the database
    return {
        "character_id": character_id,
        "result": result
    }


@router.get("/user-character/{user_id}/list-ids")
def list_character_ids(user_id: str):
    """
    API route for listing all the character IDs for a user.

    Args:
        uesr_id (str): The user's ID from Google Firebase Authentication

    Returns:
        (list[str]): The list of index keys for a user's characters
    """
    return userCharacterDataService.list_character_ids(user_id)


@router.get("/user-character/{user_id}/list")
def list_characters(user_id: str):
    """
    API route for listing all the characters for a user.

    Args:
        uesr_id (str): The user's ID from Google Firebase Authentication

    Returns:
        (list[str]): The list of index keys for a user's characters
    """
    return userCharacterDataService.list_characters(user_id)


@router.get("/user-character/{user_id}/{character_id}")
def get_character_by_id(user_id: str, character_id: str):
    """
    API route for listing all the character IDs for a user.

    Args:
        uesr_id (str): The user's ID from Google Firebase Authentication

    Returns:
        (dict[str, Any] | Any): The user's character as a Dictionary of String, Any; or None if there is no existing characters
    """
    return userCharacterDataService.get_character_by_id(user_id, character_id)


@router.get("/user-character/{user_id}/count")
def get_num_user_characters(user_id: str):
    """
    API route for listing all the character IDs for a user.

    Args:
        uesr_id (str): The user's ID from Google Firebase Authentication

    Returns:
        (int): The number of characters the user has
    """
    return userCharacterDataService.get_num_user_characters(user_id)