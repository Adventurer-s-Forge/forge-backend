import json

import pytest

from forge_backend.storage import (
    char_index_key,
    char_key,
    ref_index_key,
    ref_key,
    sort_and_paginate_search_result,
    validate_content_type,
    validate_page_for_search,
    validate_reference_record,
)


def _valid_record(**overrides):
    record = {
        "type": "race",
        "key": "srd_dragonborn",
        "name": "Dragonborn",
        "document": "srd-2014",
        "data": {"speed": "30 ft"},
    }
    record.update(overrides)
    return record


def test_ref_key_format():
    assert ref_key("race", "srd_dragonborn") == "ref:race:srd_dragonborn"


def test_char_key_format():
    assert (
        char_key("4CIZQ94T3ncLcAAizmHcN62V6Q42", "26957")
        == "char:4CIZQ94T3ncLcAAizmHcN62V6Q42:26957"
    )


def test_ref_index_key_format():
    assert ref_index_key("spell") == "ref:idx:spell"


def test_char_index_key_format():
    assert char_index_key("4CIZQ94T3ncLcAAizmHcN62V6Q42") == "char:idx:4CIZQ94T3ncLcAAizmHcN62V6Q42"


def test_validate_accepts_valid_record_with_extra_fields():
    record = _valid_record(extra_junk="ignored", data={"speed": "30 ft", "up": True})
    validate_reference_record(record, "race")


@pytest.mark.parametrize(
    ("overrides", "ref_type"),
    [
        ({"type": "spell"}, "race"),  # type not in REF_TYPES for this check / mismatch
        ({"type": "race"}, "spell"),  # type != ref_type
        ({"key": "Bad Key!"}, "race"),  # bad slug charset
        ({"key": ""}, "race"),  # empty slug
        ({"name": ""}, "race"),  # empty name
        ({"name": 42}, "race"),  # non-string name
        ({"document": ""}, "race"),  # empty document
        ({"document": None}, "race"),  # non-string document
        ({"data": [1, 2]}, "race"),  # non-Mapping data
        ({"data": "speed"}, "race"),  # non-Mapping data
    ],
)
def test_validate_rejects_bad_records(overrides, ref_type):
    with pytest.raises(ValueError):
        validate_reference_record(_valid_record(**overrides), ref_type)


@pytest.mark.test_id("UT-57")
def test_validate_page_for_search_valid_page():
    error_with_page = None
    try:
        validate_page_for_search(1)
    except ValueError as e:
        error_with_page = e
    assert error_with_page == None


@pytest.mark.test_id("UT-58")
def test_dal_search_invalid_page_raises():
    with pytest.raises(ValueError, match="invalid page"):
        validate_page_for_search(0)
        

# Read in the test search result and expected sorted result from JSON files since they are too large to hard-code into this file [7]
SEARCH_RESULT = None
with open("tests/static_test_data/test_search_result.json", "r") as file:
    SEARCH_RESULT = json.load(file)
EXPECTED_RESULT = None
with open("tests/static_test_data/expected_sorted_result.json", "r") as file:
    EXPECTED_RESULT = json.load(file)


@pytest.mark.test_id("UT-59")
def test_sort_and_paginate_results():
    assert sort_and_paginate_search_result(SEARCH_RESULT) == EXPECTED_RESULT


@pytest.mark.test_id("UT-56")
def test_validate_content_type_valid():
    assert validate_content_type("magic_item") == True


@pytest.mark.test_id("UT-55")
def test_validate_content_type_invalid():
    assert validate_content_type("fakeContentType") == False