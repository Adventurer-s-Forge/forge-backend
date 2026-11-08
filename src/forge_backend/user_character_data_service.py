from typing import Any

from forge_backend.character_models import CharacterRecord, utcnow
from forge_backend.feat_rules import (
    FEATS_BY_TYPE,
    available_background_feats,
    available_class_feats,
)
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
    list_reference_records,
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

    
    def _get_background_spell_classes(
        self, background_id: str | None
    ) -> set[str]:
        """
        Retrieve the additional spell lists granted by a character's background.

        Checks background benefits for Magic Initiate and returns the
        corresponding class spell list keys. Returns an empty set if
        the background does not grant any additional spell access.
        """
        if background_id is None:
            return set()

        background = get_reference(
            self.redis_client, "background", background_id
        )

        if background is None:
            raise ValueError("unknown backgroundId")

        spell_classes = set()

        for benefit in background.get("data", {}).get("benefits", []):
            if benefit.get("type") == "feat":
                desc = benefit.get("desc", "")

                if desc.startswith("Magic Initiate (") and desc.endswith(")"):
                    class_name = desc[len("Magic Initiate ("):-1]
                    class_key = "srd-2024_" + class_name.lower().replace(" ", "-")
                    spell_classes.add(class_key)

        return spell_classes


    def _validate_spell_selection(self, class_id: str | None, background_id: str | None, spell_ids: list[str]) -> None:
        if not spell_ids:
            return
        envelopes = []
        for spell_id in dict.fromkeys(spell_ids):
            envelope = get_reference(self.redis_client, "spell", spell_id)
            if envelope is None:
                raise ValueError("unknown spellIds")
            envelopes.append(envelope)

        background_spell_classes = self._get_background_spell_classes(
            background_id
        )

        validate_spell_class_eligibility(class_id, envelopes, background_spell_classes)

    def validate_character_references(self, character: CharacterRecord) -> None:
        self._validate_class_id(character.classId)
        self._validate_equipment_ids(character.purchasedItemIds)
        self._validate_spell_selection(character.classId, character.backgroundId, character.spellIds)
        self._validate_skill_ids(
            character.proficientSkillIds
        )  # validate the list of proficient skills
        self._validate_skill_ids(character.expertiseIds)  # validate the list of expertise skills
        self._validate_feat_ids(character.featIds)
        self._validate_class_feat_choices(character)

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

    def _validate_feat_ids(self, feat_ids: list[str]) -> None:
        for feat_id in feat_ids:
            if get_reference(self.redis_client, "feat", feat_id) is None:
                raise ValueError("unknown featIds")

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
        self._set_character_feats(character)
        self.validate_character_references(character)
        now = utcnow()
        record = character.to_record(user_id, created_at=now, updated_at=now)
        if add_new_character(self.redis_client, user_id, character.id, record) == 0:
            raise DuplicateCharacterId(f"character {character.id} already exists")
        return record

    def save_character(self, user_id: str, character_id: str, character: CharacterRecord) -> dict:
        """Full replacement save of an owned record; raises KeyError/ValueError."""
        existing = get_user_character(self.redis_client, user_id, character_id)
        if existing is None:
            raise KeyError(character_id)
        if character.id != character_id:
            raise ValueError("id must match character_id")
        self._set_character_feats(character)
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


    def _get_background_feats(self, background_id: str | None) -> list[str]:
        if background_id is None:
            return []

        background_feats = available_background_feats(background_id, self.redis_client)
        feat_names = []

        for feats in background_feats.values():
            feat_names.extend(feats)

        return feat_names


    def _get_class_feats(self, class_id: str | None, level: int) -> dict:
        if class_id is None:
            return {}

        class_feats = available_class_feats(class_id, level)

        return class_feats
    

    def _get_background_feat_ids(self, background_id: str | None) -> list[str]:
        feat_names = self._get_background_feats(background_id)

        if not feat_names:
            return []

        feat_records = list_reference_records(self.redis_client, "feat")
        feat_ids = []

        for feat in feat_records:
            if feat["name"] in feat_names:
                feat_ids.append(feat["key"])

        return feat_ids


    def _validate_class_feat_choices(self, character: CharacterRecord) -> None:
        if not character.classFeatChoices:
            return

        if character.classId is None:
            raise ValueError("class must be selected before choosing class feats")

        available_feats = self._get_class_feats(character.classId, character.level)

        unlocked_levels = []

        for levels in available_feats.values():
            unlocked_levels.extend(levels)

        selected_levels = []

        for choice in character.classFeatChoices:
            if choice.level not in unlocked_levels:
                raise ValueError("feat choice is not available at this level")

            if choice.level in selected_levels:
                raise ValueError("multiple feats selected at the same level")

            selected_levels.append(choice.level)
            feat = get_reference(self.redis_client, "feat", choice.featId)

            if feat is None:
                raise ValueError("unknown class featId")

            feat_name = feat["name"]
            allowed_feat_names = []

            for feature_name, levels in available_feats.items():
                if choice.level in levels:
                    allowed_feat_names.extend(FEATS_BY_TYPE.get(feature_name, []))

            if feat_name not in allowed_feat_names:
                raise ValueError("feat is not available for this class feature")


    def _set_character_feats(self, character: CharacterRecord) -> None:
        feat_ids = []

        # Automatically granted background feats
        background_feat_ids = self._get_background_feat_ids(character.backgroundId)

        for feat_id in background_feat_ids:
            if feat_id not in feat_ids:
                feat_ids.append(feat_id)

        # Feats selected from class opportunities
        for choice in character.classFeatChoices:
            if choice.featId not in feat_ids:
                feat_ids.append(choice.featId)

        character.featIds = feat_ids

        


