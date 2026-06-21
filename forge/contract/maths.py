"""Canonical 5e maths the engine owns (the front-end deliberately doesn't hard-code these).

Pure, dependency-light. Operates on the contract `Character` shape (UPPERCASE abilities,
`challenge` as 'CR (XP)' or '— (level N)').
"""
from __future__ import annotations

import math
import re

ABILITIES: tuple[str, ...] = ("STR", "DEX", "CON", "INT", "WIS", "CHA")
ABBR_TITLE = {"STR": "Str", "DEX": "Dex", "CON": "Con", "INT": "Int", "WIS": "Wis", "CHA": "Cha"}

# The 18 standard skills -> governing ability.
SKILL_ABILITY = {
    "Acrobatics": "DEX", "Animal Handling": "WIS", "Arcana": "INT", "Athletics": "STR",
    "Deception": "CHA", "History": "INT", "Insight": "WIS", "Intimidation": "CHA",
    "Investigation": "INT", "Medicine": "WIS", "Nature": "INT", "Perception": "WIS",
    "Performance": "CHA", "Persuasion": "CHA", "Religion": "INT", "Sleight of Hand": "DEX",
    "Stealth": "DEX", "Survival": "WIS",
}


def ability_modifier(score: int) -> int:
    return math.floor((score - 10) / 2)


def fmt_bonus(n: int) -> str:
    return f"+{n}" if n >= 0 else str(n)


# -- proficiency bonus ---------------------------------------------------------
_PB_CR_BANDS = [
    (0, 4, 2), (5, 8, 3), (9, 12, 4), (13, 16, 5),
    (17, 20, 6), (21, 24, 7), (25, 28, 8), (29, 30, 9),
]


def pb_by_cr(cr: float) -> int:
    if cr < 0:
        raise ValueError("cr must be >= 0")
    for lo, hi, pb in _PB_CR_BANDS:
        if lo <= cr <= hi:
            return pb
    return 9  # cr > 30 clamps to the top band


def pb_by_level(level: int) -> int:
    if level < 1:
        raise ValueError("level must be >= 1")
    return math.ceil(level / 4) + 1


# -- CR <-> XP -----------------------------------------------------------------
CR_XP = {
    0: 10, 0.125: 25, 0.25: 50, 0.5: 100, 1: 200, 2: 450, 3: 700, 4: 1100, 5: 1800,
    6: 2300, 7: 2900, 8: 3900, 9: 5000, 10: 5900, 11: 7200, 12: 8400, 13: 10000,
    14: 11500, 15: 13000, 16: 15000, 17: 18000, 18: 20000, 19: 22000, 20: 25000,
    21: 33000, 22: 41000, 23: 50000, 24: 62000, 25: 75000, 26: 90000, 27: 105000,
    28: 120000, 29: 135000, 30: 155000,
}


def cr_to_xp(cr: float) -> int | None:
    return CR_XP.get(cr)


_FRACTIONS = {"1/8": 0.125, "1/4": 0.25, "1/2": 0.5, "⅛": 0.125, "¼": 0.25, "½": 0.5}


def parse_challenge(challenge: str | None) -> dict:
    """Parse 'CR (XP)' or '— (level N)' -> {cr, xp, level, pb}."""
    out: dict = {"cr": None, "xp": None, "level": None, "pb": None}
    if not challenge:
        return out
    s = str(challenge).strip()

    m_level = re.search(r"level\s+(\d+)", s, re.IGNORECASE)
    if m_level:
        out["level"] = int(m_level.group(1))
        out["pb"] = pb_by_level(out["level"])
        return out

    head = s.split("(")[0].strip()
    cr = _parse_cr_token(head)
    if cr is not None:
        out["cr"] = cr
        out["pb"] = pb_by_cr(cr)
        out["xp"] = cr_to_xp(cr)

    m_xp = re.search(r"([\d,]+)\s*XP", s, re.IGNORECASE)
    if m_xp:
        out["xp"] = int(m_xp.group(1).replace(",", ""))
    return out


def _parse_cr_token(tok: str) -> float | None:
    tok = tok.strip()
    if not tok or tok in ("—", "-", "–"):
        return None
    if tok in _FRACTIONS:
        return _FRACTIONS[tok]
    try:
        return float(tok)
    except ValueError:
        return None


# -- derived bonuses -----------------------------------------------------------
def save_bonus(mod: int, pb: int, proficient: bool) -> int:
    return mod + (pb if proficient else 0)


def skill_bonus(mod: int, pb: int, proficient: bool, expertise: bool = False) -> int:
    if expertise:
        return mod + 2 * pb
    return mod + (pb if proficient else 0)


def passive_perception(wis_mod: int, pb: int, proficient: bool, expertise: bool = False) -> int:
    return 10 + skill_bonus(wis_mod, pb, proficient, expertise)


def initiative(dex_mod: int, bonus: int = 0) -> int:
    return dex_mod + bonus


def spell_save_dc(pb: int, ability_mod: int) -> int:
    return 8 + pb + ability_mod


def spell_attack_bonus(pb: int, ability_mod: int) -> int:
    return pb + ability_mod
