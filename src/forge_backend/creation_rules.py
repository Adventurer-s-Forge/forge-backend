"""Creator rules for a level-one point-buy character (US-39).

Pure: this module reads no datastore, no clock and no network. A caller loads the seeded
reference envelopes and passes them in; everything here is a transformation or a check.

Three jobs, in the order they are used:

* :func:`normalize_creation_catalog` turns raw seed envelopes into the decision data the
  creator draws from (skill pools, spell budgets, equipment alternatives). It follows the
  client's normalizers, so one contract serves both sides.
* :func:`preflight_catalog` proves the catalog can produce *some* legal character, so an
  incomplete seed fails loudly instead of silently biasing a random draw.
* :func:`validate_complete_pointbuy_character` re-checks a finished sheet against the same
  rules, for the save path that has to accept what generation produced.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Mapping, Sequence
from typing import Any, TypedDict

from forge_backend.character_models import AbilityKey, CharacterRecord
from forge_backend.spell_rules import validate_spell_class_eligibility

ABILITIES: tuple[AbilityKey, ...] = ("STR", "DEX", "CON", "INT", "WIS", "CHA")

POINT_BUY_COST: dict[int, int] = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
POINT_BUY_MIN = 8
POINT_BUY_MAX = 15
POINT_BUY_BUDGET = 27
ABILITY_CAP = 20
EXPERTISE_PICKS = 2
MAX_SPELL_LEVEL_AT_1 = 1

# The steps a generated character completes, in canonical order. ``spells`` is appended
# only when the combined level-0/1 pool is nonempty.
CREATION_STEPS: tuple[str, ...] = (
    "name",
    "race",
    "class",
    "background",
    "equipment",
    "attributes",
    "skills",
)
SPELL_STEP = "spells"


class InvalidCreationReference(ValueError):
    """Seeded reference content cannot support creation: something is missing or malformed.

    Distinct from a rejected *character* (a plain ``ValueError``): this one means the seed
    is at fault, and the API answers 503 rather than 400.
    """


class CreationCatalog(TypedDict):
    """Normalized reference rows, keyed by reference ID, for the creator's decisions."""

    races: dict[str, dict[str, Any]]
    classes: dict[str, dict[str, Any]]
    backgrounds: dict[str, dict[str, Any]]
    skills: dict[str, dict[str, Any]]
    spells: dict[str, dict[str, Any]]
    equipment: dict[str, dict[str, Any]]
    feats: dict[str, dict[str, Any]]


ABILITY_BY_NAME: dict[str, AbilityKey] = {
    "strength": "STR",
    "dexterity": "DEX",
    "constitution": "CON",
    "intelligence": "INT",
    "wisdom": "WIS",
    "charisma": "CHA",
}

# A background tool described as a category resolves to an item-ID prefix, the way the
# client's `CAT_IDS` does. Order matters: the first match wins.
CATEGORY_PATTERNS: dict[str, str] = {
    "holysymbol": "^srd-2024_holy-symbol-",
    "druidicfocus": "^srd-2024_druidic-focus-",
    "musicalinstrument": "^srd-2024_musical-instrument-",
    "gamingset": "^srd-2024_gaming-set-",
}

_STRIP_PARENS = re.compile(r"\([^/)]*\)")
_NON_ALNUM = re.compile(r"[^a-z0-9]")
_TOKENS = re.compile(r"[a-z0-9]+")
_QUANTITY = re.compile(r"^(\d+)\s")
_LEADING_QUANTITY = re.compile(r"^\s*\d+\s*")
_BUNDLE = re.compile(r"\((\d+)\)")
_GP_IN_TEXT = re.compile(r"(\d+)\s*GP", re.IGNORECASE)
_GOLD_ONLY = re.compile(r"^\d+\s*GP$", re.IGNORECASE)
_ALTERNATIVE = re.compile(r"\(([A-Z])\)\s*([^;]*)")
_CHOOSE_HEAD = re.compile(r"^\**Choose[^:]*\**", re.IGNORECASE)
_LEADING_OR = re.compile(r"^or\s+", re.IGNORECASE)
_AND = re.compile(r"\band\b", re.IGNORECASE)
_TRAILING_PUNCT = re.compile(r"[.,;]$")
_SIZE_WORD = re.compile(r"\b(Small|Medium)\b")
_SKILL_SPLIT = re.compile(r",|\s+and\s+")
_MAGIC_INITIATE = re.compile(r"^Magic Initiate \(([^)]+)\)")
_BASE_CLASS_MISSING = object()


