"""Strict vs Relaxed rules-mode enforcement for PCs.

Two modes, one engine. The deterministic MATHS (HP, saves, spell save DC, slots) is
always computed correctly elsewhere — this module governs how forgiving the forge is
about *choices*: which spells, how many, and what starting gear.

- ``relaxed`` ("Rule of Cool", default): leave the AI's thematic picks in place and
  emit info-level NOTES on anything non-standard. Nothing is removed.
- ``strict`` ("by the book"): off-list / too-high-level / over-count spells are
  CORRECTED (removed/trimmed) and reported as errors; starting gear + gold are computed
  straight from the class + background rulebook entries.

`enforce_rules(character)` reads ``pc.rulesMode`` (default "relaxed"), mutates the
character in place under strict, and returns a list of ``{level, message}`` warnings to
fold into the /forge + /character response alongside the contract validate() warnings.

Spell + slot tables are edition-native: 2024 casters resolve against the 2024 SRD spell
list + Levels tables, 2014 casters against the 2014 set. The edition is threaded through
from the character's ``ruleset`` slug.
"""
from __future__ import annotations

from functools import lru_cache

from ..canon import SRDRepository
from .abilities import modifier
from .derive import proficiency_bonus  # noqa: F401  (kept for callers/readability)

# Per-class spellcasting behaviour. Prepared casters compute a prepared count from an
# ability modifier + a fraction of level; known casters read `spells_known` from the
# Levels table. Classes absent here are non-casters (base class).
CASTER_RULES: dict[str, dict] = {
    "wizard":   {"type": "prepared", "ability": "int", "levelDiv": 1},
    "cleric":   {"type": "prepared", "ability": "wis", "levelDiv": 1},
    "druid":    {"type": "prepared", "ability": "wis", "levelDiv": 1},
    "paladin":  {"type": "prepared", "ability": "cha", "levelDiv": 2},  # half-caster
    "bard":     {"type": "known",    "ability": "cha"},
    "sorcerer": {"type": "known",    "ability": "cha"},
    "ranger":   {"type": "known",    "ability": "wis"},               # half-caster (known)
    "warlock":  {"type": "known",    "ability": "cha"},               # pact magic
}

_DATA_ROOT = None  # resolved lazily so this module is import-cheap


def _data_root():
    global _DATA_ROOT
    if _DATA_ROOT is None:
        from pathlib import Path
        _DATA_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "srd"
    return _DATA_ROOT


@lru_cache(maxsize=4)
def _repo(edition: str = "2014") -> SRDRepository:
    return SRDRepository(edition, data_root=_data_root())


def _edition_for(character: dict) -> str:
    """Resolve the SRD edition ("2014"/"2024") from the character's ruleset slug."""
    slug = character.get("ruleset")
    if not slug:
        return "2014"
    try:
        from ..ruleset import Ruleset
        return Ruleset(slug).config.get("srdEdition", "2014")
    except Exception:
        return "2014"


@lru_cache(maxsize=4)
def _spell_list_by_class(edition: str = "2014") -> dict[str, dict[str, int]]:
    """{class_index: {spell_index: spell_level}} from the edition's SRD spell list."""
    out: dict[str, dict[str, int]] = {}
    try:
        spells = _repo(edition).all("spells")
    except Exception:
        return out
    for sp in spells:
        idx, lvl = sp.get("index"), sp.get("level")
        for c in sp.get("classes", []) or []:
            out.setdefault(c.get("index"), {})[idx] = lvl
    return out


def class_spell_list(class_index: str, edition: str = "2014") -> dict[str, int]:
    """{spell_index: level} a class can cast (edition-native SRD spell list)."""
    return _spell_list_by_class(edition).get(class_index, {})


def class_spells_detailed(class_index: str, edition: str = "2014") -> list[dict]:
    """[{index, name, level}] for a class's SRD spell list, sorted by (level, name).

    Powers the front-end spell picker (browse + tick). Names come from the spell entries.
    """
    names: dict[str, str] = {}
    try:
        for sp in _repo(edition).all("spells"):
            names[sp.get("index")] = sp.get("name") or sp.get("index")
    except Exception:
        pass
    out = [{"index": idx, "name": names.get(idx, idx), "level": lvl}
           for idx, lvl in class_spell_list(class_index, edition).items()]
    out.sort(key=lambda s: (s["level"], s["name"].lower()))
    return out


def _levels_block(class_index: str, level: int, edition: str = "2014") -> dict | None:
    try:
        for e in _repo(edition).all("levels"):
            if e.get("class", {}).get("index") == class_index and e.get("level") == level:
                return e.get("spellcasting") or None
    except Exception:
        pass
    return None


