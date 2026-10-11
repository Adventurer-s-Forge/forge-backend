import pytest
from pydantic import ValidationError

from forge_backend.character_models import CharacterRecord

UUID = "0f8c1a7e-3d52-4b91-a7c8-6e2f91b40d35"


def _payload(**overrides):
    base = {"id": UUID, "name": "Gandalf"}
    base.update(overrides)
    return base


def test_minimal_draft_produces_blank_defaults():
    record = CharacterRecord.model_validate(_payload())
    dumped = record.model_dump(mode="json")
    assert list(dumped) == [
        "id",
        "name",
        "level",
        "raceId",
        "classId",
        "backgroundId",
        "abilities",
        "proficientSkillIds",
        "expertiseIds",
        "spellIds",
        "equipmentIds",
        "completedSteps",
    ]
    assert dumped["level"] == 1
    assert dumped["raceId"] is None
    assert dumped["abilities"] == {"method": None, "base": {}, "rolled": [], "originBonuses": {}}


def test_full_payload_roundtrips_verbatim():
    payload = {
        "id": UUID,
        "name": "Gandalf",
        "level": 1,
        "raceId": "draft_race",
        "classId": "test_warden",
        "backgroundId": "draft_background",
        "abilities": {
            "method": "roll",
            "base": {"STR": 15, "DEX": 14},
            "rolled": [15, 14, 13, 12, 10, 8],
            "originBonuses": {"STR": 2},
        },
        "proficientSkillIds": ["arcana"],
        "expertiseIds": ["arcana"],
        "spellIds": ["draft_spell"],
        "equipmentIds": ["srd_shield", "srd_shield"],
        "completedSteps": ["name", "class", "item"],
    }
    assert CharacterRecord.model_validate(payload).model_dump(mode="json") == payload


@pytest.mark.parametrize(
    "payload",
    [
        _payload(id="not-a-uuid"),
        _payload(id="0F8C1A7E-3D52-4B91-A7C8-6E2F91B40D35"),
        _payload(name="   "),
        _payload(level=True),
        _payload(level="5"),
        _payload(level=0),
        _payload(level=21),
        _payload(raceId=""),
        _payload(classId=""),
        _payload(abilities={"method": "epic"}),
        _payload(abilities={"base": {"STR": "15"}}),
        _payload(abilities={"base": {"FOO": 15}}),
        _payload(abilities={"unknown": 1}),
        _payload(proficientSkillIds=[""]),
        _payload(equipmentIds=[5]),
        _payload(completedSteps=["equipment"]),
        _payload(owner="test-user"),
        _payload(**{"class": "Wizard"}),
        _payload(equipment=["Shield"]),
    ],
)
def test_structural_rejections(payload):
    with pytest.raises(ValidationError):
        CharacterRecord.model_validate(payload)


def test_missing_required_rejected():
    with pytest.raises(ValidationError):
        CharacterRecord.model_validate({"name": "Gandalf"})
    with pytest.raises(ValidationError):
        CharacterRecord.model_validate({"id": UUID})
