import pytest
from pydantic import ValidationError

from forge_backend.character_models import CharacterRecord

UUID = "0f8c1a7e-3d52-4b91-a7c8-6e2f91b40d35"

PICK_A = {
    "key": "A",
    "label": "Chain Mail, Greatsword, Dungeoneer's Pack",
    "goldCp": 400,
    "grants": [
        {
            "text": "Chain Mail",
            "quantity": 1,
            "itemId": "srd-2024_chain-mail",
            "choosableFrom": None,
        },
    ],
}

PICK_B = {
    "key": "B",
    "label": "50 GP",
    "goldCp": 5000,
    "grants": [],
}


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
        "sizeChoice",
        "classId",
        "fightingStyleId",
        "toolChoiceId",
        "backgroundId",
        "equipmentChoice",
        "purchasedItemIds",
        "walletCp",
        "characterTypePresetChoice",
        "abilities",
        "proficientSkillIds",
        "expertiseIds",
        "spellIds",
        "featIds",
        "classFeatChoices",
        "completedSteps",
    ]
    assert dumped["level"] == 1
    assert dumped["raceId"] is None
    assert dumped["walletCp"] == 0
    assert dumped["fightingStyleId"] is None
    assert dumped["toolChoiceId"] is None
    assert dumped["abilities"] == {"method": None, "base": {}, "rolled": [], "originBonuses": {}}
    assert dumped["characterTypePresetChoice"] is None


def test_full_payload_roundtrips_verbatim():
    payload = {
        "id": UUID,
        "name": "Gandalf",
        "level": 1,
        "raceId": "draft_race",
        "sizeChoice": "Medium",
        "classId": "test_warden",
        "fightingStyleId": None,
        "toolChoiceId": None,
        "backgroundId": "draft_background",
        "equipmentChoice": {"class": PICK_A, "background": PICK_B},
        "purchasedItemIds": [],
        "walletCp": 0,
        # A preset needs point-buy, so a rolled sheet cannot carry one; preset values are
        # round-tripped by test_each_preset_is_accepted_with_point_buy instead.
        "characterTypePresetChoice": None,
        "abilities": {
            "method": "roll",
            "base": {"STR": 15, "DEX": 14},
            "rolled": [15, 14, 13, 12, 10, 8],
            "originBonuses": {"STR": 2},
        },
        "proficientSkillIds": ["arcana"],
        "expertiseIds": ["arcana"],
        "spellIds": ["draft_spell"],
        "featIds": ["draft_feat"],
        "classFeatChoices": [
            {
                "level": 4,
                "featId": "draft_feat",
            }
        ],
        "completedSteps": [
            "name",
            "race",
            "class",
            "background",
            "equipment",
            "attributes",
            "skills",
            "spells",
        ],
    }
    assert CharacterRecord.model_validate(payload).model_dump(mode="json", by_alias=True) == payload


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
        _payload(purchasedItemIds=[5]),
        _payload(completedSteps=["item"]),
        _payload(owner="test-user"),
        _payload(**{"class": "Wizard"}),
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


# US-42: the four presets are the frontend's CHARACTER_TYPE_PRESETS, and a preset only
# steers point-buy advice, so it is meaningless (and refused) under any other method.
PRESETS = ["Tank", "Striker", "Caster", "Skill-Focused"]


def _with_preset(preset, method):
    return _payload(characterTypePresetChoice=preset, abilities={"method": method})


def test_an_unknown_preset_is_rejected():
    # Point-buy, so the only thing that can reject it is the value itself.
    with pytest.raises(ValidationError) as exc:
        CharacterRecord.model_validate(_with_preset("Bard", "pointbuy"))

    [error] = exc.value.errors()
    assert error["loc"] == ("characterTypePresetChoice",)
    assert error["type"] == "literal_error"


@pytest.mark.parametrize("preset", PRESETS)
def test_each_preset_is_accepted_with_point_buy(preset):
    record = CharacterRecord.model_validate(_with_preset(preset, "pointbuy"))

    assert record.model_dump(mode="json")["characterTypePresetChoice"] == preset


@pytest.mark.parametrize("method", ["standard", "roll", None])
def test_a_preset_without_point_buy_is_rejected(method):
    with pytest.raises(
        ValidationError, match="characterTypePresetChoice needs the point-buy method"
    ):
        CharacterRecord.model_validate(_with_preset("Tank", method))


@pytest.mark.parametrize("method", ["standard", "pointbuy", "roll", None])
def test_no_preset_is_accepted_with_any_method(method):
    record = CharacterRecord.model_validate(_with_preset(None, method))

    assert record.characterTypePresetChoice is None