def spell_limits(class_index: str, level: int, ability_mod: int, edition: str = "2014") -> dict | None:
    """Legal spell counts for a class at a level, or None for a non-caster.

    Returns {cantrips, leveled, maxSpellLevel, casterType}. `leveled` is the number of
    known (known casters) or prepared (prepared casters) leveled spells.
    """
    rules = CASTER_RULES.get(class_index)
    if not rules:
        return None
    block = _levels_block(class_index, level, edition) or {}
    cantrips = int(block.get("cantrips_known", 0) or 0)
    max_lvl = 0
    for n in range(1, 10):
        if int(block.get(f"spell_slots_level_{n}", 0) or 0) > 0:
            max_lvl = n
    if rules["type"] == "known":
        leveled = int(block.get("spells_known", 0) or 0)
    else:  # prepared = ability mod + level/levelDiv, floor, min 1
        leveled = max(1, ability_mod + level // rules.get("levelDiv", 1))
    return {
        "cantrips": cantrips,
        "leveled": leveled,
        "maxSpellLevel": max_lvl,
        "casterType": rules["type"],
        "ability": rules["ability"],
    }


# -- starting gear ------------------------------------------------------------

def _equipment_names(entries) -> list[dict]:
    out = []
    for e in entries or []:
        eq = (e.get("equipment") or {})
        name = eq.get("name")
        qty = e.get("quantity", 1)
        if name:
            out.append({"name": name, "qty": qty} if qty and qty != 1 else {"name": name})
    return out


def starting_gear(class_index: str, background_index: str | None, edition: str = "2014") -> dict:
    """By-the-book FIXED starting equipment + background gold from the edition's SRD.

    Only the fixed grants are resolved deterministically; equip *options* (choose A/B)
    are left for the player and noted, so strict mode never silently invents a choice.
    """
    repo = _repo(edition)
    cls = repo.get("classes", class_index) or {}
    bg = repo.get("backgrounds", background_index) if background_index else None

    equipment = _equipment_names(cls.get("starting_equipment"))
    has_class_options = bool(cls.get("starting_equipment_options"))
    if bg:
        equipment += _equipment_names(bg.get("starting_equipment"))

    currency = {"cp": 0, "sp": 0, "ep": 0, "gp": 0, "pp": 0}
    gold = (bg or {}).get("starting_gold") or {}
    unit = gold.get("unit", "gp")
    if unit in currency:
        currency[unit] = int(gold.get("quantity", 0) or 0)

    return {"equipment": equipment, "currency": currency, "hasUnresolvedOptions": has_class_options}


# -- enforcement --------------------------------------------------------------

def enforce_rules(character: dict) -> list[dict]:
    """Apply rules-mode policy to a PC. Mutates under strict. Returns warnings[]."""
    pc = character.get("pc")
    if character.get("kind") != "character" or not isinstance(pc, dict):
        return []
    mode = (pc.get("rulesMode") or "relaxed").lower()
    strict = mode == "strict"
    edition = _edition_for(character)
    warnings: list[dict] = []
    warnings += _enforce_spellcasting(character, strict, edition)
    warnings += _enforce_gear(character, strict, edition)
    return warnings


def _w(level: str, msg: str) -> dict:
    return {"level": level, "message": msg}


def _enforce_spellcasting(character: dict, strict: bool, edition: str = "2014") -> list[dict]:
    pc = character["pc"]
    sc = character.get("spellcasting")
    class_index = pc.get("class")
    level = int(pc.get("level") or 1)
    note = "error" if strict else "info"
    out: list[dict] = []

    limits = spell_limits(class_index, level, _spell_ability_mod(character, class_index), edition)
    if limits is None:
        if isinstance(sc, dict) and (sc.get("cantrips") or sc.get("prepared") or sc.get("known")):
            out.append(_w(note, f"{class_index} is not a spellcaster but spells were listed"))
            if strict:
                character.pop("spellcasting", None)
        return out

    if not isinstance(sc, dict):
        return out  # caster class with no spells listed yet — nothing to police

    allowed = class_spell_list(class_index, edition)

    # cantrips: must be on-list, level 0, within the cantrips-known count
    out += _police_list(sc, "cantrips", allowed, 0, limits["cantrips"], strict, "cantrip")
    # leveled spells: the schema carries them under `prepared` (also accept `known`)
    leveled_key = "prepared" if sc.get("prepared") is not None else ("known" if sc.get("known") is not None else "prepared")
    out += _police_list(sc, leveled_key, allowed, limits["maxSpellLevel"], limits["leveled"], strict, "spell")
    return out


def _police_list(sc, key, allowed, max_level, limit, strict, label) -> list[dict]:
    """Validate sc[key] against the class list, max spell level, and the count limit."""
    items = sc.get(key)
    if not isinstance(items, list):
        return []
    note = "error" if strict else "info"
    out, kept = [], []
    for idx in items:
        lvl = allowed.get(idx)
        if lvl is None:
            out.append(_w(note, f"{label} '{idx}' is not on the class spell list"))
            if strict:
                continue
        elif label == "cantrip" and lvl != 0:
            out.append(_w(note, f"'{idx}' is not a cantrip"))
            if strict:
                continue
        elif label == "spell" and lvl > max_level:
            out.append(_w(note, f"spell '{idx}' (level {lvl}) is above the highest slot level {max_level}"))
            if strict:
                continue
        kept.append(idx)
    if len(kept) > limit:
        out.append(_w(note, f"{len(kept)} {label}s listed but only {limit} allowed at this level"))
        if strict:
            kept = kept[:limit]
    if strict:
        sc[key] = kept
    return out


def _spell_ability_mod(character: dict, class_index: str) -> int:
    ability = (CASTER_RULES.get(class_index) or {}).get("ability")
    if not ability:
        return 0
    score = (character.get("abilities") or {}).get(ability.upper())
    return modifier(int(score)) if score is not None else 0


def _enforce_gear(character: dict, strict: bool, edition: str = "2014") -> list[dict]:
    pc = character["pc"]
    if not strict:
        return []  # relaxed keeps the AI's flavourful gear as-is
    book = starting_gear(pc.get("class"), pc.get("background"), edition)
    pc["equipment"] = book["equipment"]
    pc["currency"] = book["currency"]
    out = [_w("info", "starting equipment + gold set from the rulebook (strict mode)")]
    if book["hasUnresolvedOptions"]:
        out.append(_w("info", "class offers a starting-equipment choice (A/B) - pick one at the table"))
    return out
