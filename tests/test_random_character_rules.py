"""US-39 unit proof: normalization, uniform sampling, and complete-sheet validation.

Offline by design: the shared fixture supplies the reference envelopes, so the rules are
pinned without Redis or the network. The fixture is not created by the code under test --
it is committed data, and these tests assert independently computed memberships, counts and
costs on top of calling the validator.
"""

import copy
import itertools
import json
import random

import pytest
from conftest import creation_cases

from forge_backend import random_character_rules as sampler
from forge_backend.character_models import CharacterRecord
from forge_backend.creation_rules import (
    CREATION_STEPS,
    InvalidCreationReference,
    class_skill_pool,
    expertise_count,
    normalize_creation_catalog,
    origin_maps,
    parse_starting_equipment,
    point_buy_cost,
    preflight_catalog,
    resolve_background_spell_classes,
    resolve_grant,
    spell_budget,
    spell_options,
    validate_complete_pointbuy_character,
)

ABILITIES = ("STR", "DEX", "CON", "INT", "WIS", "CHA")
CHARACTER_ID = "0f8c1a7e-3d52-4b91-a7c8-6e2f91b40d35"
MAX_ARRAY = {"STR": 15, "DEX": 15, "CON": 15, "INT": 8, "WIS": 8, "CHA": 8}
MIXED_ARRAY = {"STR": 8, "DEX": 9, "CON": 10, "INT": 11, "WIS": 12, "CHA": 13}


class PinnedRng(random.Random):
    """Seeded entropy with the ability rolls and the first selections pinned.

    ``proposals`` are consumed six values at a time by ``randrange``; ``choice_indices``
    answers successive ``choice`` calls by index into the sequence offered, in the order
    the sampler asks for them. Everything after the pinned answers is seeded randomness.
    """

    def __init__(self, seed=0, *, proposals=(), choice_indices=()):
        super().__init__(seed)
        self._rolls = [value for proposal in proposals for value in proposal.values()]
        self._choice_indices = list(choice_indices)
        self.choice_sequences = []

    def randrange(self, start, stop, step=1):
        if self._rolls:
            return self._rolls.pop(0)
        return super().randrange(start, stop, step)

    def choice(self, seq):
        self.choice_sequences.append(tuple(seq))
        if self._choice_indices:
            return seq[self._choice_indices.pop(0)]
        return super().choice(seq)


@pytest.fixture(scope="module")
def cases():
    return creation_cases()


@pytest.fixture(scope="module")
def references(cases):
    return cases["references"]


@pytest.fixture(scope="module")
def catalog(references):
    return normalize_creation_catalog(references)


@pytest.fixture
def examples(cases):
    return copy.deepcopy(cases["validCharacters"])


def pinned(
    catalog,
    *,
    race="srd-2024_human",
    cls="srd-2024_fighter",
    background="srd-2024_acolyte",
    origin=0,
    proposals=(),
    seed=11,
):
    """A generator call with the species, class, background and origin map all forced."""
    return PinnedRng(
        seed,
        proposals=proposals,
        choice_indices=[
            sorted(catalog["races"]).index(race),
            sorted(catalog["classes"]).index(cls),
            sorted(catalog["backgrounds"]).index(background),
            origin,
        ],
    )


def generate(catalog, rng):
    return sampler.generate_random_character(catalog, rng, character_id=CHARACTER_ID)


def expect_reference_error(references, mutate, match):
    refs = copy.deepcopy(references)
    mutate(refs)
    with pytest.raises(InvalidCreationReference, match=match):
        preflight_catalog(normalize_creation_catalog(refs))


def expect_invalid(catalog, raw, mutate, match):
    record = copy.deepcopy(raw)
    mutate(record)
    character = CharacterRecord.model_validate(record)
    with pytest.raises(ValueError, match=match):
        validate_complete_pointbuy_character(character, catalog)


# --------------------------------------------------------------------------------------
# Uniform sampling
# --------------------------------------------------------------------------------------


