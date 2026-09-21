import pytest

from forge_backend.user_character_data_service import UserCharacterDataService


userCharacterDataService = UserCharacterDataService()


def test_generate_character_id():  
    charid = userCharacterDataService.generate_character_id()
    assert charid.isnumeric() == True
    assert len(charid) == 5