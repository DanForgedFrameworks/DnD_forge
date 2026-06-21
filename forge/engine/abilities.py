"""Ability scores: generation methods, modifiers, and edition-aware bonuses.

Methods supported (v1): standard array, point-buy, rolled (4d6 drop lowest), manual.
The 2014/2024 ability-bonus fork lives here:
  - 2014: bonuses come from the SPECIES.
  - 2024: bonuses come from the BACKGROUND, allocated by the player as +2/+1 or
    +1/+1/+1 among the background's listed abilities.
"""
from __future__ import annotations

import random

ABILITIES: tuple[str, ...] = ("str", "dex", "con", "int", "wis", "cha")
ABILITY_NAMES = {
    "str": "Strength", "dex": "Dexterity", "con": "Constitution",
    "int": "Intelligence", "wis": "Wisdom", "cha": "Charisma",
}

STANDARD_ARRAY: tuple[int, ...] = (15, 14, 13, 12, 10, 8)

# Point-buy (PHB): total cost to raise a score from 8 to the key.
_POINT_BUY_COST = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
POINT_BUY_BUDGET = 27
POINT_BUY_MIN, POINT_BUY_MAX = 8, 15


def modifier(score: int) -> int:
    """5e ability modifier."""
    return (score - 10) // 2


# -- generation / validation methods -------------------------------------------

def assign_standard_array(assignment: dict[str, int]) -> dict[str, int]:
    """Validate that `assignment` uses exactly the standard array values."""
    scores = _as_scores(assignment)
    if sorted(scores.values()) != sorted(STANDARD_ARRAY):
        raise ValueError(
            f"standard array must use exactly {STANDARD_ARRAY}, got {sorted(scores.values())}"
        )
    return scores


def point_buy_cost(scores: dict[str, int]) -> int:
    total = 0
    for ab, sc in scores.items():
        if sc not in _POINT_BUY_COST:
            raise ValueError(
                f"{ab}={sc} outside point-buy range {POINT_BUY_MIN}-{POINT_BUY_MAX}"
            )
        total += _POINT_BUY_COST[sc]
    return total


def assign_point_buy(scores: dict[str, int]) -> tuple[dict[str, int], int]:
    s = _as_scores(scores)
    cost = point_buy_cost(s)
    if cost > POINT_BUY_BUDGET:
        raise ValueError(f"point-buy spend {cost} exceeds budget {POINT_BUY_BUDGET}")
    return s, cost


def roll_4d6_drop_lowest(rng: random.Random | None = None) -> int:
    rng = rng or random.Random()
    dice = sorted(rng.randint(1, 6) for _ in range(4))
    return sum(dice[1:])  # drop the lowest


def roll_ability_set(rng: random.Random | None = None) -> list[int]:
    """Roll six scores (4d6 drop lowest each) for the player to assign."""
    rng = rng or random.Random()
    return [roll_4d6_drop_lowest(rng) for _ in range(6)]


def assign_manual(scores: dict[str, int], lo: int = 1, hi: int = 30) -> dict[str, int]:
    s = _as_scores(scores)
    for ab, sc in s.items():
        if not (lo <= sc <= hi):
            raise ValueError(f"{ab}={sc} outside allowed range {lo}-{hi}")
    return s


def _as_scores(d: dict[str, int]) -> dict[str, int]:
    missing = [a for a in ABILITIES if a not in d]
    if missing:
        raise ValueError(f"missing ability scores: {missing}")
    extra = [a for a in d if a not in ABILITIES]
    if extra:
        raise ValueError(f"unknown abilities: {extra}")
    return {a: int(d[a]) for a in ABILITIES}


# -- edition-aware racial / background bonuses ---------------------------------

def apply_ability_bonuses(
    base: dict[str, int],
    *,
    edition: str,
    species: dict | None = None,
    background: dict | None = None,
    allocation_2024: dict[str, int] | None = None,
) -> tuple[dict[str, int], list[tuple[str, int, str]]]:
    """Return (final_scores, applied) where applied is a list of (ability, bonus, source)."""
    final = dict(base)
    applied: list[tuple[str, int, str]] = []

    if edition == "2014":
        for ab in (species or {}).get("ability_bonuses") or []:
            idx = ab["ability_score"]["index"]
            bonus = int(ab["bonus"])
            final[idx] = final.get(idx, 0) + bonus
            applied.append((idx, bonus, f"species:{(species or {}).get('index')}"))

    elif edition == "2024":
        allowed = [a["index"] for a in (background or {}).get("ability_scores", [])]
        alloc = allocation_2024 or {}
        _validate_2024_allocation(alloc, allowed)
        for idx, bonus in alloc.items():
            final[idx] = final.get(idx, 0) + int(bonus)
            applied.append((idx, int(bonus), f"background:{(background or {}).get('index')}"))

    else:
        raise ValueError(f"unknown edition {edition!r}")

    return final, applied


def _validate_2024_allocation(alloc: dict[str, int], allowed: list[str]) -> None:
    if not alloc:
        return  # leaving it unallocated is permitted here; flagged upstream
    for ab in alloc:
        if allowed and ab not in allowed:
            raise ValueError(
                f"2024 ability increase on {ab!r} not offered by background (allowed: {allowed})"
            )
    vals = sorted(alloc.values(), reverse=True)
    if vals not in ([2, 1], [1, 1, 1]):
        raise ValueError(f"2024 ability increases must be +2/+1 or +1/+1/+1, got {vals}")