@pytest.mark.test_id("ST-48")
class TestSamplePointbuy:
    def test_rejects_only_the_overspent_proposal(self):
        rng = PinnedRng(proposals=[{ability: 15 for ability in ABILITIES}, MIXED_ARRAY])

        assert sampler.sample_pointbuy(rng) == MIXED_ARRAY
        assert point_buy_cost(MIXED_ARRAY) == 15

    def test_accepts_a_bare_minimum_array_at_cost_zero(self):
        minimum = {ability: 8 for ability in ABILITIES}

        assert sampler.sample_pointbuy(PinnedRng(proposals=[minimum])) == minimum
        assert point_buy_cost(minimum) == 0

    def test_keeps_a_maximum_array_exactly(self):
        assert point_buy_cost(MAX_ARRAY) == 27

        assert sampler.sample_pointbuy(PinnedRng(proposals=[MAX_ARRAY])) == MAX_ARRAY

    def test_a_hundred_plus_draws_stay_legal_and_vary(self):
        arrays = [sampler.sample_pointbuy(random.Random(seed)) for seed in range(120)]

        assert len({tuple(sorted(array.values())) for array in arrays}) > 5
        for array in arrays:
            assert set(array) == set(ABILITIES)
            assert all(8 <= score <= 15 for score in array.values())
            assert point_buy_cost(array) <= 27


@pytest.mark.test_id("ST-48")
class TestOriginMaps:
    def test_three_abilities_make_six_pairs_and_one_triple(self):
        maps = origin_maps(("INT", "WIS", "CHA"))
        pairs = [m for m in maps if sorted(m.values()) == [1, 2]]
        triples = [m for m in maps if sorted(m.values()) == [1, 1, 1]]

        assert len(maps) == 7
        assert len(pairs) == 6
        assert len(triples) == 1
        assert [
            (next(a for a, v in m.items() if v == 2), next(a for a, v in m.items() if v == 1))
            for m in pairs
        ] == list(itertools.permutations(("INT", "WIS", "CHA"), 2))
        assert list(triples[0]) == ["INT", "WIS", "CHA"]

    def test_every_map_is_reachable_by_its_index(self, catalog):
        minimum = {ability: 8 for ability in ABILITIES}

        for index in range(7):
            rng = PinnedRng(seed=3, proposals=[minimum], choice_indices=[0, 0, 0, index])
            record = generate(catalog, rng)

            background = catalog["backgrounds"][record.backgroundId]
            assert (
                record.abilities.originBonuses
                == origin_maps(list(background["abilityOptions"]))[index]
            )


# --------------------------------------------------------------------------------------
# Generation
# --------------------------------------------------------------------------------------


