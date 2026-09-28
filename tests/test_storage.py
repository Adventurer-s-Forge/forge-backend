import pytest

from forge_backend.storage import (
    char_index_key,
    char_key,
    ref_index_key,
    ref_key,
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
    assert char_key("4CIZQ94T3ncLcAAizmHcN62V6Q42", "26957") == "char:4CIZQ94T3ncLcAAizmHcN62V6Q42:26957"


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
