from forge_backend.open_5e_caller import Open5eCaller
from forge_backend.storage import get_redis, refresh_reference_type

# This script is only to populate the database. 
# It will be backup in case the API is down and the data is retrived from database.
open_5e_caller = Open5eCaller()
redis_client = get_redis()

races = open_5e_caller.get_races()
classes = open_5e_caller.get_classes()
backgrounds = open_5e_caller.get_backgrounds()
items = open_5e_caller.get_items()
spells = open_5e_caller.get_spells()

# Following are steps to format the raw data to the format redis will accept as.
races_formatted = []
classes_formatted = []
backgrounds_formatted = []
items_formatted = []
spells_formatted = []

for race in races:
    races_formatted.append({"type": "race",
        "key": race.get("slug"),
        "name": race.get("name"),
        "document": race.get("document__slug"),
        "data": race
        })

for clas in classes:
    classes_formatted.append({"type": "class",
        "key": clas.get("slug"),
        "name": clas.get("name"),
        "document": clas.get("document__slug"),
        "data": clas
        })

for background in backgrounds:
    backgrounds_formatted.append({"type": "background",
        "key": background.get("slug"),
        "name": background.get("name"),
        "document": background.get("document__slug"),
        "data": background
        })

for item in items:
    items_formatted.append({"type": "item",
        "key": item.get("slug"),
        "name": item.get("name"),
        "document": item.get("document__slug"),
        "data": item
        })

for spell in spells:
    spells_formatted.append({"type": "spell",
        "key": spell.get("slug"),
        "name": spell.get("name"),
        "document": spell.get("document__slug"),
        "data": spell
        })

# After formatting, pushing to redis for data to be saved.
refresh_reference_type(redis_client, "race", races_formatted)
refresh_reference_type(redis_client, "class", classes_formatted)
refresh_reference_type(redis_client, "background", backgrounds_formatted)
refresh_reference_type(redis_client, "item", items_formatted)
refresh_reference_type(redis_client, "spell", spells_formatted)