@pytest.mark.test_id("ST-48")
class TestGeneration:
    def test_a_pinned_run_is_fully_determined(self, catalog):
        rng = pinned(
            catalog,
            race="srd-2024_dwarf",
            cls="srd-2024_fighter",
            background="srd-2024_soldier",
            origin=0,
            proposals=[MAX_ARRAY],
        )

        record = generate(catalog, rng)

        assert record.raceId == "srd-2024_dwarf"
        assert record.classId == "srd-2024_fighter"
        assert record.backgroundId == "srd-2024_soldier"
        assert record.abilities.base == MAX_ARRAY
        assert record.abilities.method == "pointbuy"
        assert record.abilities.rolled == []
        assert record.level == 1
        assert record.id == CHARACTER_ID
        assert record.name == "Random Dwarf Fighter"
        assert record.sizeChoice == "Medium"  # the dwarf's only size
        assert record.fightingStyleId in {
            style["id"] for style in catalog["classes"]["srd-2024_fighter"]["fightingStyles"]
        }
        assert record.toolChoiceId in catalog["equipment"]
        assert record.purchasedItemIds == []
        assert record.featIds == ["srd-2024_savage-attacker"]
        assert record.classFeatChoices == []
        assert record.spellIds == []
        assert record.completedSteps == list(CREATION_STEPS)

    def test_the_same_seed_produces_the_same_character(self, catalog):
        first = generate(catalog, pinned(catalog, proposals=[MIXED_ARRAY], seed=5))
        second = generate(catalog, pinned(catalog, proposals=[MIXED_ARRAY], seed=5))

        assert first.model_dump() == second.model_dump()

    def test_scores_are_never_reassigned_across_classes(self, catalog):
        classes_seen = set()

        for seed in range(60):
            rng = PinnedRng(seed=seed, proposals=[MIXED_ARRAY])
            record = generate(catalog, rng)

            assert record.abilities.base == MIXED_ARRAY
            classes_seen.add(record.classId)

        assert len(classes_seen) > 1

    def test_both_size_choices_are_reachable(self, catalog):
        sizes = set()

        for seed in range(40):
            record = generate(catalog, PinnedRng(seed=seed, proposals=[MAX_ARRAY]))
            if record.raceId == "srd-2024_human":
                sizes.add(record.sizeChoice)

        assert sizes == {"Medium", "Small"}

    def test_a_finishable_candidate_set_is_required_before_sampling(self, references):
        refs = copy.deepcopy(references)
        refs["spell"] = []
        catalog = normalize_creation_catalog(refs)

        with pytest.raises(InvalidCreationReference, match="needs 3 cantrips"):
            generate(catalog, PinnedRng(proposals=[MAX_ARRAY]))

    def test_generation_does_not_mutate_the_catalog(self, catalog):
        before = json.dumps(catalog, sort_keys=True)
        record = generate(catalog, pinned(catalog, cls="srd-2024_fighter", proposals=[MAX_ARRAY]))

        assert json.dumps(catalog, sort_keys=True) == before
        # The frozen pick is a copy: editing it cannot reach back into the catalog.
        assert record.equipmentChoice.class_ is not None
        record.equipmentChoice.class_.goldCp = 0
        record.equipmentChoice.class_.grants.clear()
        assert json.dumps(catalog, sort_keys=True) == before

    def test_a_non_caster_without_a_spell_source_skips_the_spells_step(self, catalog):
        rng = pinned(
            catalog, cls="srd-2024_rogue", background="srd-2024_soldier", proposals=[MAX_ARRAY]
        )

        record = generate(catalog, rng)

        assert (
            spell_options(
                catalog["classes"]["srd-2024_rogue"],
                catalog["backgrounds"]["srd-2024_soldier"],
                catalog["spells"],
            )
            == []
        )
        assert record.spellIds == []
        assert "spells" not in record.completedSteps
        assert record.expertiseIds != [] and len(record.expertiseIds) == 2


@pytest.mark.test_id("ST-48")
class TestSpellBudgets:
    @pytest.mark.parametrize(
        ("class_id", "cantrips", "prepared"),
        [
            ("srd-2024_paladin", 0, 2),
            ("srd-2024_ranger", 0, 2),
            ("srd-2024_warlock", 2, 2),
            ("srd-2024_wizard", 1, 1),
        ],
    )
    def test_class_budgets_match_the_seeded_table(self, catalog, class_id, cantrips, prepared):
        assert catalog["classes"][class_id]["spellCounts"] == {
            "cantrips": cantrips,
            "prepared": prepared,
        }

        record = generate(
            catalog,
            pinned(catalog, cls=class_id, background="srd-2024_soldier", proposals=[MAX_ARRAY]),
        )
        levels = [catalog["spells"][spell_id]["level"] for spell_id in record.spellIds]

        assert levels.count(0) == cantrips
        assert levels.count(1) == prepared

    def test_background_initiate_extends_the_budget_by_two_and_one(self, catalog):
        wizard = catalog["classes"]["srd-2024_wizard"]
        acolyte = catalog["backgrounds"]["srd-2024_acolyte"]

        assert spell_budget(wizard, acolyte) == {"cantrips": 3, "prepared": 2}
        assert spell_budget(wizard, catalog["backgrounds"]["srd-2024_soldier"]) == {
            "cantrips": 1,
            "prepared": 1,
        }

        options = spell_options(wizard, acolyte, catalog["spells"])
        cantrips = [spell["id"] for spell in options if spell["level"] == 0]

        # Wizard and Cleric share one cantrip; the combined pool must not double count it.
        assert cantrips.count("srd-2024_light") == 1
        assert len(cantrips) == 5

        record = generate(catalog, pinned(catalog, cls="srd-2024_wizard", proposals=[MAX_ARRAY]))
        levels = [catalog["spells"][spell_id]["level"] for spell_id in record.spellIds]

        assert levels.count(0) == 3
        assert levels.count(1) == 2
        assert record.completedSteps[-1] == "spells"


