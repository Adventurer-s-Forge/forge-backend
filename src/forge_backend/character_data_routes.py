from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from forge_backend.character_data_service import CharacterDataService

router = APIRouter(tags=["Reference content"])
service = CharacterDataService()


class ReferenceRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["race", "class", "background", "item", "spell", "skill"]
    key: str
    name: str
    document: str
    data: dict[str, Any]

class SpellsSelection(BaseModel):
    spells: list[str]


@router.get(
    "/races",
    operation_id="list_races",
    response_model=list[ReferenceRecord],
    summary="List races",
    description="List seeded race reference records.",
)
def get_races():
    return service.get_races()


@router.get(
    "/classes",
    operation_id="list_classes",
    response_model=list[ReferenceRecord],
    summary="List classes",
    description='List seeded class reference records, e.g. `key="srd_wizard"`.',
)
def get_classes():
    return service.get_classes()


@router.get(
    "/backgrounds",
    operation_id="list_backgrounds",
    response_model=list[ReferenceRecord],
    summary="List backgrounds",
    description="List seeded background reference records.",
)
def get_backgrounds():
    return service.get_backgrounds()


@router.get(
    "/equipments",
    operation_id="list_items",
    response_model=list[ReferenceRecord],
    summary="List items",
    description="List seeded item reference records.",
)
def get_items():
    return service.get_items()


@router.get(
    "/spells",
    operation_id="list_spells",
    response_model=list[ReferenceRecord],
    summary="List spells",
    description="List seeded spell reference records.",
)
def get_spells():
    return service.get_spells()


#TODO: Need to have more robust spells validity check for class. Explore it.
@router.put("/characters/{character_id}/spells")
def set_user_character_spells(character_id: str, selection: SpellsSelection, uid: str = Depends(get_uid)):
    user_service = UserCharacterDataService()
    if user_service.get_character_by_id(uid, character_id) is None:
        raise HTTPException(status_code=404, detail="Character not found")
    if not user_service.spells_exist(selection.spells):
        raise HTTPException(status_code=400, detail="Spells not found")
    return user_service.set_character_spells(uid, character_id, selection.spells)

@router.get(
    "/skills",
    operation_id="list_skills",
    response_model=list[ReferenceRecord],
    summary="List skills",
    description="List seeded skill reference records.",
)
def get_skills():
    return service.get_skills()
