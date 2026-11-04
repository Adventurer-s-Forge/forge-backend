# import requests
from typing import Any

from forge_backend.storage import (
    get_all_ref_types,
    get_redis,
    get_reference,
    list_reference_records,
    search_reference_records,
    validate_content_type,
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

    def search_reference(self, query: str, page: int = 1, content_type: str | None = None):
        return search_reference_records(self.redis_client, query, page, content_type)

    def validate_filter(self, filter: str,) -> None:
        if not validate_content_type(filter):
            raise ValueError(f"invalid 'type' for filter: {filter!r}")

    def count_total_search_results(self, search_result: list[dict[str, Any]]) -> int:
        return len(search_result)

    def count_matching_searches_per_category(self, search_result: list[dict[str, Any]]) -> dict[str, int]:
        # Start contstructing the counts dictionary by adding the ref types and initializing their counts to 0 [7]
        #all_ref_types = get_all_ref_types()
        counts_dict = {ref_type:0 for ref_type in get_all_ref_types()}

        # Construct the list of all ref types/categories included in the search result [5]
        all_categories_in_results = [result["type"] for result in search_result]
        # Construct the list of distinct ref types/categories included in the search result [4]
        distinct_categories_in_results = set(all_categories_in_results)

        for category in distinct_categories_in_results:
            num_instances_of_category = all_categories_in_results.count(category) # [6]
            counts_dict[category] = num_instances_of_category
        
        return counts_dict