# --------------------------------------------------------------------------------------
# Normalization of the seeded contract
# --------------------------------------------------------------------------------------


@pytest.mark.test_id("ST-48")
class TestNormalization:
    def test_subclasses_and_missing_metadata_are_not_candidates(self, catalog, references):
        assert "srd-2024_champion" not in catalog["classes"]
        assert {record["key"] for record in references["class"]} >= {"srd-2024_champion"}

        refs = copy.deepcopy(references)
        for record in refs["class"]:
            record.setdefault("creationRules", None)
            if record["key"] == "srd-2024_fighter":
                del record["creationRules"]
        with pytest.raises(InvalidCreationReference, match="no usable creationRules"):
            normalize_creation_catalog(refs)

    def test_only_top_level_species_are_offered(self, references):
        refs = copy.deepcopy(references)
        refs["race"][0]["data"]["subspecies_of"] = {"key": "srd-2024_human", "name": "Human"}

        catalog = normalize_creation_catalog(refs)

        assert set(catalog["races"]) == {"srd-2024_dwarf"}

    def test_size_words_come_from_the_size_trait(self, catalog):
        assert catalog["races"]["srd-2024_human"]["sizes"] == ["Medium", "Small"]
        assert catalog["races"]["srd-2024_dwarf"]["sizes"] == ["Medium"]

    def test_class_metadata_matches_the_seeded_tables(self, catalog):
        fighter = catalog["classes"]["srd-2024_fighter"]

        assert fighter["skillChoices"] == {
            "count": 2,
            "from": [
                "acrobatics",
                "athletics",
                "history",
                "insight",
                "intimidation",
                "perception",
                "survival",
            ],
        }
        assert [style["id"] for style in fighter["fightingStyles"]] == [
            "archery",
            "defense",
            "dueling",
            "great-weapon-fighting",
            "protection",
            "two-weapon-fighting",
        ]
        assert fighter["fightingStyleAt"] == 1
        assert fighter["expertiseAt"] is None
        assert catalog["classes"]["srd-2024_rogue"]["expertiseAt"] == 1
        assert catalog["classes"]["srd-2024_ranger"]["expertiseAt"] == 9
        assert expertise_count(catalog["classes"]["srd-2024_ranger"]) == 0
        assert catalog["classes"]["srd-2024_paladin"]["fightingStyleAt"] == 2
        assert catalog["classes"]["srd-2024_paladin"]["fightingStyles"] == []

    def test_a_caster_without_a_prepared_spells_row_is_a_reference_defect(self, references):
        refs = copy.deepcopy(references)
        for record in refs["class"]:
            if record["key"] == "srd-2024_wizard":
                record["data"]["features"] = [
                    feature
                    for feature in record["data"]["features"]
                    if feature["name"] != "Prepared Spells"
                ]

        with pytest.raises(InvalidCreationReference, match="no level-one Prepared Spells row"):
            normalize_creation_catalog(refs)

    def test_background_names_resolve_against_loaded_records(self, catalog, references):
        acolyte = catalog["backgrounds"]["srd-2024_acolyte"]

        assert acolyte["skillIds"] == ["insight", "religion"]
        assert acolyte["abilityOptions"] == ["INT", "WIS", "CHA"]
        assert acolyte["initiateClassIds"] == ["srd-2024_cleric"]
        assert acolyte["featIds"] == ["srd-2024_magic-initiate"]
        assert acolyte["tool"] == {
            "text": "Calligrapher's Supplies",
            "quantity": 1,
            "itemId": "srd-2024_calligraphers-supplies",
            "choosableFrom": None,
        }
        assert catalog["backgrounds"]["srd-2024_soldier"]["featIds"] == ["srd-2024_savage-attacker"]

        # The same resolver, run against the raw records, matches by name rather than by
        # turning "Cleric" into an ID by string surgery.
        record = next(r for r in references["background"] if r["key"] == "srd-2024_acolyte")
        assert resolve_background_spell_classes(
            record, [{"key": "test_cleric", "name": "Cleric"}]
        ) == {"test_cleric"}
        assert (
            resolve_background_spell_classes(record, [{"key": "test_x", "name": "Monk"}]) == set()
        )

    def test_equipment_alternatives_keep_the_clients_readings(self, catalog):
        fighter = {
            option["key"]: option
            for option in catalog["classes"]["srd-2024_fighter"]["startingEquipment"]
        }

        assert set(fighter) == {"A", "B", "C"}
        assert fighter["C"] == {"key": "C", "label": "155 GP", "grants": [], "goldCp": 15500}
        # "20 Arrows" is one bundle of Arrows (20); "8 Javelins" is eight separate items.
        arrows = {grant["text"]: grant for grant in fighter["B"]["grants"]}["20 Arrows"]
        assert (arrows["quantity"], arrows["itemId"]) == (1, "srd-2024_arrows-20")
        javelins = {grant["text"]: grant for grant in fighter["A"]["grants"]}["8 Javelins"]
        assert (javelins["quantity"], javelins["itemId"]) == (8, "srd-2024_javelin")

        soldier = catalog["backgrounds"]["srd-2024_soldier"]["startingEquipment"][0]
        gaming_set = next(grant for grant in soldier["grants"] if "Gaming Set" in grant["text"])
        assert gaming_set == {
            "text": "Gaming Set (same as above)",
            "quantity": 1,
            "itemId": None,
            "choosableFrom": "^srd-2024_gaming-set-",
        }

        acolyte = catalog["backgrounds"]["srd-2024_acolyte"]["startingEquipment"][0]
        book = next(grant for grant in acolyte["grants"] if grant["text"].startswith("Book"))
        # An item the seed does not carry stays as its own text rather than becoming an item.
        assert book == {
            "text": "Book (prayers)",
            "quantity": 1,
            "itemId": None,
            "choosableFrom": None,
        }

    def test_unparseable_equipment_prose_is_a_reference_defect(self):
        with pytest.raises(InvalidCreationReference, match="unparseable starting equipment"):
            parse_starting_equipment("Choose A or B: nothing here", [])

        assert parse_starting_equipment("", []) == []
        assert resolve_grant("Choose one kind of Musical Instrument", []) == {
            "text": "Choose one kind of Musical Instrument",
            "quantity": 1,
            "itemId": None,
            "choosableFrom": "^srd-2024_musical-instrument-",
        }


