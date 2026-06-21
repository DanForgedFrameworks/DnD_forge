"""Derived-stat primitives computed from canonical data + ability modifiers."""
from __future__ import annotations


def proficiency_bonus(total_level: int) -> int:
    """Universal across editions: +2 at L1-4, +3 at 5-8, +4 at 9-12, ..."""
    if total_level < 1:
        raise ValueError("level must be >= 1")
    return 2 + (total_level - 1) // 4


def skill_ability_map(repo) -> dict[str, str]:
    """{skill_index: ability_index} from the canonical Skills data."""
    out: dict[str, str] = {}
    for sk in repo.all("skills"):
        out[sk["index"]] = sk.get("ability_score", {}).get("index")
    return out


def class_skill_choice(cls: dict | None) -> tuple[int, set[str]] | None:
    """The class's starting skill choice as (choose_n, allowed_skill_indices), or None.

    SRD skill options are referenced as 'skill-<index>' inside proficiency_choices.
    """
    if not cls:
        return None
    for pc in cls.get("proficiency_choices", []):
        allowed: set[str] = set()
        for opt in pc.get("from", {}).get("options", []):
            idx = opt.get("item", {}).get("index", "")
            if idx.startswith("skill-"):
                allowed.add(idx[len("skill-"):])
        if allowed:
            return pc.get("choose"), allowed
    return None


def spell_slots(levels_repo, class_index: str, level: int) -> dict | None:
    """Spellcasting block (cantrips_known + spell_slots_level_1..9) for class+level."""
    if levels_repo is None:
        return None
    for entry in levels_repo.all("levels"):
        if entry.get("class", {}).get("index") == class_index and entry.get("level") == level:
            return entry.get("spellcasting") or None
    return None


def average_hp(hit_die: int, con_mod: int, level: int) -> int:
    """Fixed/average HP: max die at L1, then average-per-level thereafter."""
    per_level_avg = hit_die // 2 + 1
    return hit_die + con_mod + (level - 1) * (per_level_avg + con_mod)
