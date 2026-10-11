import pytest

from forge_backend.user_character_data_service import UserCharacterDataService

pytestmark = pytest.mark.integration


def test_generate_character_id(redis_conn):
    service = UserCharacterDataService(redis_conn)
    charid = service.generate_character_id("m12345")
    assert len(charid) == 8
    assert int(charid, 16) >= 0


def test_create_new_character_roundtrip(redis_conn):
    service = UserCharacterDataService(redis_conn)
    user_id = "4CIZQ94T3ncLcAAizmHcN62V6Q43"
    user_name = "iLoveSourCream"
    character_name = "Bart Penelope"
    character_id = "12345"

    expected = {"owner": user_name, "name": character_name}
    assert service.create_user_character(user_id, character_name, user_name, character_id) == 1
    assert service.get_num_user_characters(user_id) == 1
    assert service.get_character_by_id(user_id, character_id) == expected
    assert service.list_character_ids(user_id) == [character_id]
    assert service.list_characters(user_id) == [expected]


def test_valid_skill_values(redis_conn):
    service = UserCharacterDataService(redis_conn)
    assert service.valid_skill_values() == set()


def test_skill_exists(redis_conn):
    service = UserCharacterDataService()
    test_skills_list = ["arcana", "animal-handling", "survival", "stealth", "intimitation", "history"]
    all_skills_exist = True

    for test_skill in test_skills_list:
        result = service.skill_exists(test_skill)
        # If a test skill is not found, exit the loop and indicate that not all skills were found in the ref skills list.
        if result == False:
            break

    assert all_skills_exist == True


def test_skill_does_not_exist(redis_conn):
    service = UserCharacterDataService()
    assert service.skill_exists("fake_skill") == False


def test_add_proficient_skills(redis_conn):
    service = UserCharacterDataService(redis_conn)
    user_id = "4CIZQ94T3ncLcAAizmHcN62V6Q43"
    user_name = "iLoveSourCream"
    character_name = "Bart Proficient"
    test_skill_label = "proficientIds"
    test_skill_list = ["arcana", "history", "intimidation"]
    expected = ["arcana", "history", "intimidation"]

    character_id = service.generate_character_id(user_id)
    service.create_user_character(user_id, character_name, user_name, character_id)
    char = service.set_character_skills(user_id, character_id, test_skill_label, test_skill_list)
    assert (test_skill_label in char) == True # validate the the skill label was added as a key to the character dictionary [3]
    assert char[test_skill_label] == expected


def test_add_expertise_skills(redis_conn):
    service = UserCharacterDataService(redis_conn)
    user_id = "4CIZQ94T3ncLcAAizmHcN62V6Q43"
    user_name = "iLoveSourCream"
    character_name = "Bart Expertise"
    test_skill_label = "expertiseIds"
    test_skill_list = ["athletics", "persuasion"]
    expected = ["athletics", "persuasion"]

    character_id = service.generate_character_id(user_id)
    service.create_user_character(user_id, character_name, user_name, character_id)
    char = service.set_character_skills(user_id, character_id, test_skill_label, test_skill_list)
    assert (test_skill_label in char) == True # validate the the skill label was added as a key to the character dictionary [3]
    assert char[test_skill_label] == expected
    

def test_add_skill_to_list(redis_conn):
    service = UserCharacterDataService(redis_conn)
    user_id = "4CIZQ94T3ncLcAAizmHcN62V6Q43"
    user_name = "iLoveSourCream"
    character_name = "Bart AddSkill"
    test_skill_label = "proficientIds"
    original_skill_list = ["arcana", "history", "intimidation"]
    updated_skill_list = ["arcana", "history", "intimidation", "animal-handling"]
    expected = ["arcana", "history", "intimidation", "animal-handling"]

    character_id = service.generate_character_id(user_id)
    service.create_user_character(user_id, character_name, user_name, character_id)
    char = service.set_character_skills(user_id, character_id, test_skill_label, original_skill_list)
    char = service.set_character_skills(user_id, character_id, test_skill_label, updated_skill_list)
    assert (test_skill_label in char) == True # validate the the skill label was added as a key to the character dictionary [3]
    assert char[test_skill_label] == expected


def test_remove_skill_from_list(redis_conn):
    service = UserCharacterDataService(redis_conn)
    user_id = "4CIZQ94T3ncLcAAizmHcN62V6Q43"
    user_name = "iLoveSourCream"
    character_name = "Bart RemoveSkill"
    test_skill_label = "proficientIds"
    original_skill_list = ["arcana", "history", "intimidation"]
    updated_skill_list = ["arcana", "intimidation"]
    expected = ["arcana", "intimidation"]

    character_id = service.generate_character_id(user_id)
    service.create_user_character(user_id, character_name, user_name, character_id)
    char = service.set_character_skills(user_id, character_id, test_skill_label, original_skill_list)
    char = service.set_character_skills(user_id, character_id, test_skill_label, updated_skill_list)
    assert (test_skill_label in char) == True # validate the the skill label was added as a key to the character dictionary [3]
    assert char[test_skill_label] == expected


def test_key_error_when_setting_skills(redis_conn):
    """Verify that a KeyError is thrown and that it returns the character ID that was inputted."""
    service = UserCharacterDataService(redis_conn)
    user_id = "4CIZQ94T3ncLcAAizmHcN62V6Q43"
    user_name = "iLoveSourCream"
    character_name = "Bart Proficient"
    test_skill_label = "proficientIds"
    test_skill_list = ["arcana", "history", "intimidation"]
    expected = "fakeCharID"

    character_id = service.generate_character_id(user_id)
    service.create_user_character(user_id, character_name, user_name, character_id)
    
    error_setting_skills = None
    try:
        char = service.set_character_skills(user_id, "fakeCharID", test_skill_label, test_skill_list)
    except KeyError as error:
        error_setting_skills = error
    
    assert error_setting_skills != None
    assert error_setting_skills.args[0] == expected # The actual error message is in position 0 of the error args