# --------------------------------------------------------------------------------------
# Preflight: seed defects
# --------------------------------------------------------------------------------------


@pytest.mark.test_id("ST-48")
class TestPreflight:
    def test_an_empty_optional_pool_is_fine_when_nothing_needs_it(self, references):
        refs = copy.deepcopy(references)
        refs["class"] = [
            r for r in refs["class"] if r["key"] in {"srd-2024_fighter", "srd-2024_rogue"}
        ]
        refs["background"] = [r for r in refs["background"] if r["key"] == "srd-2024_soldier"]
        refs["spell"] = []
        refs["feat"] = [r for r in refs["feat"] if r["name"] == "Savage Attacker"]

        catalog = normalize_creation_catalog(refs)
        preflight_catalog(catalog)
        record = generate(catalog, PinnedRng(seed=1, proposals=[MAX_ARRAY]))

        assert record.spellIds == []

    def test_missing_reference_types_are_seed_defects(self, references):
        for ref_type, match in (
            ("equipment", "no equipment are seeded"),
            ("race", "no races are seeded"),
            ("class", "no classes are seeded"),
            ("background", "no backgrounds are seeded"),
            ("skill", "no skills are seeded"),
        ):
            refs = copy.deepcopy(references)
            refs[ref_type] = []
            if ref_type == "class":
                # A background's initiate class is resolved by name, so the Magic Initiate
                # background has to go too or normalization fails first for a different
                # (also correct) reason.
                refs["background"] = [
                    record for record in refs["background"] if record["key"] != "srd-2024_acolyte"
                ]
            expect_reference_error(refs, lambda _: None, match)

    def test_missing_feat_records_are_a_seed_defect(self, references):
        expect_reference_error(
            references, lambda refs: refs.__setitem__("feat", []), "feats that are not seeded"
        )

    def test_an_unresolvable_initiate_class_is_a_seed_defect(self, references):
        expect_reference_error(
            references,
            lambda refs: refs.__setitem__(
                "class",
                [r for r in refs["class"] if r["key"] != "srd-2024_cleric"],
            ),
            "no such class is seeded",
        )

    def test_a_seeded_skill_the_class_offers_but_does_not_have_is_a_defect(self, references):
        def mutate(refs):
            for record in refs["class"]:
                if record["key"] == "srd-2024_fighter":
                    record["creationRules"]["skillChoices"] = {
                        "count": 2,
                        "from": ["acrobatics", "bogus-skill"],
                    }

        expect_reference_error(references, mutate, "offers unseeded skills")

    def test_a_level_one_style_without_options_is_a_defect(self, references):
        def mutate(refs):
            for record in refs["class"]:
                if record["key"] == "srd-2024_fighter":
                    record["creationRules"]["fightingStyles"] = []

        expect_reference_error(references, mutate, "gains a Fighting Style at level 1")

    def test_a_background_without_three_ability_options_is_a_defect(self, references):
        def mutate(refs):
            for record in refs["background"]:
                if record["key"] == "srd-2024_soldier":
                    record["data"]["benefits"] = [
                        benefit
                        for benefit in record["data"]["benefits"]
                        if benefit["type"] != "ability_score"
                    ] + [{"type": "ability_score", "desc": "Strength, Dexterity"}]

        expect_reference_error(references, mutate, "fewer than three ability options")

    def test_a_tool_category_with_no_item_is_a_defect(self, references):
        def mutate(refs):
            refs["equipment"] = [
                record for record in refs["equipment"] if "gaming-set" not in record["key"]
            ]

        expect_reference_error(references, mutate, "needs an item matching")

    def test_a_search_space_too_small_for_the_skill_count_is_a_defect(self, references):
        def mutate(refs):
            for record in refs["class"]:
                if record["key"] == "srd-2024_wizard":
                    record["creationRules"]["skillChoices"] = {
                        "count": 2,
                        "from": ["insight", "religion"],
                    }

        # Acolyte grants both of the wizard's two offered skills.
        expect_reference_error(references, mutate, "offers 0 of 2 required skills")

    def test_too_few_spells_for_a_background_budget_is_a_defect(self, references):
        def mutate(refs):
            refs["spell"] = [
                record
                for record in refs["spell"]
                if "srd-2024_cleric" not in [entry["key"] for entry in record["data"]["classes"]]
            ]

        expect_reference_error(references, mutate, "cantrips")


