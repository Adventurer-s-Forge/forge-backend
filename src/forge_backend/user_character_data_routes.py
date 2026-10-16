"""Player-character router: sole owner of the /characters contract."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from forge_backend.auth import current_uid
from forge_backend.character_models import CharacterDocument, CharacterRecord
from forge_backend.user_character_data_service import (
    DuplicateCharacterId,
    UserCharacterDataService,
)

Uid = Annotated[str, Depends(current_uid)]

router = APIRouter(prefix="/characters", tags=["Characters"])

_service = UserCharacterDataService()


class ErrorResponse(BaseModel):
    detail: str


@router.post(
    "",
    operation_id="create_character",
    status_code=201,
    response_model=CharacterDocument,
    responses={409: {"model": ErrorResponse}},
    summary="Create a character",
    description=(
        "Create a full character record. The caller supplies the UUID."
        "Ownership comes from the verified Firebase ID token."
    ),
)
def create_new_character(character: CharacterRecord, uid: Uid):
    try:
        return _service.create_user_character(uid, character)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except DuplicateCharacterId:
        raise HTTPException(status_code=409, detail="Character ID collision, retry")


@router.get(
    "",
    operation_id="list_characters",
    response_model=list[CharacterDocument],
    summary="List characters",
    description="List stored character records for the authenticated caller.",
)
def list_characters(uid: Uid):
    return _service.list_characters(uid)


@router.get(
    "/ids",
    operation_id="list_character_ids",
    response_model=list[str],
    summary="List character IDs",
    description="List sorted character IDs for the authenticated caller.",
)
def list_character_ids(uid: Uid):
    return _service.list_character_ids(uid)


@router.get(
    "/count",
    operation_id="count_characters",
    response_model=int,
    summary="Count characters",
    description="Count character index entries for the authenticated caller.",
)
def get_num_user_characters(uid: Uid):
    return _service.get_num_user_characters(uid)


@router.get(
    "/{character_id}",
    operation_id="get_character",
    response_model=CharacterDocument,
    responses={404: {"model": ErrorResponse}},
    summary="Get a character",
    description="Return one stored character record.",
)
def get_character_by_id(character_id: str, uid: Uid):
    record = _service.get_character_by_id(uid, character_id)
    if record is None:
        raise HTTPException(status_code=404, detail="character not found")
    return record


# Other specific endpoint PUTs have been removed since there is only 1 PUT after POST in the client.
# Client forces uses a confirmation if they accidentally hit escape or 'x' when creating character.
# It provides user 3 options: "Keep editing", "Discard", and "Save and close"
# "Save and close" **OR** "Complete" is the "1 PUT" the client sends out. Otherwise, no other PUTs happen between steps.
@router.put(
    "/{character_id}",
    operation_id="save_character",
    response_model=CharacterDocument,
    responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
    summary="Save a character",
    description=(
        "Full-replacement save of one owned character record. The path ID and "
        "body id must match. Ownership comes from the verified Firebase ID token."
    ),
)
def save_character(character_id: str, character: CharacterRecord, uid: Uid):
    try:
        return _service.save_character(uid, character_id, character)
    except KeyError:
        raise HTTPException(status_code=404, detail="character not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/{character_id}",
    operation_id="delete_character",
    status_code=204,
    summary="Delete a character",
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def delete_character(character_id: str, uid: Uid) -> None:
    if not _service.remove_character(uid, character_id):
        raise HTTPException(404, "character not found")