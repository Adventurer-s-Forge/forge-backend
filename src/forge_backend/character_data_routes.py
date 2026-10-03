from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from forge_backend.character_data_service import CharacterDataService

router = APIRouter(tags=["Reference content"])
service = CharacterDataService()


class ReferenceRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal["race", "class", "background", "item", "spell"]
    key: str
    name: str
    document: str
    data: dict[str, Any]


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
    "/items",
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
