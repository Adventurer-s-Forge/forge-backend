# import requests
from forge_backend.storage import get_redis, list_reference_records

# This is the getter methods to grab information from the API or the database
# in case of API is down.
class CharacterDataService:

    def __init__(self):
        self.redis_client = get_redis()

    def get_races(self):
        # try:
        #     response = requests.get("https://api.open5e.com/v1/races/", timeout=5)
        #     response.raise_for_status()
        #     response = response.json()
        # except requests.exceptions.RequestException:
        #     response =  list_reference_records(self.redis_client, "race")
        response =  list_reference_records(self.redis_client, "race")
        return response

    def get_classes(self):
        # try:
        #     response = requests.get("https://api.open5e.com/v1/classes/", timeout=5)
        #     response.raise_for_status()
        #     response = response.json()
        # except requests.exceptions.RequestException:
        #     response = list_reference_records(self.redis_client, "class")
        response = list_reference_records(self.redis_client, "class")
        return response