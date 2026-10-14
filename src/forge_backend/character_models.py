"""Canonical character contract for full-character save (US-19)."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, field_validator

AbilityKey = Literal["STR", "DEX", "CON", "INT", "WIS", "CHA"]
AbilityMethod = Literal["standard", "pointbuy", "roll"]
StepId = Literal["name", "race", "class", "background", "attributes", "skills", "spells", "item"]


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
    classId: StrictStr | None = None
    backgroundId: StrictStr | None = None
    abilities: CharacterAbilities = Field(default_factory=CharacterAbilities)
    proficientSkillIds: list[StrictStr] = Field(default_factory=list)
    expertiseIds: list[StrictStr] = Field(default_factory=list)
    spellIds: list[StrictStr] = Field(default_factory=list)
    equipmentIds: list[StrictStr] = Field(default_factory=list)
    completedSteps: list[StepId] = Field(default_factory=list)

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

    @field_validator("proficientSkillIds", "expertiseIds", "spellIds", "equipmentIds")
    @classmethod
    def _validate_id_lists(cls, v: list[str]) -> list[str]:
        for entry in v:
            if entry == "":
                raise ValueError("id list entries must be nonempty strings")
        return v
