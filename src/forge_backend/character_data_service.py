# import requests
from forge_backend.storage import get_redis, list_reference_records, get_reference


# This is the getter methods to grab information from the API or the database
# in case of API is down.
class CharacterDataService:
    def __init__(self):
        self.redis_client = get_redis()

    def get_race(self, race):
        return get_reference(self.redis_client, "race", race)

    def get_races(self):
        response =  list_reference_records(self.redis_client, "race")
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
        return get_reference(self.redis_client, "item", item)

    def get_items(self):
        response = list_reference_records(self.redis_client, "item")
        return response

    def get_spell(self, spell):
        return get_reference(self.redis_client, "spell", spell)

    def get_spells(self):
        response = list_reference_records(self.redis_client, "spell")
        return response
