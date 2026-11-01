# import requests
from typing import Any

from forge_backend.storage import (
    get_redis,
    get_reference,
    list_reference_records,
    search_reference_records,
    sort_and_paginate_search_result,
    validate_content_type,
    validate_page_for_search,
)


# This is the getter methods to grab information from the database.
class CharacterDataService:
    def __init__(self, redis_client=None):
        self.redis_client = redis_client if redis_client is not None else get_redis()

    def get_race(self, race):
        return get_reference(self.redis_client, "race", race)

    def get_races(self):
        response = list_reference_records(self.redis_client, "race")
        return response

    def get_class(self, clas):
        return get_reference(self.redis_client, "class", clas)

    def get_classes(self):
        response = list_reference_records(self.redis_client, "class")
        return response

    def get_background(self, bg):
        return get_reference(self.redis_client, "background", bg)

    def get_backgrounds(self):
        response = list_reference_records(self.redis_client, "background")
        return response

    def get_item(self, item):
        return get_reference(self.redis_client, "equipment", item)

    def get_items(self):
        response = list_reference_records(self.redis_client, "equipment")
        return response

    def get_spell(self, spell):
        return get_reference(self.redis_client, "spell", spell)

    def get_spells(self):
        response = list_reference_records(self.redis_client, "spell")
        return response

    def get_skill(self, skill):
        return get_reference(self.redis_client, "skill", skill)

    def get_skills(self):
        response = list_reference_records(self.redis_client, "skill")
        return response

    def search_reference(self, query: str, page: int = 1):
        return search_reference_records(self.redis_client, query, page)

    def validate_filter(self, filter: str,) -> None | ValueError:
        if not validate_content_type(filter):
            raise ValueError(f"invalid 'type' for filter: {filter!r}")
        return

    def filter_search_result(self, content_filter: str, search_result: list[dict[str, Any]], page: int = 1) -> list[dict[str, Any]]:
        validate_page_for_search(page)
        """Assumes that the filter has already been verified as valid."""
        filtered_result = [d for d in search_result if d['type']==content_filter] # [4] [5]
        """Ensure that the results are sorted and paginated properly even after being filtered"""
        return sort_and_paginate_search_result(filtered_result, page)