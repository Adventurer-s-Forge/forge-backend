from fastapi import APIRouter

from forge_backend.character_data_service import CharacterDataService

router = APIRouter()
service = CharacterDataService()


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
