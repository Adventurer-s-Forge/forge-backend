from typing import Any

from forge_backend.character_models import CharacterRecord
from forge_backend.spell_rules import validate_spell_class_eligibility
from forge_backend.storage import (
    add_new_character,
    count_characters,
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

    def create_user_character(self, user_id: str, character: CharacterRecord) -> int:
        """Validate selections, persist the complete record; raises DuplicateCharacterId."""
        self.validate_character_references(character)
        record = character.model_dump(mode="json")
        result = add_new_character(self.redis_client, user_id, character.id, record)
        if result == 0:
            raise DuplicateCharacterId(
                "Cannot add duplicate character with ID: " + character.id + "!"
            )
        return result

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
        self._validate_equipment_ids(character.equipmentIds)
        self._validate_spell_selection(character.classId, character.spellIds)

    def _validate_class_id(self, class_id: str | None) -> None:
        if class_id is None:
            return
        if get_reference(self.redis_client, "class", class_id) is None:
            raise ValueError("unknown classId")

    def _validate_equipment_ids(self, equipment_ids: list[str]) -> None:
        if not equipment_ids:
            return
        valid = set(list_reference_keys(self.redis_client, "item"))
        for entry in equipment_ids:
            if entry not in valid:
                raise ValueError("unknown equipmentIds")

    def save_character(self, user_id: str, character_id: str, character: CharacterRecord) -> dict:
        """Full-replacement save of an owned record; raises KeyError/ValueError."""
        existing = get_user_character(self.redis_client, user_id, character_id)
        if existing is None:
            raise KeyError(character_id)
        if character.id != character_id:
            raise ValueError("id must match character_id")
        self.validate_character_references(character)
        record = character.model_dump(mode="json")
        update_character(self.redis_client, user_id, character_id, record)
        return record

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

    def set_character_class(self, user_id: str, character_id: str, class_id: str) -> dict:
        """Replace the record's classId; raises KeyError/ValueError."""
        record = self.get_character_by_id(user_id, character_id)
        if record is None:
            raise KeyError(character_id)
        self._validate_class_id(class_id)
        self._validate_spell_selection(class_id, record.get("spellIds", []))
        record["classId"] = class_id
        update_character(self.redis_client, user_id, character_id, record)
        return record

    def set_character_equipment(
        self, user_id: str, character_id: str, equipment_ids: list[str]
    ) -> dict:
        """Replace the record's equipmentIds; raises KeyError/ValueError."""
        record = self.get_character_by_id(user_id, character_id)
        if record is None:
            raise KeyError(character_id)
        self._validate_equipment_ids(equipment_ids)
        record["equipmentIds"] = equipment_ids
        update_character(self.redis_client, user_id, character_id, record)
        return record

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

    def set_character_spells(self, user_id: str, character_id: str, spell_ids: list[str]) -> dict:
        """Replace the record's spellIds; raises KeyError/ValueError."""
        record = self.get_character_by_id(user_id, character_id)
        if record is None:
            raise KeyError(character_id)
        if spell_ids:
            self._validate_class_id(record.get("classId"))
            self._validate_spell_selection(record.get("classId"), spell_ids)
        record["spellIds"] = spell_ids
        update_character(self.redis_client, user_id, character_id, record)
        return record