def point_buy_cost(base: Mapping[str, int]) -> int:
    """Point-buy cost of an assignment, or a value above the budget when out of range."""
    spent = 0
    for ability in ABILITIES:
        cost = POINT_BUY_COST.get(base.get(ability))  # type: ignore[arg-type]
        if cost is None:
            return POINT_BUY_BUDGET + 1
        spent += cost
    return spent


def origin_maps(abilities: Sequence[AbilityKey]) -> list[dict[AbilityKey, int]]:
    """Every legal origin allocation over the background's abilities.

    Six ordered ``+2/+1`` maps then each ``+1/+1/+1`` triple, so a uniform draw over this
    list is uniform over maps rather than over the two spread families.
    """
    maps: list[dict[AbilityKey, int]] = [
        {high: 2, low: 1} for high, low in itertools.permutations(abilities, 2)
    ]
    maps.extend({a: 1, b: 1, c: 1} for a, b, c in itertools.combinations(abilities, 3))
    return maps


def class_skill_pool(cls: Mapping[str, Any], all_skill_ids: Sequence[str]) -> list[str]:
    """Skill IDs the class may grant, before the background's own grants are removed."""
    source = cls["skillChoices"]["from"]
    return sorted(all_skill_ids) if source == "any" else list(source)


def expertise_count(cls: Mapping[str, Any]) -> int:
    """Expertise picks a level-one character of this class owes (two, or none)."""
    at = cls["expertiseAt"]
    return EXPERTISE_PICKS if isinstance(at, int) and at <= 1 else 0


def spell_lists(cls: Mapping[str, Any], bg: Mapping[str, Any]) -> list[str]:
    """Class spell lists a character reaches: its own (casters only) plus initiates'."""
    lists = [cls["id"]] if cls["casterType"] != "NONE" else []
    for class_id in bg["initiateClassIds"]:
        if class_id not in lists:
            lists.append(class_id)
    return lists


def spell_budget(cls: Mapping[str, Any], bg: Mapping[str, Any]) -> dict[str, int]:
    """Cantrip/prepared counts at level 1, including two cantrips and one spell per initiate."""
    own = cls["spellCounts"] if cls["casterType"] != "NONE" else {"cantrips": 0, "prepared": 0}
    initiates = len(bg["initiateClassIds"])
    return {"cantrips": own["cantrips"] + initiates * 2, "prepared": own["prepared"] + initiates}


def spell_options(
    cls: Mapping[str, Any], bg: Mapping[str, Any], spells: Mapping[str, Mapping[str, Any]]
) -> list[Mapping[str, Any]]:
    """Level-0/1 spells whose class list is reachable, in catalog order."""
    lists = spell_lists(cls, bg)
    if not lists:
        return []
    return [
        spell
        for spell in spells.values()
        if spell["level"] <= MAX_SPELL_LEVEL_AT_1
        and any(class_id in lists for class_id in spell["classIds"])
    ]


def resolve_background_spell_classes(
    background: Mapping[str, Any], class_records: Sequence[Mapping[str, Any]]
) -> set[str]:
    """Class keys a background's ``Magic Initiate (X)`` benefits open, resolved by name.

    Names are matched against the loaded records rather than turned into IDs by string
    surgery, so a seed with unusual keys still lines up. A name that resolves to no loaded
    class contributes nothing here; the creation catalog rejects that case up front.
    """
    data = background.get("data")
    benefits = data.get("benefits") if isinstance(data, Mapping) else None
    if not isinstance(benefits, list):
        return set()

    by_name = {
        str(record["name"]).strip().casefold(): record["key"]
        for record in class_records
        if isinstance(record.get("name"), str)
    }

    resolved: set[str] = set()
    for benefit in benefits:
        if not isinstance(benefit, Mapping) or benefit.get("type") != "feat":
            continue
        match = _MAGIC_INITIATE.match(str(benefit.get("desc") or "").strip())
        if match is None:
            continue
        class_id = by_name.get(match.group(1).strip().casefold())
        if class_id is not None:
            resolved.add(class_id)
    return resolved


# --------------------------------------------------------------------------------------
# Normalization
# --------------------------------------------------------------------------------------


