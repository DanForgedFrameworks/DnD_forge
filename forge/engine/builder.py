"""Resolve a character *intent* into a full, computed character object.

This is the deterministic core: given choices (species/class/level/background/
ability scores/skill picks) it computes every derived number from the canonical
SRD data and reports legality issues. No randomness, no LLM.

Intent dict (v1) keys:
    ruleset            "2014" | "2024"
    name               str
    species            slug (e.g. "elf")
    subspecies         slug | None        (bonuses applied later; TODO v1)
    class              slug (e.g. "wizard")
    level              int 1-20
    background         slug | None
    alignment          str | None
    ability_method     "standard_array" | "point_buy" | "rolled" | "manual"
    ability_scores     {str,dex,con,int,wis,cha}  (BASE, pre-racial)
    ability_allocation_2024  {ability: bonus}      (2024 only)
    skill_proficiencies      [skill_index, ...]    (the class skill picks)

`repo` is the edition's SRDRepository. Pass `levels_repo` (and optionally
`class_repo`) of the SAME edition so spell-slot tables resolve natively; 2024
now ships its own Levels/Spells data, so a 2024 character should pass 2024 repos.
"""
from __future__ import annotations

from .abilities import ABILITIES, modifier, apply_ability_bonuses
from .derive import (
    proficiency_bonus, skill_ability_map, class_skill_choice, spell_slots, average_hp,
)

SCHEMA_VERSION = "0.1"


def build_character(intent: dict, repo, *, levels_repo=None, class_repo=None) -> dict:
    edition = intent["ruleset"]
    issues: list[str] = []
    prov: dict[str, str] = {}

    # --- canonical lookups -----------------------------------------------------
    species = repo.get("species", intent["species"])
    cls = repo.get("classes", intent["class"])
    background = repo.get("backgrounds", intent["background"]) if intent.get("background") else None
    level = int(intent.get("level", 1))

    if species is None:
        issues.append(f"unknown species '{intent.get('species')}'")
    if cls is None:
        issues.append(f"unknown class '{intent.get('class')}'")
    if intent.get("background") and background is None:
        issues.append(f"unknown background '{intent.get('background')}'")
    if not (1 <= level <= 20):
        issues.append(f"level {level} out of range 1-20")

    # --- ability scores: base -> +bonuses -> modifiers -------------------------
    base = {a: int(intent["ability_scores"][a]) for a in ABILITIES}
    final_scores, applied = apply_ability_bonuses(
        base,
        edition=edition,
        species=species,
        background=background,
        allocation_2024=intent.get("ability_allocation_2024"),
    )
    mods = {a: modifier(final_scores[a]) for a in ABILITIES}
    for a in ABILITIES:
        prov[f"ability_scores.{a}"] = intent.get("ability_method", "manual")

    if edition == "2024" and background is not None and not intent.get("ability_allocation_2024"):
        issues.append("2024 character has no ability_allocation_2024 (background bonuses unassigned)")

    pb = proficiency_bonus(level)

    # --- saving throws (class grants proficiency) ------------------------------
    save_prof = [s["index"] for s in (cls.get("saving_throws") if cls else [])]
    saving_throws = {
        a: {"modifier": mods[a] + (pb if a in save_prof else 0), "proficient": a in save_prof}
        for a in ABILITIES
    }

    # --- skills ----------------------------------------------------------------
    skmap = skill_ability_map(repo)
    chosen_skills = set(intent.get("skill_proficiencies", []))
    for s in chosen_skills:
        if s not in skmap:
            issues.append(f"unknown skill proficiency '{s}'")

    choice = class_skill_choice(cls)
    if choice:
        n, allowed = choice
        for s in chosen_skills:
            if allowed and s not in allowed:
                issues.append(f"skill '{s}' not in {intent.get('class')} skill options")
        if n is not None and len(chosen_skills) != n:
            issues.append(
                f"{intent.get('class')} grants {n} skill proficiencies, got {len(chosen_skills)}"
            )

    skills = {
        sk: {
            "ability": ab,
            "proficient": sk in chosen_skills,
            "modifier": mods[ab] + (pb if sk in chosen_skills else 0),
        }
        for sk, ab in skmap.items()
    }

    # --- HP / hit dice / speed / defences --------------------------------------
    hit_die = cls.get("hit_die") if cls else None
    max_hp = average_hp(hit_die, mods["con"], level) if hit_die else None
    speed = species.get("speed") if species else None
    perc_prof = "perception" in chosen_skills
    derived = {
        "proficiency_bonus": pb,
        "max_hp": max_hp,
        "hit_dice": f"{level}d{hit_die}" if hit_die else None,
        "armor_class": 10 + mods["dex"],
        "armor_class_note": "unarmored (10 + DEX); armored/shield AC is a v1 follow-up",
        "initiative": mods["dex"],
        "speed": speed,
        "passive_perception": 10 + mods["wis"] + (pb if perc_prof else 0),
        "saving_throws": saving_throws,
        "skills": skills,
    }

    # --- spellcasting ----------------------------------------------------------
    spellcasting = _resolve_spellcasting(
        edition, cls, class_repo, levels_repo, level, mods, pb, issues
    )

    return {
        "meta": {
            "schema_version": SCHEMA_VERSION,
            "ruleset": edition,
            "ability_method": intent.get("ability_method"),
        },
        "identity": {
            "name": intent.get("name"),
            "species": intent.get("species"),
            "subspecies": intent.get("subspecies"),
            "class": intent.get("class"),
            "level": level,
            "background": intent.get("background"),
            "alignment": intent.get("alignment"),
        },
        "ability_scores": {
            a: {"base": base[a], "total": final_scores[a], "modifier": mods[a]}
            for a in ABILITIES
        },
        "ability_bonuses_applied": [
            {"ability": a, "bonus": b, "source": src} for (a, b, src) in applied
        ],
        "derived": derived,
        "spellcasting": spellcasting,
        "provenance": prov,
        "legality_issues": issues,
    }


def _resolve_spellcasting(edition, cls, class_repo, levels_repo, level, mods, pb, issues):
    if not cls:
        return None

    sc_meta = cls.get("spellcasting")
    src_index = cls["index"]
    # 2024 now ships its own spell + level/slot tables, so the native 2024 class
    # metadata is used. Only if the 2024 source is missing spellcasting metadata do we
    # fall back to the 2014 class entry (legacy borrow), and flag it.
    borrowed_2024 = False
    if edition == "2024" and not sc_meta and class_repo is not None:
        borrowed = class_repo.get("classes", src_index)
        if borrowed and borrowed.get("spellcasting"):
            sc_meta = borrowed.get("spellcasting")
            borrowed_2024 = True

    if not sc_meta:
        return None  # non-caster

    ability_idx = sc_meta.get("spellcasting_ability", {}).get("index")
    slots = spell_slots(levels_repo, src_index, level)
    if slots is None:
        issues.append(f"no spell-slot data found for {src_index} L{level}")

    out = {
        "is_spellcaster": True,
        "spellcasting_ability": ability_idx,
        "spell_save_dc": (8 + pb + mods.get(ability_idx, 0)) if ability_idx else None,
        "spell_attack_bonus": (pb + mods.get(ability_idx, 0)) if ability_idx else None,
        "slots": slots,
    }
    if borrowed_2024:
        out["note"] = "2024 source lacked spellcasting metadata; borrowed 2014 class entry"
    return out
