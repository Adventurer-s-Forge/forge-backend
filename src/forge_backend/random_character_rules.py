"""Uniform random level-one character generation (US-39).

Pure: the catalog, the entropy source and the character ID all arrive as arguments. There
is no I/O, no clock, no global RNG, and no optimizer: every legal decision is drawn
uniformly and nothing is reassigned afterwards. US-40 (Smart Randomize) is a separate
feature and deliberately not reachable from here.
"""

from __future__ import annotations

import copy
import random
import re
from typing import Any

from forge_backend.character_models import AbilityKey, CharacterRecord
from forge_backend.creation_rules import (
    ABILITIES,
    CREATION_STEPS,
    POINT_BUY_BUDGET,
    SPELL_STEP,
    CreationCatalog,
    class_skill_pool,
    expertise_count,
    origin_maps,
    point_buy_cost,
    preflight_catalog,
    spell_budget,
    spell_options,
    validate_complete_pointbuy_character,
)

PROPOSAL_MIN = 8
PROPOSAL_MAX = 16  # exclusive: randrange(8, 16) is 8..15, the legal base range


def sample_pointbuy(rng: random.Random) -> dict[AbilityKey, int]:
    """Six independent 8-15 draws, kept whole only when the array costs 27 or less.

    Each ordered proposal has the same probability, so conditioning on the budget yields a
    uniform draw over the legal arrays. Nothing is sorted, reassigned, or spent up to the
    cap, and a rejected proposal is simply redrawn.
    """
    while True:
        proposal: dict[AbilityKey, int] = {
            ability: rng.randrange(PROPOSAL_MIN, PROPOSAL_MAX) for ability in ABILITIES
        }
        if point_buy_cost(proposal) <= POINT_BUY_BUDGET:
            return proposal


def generate_random_character(
    catalog: CreationCatalog, rng: random.Random, *, character_id: str
) -> CharacterRecord:
    """Draw one complete, legal level-one character and prove it valid before returning."""
    preflight_catalog(catalog)

    race = catalog["races"][rng.choice(sorted(catalog["races"]))]
    cls = catalog["classes"][rng.choice(sorted(catalog["classes"]))]
    bg = catalog["backgrounds"][rng.choice(sorted(catalog["backgrounds"]))]

    base = sample_pointbuy(rng)
    bonuses = rng.choice(origin_maps(list(bg["abilityOptions"])))

    granted_skills = set(bg["skillIds"])
    pool = [
        skill
        for skill in class_skill_pool(cls, list(catalog["skills"]))
        if skill not in granted_skills
    ]
    proficient = sorted(rng.sample(pool, cls["skillChoices"]["count"]))

    picks = expertise_count(cls)
    expertise: list[str] = []
    if picks:
        candidates = sorted(set(proficient) | granted_skills)
        expertise = sorted(rng.sample(candidates, picks))

    fighting_style_id = None
    if cls["fightingStyleAt"] == 1:
        fighting_style_id = rng.choice(sorted(style["id"] for style in cls["fightingStyles"]))

    tool_choice_id = None
    tool_pattern = bg["tool"]["choosableFrom"]
    if tool_pattern is not None:
        matches = sorted(
            equipment_id
            for equipment_id in catalog["equipment"]
            if re.search(tool_pattern, equipment_id)
        )
        tool_choice_id = rng.choice(matches)

    options = spell_options(cls, bg, catalog["spells"])
    spell_ids: list[str] = []
    if options:
        budget = spell_budget(cls, bg)
        cantrips = sorted(spell["id"] for spell in options if spell["level"] == 0)
        prepared = sorted(spell["id"] for spell in options if spell["level"] == 1)
        spell_ids = sorted(
            rng.sample(cantrips, budget["cantrips"]) + rng.sample(prepared, budget["prepared"])
        )

    class_pick = _freeze(rng, cls["startingEquipment"])
    background_pick = _freeze(rng, bg["startingEquipment"])

    completed = list(CREATION_STEPS)
    if options:
        completed.append(SPELL_STEP)

    record = CharacterRecord.model_validate(
        {
            "id": character_id,
            "name": f"Random {race['name']} {cls['name']}",
            "level": 1,
            "raceId": race["id"],
            "sizeChoice": rng.choice(sorted(race["sizes"])),
            "classId": cls["id"],
            "fightingStyleId": fighting_style_id,
            "toolChoiceId": tool_choice_id,
            "backgroundId": bg["id"],
            "equipmentChoice": {"class": class_pick, "background": background_pick},
            "purchasedItemIds": [],
            "walletCp": _gold(class_pick) + _gold(background_pick),
            "abilities": {
                "method": "pointbuy",
                "base": base,
                "rolled": [],
                "originBonuses": bonuses,
            },
            "proficientSkillIds": proficient,
            "expertiseIds": expertise,
            "spellIds": spell_ids,
            "featIds": sorted(bg["featIds"]),
            "classFeatChoices": [],
            "completedSteps": completed,
        }
    )

    validate_complete_pointbuy_character(record, catalog)
    return record


def _freeze(rng: random.Random, offered: list[dict[str, Any]]) -> dict[str, Any] | None:
    """A deep copy of a uniformly chosen alternative, so the catalog stays untouched."""
    return copy.deepcopy(rng.choice(offered)) if offered else None


def _gold(pick: dict[str, Any] | None) -> int:
    return pick["goldCp"] if pick else 0