# --------------------------------------------------------------------------------------
# Validation of finished sheets
# --------------------------------------------------------------------------------------


@pytest.mark.test_id("ST-48")
class TestCompleteValidation:
    @pytest.mark.parametrize(
        "key", ["fighter_soldier", "rogue_acolyte", "wizard_acolyte", "fighter_acolyte"]
    )
    def test_the_fixtures_finished_characters_are_accepted(self, catalog, examples, key):
        character = CharacterRecord.model_validate(examples[key])

        assert validate_complete_pointbuy_character(character, catalog) is None

    def test_the_fixtures_characters_carry_independently_checked_selections(
        self, catalog, examples
    ):
        fighter = examples["fighter_soldier"]
        assert point_buy_cost(fighter["abilities"]["base"]) == 27
        assert fighter["abilities"]["originBonuses"] == {"STR": 2, "CON": 1}
        assert fighter["walletCp"] == 400 + 1400  # Fighter A (4 GP) + Soldier A (14 GP)
        assert fighter["proficientSkillIds"] == ["perception", "survival"]
        assert fighter["toolChoiceId"] == "srd-2024_gaming-set-dice"
        # Acolyte overlaps the Fighter's own pool (Insight) while also granting Religion,
        # which the Fighter could never pick for itself.
        acolyte_granted = set(catalog["backgrounds"]["srd-2024_acolyte"]["skillIds"])
        fighter_pool = set(
            class_skill_pool(catalog["classes"]["srd-2024_fighter"], list(catalog["skills"]))
        )
        assert acolyte_granted & fighter_pool == {"insight"}
        assert acolyte_granted - fighter_pool == {"religion"}

        rogue = examples["rogue_acolyte"]
        assert len(rogue["expertiseIds"]) == 2
        assert "religion" in rogue["expertiseIds"]  # a background grant, not a class pick
        assert set(rogue["expertiseIds"]) <= set(rogue["proficientSkillIds"]) | acolyte_granted

        wizard = examples["wizard_acolyte"]
        levels = [catalog["spells"][spell_id]["level"] for spell_id in wizard["spellIds"]]
        assert levels.count(0) == 3 and levels.count(1) == 2

        gold_only = examples["fighter_acolyte"]
        assert gold_only["equipmentChoice"]["class"]["grants"] == []
        assert gold_only["equipmentChoice"]["class"]["goldCp"] == 15500
        assert gold_only["walletCp"] == 15500 + 5000

    def test_an_unknown_reference_id_is_a_record_defect(self, catalog, examples):
        expect_invalid(
            catalog,
            examples["fighter_soldier"],
            lambda raw: raw.__setitem__("raceId", "srd-2024_nobody"),
            "unknown raceId",
        )

    @pytest.mark.parametrize(
        ("mutate", "match"),
        [
            (lambda raw: raw["abilities"]["base"].__setitem__("STR", 16), "must be 8-15"),
            (lambda raw: raw["abilities"]["base"].__setitem__("STR", 7), "must be 8-15"),
            (
                lambda raw: raw["abilities"].__setitem__(
                    "base", {"STR": 15, "DEX": 15, "CON": 15, "INT": 14, "WIS": 8, "CHA": 8}
                ),
                "point-buy cost exceeds 27",
            ),
            (
                lambda raw: raw["abilities"].__setitem__("originBonuses", {"WIS": 2, "CON": 1}),
                "not offered by the selected background",
            ),
            (
                lambda raw: raw["abilities"].__setitem__("originBonuses", {"STR": 2, "CON": 2}),
                "must be \\+2/\\+1 or \\+1/\\+1/\\+1",
            ),
            (
                lambda raw: raw["abilities"].__setitem__("originBonuses", {"STR": 3}),
                "must be \\+2/\\+1 or \\+1/\\+1/\\+1",
            ),
            (
                lambda raw: raw["abilities"].__setitem__("method", "standard"),
                "must be 'pointbuy'",
            ),
            (
                lambda raw: raw.update({"sizeChoice": "Small", "raceId": "srd-2024_dwarf"}),
                "not allowed for the selected race",
            ),
            (lambda raw: raw.__setitem__("fightingStyleId", None), "requires a fighting style"),
            (lambda raw: raw.__setitem__("fightingStyleId", "bogus"), "not offered"),
            (
                lambda raw: raw.__setitem__("proficientSkillIds", ["perception"]),
                "choose exactly 2 class skills",
            ),
            (
                lambda raw: raw.__setitem__("proficientSkillIds", ["perception", "perception"]),
                "must be unique",
            ),
            (
                lambda raw: raw.__setitem__("proficientSkillIds", ["perception", "athletics"]),
                "not offered by the selected class and background",
            ),
            (
                lambda raw: raw.__setitem__("proficientSkillIds", ["perception", "arcana"]),
                "not offered by the selected class and background",
            ),
            (lambda raw: raw.__setitem__("expertiseIds", ["perception"]), "exactly 0 skill"),
            (lambda raw: raw.__setitem__("toolChoiceId", None), "requires a tool choice"),
            (
                lambda raw: raw.__setitem__("toolChoiceId", "srd-2024_rope"),
                "not in the background's tool category",
            ),
            (
                lambda raw: raw.__setitem__(
                    "equipmentChoice",
                    {"class": None, "background": raw["equipmentChoice"]["background"]},
                ),
                "must be chosen for the class",
            ),
            (
                lambda raw: raw["equipmentChoice"]["class"].__setitem__("goldCp", 1),
                "does not match the offered alternative",
            ),
            (
                lambda raw: raw["equipmentChoice"]["class"]["grants"].append(
                    {
                        "text": "Rope",
                        "quantity": 1,
                        "itemId": "srd-2024_rope",
                        "choosableFrom": None,
                    }
                ),
                "does not match the offered alternative",
            ),
            (lambda raw: raw.__setitem__("walletCp", -1), "must not be negative"),
            (
                lambda raw: raw.__setitem__("purchasedItemIds", ["srd-2024_nothing"]),
                "unknown equipmentIds",
            ),
            (
                lambda raw: raw.__setitem__("featIds", []),
                "must hold the background's automatic feats",
            ),
            (
                lambda raw: raw.__setitem__(
                    "completedSteps",
                    [step for step in raw["completedSteps"] if step != "skills"],
                ),
                "missing completion markers: \\['skills'\\]",
            ),
        ],
    )
    def test_a_tampered_finished_fighter_is_rejected(self, catalog, examples, mutate, match):
        expect_invalid(catalog, examples["fighter_soldier"], mutate, match)

    @pytest.mark.parametrize(
        ("mutate", "match"),
        [
            (lambda raw: raw.__setitem__("spellIds", []), "must hold 2 cantrip"),
            (
                lambda raw: raw.__setitem__("spellIds", ["srd-2024_sacred-flame"]),
                "must hold 2 cantrip",
            ),
            (
                lambda raw: raw.__setitem__(
                    "spellIds",
                    ["srd-2024_sacred-flame", "srd-2024_guidance", "srd-2024_sacred-flame"],
                ),
                "must be unique",
            ),
            (
                lambda raw: raw.__setitem__(
                    "spellIds",
                    ["srd-2024_sacred-flame", "srd-2024_guidance", "srd-2024_mage-armor"],
                ),
                "not available at level 1",
            ),
            (
                lambda raw: raw.__setitem__(
                    "spellIds",
                    ["srd-2024_sacred-flame", "srd-2024_guidance", "srd-2024_fireball"],
                ),
                "unknown spellIds",
            ),
            (
                lambda raw: raw.__setitem__(
                    "spellIds", ["srd-2024_sacred-flame", "srd-2024_guidance"]
                ),
                "must hold 2 cantrip",
            ),
            (
                lambda raw: raw.__setitem__(
                    "completedSteps",
                    [step for step in raw["completedSteps"] if step != "spells"],
                ),
                "missing completion markers: \\['spells'\\]",
            ),
        ],
    )
    def test_a_tampered_caster_is_rejected(self, catalog, examples, mutate, match):
        expect_invalid(catalog, examples["fighter_acolyte"], mutate, match)

    def test_a_level_one_rogue_owes_exactly_two_expertise_picks(self, catalog, examples):
        expect_invalid(
            catalog,
            examples["rogue_acolyte"],
            lambda raw: raw.__setitem__("expertiseIds", ["athletics"]),
            "exactly 2 skill",
        )
        expect_invalid(
            catalog,
            examples["rogue_acolyte"],
            lambda raw: raw.__setitem__("expertiseIds", ["perception", "stealth"]),
            "must come from proficient or background skills",
        )

    def test_a_non_caster_without_a_spell_source_must_not_list_spells(self, catalog, examples):
        expect_invalid(
            catalog,
            examples["fighter_soldier"],
            lambda raw: raw.__setitem__("spellIds", ["srd-2024_sacred-flame"]),
            "grant no spells at level 1",
        )
