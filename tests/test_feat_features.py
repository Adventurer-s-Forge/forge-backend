from unittest.mock import patch

from forge_backend.feat_rules import (
    available_background_feats,
    available_class_feats,
)


def test_available_class_feats_respects_character_level():
    mock_class = {
        "data": {
            "features": [
                {
                    "name": "Fighting Style",
                    "gained_at": [1],
                },
                {
                    "name": "Ability Score Improvement",
                    "gained_at": [4, 8, 12, 16, 19],
                },
                {
                    "name": "Epic Boon",
                    "gained_at": [19],
                },
            ]
        }
    }

    with patch(
        "forge_backend.feat_rules.character_data_service.CharacterDataService"
    ) as mock_service:
        mock_service.return_value.get_class.return_value = mock_class

        result = available_class_feats("test_fighter", 4)

    assert result == {
        "Fighting Style": [1],
        "Ability Score Improvement": [4],
    }



def test_available_background_feats():
    mock_background = {
        "type": "background",
        "key": "srd-2024_acolyte",
        "name": "Acolyte",
        "document": "srd-2024",
        "data": {
            "benefits": [
                {
                    "type": "feat", "desc": "Magic Initiate (Cleric)"
                }
            ],
        }
    }

    with patch(
        "forge_backend.feat_rules.character_data_service.CharacterDataService"
    ) as mock_service:
        mock_service.return_value.get_background.return_value = mock_background

        result = available_background_feats("srd-2024_acolyte")

    assert result == {"Acolyte": ["Magic Initiate"]}



def test_class_feat_choice_rejected_below_required_level():
    from types import SimpleNamespace
    from unittest.mock import patch

    import pytest

    from forge_backend.user_character_data_service import UserCharacterDataService

    character = SimpleNamespace(
        classId="srd-2024_barbarian",
        level=3,
        classFeatChoices=[
            SimpleNamespace(
                featId="srd-2024_ability-score-improvement",
                level=4,
            )
        ],
    )

    with patch.object(
        UserCharacterDataService,
        "_get_class_feats",
        return_value={"Ability Score Improvement": []},
    ):
        service = UserCharacterDataService(redis_client=object())

        with pytest.raises(
            ValueError,
            match="feat choice is not available at this level",
        ):
            service._validate_class_feat_choices(character)
