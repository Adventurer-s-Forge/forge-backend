import pytest

from forge_backend.user_character_data_service import UserCharacterDataService


userCharacterDataService = UserCharacterDataService()


def test_generate_character_id():  
    charid = userCharacterDataService.generate_character_id()
    assert charid.isnumeric() == True # Verify that the output is a number [6]
    assert len(charid) == 5