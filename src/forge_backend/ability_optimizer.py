import random
from collections.abc import Mapping
from typing import Any

from forge_backend.creation_rules import origin_maps

ABILITIES = ("STR", "DEX", "CON", "INT", "WIS", "CHA")

POINT_BUY_BUDGET = 27

POINT_BUY_COSTS = {
    8: 0,
    9: 1,
    10: 2,
    11: 3,
    12: 4,
    13: 5,
    14: 7,
    15: 9,
}


def class_weights(cls: Mapping[str, Any]) -> dict[str, int]:
    primary = set(cls["primaryAbilities"])
    saving_throws = set(cls["savingThrows"])

    return {
        ability: (
            3 if ability in primary else 2 if ability in saving_throws or ability == "CON" else 1
        )
        for ability in ABILITIES
    }


def ability_modifier(score: int) -> int:
    return (score - 10) // 2


def weighted_modifier(score: int, weight: int) -> int:
    return ability_modifier(score) * weight


def optimize_pointbuy(
    weights: Mapping[str, int],
    bonuses: Mapping[str, int],
) -> dict[str, int]:

    dp = {0: (0, {})}

    for ability in ABILITIES:
        next_dp = {}

        for spent, (value, scores) in dp.items():
            for score, cost in POINT_BUY_COSTS.items():
                new_spent = spent + cost

                if new_spent > POINT_BUY_BUDGET:
                    continue

                final_score = score + bonuses.get(ability, 0)

                new_value = value + weighted_modifier(final_score, weights[ability])

                if new_spent not in next_dp or new_value > next_dp[new_spent][0]:
                    next_dp[new_spent] = (
                        new_value,
                        {**scores, ability: score},
                    )

        dp = next_dp

    return dp[POINT_BUY_BUDGET][1]


def optimize_abilities(
    cls: Mapping[str, Any],
    background: Mapping[str, Any],
    rng: random.Random,
) -> tuple[dict[str, int], dict[str, int]]:

    weights = class_weights(cls)
    best_value = float("-inf")
    best_candidates = []

    for bonuses in origin_maps(list(background["abilityOptions"])):
        base = optimize_pointbuy(weights, bonuses)

        value = sum(
            weighted_modifier(
                base[ability] + bonuses.get(ability, 0),
                weights[ability],
            )
            for ability in ABILITIES
        )

        if value > best_value:
            best_value = value
            best_candidates = [(base, bonuses)]

        elif value == best_value:
            best_candidates.append((base, bonuses))

    return rng.choice(best_candidates)
