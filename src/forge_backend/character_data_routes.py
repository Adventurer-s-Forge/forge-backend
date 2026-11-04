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
    response_model=dict[str, int | dict[str, int] | list[ReferenceRecord]],
    summary="Search reference content by name and optionally filter by content type",
    description="Case-insensitive substring search of reference record names across all types. An exact-match is used when filtering by content-type, if a filter is provided.\n"
    "The response includes the total number of results retrieved, the number of results for each category, and the results themselves.\n"
    "Results are sorted by name and paged at 100 per page; pass ?page=N for later pages.",
)
def search_reference(
    q: Annotated[str, Query(min_length=1, pattern=r"\S")],
    page: Annotated[int, Query(ge=1)] = 1,
    content_filter: Annotated[str | None, Query(min_length=1, pattern=r"\S")] = None,
):
    final_return_response = {"total": 0, "counts": {}, "result": []} # Initialize the final return response

    """Search reference names, optionally narrowed to one content type.

    The filter is applied before paging, so later pages of a filtered search
    stay reachable.
    """
    if content_filter is not None:
        try:
            service.validate_filter(content_filter)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    final_return_response["result"] = service.search_reference(q, page, content_filter)

    """Calculate the total number of results and the number of results for each category"""
    final_return_response["total"] = service.count_total_search_results(final_return_response["result"])
    final_return_response["counts"] = service.count_matching_searches_per_category(final_return_response["result"])
   
    return final_return_response