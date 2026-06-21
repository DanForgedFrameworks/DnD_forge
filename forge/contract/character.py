"""The Character contract: derivation + validation as pure functions.

Prompt A deliverables:
  - deriveModifiers(character) -> derived block (mods, PB, and the computed
    saves/skills/senses STRINGS from structured proficiencies).
  - validate(character) -> {"ok": bool, "warnings": [...]}.

`character` is the contract dict (see forge/schema/character.schema.json). These
functions never mutate the input.
"""
from __future__ import annotations

import re

from .maths import (
    ABILITIES, ABBR_TITLE, SKILL_ABILITY,
    ability_modifier, fmt_bonus, parse_challenge, cr_to_xp,
    save_bonus, skill_bonus, passive_perception,
    spell_save_dc, spell_attack_bonus,
)

_TITLE_TO_ABBR = {v: k for k, v in ABBR_TITLE.items()}


def derive_modifiers(character: dict) -> dict:
    """Compute ability mods, proficiency bonus, and (from structured profs) the
    display strings the front-end shows read-only."""
    ab = character.get("abilities", {}) or {}
    mods = {a: ability_modifier(int(ab[a])) for a in ABILITIES if a in ab}
    ch = parse_challenge(character.get("challenge"))
    pb = ch["pb"]

    result = {"abilityMods": mods, "proficiencyBonus": pb, "challenge": ch, "derived": {}}
    if pb is None:
        return result

    derived = result["derived"]

    save_profs = character.get("saveProfs")
    if save_profs is not None:
        prof = {a.upper() for a in save_profs}
        parts, bonuses = [], {}
        for a in ABILITIES:
            if a in prof:
                b = save_bonus(mods.get(a, 0), pb, True)
                bonuses[a] = b
                parts.append(f"{ABBR_TITLE[a]} {fmt_bonus(b)}")
        derived["saves"] = ", ".join(parts)
        derived["saveBonuses"] = bonuses

    skill_profs = character.get("skillProfs")
    if skill_profs is not None:
        parts, perc_prof, perc_exp = [], False, False
        for sp in skill_profs:
            name = sp["skill"]
            exp = bool(sp.get("expertise", False))
            abil = SKILL_ABILITY.get(name)
            if abil is None:
                continue
            b = skill_bonus(mods.get(abil, 0), pb, True, exp)
            parts.append(f"{name} {fmt_bonus(b)}")
            if name == "Perception":
                perc_prof, perc_exp = True, exp
        derived["skills"] = ", ".join(parts)
        pp = passive_perception(mods.get("WIS", 0), pb, perc_prof, perc_exp)
        derived["passivePerception"] = pp
        derived["senses"] = f"passive Perception {pp}"

    # initiative (DEX mod + optional PC bonus) and, for casters, spell DC / attack
    derived["initiative"] = mods.get("DEX", 0) + int((character.get("pc") or {}).get("initiativeBonus", 0) or 0)
    sc = character.get("spellcasting")
    if isinstance(sc, dict) and sc.get("ability"):
        amod = mods.get(str(sc["ability"]).upper(), 0)
        derived["spellcasting"] = {
            "saveDc": spell_save_dc(pb, amod),
            "attackBonus": spell_attack_bonus(pb, amod),
        }

    return result


def apply_derived(character: dict) -> dict:
    """Write the engine-owned derived values back onto the character in place:
    the saves/skills/senses strings and spellcasting.saveDc/attackBonus."""
    derived = derive_modifiers(character).get("derived", {})
    for field in ("saves", "skills", "senses"):
        if derived.get(field):
            character[field] = derived[field]
    sc_derived = derived.get("spellcasting")
    if sc_derived and isinstance(character.get("spellcasting"), dict):
        character["spellcasting"]["saveDc"] = sc_derived["saveDc"]
        character["spellcasting"]["attackBonus"] = sc_derived["attackBonus"]
    return character


def validate(character: dict) -> dict:
    """Return {'ok': bool, 'warnings': [{level, message}]} — non-fatal consistency checks.
    level: 'error' (illegal/unknown) | 'warning' (drift) | 'info'."""
    issues: list[tuple[str, str]] = []
    ab = character.get("abilities", {}) or {}
    mods = {a: ability_modifier(int(ab[a])) for a in ABILITIES if a in ab}

    # ability presence + bounds
    for a in ABILITIES:
        if a not in ab:
            issues.append(("error", f"missing ability {a}"))
        elif not (1 <= int(ab[a]) <= 30):
            issues.append(("error", f"{a} {ab[a]} outside 1-30"))

    ch = parse_challenge(character.get("challenge"))
    pb = ch["pb"]
    if pb is None:
        issues.append(("warning", "challenge does not yield a proficiency bonus (unparseable CR/level)"))

    # CR <-> XP consistency
    if ch["cr"] is not None and ch["xp"] is not None:
        expect = cr_to_xp(ch["cr"])
        if expect is not None and expect != ch["xp"]:
            issues.append(("warning", f"challenge XP {ch['xp']:,} != {expect:,} expected for CR {ch['cr']}"))

    if pb is not None:
        for m in _check_save_string(character.get("saves"), mods, pb):
            issues.append(("warning", m))
        for m in _check_passive(character.get("senses"), mods, pb):
            issues.append(("warning", m))
        for m in _check_structured_vs_string(character, mods, pb):
            issues.append(("warning", m))

    warnings = [{"level": lvl, "message": msg} for lvl, msg in issues]
    ok = not any(w["level"] in ("error", "warning") for w in warnings)
    return {"ok": ok, "warnings": warnings}


# -- internal consistency probes ----------------------------------------------
_SAVE_RE = re.compile(r"([A-Za-z]{3})\s*([+-]\d+)")
_PP_RE = re.compile(r"passive Perception\s+(\d+)", re.IGNORECASE)


def _check_save_string(saves: str | None, mods: dict, pb: int) -> list[str]:
    if not saves:
        return []
    out = []
    for abbr3, bonus in _SAVE_RE.findall(saves):
        abbr = _TITLE_TO_ABBR.get(abbr3.title())
        if abbr is None or abbr not in mods:
            continue
        implied_pb = int(bonus) - mods[abbr]
        if implied_pb != pb and 2 <= implied_pb <= 9:
            out.append(
                f"save {abbr3} {bonus} implies PB +{implied_pb} but challenge -> PB +{pb}"
            )
    return out


def _check_passive(senses: str | None, mods: dict, pb: int) -> list[str]:
    if not senses:
        return []
    m = _PP_RE.search(senses)
    if not m:
        return []
    stated = int(m.group(1))
    wis = mods.get("WIS", 0)
    unprof, prof = 10 + wis, 10 + wis + pb
    if stated not in (unprof, prof):
        return [
            f"senses passive Perception {stated} matches neither {unprof} (unproficient) "
            f"nor {prof} (Perception-proficient) for PB +{pb}"
        ]
    return []


def _check_structured_vs_string(character: dict, mods: dict, pb: int) -> list[str]:
    """If both structured profs and authored strings exist, flag disagreement."""
    out = []
    derived = derive_modifiers(character)["derived"]
    for field in ("saves", "skills", "senses"):
        authored = character.get(field)
        computed = derived.get(field)
        if authored and computed and _norm(authored) != _norm(computed):
            out.append(f"{field} string '{authored}' disagrees with engine-derived '{computed}'")
    return out


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())
