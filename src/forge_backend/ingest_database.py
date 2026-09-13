from forge_backend.open_5e_caller import Open5eCaller
from forge_backend.storage import get_redis, refresh_reference_type

# This script is only to populate the database. 
# It will be backup in case the API is down and the data is retrived from database.
open_5e_caller = Open5eCaller()
redis_client = get_redis()

races = open_5e_caller.get_races()
classes = open_5e_caller.get_classes()

# Following are steps to format the raw data to the format redis will accept as.
races_formatted = []
classes_formatted = []

for race in races["results"]:
    races_formatted.append({"type": "race",
        "key": race.get("slug"),
        "name": race.get("name"),
        "document": race.get("document__slug"),
        "data": race
        })

for clas in classes["results"]:
    classes_formatted.append({"type": "class",
        "key": clas.get("slug"),
        "name": clas.get("name"),
        "document": clas.get("document__slug"),
        "data": clas
        })

# After formatting, pushing to redis for data to be saved.
refresh_reference_type(redis_client, "race", races_formatted)
refresh_reference_type(redis_client, "class", classes_formatted)