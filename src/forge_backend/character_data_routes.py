from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from forge_backend.character_data_service import CharacterDataService
from forge_backend.user_character_data_service import UserCharacterDataService

router = APIRouter()
service = CharacterDataService()


class ClassSelection(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    character_class: str = Field(alias="class", min_length=1)

class SpellsSelection(BaseModel):
    spells: list[str]


# TODO(US-19/auth): replace with Firebase ID-token verification.
def get_uid(x_user_id: str = Header(alias="X-User-Id")) -> str:
    if not x_user_id:
        raise HTTPException(status_code=422, detail="X-User-Id header required")
    return x_user_id


@router.get("/races")
def get_races():
    return service.get_races()


@router.get("/classes")
def get_classes():
    return service.get_classes()


@router.get("/backgrounds")
def get_backgrounds():
    return service.get_backgrounds()


@router.get("/equipments")
def get_items():
    return service.get_items()


@router.get("/spells")
def get_spells():
    return service.get_spells()


@router.get("/characters/{character_id}")
def get_character(character_id: str, uid: str = Depends(get_uid)):
    record = UserCharacterDataService().get_character_by_id(uid, character_id)
    if record is None:
        raise HTTPException(status_code=404, detail="character not found")
    return record


@router.put("/characters/{character_id}/class")
def set_character_class(character_id: str, selection: ClassSelection, uid: str = Depends(get_uid)):
    user_service = UserCharacterDataService()
    if user_service.get_character_by_id(uid, character_id) is None:
        raise HTTPException(status_code=404, detail="character not found")
    if not user_service.class_exists(selection.character_class):
        raise HTTPException(status_code=400, detail="unknown class")
    return user_service.set_character_class(uid, character_id, selection.character_class)

#TODO: Need to have more robust spells validity check for class. Explore it.
@router.put("/characters/{character_id}/spells")
def set_user_character_spells(character_id: str, selection: SpellsSelection, uid: str = Depends(get_uid)):
    user_service = UserCharacterDataService()
    if user_service.get_character_by_id(uid, character_id) is None:
        raise HTTPException(status_code=404, detail="Character not found")
    if not user_service.spells_exist(selection.spells):
        raise HTTPException(status_code=400, detail="Spells not found")
    return user_service.set_character_spells(uid, character_id, selection.spells)
