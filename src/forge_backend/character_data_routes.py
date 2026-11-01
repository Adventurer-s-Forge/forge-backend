from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from forge_backend.character_data_service import CharacterDataService

router = APIRouter(tags=["Reference content"])
service = CharacterDataService()


class ReferenceRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: Literal[
        "race",
        "class",
        "background",
        "equipment",
        "skill",
        "spell",
        "monster",
        "magic_item",
        "condition",
    ]
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
    description='List seeded class reference records, e.g. `key="srd-2024_wizard"`.',
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
    "/equipment",
    operation_id="list_items",
    response_model=list[ReferenceRecord],
    summary="List equipment",
    description="List seeded equipment reference records.",
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


@router.get(
    "/skills",
    operation_id="list_skills",
    response_model=list[ReferenceRecord],
    summary="List skills",
    description="List seeded skill reference records.",
)
def get_skills():
    return service.get_skills()


@router.get(
    "/search",
    operation_id="search_reference",
    response_model=list[ReferenceRecord],
    summary="Search reference content by name",
    description="Case-insensitive substring search of reference record names across all types. "
    "Results are sorted by name and paged at 100 per page; pass ?page=N for later pages.",
)
def search_reference(
    q: Annotated[str, Query(min_length=1, pattern=r"\S")],
    page: Annotated[int, Query(ge=1)] = 1,
    content_filter: Annotated[str, Query(min_length=1, pattern=r"\S")] = "N/A", # [6]
):
    search_result = service.search_reference(q, page)
    """
    If the user does not apply any filters, then return the base search result.
    Otherwise, filter the base search result using the incoming content filter and return the filtered result.
    """
    if content_filter == "N/A":
        return search_result
    else:
        try:
            service.validate_filter(content_filter)
            return service.filter_search_result(content_filter, search_result, page)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))