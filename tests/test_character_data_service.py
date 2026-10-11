from unittest.mock import patch

from forge_backend.character_data_service import CharacterDataService


@patch("forge_backend.character_data_service.get_redis")
@patch("forge_backend.character_data_service.get_reference")
def test_get_race(mock_get_reference, mock_get_redis):
    mock_get_reference.return_value = {"type": "race", "key": "elf", "name": "Elf"}
    service = CharacterDataService()
    result_mock_return = service.get_race("elf")
    assert result_mock_return["name"] == "Elf"


@patch("forge_backend.character_data_service.get_redis")
@patch("forge_backend.character_data_service.list_reference_records")
def test_get_races(mock_list_reference_records, mock_get_redis):
    mock_list_reference_records.return_value = [
        {"type": "race", "key": "elf", "name": "Elf"},
        {"type": "race", "key": "human", "name": "Human"},
    ]

    service = CharacterDataService()
    result = service.get_races()

    assert len(result) == 2
    assert result == mock_list_reference_records.return_value
    mock_list_reference_records.assert_called_once_with(
        service.redis_client, "race"
    )


@patch("forge_backend.character_data_service.get_redis")
@patch("forge_backend.character_data_service.get_reference")
def test_get_class(mock_get_reference, mock_get_redis):
    mock_get_reference.return_value = {"type": "race", "key": "wizard", "name": "Wizard"}
    service = CharacterDataService()
    result_mock_return = service.get_class("wizard")
    assert result_mock_return["name"] == "Wizard"


@patch("forge_backend.character_data_service.get_redis")
@patch("forge_backend.character_data_service.list_reference_records")
def test_get_classes(mock_list_reference_records, mock_get_redis):
    mock_list_reference_records.return_value = [
        {"type": "class", "key": "wizard", "name": "Wizard"},
        {"type": "class", "key": "fighter", "name": "Fighter"},
    ]

    service = CharacterDataService()
    result = service.get_classes()

    assert len(result) == 2
    assert result == mock_list_reference_records.return_value
    mock_list_reference_records.assert_called_once_with(
        service.redis_client, "class"
    )


@patch("forge_backend.character_data_service.get_redis")
@patch("forge_backend.character_data_service.get_reference")
def test_get_background(mock_get_reference, mock_get_redis):
    mock_get_reference.return_value = {
        "type": "background",
        "key": "acolyte",
        "name": "Acolyte",
    }

    service = CharacterDataService()
    result = service.get_background("acolyte")

    assert result["name"] == "Acolyte"
    mock_get_reference.assert_called_once_with(
        service.redis_client, "background", "acolyte"
    )


@patch("forge_backend.character_data_service.get_redis")
@patch("forge_backend.character_data_service.list_reference_records")
def test_get_backgrounds(mock_list_reference_records, mock_get_redis):
    mock_list_reference_records.return_value = [
        {"type": "background", "key": "acolyte", "name": "Acolyte"},
        {"type": "background", "key": "sage", "name": "Sage"},
    ]

    service = CharacterDataService()
    result = service.get_backgrounds()

    assert len(result) == 2
    assert result == mock_list_reference_records.return_value
    mock_list_reference_records.assert_called_once_with(
        service.redis_client, "background"
    )

@patch("forge_backend.character_data_service.get_redis")
@patch("forge_backend.character_data_service.get_reference")
def test_get_item(mock_get_reference, mock_get_redis):
    mock_get_reference.return_value = {
        "type": "item",
        "key": "longsword",
        "name": "Longsword",
    }

    service = CharacterDataService()
    result = service.get_item("longsword")

    assert result["name"] == "Longsword"
    mock_get_reference.assert_called_once_with(
        service.redis_client, "item", "longsword"
    )


@patch("forge_backend.character_data_service.get_redis")
@patch("forge_backend.character_data_service.list_reference_records")
def test_get_items(mock_list_reference_records, mock_get_redis):
    mock_list_reference_records.return_value = [
        {"type": "item", "key": "longsword", "name": "Longsword"},
        {"type": "item", "key": "shield", "name": "Shield"},
    ]

    service = CharacterDataService()
    result = service.get_items()

    assert len(result) == 2
    assert result == mock_list_reference_records.return_value
    mock_list_reference_records.assert_called_once_with(
        service.redis_client, "item"
    )


@patch("forge_backend.character_data_service.get_redis")
@patch("forge_backend.character_data_service.get_reference")
def test_get_spell(mock_get_reference, mock_get_redis):
    mock_get_reference.return_value = {
        "type": "spell",
        "key": "fireball",
        "name": "Fireball",
    }

    service = CharacterDataService()
    result = service.get_spell("fireball")

    assert result["name"] == "Fireball"
    mock_get_reference.assert_called_once_with(
        service.redis_client, "spell", "fireball"
    )


@patch("forge_backend.character_data_service.get_redis")
@patch("forge_backend.character_data_service.list_reference_records")
def test_get_spells(mock_list_reference_records, mock_get_redis):
    mock_list_reference_records.return_value = [
        {"type": "spell", "key": "fireball", "name": "Fireball"},
        {"type": "spell", "key": "magic-missile", "name": "Magic Missile"},
        {"type": "spell", "key": "light", "name": "Light"},
    ]

    service = CharacterDataService()
    result = service.get_spells()

    assert len(result) == 3
    assert result == mock_list_reference_records.return_value
    mock_list_reference_records.assert_called_once_with(
        service.redis_client, "spell"
    )

@patch("forge_backend.character_data_service.get_redis")
@patch("forge_backend.character_data_service.get_reference")
def test_get_skill(mock_get_reference, mock_get_redis):
    mock_get_reference.return_value = {
        "type": "skill",
        "key": "acrobatics",
        "name": "Acrobatics",
    }

    service = CharacterDataService()
    result = service.get_skill("acrobatics")

    assert result["name"] == "Acrobatics"
    mock_get_reference.assert_called_once_with(
        service.redis_client, "skill", "acrobatics"
    )


@patch("forge_backend.character_data_service.get_redis")
@patch("forge_backend.character_data_service.list_reference_records")
def test_get_skills(mock_list_reference_records, mock_get_redis):
    mock_list_reference_records.return_value = [
        {"type": "skill", "key": "acrobatics", "name": "Acrobatics"},
        {"type": "skill", "key": "perception", "name": "Perception"},
    ]

    service = CharacterDataService()
    result = service.get_skills()

    assert len(result) == 2
    assert result == mock_list_reference_records.return_value
    mock_list_reference_records.assert_called_once_with(
        service.redis_client, "skill"
    )

