from unittest.mock import patch

from forge_backend.character_data_service import CharacterDataService

mock_race_records = [
    {
        "type": "race",
        "key": "srd_elf",
        "name": "Elf",
        "document": "srd-2014",
        "data": {"key": "srd_elf", "name": "Elf", "document": {"key": "srd-2014"}},
    },
    {
        "type": "race",
        "key": "srd_human",
        "name": "Human",
        "document": "srd-2014",
        "data": {"key": "srd_human", "name": "Human", "document": {"key": "srd-2014"}},
    },
    {
        "type": "race",
        "key": "srd_dwarf",
        "name": "Dwarf",
        "document": "srd-2014",
        "data": {"key": "srd_dwarf", "name": "Dwarf", "document": {"key": "srd-2014"}},
    },
]

mock_class_records = [
    {
        "type": "class",
        "key": "srd_fighter",
        "name": "Fighter",
        "document": "srd-2014",
        "data": {"hit_dice": "1d10"},
    },
    {
        "type": "class",
        "key": "srd_wizard",
        "name": "Wizard",
        "document": "srd-2014",
        "data": {"hit_dice": "1d6"},
    },
    {
        "type": "class",
        "key": "srd_ranger",
        "name": "Ranger",
        "document": "srd-2014",
        "data": {"hit_dice": "1d10"},
    },
]

mock_background_records = [
    {
        "type": "background",
        "key": "srd_acolyte",
        "name": "Acolyte",
        "document": "srd-2014",
        "data": {},
    },
    {
        "type": "background",
        "key": "srd_criminal",
        "name": "Criminal",
        "document": "srd-2014",
        "data": {},
    },
    {
        "type": "background",
        "key": "srd_hermit",
        "name": "Hermit",
        "document": "srd-2014",
        "data": {},
    },
]

mock_item_records = [
    {
        "type": "item",
        "key": "srd_longsword",
        "name": "Longsword",
        "document": "srd-2014",
        "data": {},
    },
    {
        "type": "item",
        "key": "srd_dagger",
        "name": "Dagger",
        "document": "srd-2014",
        "data": {},
    },
    {
        "type": "item",
        "key": "srd_shield",
        "name": "Shield",
        "document": "srd-2014",
        "data": {},
    },
]

mock_spell_records = [
    {
        "type": "spell",
        "key": "srd_fireball",
        "name": "Fireball",
        "document": "srd-2014",
        "data": {"level": 3},
    },
    {
        "type": "spell",
        "key": "srd_magic_missile",
        "name": "Magic Missile",
        "document": "srd-2014",
        "data": {"level": 1},
    },
    {
        "type": "spell",
        "key": "srd_light",
        "name": "Light",
        "document": "srd-2014",
        "data": {"level": 0},
    },
]


@patch("forge_backend.character_data_service.get_redis")
@patch("forge_backend.character_data_service.list_reference_records")
def test_get_races(mock_list_reference_records, mock_get_redis):
    mock_list_reference_records.return_value = mock_race_records
    service = CharacterDataService()
    results = service.get_races()

    assert results[0]["name"] == "Elf"
    assert results[1]["name"] == "Human"
    assert results[2]["name"] == "Dwarf"


@patch("forge_backend.character_data_service.get_redis")
@patch("forge_backend.character_data_service.list_reference_records")
def test_get_classes(mock_list_reference_records, mock_get_redis):
    mock_list_reference_records.return_value = mock_class_records

    service = CharacterDataService()
    results = service.get_classes()

    assert results[0]["name"] == "Fighter"
    assert results[1]["name"] == "Wizard"
    assert results[2]["name"] == "Ranger"


@patch("forge_backend.character_data_service.get_redis")
@patch("forge_backend.character_data_service.list_reference_records")
def test_get_backgrounds(mock_list_reference_records, mock_get_redis):
    mock_list_reference_records.return_value = mock_background_records

    service = CharacterDataService()
    results = service.get_backgrounds()

    assert results[0]["name"] == "Acolyte"
    assert results[1]["name"] == "Criminal"
    assert results[2]["name"] == "Hermit"


@patch("forge_backend.character_data_service.get_redis")
@patch("forge_backend.character_data_service.list_reference_records")
def test_get_items(mock_list_reference_records, mock_get_redis):
    mock_list_reference_records.return_value = mock_item_records

    service = CharacterDataService()
    results = service.get_items()

    assert results[0]["name"] == "Longsword"
    assert results[1]["name"] == "Dagger"
    assert results[2]["name"] == "Shield"


@patch("forge_backend.character_data_service.get_redis")
@patch("forge_backend.character_data_service.list_reference_records")
def test_get_spells(mock_list_reference_records, mock_get_redis):
    mock_list_reference_records.return_value = mock_spell_records

    service = CharacterDataService()
    results = service.get_spells()

    assert results[0]["name"] == "Fireball"
    assert results[1]["name"] == "Magic Missile"
    assert results[2]["name"] == "Light"
