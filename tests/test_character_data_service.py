from unittest.mock import patch
import pytest
from forge_backend.character_data_service import CharacterDataService

@patch("forge_backend.character_data_service.get_redis")
@patch("forge_backend.character_data_service.get_reference")
def test_get_race(mock_get_reference, mock_get_redis):
    mock_get_reference.return_value = {
        "type": "race",
        "key": "elf",
        "name": "Elf"
    }
    service = CharacterDataService()
    result_mock_return =  service.get_race("elf")
    assert result_mock_return["name"] == "Elf"

@patch("forge_backend.character_data_service.get_redis")
@patch("forge_backend.character_data_service.get_reference")
def test_get_class(mock_get_reference, mock_get_redis):
    mock_get_reference.return_value = {
            "type": "race",
            "key": "wizard",
            "name": "Wizard"
        }
    service = CharacterDataService()
    result_mock_return =  service.get_class("wizard")
    assert result_mock_return["name"] == "Wizard"