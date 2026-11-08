from forge_backend import character_data_service


FEATS_BY_TYPE = {
    "Origin": [
        "Alert",
        "Magic Initiate",
        "Savage Attacker",
        "Skilled",
    ],
    "Ability Score Improvement": [ # added this to deal with inconsistent feat library
            "Ability Score Improvement",
            "Grappler",
    ],
    "General": [
        "Ability Score Improvement",
        "Grappler",
    ],
    "Fighting Style": [
        "Archery",
        "Defense",
        "Great Weapon Fighting",
        "Two-Weapon Fighting",
    ],
    "Epic Boon": [
        "Boon of Combat Prowess",
        "Boon of Dimensional Travel",
        "Boon of Fate",
        "Boon of Irresistible Offense",
        "Boon of Spell Recall",
        "Boon of the Night Spirit",
        "Boon of Truesight",
    ],
}


def available_class_feats(char_class: str, char_level: int):
    details = character_data_service.CharacterDataService()
    char_class_details = details.get_class(char_class)

    char_class_feat = {}

    for feature in char_class_details.get("data", {}).get("features", []):
        name = feature.get("name")
        gained_at = feature.get("gained_at", [])

        if name in FEATS_BY_TYPE:
            unlocked_levels = []

            for level in gained_at:
                if level <= char_level:
                    unlocked_levels.append(level)

            if unlocked_levels:
                char_class_feat[name] = unlocked_levels

    return char_class_feat
    


def available_background_feats(char_backgrd: str, redis_client=None):
    details = character_data_service.CharacterDataService(redis_client)
    char_backgrd_details = details.get_background(char_backgrd)

    char_backgrd_feat = {}

    for feature in char_backgrd_details.get("data", {}).get("benefits", []):
        if feature.get("type") == "feat":
            for ref in feature.get("crossreferences", {}).get("to", []):
                ft = ref.get("anchor")
                char_backgrd_feat.setdefault(char_backgrd_details.get("name"), []).append(ft)

    return char_backgrd_feat