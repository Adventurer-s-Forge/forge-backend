import pytest
from unittest.mock import patch

from forge_backend.character_data_service import CharacterDataService

# TODO: More tests needs to be written. Pausing for now.


@patch("forge_backend.character_data_service.get_redis")
@patch("forge_backend.character_data_service.get_reference")
def test_get_race(mock_get_reference, mock_get_redis):
    mock_get_reference.return_value = {"type": "race", "key": "elf", "name": "Elf"}
    service = CharacterDataService()
    result_mock_return = service.get_race("elf")
    assert result_mock_return["name"] == "Elf"


@patch("forge_backend.character_data_service.get_redis")
@patch("forge_backend.character_data_service.get_reference")
def test_get_class(mock_get_reference, mock_get_redis):
    mock_get_reference.return_value = {"type": "race", "key": "wizard", "name": "Wizard"}
    service = CharacterDataService()
    result_mock_return = service.get_class("wizard")
    assert result_mock_return["name"] == "Wizard"


def test_validate_filter_success():
    service = CharacterDataService()
    error_validating_filter = None
    try:
        service.validate_filter("magic_item")
    except ValueError as e:
        error_validating_filter = e
    assert error_validating_filter is None


def test_validate_filter_valueerror():
    service = CharacterDataService()
    error_validating_filter = None
    try:
        service.validate_filter("fakeFilter")
    except ValueError as e:
        error_validating_filter = e
    assert type(error_validating_filter) is ValueError
    assert error_validating_filter.args[0] == "invalid 'type' for filter: 'fakeFilter'"


@pytest.mark.integration
def test_filter_search_result():
    service = CharacterDataService()
    search_result = service.search_reference("par") # Do the initial search
    filtered_result = service.filter_search_result("magic_item", search_result) # Filter the search result
    assert len(filtered_result) == 2
    for result in filtered_result:
        assert result["type"] == "magic_item"


@pytest.mark.integration
def test_filter_search_result_no_results():
    service = CharacterDataService()
    search_result = service.search_reference("par") # Do the initial search
    filtered_result = service.filter_search_result("race", search_result) # Filter the search result
    assert len(filtered_result) == 0