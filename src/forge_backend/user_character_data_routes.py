"""Player-character router: sole owner of the /characters contract."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

from forge_backend.character_models import CharacterRecord
from forge_backend.user_character_data_service import (
    DuplicateCharacterId,
    UserCharacterDataService,
)

router = APIRouter(prefix="/characters", tags=["Characters"])

_service = UserCharacterDataService()


class ErrorResponse(BaseModel):
    detail: str


class SpellSelection(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"spellIds": ["srd-2024_fireball"]}},
    )

    spellIds: list[StrictStr]

    @field_validator("spellIds")
    @classmethod
    def _validate_id_list(cls, v: list[str]) -> list[str]:
        for entry in v:
            if entry == "":
                raise ValueError("id list entries must be nonempty strings")
        return v


class ClassSelection(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"classId": "srd-2024_wizard"}},
    )

    classId: str = Field(min_length=1)


class EquipmentSelection(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"equipmentIds": ["srd-2024_longsword"]}},
    )

    equipmentIds: list[str]


# TODO(US-19/auth): replace with Firebase ID-token verification.
def get_uid(
    x_user_id: str = Header(
        alias="X-User-Id",
        min_length=1,
        description="Temporary development identity; not authentication.",
    ),
) -> str:
    return x_user_id


@router.post(
    "",
    operation_id="create_character",
    status_code=201,
    response_model=CharacterRecord,
    responses={409: {"model": ErrorResponse}},
    summary="Create a character",
    description=(
        "Create a full character record. The caller supplies the UUID. The "
        "X-User-Id header selects the storage namespace; the header does not "
        "authenticate the caller."
    ),
)
def create_new_character(character: CharacterRecord, uid: str = Depends(get_uid)):
    try:
        _service.create_user_character(uid, character)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DuplicateCharacterId:
        raise HTTPException(status_code=409, detail="Character ID collision, retry")
    return character


@router.get(
    "",
    operation_id="list_characters",
    response_model=list[CharacterRecord],
    summary="List characters",
    description="List stored character records for the X-User-Id storage namespace.",
)
def list_characters(uid: str = Depends(get_uid)):
    return _service.list_characters(uid)


@router.get(
    "/ids",
    operation_id="list_character_ids",
    response_model=list[str],
    summary="List character IDs",
    description="List sorted character IDs for the X-User-Id storage namespace.",
)
def list_character_ids(uid: str = Depends(get_uid)):
    return _service.list_character_ids(uid)


@router.get(
    "/count",
    operation_id="count_characters",
    response_model=int,
    summary="Count characters",
    description="Count character index entries for the X-User-Id storage namespace.",
)
def get_num_user_characters(uid: str = Depends(get_uid)):
    return _service.get_num_user_characters(uid)


@router.get(
    "/{character_id}",
    operation_id="get_character",
    response_model=CharacterRecord,
    responses={404: {"model": ErrorResponse}},
    summary="Get a character",
    description="Return one stored character record.",
)
def get_character_by_id(character_id: str, uid: str = Depends(get_uid)):
    record = _service.get_character_by_id(uid, character_id)
    if record is None:
        raise HTTPException(status_code=404, detail="character not found")
    return record


@router.put(
    "/{character_id}",
    operation_id="save_character",
    response_model=CharacterRecord,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Save a character",
    description=(
        "Full-replacement save of one owned character record. The path ID and "
        "body id must match. The X-User-Id header selects the storage namespace; "
        "the header does not authenticate the caller."
    ),
)
def save_character(character_id: str, character: CharacterRecord, uid: str = Depends(get_uid)):
    try:
        return _service.save_character(uid, character_id, character)
    except KeyError:
        raise HTTPException(status_code=404, detail="character not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/{character_id}/class",
    operation_id="set_character_class",
    response_model=CharacterRecord,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Set character class",
    description=(
        'Replace the record\'s classId, e.g. `{"classId":"srd-2024_wizard"}`. '
        "Only seeded reference keys are accepted."
    ),
)
def set_character_class(character_id: str, selection: ClassSelection, uid: str = Depends(get_uid)):
    try:
        return _service.set_character_class(uid, character_id, selection.classId)
    except KeyError:
        raise HTTPException(status_code=404, detail="character not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/{character_id}/spells",
    operation_id="set_character_spells",
    response_model=CharacterRecord,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Set character spells",
    description=(
        "Replace the spellIds list with seeded keys available to classId. "
        "An empty list clears the selection."
    ),
)
def set_character_spells(character_id: str, selection: SpellSelection, uid: str = Depends(get_uid)):
    try:
        return _service.set_character_spells(uid, character_id, selection.spellIds)
    except KeyError:
        raise HTTPException(status_code=404, detail="character not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/{character_id}/equipment",
    operation_id="set_character_equipment",
    response_model=CharacterRecord,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Set character equipment",
    description="Replace the equipmentIds list. An empty list clears the selection.",
)
def set_character_equipment(
    character_id: str, selection: EquipmentSelection, uid: str = Depends(get_uid)
):
    try:
        return _service.set_character_equipment(uid, character_id, selection.equipmentIds)
    except KeyError:
        raise HTTPException(status_code=404, detail="character not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