def _strip_parens(value: str) -> str:
    return _STRIP_PARENS.sub("", value)


def _item_key(value: str) -> str:
    return _NON_ALNUM.sub("", _strip_parens(value).lower())


def _item_tokens(value: str) -> str:
    return " ".join(sorted(_TOKENS.findall(_strip_parens(value).lower())))


def _equipment_rows(references: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[dict[str, str]]:
    return [
        {"id": record["key"], "name": record["name"]}
        for record in references.get("equipment") or []
    ]


def resolve_grant(text: str, equipment: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    """One ``Item`` phrase to a grant, keeping an unrecognized phrase as its own text.

    A phrase whose item is not seeded stays unresolved (text and quantity only) rather
    than inventing an item; a category phrase records the ID pattern it will accept.
    """
    match = _QUANTITY.match(text)
    quantity = int(match.group(1)) if match else 1
    bare = _LEADING_QUANTITY.sub("", text)
    key = _item_key(bare)

    found: Mapping[str, str] | None = None
    for candidate in (key, re.sub(r"es$", "", key), re.sub(r"s$", "", key)):
        found = next((row for row in equipment if _item_key(row["name"]) == candidate), None)
        if found is not None:
            break
    if found is None:
        tokens = _item_tokens(bare)
        found = next((row for row in equipment if _item_tokens(row["name"]) == tokens), None)

    if found is not None:
        bundle = _BUNDLE.search(found["name"])
        bundled = int(bundle.group(1)) if bundle else 0
        return {
            "text": text,
            "quantity": 1 if bundled == quantity else quantity,
            "itemId": found["id"],
            "choosableFrom": None,
        }

    pattern = next((value for name, value in CATEGORY_PATTERNS.items() if name in key), None)
    return {"text": text, "quantity": quantity, "itemId": None, "choosableFrom": pattern}


def parse_starting_equipment(
    text: str, equipment: Sequence[Mapping[str, str]]
) -> list[dict[str, Any]]:
    """``Choose A or B: ...`` prose to frozen alternatives, exactly as the client reads it.

    An empty description means the source offers nothing. A nonempty one that names no
    alternative is a reference defect, not an empty list.
    """
    body = _CHOOSE_HEAD.sub("", text or "").strip()
    if not body:
        return []

    options: list[dict[str, Any]] = []
    for match in _ALTERNATIVE.finditer(body):
        label = _TRAILING_PUNCT.sub("", _LEADING_OR.sub("", match.group(2)).strip())
        gold = _GP_IN_TEXT.search(label)
        grants = []
        for entry in label.split(","):
            entry = _AND.sub("", entry).strip()
            if not entry or _GOLD_ONLY.match(entry):
                continue
            grants.append(resolve_grant(entry, equipment))
        options.append(
            {
                "key": match.group(1),
                "label": label,
                "grants": grants,
                "goldCp": (int(gold.group(1)) * 100) if gold else 0,
            }
        )

    if not options:
        raise InvalidCreationReference(f"unparseable starting equipment: {text!r}")
    return options


def _core_trait_row(features: Sequence[Any], label: str) -> str:
    pattern = re.compile(rf"\|{re.escape(label)}\|([^|]*)\|")
    for feature in features:
        if not isinstance(feature, Mapping):
            continue
        match = pattern.search(feature.get("desc") or "")
        if match:
            return match.group(1).strip()
    return ""


def _feature_level(features: Sequence[Any], name: str) -> int | None:
    levels = [
        entry["level"]
        for feature in features
        if isinstance(feature, Mapping) and feature.get("name") == name
        for entry in (feature.get("gained_at") or [])
        if isinstance(entry, Mapping) and isinstance(entry.get("level"), int)
    ]
    return min(levels) if levels else None


def _class_table_value(features: Sequence[Any], column: str) -> int | None:
    """Level-one value of a class-table column, or ``None`` when the class has no row."""
    for feature in features:
        if not isinstance(feature, Mapping) or feature.get("name") != column:
            continue
        for row in feature.get("data_for_class_table") or []:
            if isinstance(row, Mapping) and row.get("level") == 1:
                try:
                    return int(str(row.get("column_value")))
                except (TypeError, ValueError):
                    return None
        return None
    return None


def _is_base_class(record: Mapping[str, Any]) -> bool:
    data = record.get("data")
    if not isinstance(data, Mapping):
        return False
    return data.get("subclass_of", _BASE_CLASS_MISSING) is None


def _is_top_level_race(record: Mapping[str, Any]) -> bool:
    data = record.get("data")
    if not isinstance(data, Mapping):
        return False
    return not data.get("subspecies_of")


def _skill_choices(record: Mapping[str, Any]) -> dict[str, Any]:
    rules = record.get("creationRules")
    choices = rules.get("skillChoices") if isinstance(rules, Mapping) else None
    count = choices.get("count") if isinstance(choices, Mapping) else None
    source = choices.get("from") if isinstance(choices, Mapping) else None
    pool_ok = source == "any" or (
        isinstance(source, list) and all(isinstance(entry, str) for entry in source)
    )
    if not isinstance(count, int) or isinstance(count, bool) or count < 0 or not pool_ok:
        raise InvalidCreationReference(
            f"class {record.get('key')!r} has no usable creationRules.skillChoices "
            "(refresh the reference seed)"
        )
    return {"count": count, "from": source if source == "any" else list(source)}


def _fighting_styles(record: Mapping[str, Any]) -> list[dict[str, str]]:
    rules = record.get("creationRules")
    styles = rules.get("fightingStyles") if isinstance(rules, Mapping) else None
    if not isinstance(styles, list) or not all(
        isinstance(style, Mapping)
        and all(isinstance(style.get(field), str) for field in ("id", "name", "note"))
        for style in styles
    ):
        raise InvalidCreationReference(
            f"class {record.get('key')!r} has no usable creationRules.fightingStyles "
            "(refresh the reference seed)"
        )
    return [{"id": s["id"], "name": s["name"], "note": s["note"]} for s in styles]


def _normalize_race(record: Mapping[str, Any]) -> dict[str, Any]:
    data = record["data"]
    traits = data.get("traits")
    if not isinstance(traits, list):
        raise InvalidCreationReference(f"race {record.get('key')!r} has no traits")

    size_desc = next(
        (
            trait.get("desc") or ""
            for trait in traits
            if isinstance(trait, Mapping) and trait.get("name") == "Size"
        ),
        "",
    )
    sizes = list(dict.fromkeys(_SIZE_WORD.findall(size_desc))) or ["Medium"]
    return {"id": record["key"], "name": record["name"], "sizes": sizes}


def _abilities_named(text: str) -> list[AbilityKey]:
    return [
        ABILITY_BY_NAME[word.casefold()]
        for word in re.findall(r"[A-Za-z]+", text)
        if word.casefold() in ABILITY_BY_NAME
    ]


def _saving_throws(data: Mapping[str, Any]) -> list[AbilityKey]:
    abilities = _abilities_named(_core_trait_row(data["features"], "Saving Throw Proficiencies"))

    if abilities:
        return abilities

    return [
        ABILITY_BY_NAME[entry["name"].casefold()]
        for entry in (data.get("saving_throws") or [])
        if entry["name"].casefold() in ABILITY_BY_NAME
    ]


def _normalize_class(
    record: Mapping[str, Any], equipment: Sequence[Mapping[str, str]]
) -> dict[str, Any]:
    key = record["key"]
    data = record["data"]
    features = data.get("features")
    if not isinstance(features, list):
        raise InvalidCreationReference(f"class {key!r} has no features")

    caster = data.get("caster_type") or "NONE"
    prepared = _class_table_value(features, "Prepared Spells")
    if caster != "NONE" and prepared is None:
        raise InvalidCreationReference(
            f"class {key!r} casts at level 1 but has no level-one Prepared Spells row"
        )

    return {
        "id": key,
        "name": record["name"],
        "primaryAbilities": _abilities_named(_core_trait_row(features, "Primary Ability")),
        "savingThrows": _saving_throws(data),
        "skillChoices": _skill_choices(record),
        "fightingStyles": _fighting_styles(record),
        "fightingStyleAt": _feature_level(features, "Fighting Style"),
        "expertiseAt": _feature_level(features, "Expertise"),
        "casterType": caster,
        "spellCounts": {
            "cantrips": _class_table_value(features, "Cantrips") or 0,
            "prepared": prepared or 0,
        },
        "startingEquipment": parse_starting_equipment(
            _core_trait_row(features, "Starting Equipment"), equipment
        ),
    }


def _skill_ids_from_names(csv: str, skills_by_name: Mapping[str, str]) -> list[str]:
    return [
        key
        for part in _SKILL_SPLIT.split(csv or "")
        if (key := skills_by_name.get(part.strip().casefold())) is not None
    ]


def _initiate_names(benefits: Sequence[Any]) -> list[str]:
    return [
        name.strip()
        for benefit in benefits
        if isinstance(benefit, Mapping) and benefit.get("type") == "feat"
        if (match := _MAGIC_INITIATE.match(str(benefit.get("desc") or "").strip()))
        for name in [match.group(1)]
    ]


def _benefit_desc(benefits: Sequence[Any], benefit_type: str) -> str:
    for benefit in benefits:
        if isinstance(benefit, Mapping) and benefit.get("type") == benefit_type:
            return str(benefit.get("desc") or "")
    return ""


def _normalize_background(
    record: Mapping[str, Any],
    equipment: Sequence[Mapping[str, str]],
    skills_by_name: Mapping[str, str],
    classes_by_name: Mapping[str, str],
    feats: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    key = record["key"]
    data = record["data"]
    benefits = data.get("benefits")
    if not isinstance(benefits, list):
        raise InvalidCreationReference(f"background {key!r} has no benefits")

    ability_options = [
        ability
        for part in _benefit_desc(benefits, "ability_score").split(",")
        if (ability := ABILITY_BY_NAME.get(part.strip().casefold())) is not None
    ]

    initiate_ids: list[str] = []
    for class_name in _initiate_names(benefits):
        class_id = classes_by_name.get(class_name.casefold())
        if class_id is None:
            raise InvalidCreationReference(
                f"background {key!r} grants Magic Initiate ({class_name}) but no such class is seeded"
            )
        initiate_ids.append(class_id)

    feat_names = [
        str(benefit.get("desc") or "").split("(", 1)[0].strip()
        for benefit in benefits
        if isinstance(benefit, Mapping) and benefit.get("type") == "feat"
    ]
    feat_names = [name for name in feat_names if name]
    seeded_feat_names = {row["name"] for row in feats.values()}
    missing_feat_names = sorted(name for name in feat_names if name not in seeded_feat_names)
    if missing_feat_names:
        raise InvalidCreationReference(
            f"background {key!r} grants feats that are not seeded: {missing_feat_names}"
        )
    feat_ids = [row["id"] for row in feats.values() if row["name"] in feat_names]

    return {
        "id": key,
        "name": record["name"],
        "skillIds": _skill_ids_from_names(
            _benefit_desc(benefits, "skill_proficiency"), skills_by_name
        ),
        "abilityOptions": ability_options,
        "initiateClassIds": initiate_ids,
        "featIds": feat_ids,
        "tool": resolve_grant(_benefit_desc(benefits, "tool_proficiency").strip(), equipment),
        "startingEquipment": parse_starting_equipment(
            _benefit_desc(benefits, "equipment"), equipment
        ),
    }


def _normalize_spell(record: Mapping[str, Any]) -> dict[str, Any]:
    data = record["data"]
    classes = data.get("classes") if isinstance(data, Mapping) else None
    class_ids = (
        [
            entry["key"]
            for entry in classes
            if isinstance(entry, Mapping) and isinstance(entry.get("key"), str)
        ]
        if isinstance(classes, list)
        else []
    )
    level = data.get("level") if isinstance(data, Mapping) else None
    return {
        "id": record["key"],
        "name": record["name"],
        "level": level if isinstance(level, int) and not isinstance(level, bool) else None,
        "classIds": class_ids,
        "envelope": dict(record),
    }


def normalize_creation_catalog(
    references: Mapping[str, Sequence[Mapping[str, Any]]],
) -> CreationCatalog:
    """Normalize the seven seeded reference types into creator decision data.

    A malformed race, base class or background is a reference defect (they are all
    candidates, so nothing is silently dropped). Subclasses and non-top-level species are
    not candidates and are left out.
    """
    equipment = _equipment_rows(references)
    skills = {
        record["key"]: {"id": record["key"], "name": record["name"]}
        for record in references.get("skill") or []
    }
    feats = {
        record["key"]: {"id": record["key"], "name": record["name"]}
        for record in references.get("feat") or []
    }
    spells = {record["key"]: _normalize_spell(record) for record in references.get("spell") or []}

    races = {
        record["key"]: _normalize_race(record)
        for record in references.get("race") or []
        if _is_top_level_race(record)
    }
    base_classes = [record for record in references.get("class") or [] if _is_base_class(record)]
    classes = {record["key"]: _normalize_class(record, equipment) for record in base_classes}

    classes_by_name = {
        str(record["name"]).strip().casefold(): record["key"] for record in base_classes
    }
    skills_by_name = {str(row["name"]).strip().casefold(): key for key, row in skills.items()}
    backgrounds = {
        record["key"]: _normalize_background(
            record, equipment, skills_by_name, classes_by_name, feats
        )
        for record in references.get("background") or []
    }

    return CreationCatalog(
        races=races,
        classes=classes,
        backgrounds=backgrounds,
        skills=skills,
        spells=spells,
        equipment={row["id"]: dict(row) for row in equipment},
        feats=feats,
    )


# --------------------------------------------------------------------------------------
# Preflight: can this catalog produce a legal character at all?
# --------------------------------------------------------------------------------------


def preflight_catalog(catalog: CreationCatalog) -> None:
    """Raise ``InvalidCreationReference`` unless every candidate can be finished legally.

    Every base class, background and species is a candidate, so an unusable one is a seed
    defect: dropping it or rerolling to another would bias the draw.
    """
    for ref_type in ("races", "classes", "backgrounds", "skills", "equipment"):
        if not catalog[ref_type]:  # type: ignore[literal-required]
            raise InvalidCreationReference(f"no {ref_type} are seeded")

    skill_ids = set(catalog["skills"])
    for class_key, cls in sorted(catalog["classes"].items()):
        source = cls["skillChoices"]["from"]
        if isinstance(source, list):
            unknown = [skill for skill in source if skill not in skill_ids]
            if unknown:
                raise InvalidCreationReference(
                    f"class {class_key!r} offers unseeded skills: {sorted(unknown)}"
                )
        if cls["fightingStyleAt"] == 1 and not cls["fightingStyles"]:
            raise InvalidCreationReference(
                f"class {class_key!r} gains a Fighting Style at level 1 but offers none"
            )

    for background_key, bg in sorted(catalog["backgrounds"].items()):
        if len(bg["abilityOptions"]) < 3:
            raise InvalidCreationReference(
                f"background {background_key!r} offers fewer than three ability options"
            )
        pattern = bg["tool"]["choosableFrom"]
        if pattern is not None and not any(
            re.search(pattern, equipment_id) for equipment_id in catalog["equipment"]
        ):
            raise InvalidCreationReference(
                f"background {background_key!r} needs an item matching {pattern!r}"
            )

    for class_key, cls in sorted(catalog["classes"].items()):
        pool = set(class_skill_pool(cls, list(skill_ids)))
        for background_key, bg in sorted(catalog["backgrounds"].items()):
            _preflight_skills(class_key, background_key, cls, bg, pool)
            _preflight_spells(class_key, background_key, cls, bg, catalog["spells"])


def _preflight_skills(
    class_key: str,
    background_key: str,
    cls: Mapping[str, Any],
    bg: Mapping[str, Any],
    pool: set[str],
) -> None:
    granted = set(bg["skillIds"])
    offered = pool - granted
    needed = cls["skillChoices"]["count"]
    if len(offered) < needed:
        raise InvalidCreationReference(
            f"class {class_key!r} + background {background_key!r} offers {len(offered)} "
            f"of {needed} required skills"
        )
    expertise = expertise_count(cls)
    candidates = pool | granted
    if len(candidates) < expertise:
        raise InvalidCreationReference(
            f"class {class_key!r} + background {background_key!r} has {len(candidates)} "
            f"expertise candidates for {expertise} picks"
        )


def _preflight_spells(
    class_key: str,
    background_key: str,
    cls: Mapping[str, Any],
    bg: Mapping[str, Any],
    spells: Mapping[str, Mapping[str, Any]],
) -> None:
    budget = spell_budget(cls, bg)
    options = spell_options(cls, bg, spells)
    cantrips = [spell for spell in options if spell["level"] == 0]
    prepared = [spell for spell in options if spell["level"] == 1]
    if len(cantrips) < budget["cantrips"] or len(prepared) < budget["prepared"]:
        raise InvalidCreationReference(
            f"class {class_key!r} + background {background_key!r} needs "
            f"{budget['cantrips']} cantrips and {budget['prepared']} level-one spells; "
            f"the seed offers {len(cantrips)} and {len(prepared)}"
        )


# --------------------------------------------------------------------------------------
# Validation of a finished sheet
# --------------------------------------------------------------------------------------


def _required_row(
    mapping: Mapping[str, dict[str, Any]], key: str | None, field: str
) -> dict[str, Any]:
    if key is None or key not in mapping:
        raise ValueError(f"unknown {field}")
    return mapping[key]


def validate_complete_pointbuy_character(
    character: CharacterRecord, catalog: CreationCatalog
) -> None:
    """Raise unless a finished level-one point-buy sheet follows the creator's rules.

    ``ValueError`` means the record is not legal. ``InvalidCreationReference`` means the
    catalog itself cannot answer (unknown spell ID is a record defect, an empty skill
    catalog is a seed defect).
    """
    race = _required_row(catalog["races"], character.raceId, "raceId")
    cls = _required_row(catalog["classes"], character.classId, "classId")
    bg = _required_row(catalog["backgrounds"], character.backgroundId, "backgroundId")

    _validate_size(character, race)
    _validate_class_choices(character, cls)
    _validate_abilities(character, bg)
    _validate_skills(character, cls, bg, catalog)
    _validate_tool(character, bg, catalog)
    _validate_feats(character, bg)
    _validate_spells(character, cls, bg, catalog)
    _validate_equipment(character, cls, bg, catalog)
    _validate_completion(character, cls, bg, catalog)


def _validate_size(character: CharacterRecord, race: Mapping[str, Any]) -> None:
    if character.sizeChoice is not None and character.sizeChoice not in race["sizes"]:
        raise ValueError("sizeChoice is not allowed for the selected race")


def _validate_class_choices(character: CharacterRecord, cls: Mapping[str, Any]) -> None:
    offered = {style["id"] for style in cls["fightingStyles"]}
    if character.fightingStyleId is not None and character.fightingStyleId not in offered:
        raise ValueError("fightingStyleId is not offered by the selected class")
    if cls["fightingStyleAt"] == 1 and character.fightingStyleId is None:
        raise ValueError("the selected class requires a fighting style")


def _validate_abilities(character: CharacterRecord, bg: Mapping[str, Any]) -> None:
    abilities = character.abilities
    if abilities.method != "pointbuy":
        raise ValueError("abilities.method must be 'pointbuy'")

    base = dict(abilities.base)
    for ability in ABILITIES:
        score = base.get(ability)
        if not isinstance(score, int) or isinstance(score, bool):
            # A bad record value, not a bad argument type: this must stay a ValueError so a
            # save answers 400 rather than crashing with a TypeError.
            raise ValueError(f"base score for {ability} must be an integer")  # noqa: TRY004
        if not POINT_BUY_MIN <= score <= POINT_BUY_MAX:
            raise ValueError(f"base score for {ability} must be {POINT_BUY_MIN}-{POINT_BUY_MAX}")
    if point_buy_cost(base) > POINT_BUY_BUDGET:
        raise ValueError(f"point-buy cost exceeds {POINT_BUY_BUDGET}")

    allowed = set(bg["abilityOptions"])
    bonuses = dict(abilities.originBonuses)
    for ability, amount in bonuses.items():
        if ability not in allowed:
            raise ValueError("origin bonus is not offered by the selected background")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount <= 0:
            raise ValueError("origin bonuses must be positive integers")

    spread = sorted(bonuses.values())
    if spread not in ([1, 2], [1, 1, 1]):
        raise ValueError("origin bonuses must be +2/+1 or +1/+1/+1")

    for ability in ABILITIES:
        if base[ability] + bonuses.get(ability, 0) > ABILITY_CAP:
            raise ValueError(f"final {ability} exceeds {ABILITY_CAP}")


def _validate_skills(
    character: CharacterRecord,
    cls: Mapping[str, Any],
    bg: Mapping[str, Any],
    catalog: CreationCatalog,
) -> None:
    pool = [
        skill
        for skill in class_skill_pool(cls, list(catalog["skills"]))
        if skill not in set(bg["skillIds"])
    ]
    picks = character.proficientSkillIds
    if len(picks) != cls["skillChoices"]["count"]:
        raise ValueError(f"choose exactly {cls['skillChoices']['count']} class skills")
    if len(set(picks)) != len(picks):
        raise ValueError("skill picks must be unique")
    for skill in picks:
        if skill not in pool:
            raise ValueError("skill is not offered by the selected class and background")

    expertise = character.expertiseIds
    want = expertise_count(cls)
    if len(expertise) != want:
        raise ValueError(f"expertise must hold exactly {want} skill(s)")
    if len(set(expertise)) != len(expertise):
        raise ValueError("expertise picks must be unique")
    candidates = set(picks) | set(bg["skillIds"])
    for skill in expertise:
        if skill not in candidates:
            raise ValueError("expertise must come from proficient or background skills")


def _validate_tool(
    character: CharacterRecord, bg: Mapping[str, Any], catalog: CreationCatalog
) -> None:
    pattern = bg["tool"]["choosableFrom"]
    choice = character.toolChoiceId
    if pattern is None:
        if choice is not None:
            raise ValueError("the selected background requires no tool choice")
        return
    if choice is None:
        raise ValueError("the selected background requires a tool choice")
    if choice not in catalog["equipment"]:
        raise ValueError("unknown toolChoiceId")
    if not re.search(pattern, choice):
        raise ValueError("toolChoiceId is not in the background's tool category")


def _validate_feats(character: CharacterRecord, bg: Mapping[str, Any]) -> None:
    expected = set(bg["featIds"]) | {choice.featId for choice in character.classFeatChoices}
    if set(character.featIds) != expected:
        raise ValueError("featIds must hold the background's automatic feats")


def _validate_spells(
    character: CharacterRecord,
    cls: Mapping[str, Any],
    bg: Mapping[str, Any],
    catalog: CreationCatalog,
) -> None:
    options = spell_options(cls, bg, catalog["spells"])
    ids = character.spellIds
    if not options:
        if ids:
            raise ValueError("the selected class and background grant no spells at level 1")
        return

    if len(set(ids)) != len(ids):
        raise ValueError("spell selections must be unique")

    option_ids = {spell["id"] for spell in options}
    chosen: list[Mapping[str, Any]] = []
    for spell_id in ids:
        row = catalog["spells"].get(spell_id)
        if row is None:
            raise ValueError("unknown spellIds")
        if row["id"] not in option_ids:
            raise ValueError("spell is not available at level 1 for the selected class")
        chosen.append(row)

    budget = spell_budget(cls, bg)
    cantrips = sum(1 for row in chosen if row["level"] == 0)
    if cantrips != budget["cantrips"] or len(chosen) - cantrips != budget["prepared"]:
        raise ValueError(
            f"spells must hold {budget['cantrips']} cantrip(s) and "
            f"{budget['prepared']} level-one spell(s)"
        )

    validate_spell_class_eligibility(
        character.classId,
        [dict(row["envelope"]) for row in chosen],
        set(bg["initiateClassIds"]),
    )


def _validate_pick(pick: Any, offered: Sequence[Mapping[str, Any]], source: str) -> None:
    if not offered:
        if pick is not None:
            raise ValueError(f"the {source} offers no equipment alternatives")
        return
    if pick is None:
        raise ValueError(f"an equipment alternative must be chosen for the {source}")

    option = next((row for row in offered if row["key"] == pick.key), None)
    if option is None:
        raise ValueError(f"the {source} equipment pick names no offered alternative")
    if pick.model_dump(mode="json") != option:
        raise ValueError(f"the {source} equipment pick does not match the offered alternative")


def _validate_equipment(
    character: CharacterRecord,
    cls: Mapping[str, Any],
    bg: Mapping[str, Any],
    catalog: CreationCatalog,
) -> None:
    _validate_pick(character.equipmentChoice.class_, cls["startingEquipment"], "class")
    _validate_pick(character.equipmentChoice.background, bg["startingEquipment"], "background")
    for item_id in character.purchasedItemIds:
        if item_id not in catalog["equipment"]:
            raise ValueError("unknown equipmentIds")
    if character.walletCp < 0:
        raise ValueError("walletCp must not be negative")


def _validate_completion(
    character: CharacterRecord,
    cls: Mapping[str, Any],
    bg: Mapping[str, Any],
    catalog: CreationCatalog,
) -> None:
    required = set(CREATION_STEPS)
    if spell_options(cls, bg, catalog["spells"]):
        required.add(SPELL_STEP)
    missing = sorted(required - set(character.completedSteps))
    if missing:
        raise ValueError(f"missing completion markers: {missing}")
