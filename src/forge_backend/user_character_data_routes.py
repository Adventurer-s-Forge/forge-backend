"""Player-character router: sole owner of the /characters contract."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from forge_backend.user_character_data_service import (
    DuplicateCharacterId,
    UserCharacterDataService,
)

router = APIRouter(prefix="/characters", tags=["Characters"])

_service = UserCharacterDataService()


class CreateCharacterResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"character_id": "1a2b3c4d", "result": 1}}
    )

    character_id: str
    result: int


class CharacterRecord(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        json_schema_extra={"example": {"owner": "test-user", "name": "Gandalf"}},
    )

    owner: str
    name: str
    character_class: str | None = Field(default=None, alias="class")


class ErrorResponse(BaseModel):
    detail: str


class NewCharacterData(BaseModel):
    """Expected schema for new characters being created."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"character_name": "Gandalf", "user_name": "test-user"}},
    )

    character_name: str
    user_name: str


class ClassSelection(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={"example": {"class": "Wizard"}},
    )

    character_class: str = Field(alias="class", min_length=1)


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
    response_model=CreateCharacterResponse,
    responses={409: {"model": ErrorResponse}},
    summary="Create a character",
    description=(
        "Create a blank character record. `owner` is a display name and the "
        "X-User-Id header selects the storage namespace; the header does not "
        "authenticate the caller."
    ),
)
def create_new_character(new_character_data: NewCharacterData, uid: str = Depends(get_uid)):
    character_id = _service.generate_character_id(uid)
    try:
        result = _service.create_user_character(
            uid,
            new_character_data.character_name,
            new_character_data.user_name,
            character_id,
        )
    except DuplicateCharacterId:
        raise HTTPException(status_code=409, detail="Character ID collision, retry")
    return {"character_id": character_id, "result": result}


@router.get(
    "",
    operation_id="list_characters",
    response_model=list[CharacterRecord],
    response_model_exclude_unset=True,
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
    response_model_exclude_unset=True,
    responses={404: {"model": ErrorResponse}},
    summary="Get a character",
    description="Return one stored record. Blank records look like "
    '`{"owner":"test-user","name":"Gandalf"}`.',
)
def get_character_by_id(character_id: str, uid: str = Depends(get_uid)):
    record = _service.get_character_by_id(uid, character_id)
    if record is None:
        raise HTTPException(status_code=404, detail="character not found")
    return record


@router.put(
    "/{character_id}/class",
    operation_id="set_character_class",
    response_model=CharacterRecord,
    response_model_exclude_unset=True,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Set character class",
    description=(
        'Replace the record\'s single class value, e.g. `{"class":"Wizard"}`. '
        "Seeded names/slugs persist verbatim."
    ),
)
def set_character_class(character_id: str, selection: ClassSelection, uid: str = Depends(get_uid)):
    if _service.get_character_by_id(uid, character_id) is None:
        raise HTTPException(status_code=404, detail="character not found")
    if not _service.class_exists(selection.character_class):
        raise HTTPException(status_code=400, detail="unknown class")
    try:
        return _service.set_character_class(uid, character_id, selection.character_class)
    except KeyError:
        raise HTTPException(status_code=404, detail="character not found")

        """please work i beg u"""
