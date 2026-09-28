from fastapi import APIRouter, Depends, Header, HTTPException

from forge_backend.character_data_service import CharacterDataService
from forge_backend.user_character_data_service import UserCharacterDataService

router = APIRouter()
service = CharacterDataService()


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


@router.get("/items")
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
