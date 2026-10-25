"""Canonical character contract for full-character save (US-19)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator

AbilityKey = Literal["STR", "DEX", "CON", "INT", "WIS", "CHA"]
AbilityMethod = Literal["standard", "pointbuy", "roll"]
StepId = Literal[
    "name", "race", "class", "background", "attributes", "skills", "spells", "equipment"
]
Size = Literal["Small", "Medium"]

SCHEMA_VERSION = 1


def utcnow() -> str:
    """Server-side timestamp. The client's clock is never trusted."""
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class EquipmentGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    quantity: int
    itemId: str | None
    choosableFrom: str | None

class EquipmentPick(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str                # "A" | "B" | "C"
    label: str              # the option's display text
    goldCp: int             # frozen coin grant
    grants: list[EquipmentGrant]

class EquipmentChoice(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    class_: EquipmentPick | None = Field(None, alias="class")
    background: EquipmentPick | None = None

def _nonempty_str(v: str | None, field: str) -> str | None:
    if v is not None and (not isinstance(v, str) or v == ""):
        raise ValueError(f"{field} must be a nonempty string")
    return v


class CharacterAbilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: AbilityMethod | None = None
    base: dict[AbilityKey, StrictInt] = Field(default_factory=dict)
    rolled: list[StrictInt] = Field(default_factory=list)
    originBonuses: dict[AbilityKey, StrictInt] = Field(default_factory=dict)


class CharacterRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: StrictStr
    name: StrictStr
    level: StrictInt = Field(default=1, ge=1, le=20)
    raceId: StrictStr | None = None
    sizeChoice: Size | None = None
    classId: StrictStr | None = None
    fightingStyleId: str | None = None
    toolChoiceId: str | None = None
    backgroundId: StrictStr | None = None
    equipmentChoice: EquipmentChoice = Field(default_factory=EquipmentChoice)
    purchasedItemIds: list[StrictStr] = Field(default_factory=list, max_length=100)
    walletCp: int = 0
    abilities: CharacterAbilities = Field(default_factory=CharacterAbilities)
    proficientSkillIds: list[StrictStr] = Field(default_factory=list, max_length=100)
    expertiseIds: list[StrictStr] = Field(default_factory=list, max_length=100)
    spellIds: list[StrictStr] = Field(default_factory=list, max_length=100)
    completedSteps: list[StepId] = Field(default_factory=list, max_length=100)

    def to_record(self, uid: str, created_at: str, updated_at: str) -> dict[str, Any]:
        """Stored shape: the client's fields plus four the server owns."""
        return {
            "schemaVersion": SCHEMA_VERSION,
            "ownerUid": uid,
            "createdAt": created_at,
            "updatedAt": updated_at,
            **self.model_dump(mode="json", by_alias=True),
        }

    @field_validator("id")
    @classmethod
    def _validate_id(cls, v: str) -> str:
        parsed = uuid.UUID(v)
        if str(parsed) != v:
            raise ValueError("id must be a canonical lowercase hyphenated UUID")
        return v

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        if v.strip() == "":
            raise ValueError("name must not be blank")
        return v

    @field_validator("raceId", "classId", "backgroundId")
    @classmethod
    def _validate_ref(cls, v: str | None) -> str | None:
        if v is not None and v == "":
            raise ValueError("reference id must be nonempty or null")
        return v

    @field_validator("proficientSkillIds", "expertiseIds", "spellIds", "purchasedItemIds")
    @classmethod
    def _validate_id_lists(cls, v: list[str]) -> list[str]:
        for entry in v:
            if entry == "":
                raise ValueError("id list entries must be nonempty strings")
        return v


class CharacterDocument(CharacterRecord):
    """What the API returns: the client's 14 fields plus the 4 the server owns.

    ``CharacterRecord`` is the *request* contract and forbids these four, so it cannot
    double as the response model -- a stored document always carries them.
    """

    schemaVersion: StrictInt
    ownerUid: StrictStr
    createdAt: StrictStr
    updatedAt: StrictStr
