from typing import Any

from forge_backend.character_models import CharacterRecord, utcnow
from forge_backend.spell_rules import validate_spell_class_eligibility
from forge_backend.storage import (
    add_new_character,
    count_characters,
    delete_character,
    get_redis,
    get_reference,
    get_user_character,
    list_char_keys,
    list_character_records,
    list_reference_keys,
    update_character,
)


class DuplicateCharacterId(Exception):
    """Exception raised when there is a duplicate character ID [15]"""

    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


class UserCharacterDataService:
    """This class provides functions to manipulate the user's character in the database."""

    def __init__(self, redis_client=None):
        self.redis_client = redis_client if redis_client is not None else get_redis()

    def _validate_spell_selection(self, class_id: str | None, spell_ids: list[str]) -> None:
        if not spell_ids:
            return
        envelopes = []
        for spell_id in dict.fromkeys(spell_ids):
            envelope = get_reference(self.redis_client, "spell", spell_id)
            if envelope is None:
                raise ValueError("unknown spellIds")
            envelopes.append(envelope)
        validate_spell_class_eligibility(class_id, envelopes)

    def validate_character_references(self, character: CharacterRecord) -> None:
        self._validate_class_id(character.classId)
        self._validate_equipment_ids(character.purchasedItemIds)
        self._validate_spell_selection(character.classId, character.spellIds)
        self._validate_skill_selection(character.proficientSkillIds) # validate the list of proficient skills
        self._validate_skill_selection(character.expertiseIds) # validate the list of expertise skills

    def _validate_class_id(self, class_id: str | None) -> None:
        if class_id is None:
            return
        if get_reference(self.redis_client, "class", class_id) is None:
            raise ValueError("unknown classId")

    def _validate_equipment_ids(self, equipment_ids: list[str]) -> None:
        if not equipment_ids:
            return
        valid = set(list_reference_keys(self.redis_client, "equipment"))
        for entry in equipment_ids:
            if entry not in valid:
                raise ValueError("unknown equipmentIds")

    def _validate_skill_ids(self, skill_ids: list[str]) -> None:
        if not skill_ids:
            return
        valid_skills = set(list_reference_keys(self.redis_client, "skill"))
        for skill in skill_ids:
            if skill not in valid_skills:
                raise ValueError("unknown skill IDs")

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

    def get_character_by_id(self, user_id, character_id) -> dict[str, Any] | None:
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

    # Removed `set_character_class`, `set_character_spell`, and `set_character_equipment`
    # Replaced them with these two below:
    def create_user_character(self, user_id: str, character: CharacterRecord) -> dict:
        self.validate_character_references(character)
        now = utcnow()
        record = character.to_record(user_id, created_at=now, updated_at=now)
        if add_new_character(self.redis_client, user_id, character.id, record) == 0:
            raise DuplicateCharacterId(f"character {character.id} already exists")
        return record

    def save_character(
        self, user_id: str, character_id: str, character: CharacterRecord
    ) -> dict:
        """Full replacement save of an owned record; raises KeyError/ValueError."""
        existing = get_user_character(self.redis_client, user_id, character_id)
        if existing is None:
            raise KeyError(character_id)
        if character.id != character_id:
            raise ValueError("id must match character_id")
        self.validate_character_references(character)
        record = character.to_record(
            user_id,
            created_at=existing.get("createdAt") or utcnow(),
            updated_at=utcnow(),
        )
        update_character(self.redis_client, user_id, character_id, record)
        return record

    def remove_character(self, user_id: str, character_id: str) -> bool:
        return delete_character(self.redis_client, user_id, character_id)

    def get_num_user_characters(self, user_id) -> int:
        """
        Helper function to retrieve the count of characters for a certain user in the database.

        Args:
            self (redis.Redis): The Redis database connection
            user_id (str): The user's ID from Google Firebase Authentication

        Returns:
            (int): The number of characters the user has
        """
        return count_characters(self.redis_client, user_id)
