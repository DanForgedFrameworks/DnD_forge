"""PC progression (levelling) + multiclass re-derivation — deterministic, no LLM.

This is the on-demand counterpart to the forge-time derivation in
``forge.agents.autofill._assemble_pc``. Given a saved character and a new level (or a
new class mix) it RE-RUNS only the level-dependent maths and leaves the player's
choices alone:

  re-derived ............ HP + hit dice, proficiency bonus, spell slots, spell save DC /
                          attack, class features gained, advisory spell-count limits
  never clobbered ....... exact ability scores, hand-picked cantrips/spells, equipment
                          (strict mode still regenerates gear via enforce_rules, as today)

Data model (additive, see PC-PROGRESSION-MULTICLASS-BRIEF.md):
  - single-class stays byte-for-byte: ``pc.class`` / ``pc.subclass`` / ``pc.level`` only,
    and the single class reads its OWN native slot table.
  - multiclass materialises ``pc.classes = [{class, subclass, level}, ...]`` (only when
    2+ classes). ``pc.class`` mirrors ``classes[0]`` and ``pc.level`` mirrors the SUM.

Multiclass spellcasting follows the PHB: the multiclass spell-slot table is identical to
the full-caster (wizard) progression, so combined caster level -> the wizard Levels table.
Warlock Pact Magic is kept separate (``spellcasting.pactSlots``). Edition-native throughout
(2014 / 2024) via the character's ``ruleset`` slug.

Entry point: ``rederive(character, level=?, classes=?) -> (character, warnings, changes)``.
"""
from __future__ import annotations

from pathlib import Path

from ..canon import SRDRepository
from ..contract import apply_derived
from .abilities import modifier
from .derive import proficiency_bonus, spell_slots
from .grants import resolve_pc_proficiencies
from .rules_mode import CASTER_RULES, enforce_rules

_DATA_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "srd"

# Caster-level contribution for the PHB multiclass spell-slot table.
FULL_CASTERS = frozenset({"bard", "cleric", "druid", "sorcerer", "wizard"})
HALF_CASTERS = frozenset({"paladin", "ranger"})  # contribute level // 2 (0 at L1)
# warlock is deliberately absent: Pact Magic does not combine (handled separately).


# -- repo / edition -----------------------------------------------------------
def _edition_for(character: dict) -> str:
    slug = character.get("ruleset")
    if not slug:
        return "2014"
    try:
        from ..ruleset import Ruleset
        return Ruleset(slug).config.get("srdEdition", "2014")
    except Exception:
        return "2014"


def _repo(edition: str) -> SRDRepository:
    return SRDRepository(edition, data_root=_DATA_ROOT)


def _hit_die(repo, class_index: str) -> int:
    cls = repo.get("classes", class_index) or {}
    return int(cls.get("hit_die") or 8)


# -- class-list normalisation -------------------------------------------------
def _norm_entry(entry: dict) -> dict:
    ci = (entry.get("class") or "").strip().lower() or None
    sub = entry.get("subclass")
    sub = sub.strip().lower() if isinstance(sub, str) and sub.strip() else None
    lvl = max(1, min(20, int(entry.get("level") or 1)))
    return {"class": ci, "subclass": sub, "level": lvl}


def normalize_classes(pc: dict, *, level=None, classes=None) -> list[dict]:
    """Resolve the effective class list from explicit args or the stored shape.

    Priority: explicit ``classes`` arg > stored ``pc.classes`` > single ``pc.class``.
    A bare ``level`` arg re-levels the primary (first) class — the single-class shortcut.
    """
    if classes:
        out = [_norm_entry(c) for c in classes if c and c.get("class")]
        if out:
            return out
    existing = pc.get("classes")
    if isinstance(existing, list) and any((e or {}).get("class") for e in existing):
        out = [_norm_entry(c) for c in existing if (c or {}).get("class")]
        if level is not None and out:
            out[0]["level"] = max(1, min(20, int(level)))
        return out
    lvl = int(level) if level is not None else int(pc.get("level") or 1)
    return [{"class": (pc.get("class") or "").lower() or None,
             "subclass": (pc.get("subclass") or None),
             "level": max(1, min(20, lvl))}]


def total_level(cls_list: list[dict]) -> int:
    return sum(int(e["level"]) for e in cls_list)


def _apply_classes(character: dict, pc: dict, cls_list: list[dict]) -> None:
    """Write the class list back: primary mirror + (only when 2+) pc.classes + challenge."""
    primary = cls_list[0]
    pc["class"] = primary["class"]
    pc["subclass"] = primary["subclass"]
    total = total_level(cls_list)
    pc["level"] = total
    if len(cls_list) > 1:
        pc["classes"] = [dict(e) for e in cls_list]
    else:
        pc.pop("classes", None)  # collapse back to the single-class shape
    character["challenge"] = f"— (level {total})"


# -- HP + hit dice ------------------------------------------------------------
def _ordered_dice(repo, cls_list: list[dict]) -> list[tuple[str, int]]:
    """[('d6', 5), ('d8', 3)] — die sizes in class order, counts summed per die."""
    order: list[str] = []
    agg: dict[str, int] = {}
    for e in cls_list:
        die = f"d{_hit_die(repo, e['class'])}"
        if die not in agg:
            agg[die] = 0
            order.append(die)
        agg[die] += int(e["level"])
    return [(d, agg[d]) for d in order]


def average_hp_multiclass(repo, cls_list: list[dict], con_mod: int) -> int:
    """Fixed/average HP across a class mix: max die for the FIRST class's L1, average after."""
    total = 0
    first = True
    for e in cls_list:
        die = _hit_die(repo, e["class"])
        lvls = int(e["level"])
        if first:
            total += die + con_mod  # level 1 = max die
            lvls -= 1
            first = False
        per_level_avg = die // 2 + 1
        total += lvls * (per_level_avg + con_mod)
    return total


def _hp_string(repo, cls_list: list[dict], con_mod: int, hp_total: int) -> str:
    pools = _ordered_dice(repo, cls_list)
    dice = " + ".join(f"{n}{die}" for die, n in pools)
    con_total = con_mod * total_level(cls_list)
    if con_total > 0:
        tail = f" + {con_total}"
    elif con_total < 0:
        tail = f" - {abs(con_total)}"
    else:
        tail = ""
    return f"{hp_total} ({dice}{tail})"


def _set_hit_dice(repo, pc: dict, cls_list: list[dict]) -> None:
    pools = _ordered_dice(repo, cls_list)
    total = total_level(cls_list)
    old_remaining = (pc.get("hitDice") or {}).get("remaining")
    remaining = min(int(old_remaining), total) if isinstance(old_remaining, int) else total
    pc["hitDice"] = {"die": pools[0][0], "total": total, "remaining": remaining}
    if len(pools) > 1:
        pc["hitDicePools"] = [{"die": d, "total": n, "remaining": n} for d, n in pools]
    else:
        pc.pop("hitDicePools", None)


# -- spellcasting -------------------------------------------------------------
def _block_to_totals(block: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for n in range(1, 10):
        t = int(block.get(f"spell_slots_level_{n}", 0) or 0)
        if t > 0:
            out[str(n)] = t
    return out


def combined_caster_level(cls_list: list[dict]) -> int:
    lvl = 0
    for e in cls_list:
        ci = e["class"]
        if ci in FULL_CASTERS:
            lvl += int(e["level"])
        elif ci in HALF_CASTERS:
            lvl += int(e["level"]) // 2
    return lvl


def multiclass_slots(repo, caster_level: int) -> dict[str, int]:
    """PHB multiclass slot table == the full-caster (wizard) progression."""
    if caster_level < 1:
        return {}
    return _block_to_totals(spell_slots(repo, "wizard", min(caster_level, 20)) or {})


def pact_slots(repo, warlock_level: int) -> dict[str, int]:
    if warlock_level < 1:
        return {}
    return _block_to_totals(spell_slots(repo, "warlock", min(warlock_level, 20)) or {})


def _merge_slots(target: dict, key: str, totals: dict[str, int]) -> None:
    """Set target[key] to the new totals, preserving each level's `expended` (capped)."""
    old = target.get(key) or {}
    out: dict[str, dict] = {}
    for k, total in totals.items():
        exp = int((old.get(k) or {}).get("expended", 0) or 0)
        out[k] = {"total": total, "expended": min(exp, total)}
    target[key] = out


def _derive_spellcasting(character, pc, cls_list, repo, pb, mods) -> None:
    caster_entries = [e for e in cls_list if e["class"] in CASTER_RULES]
    if not caster_entries:
        return  # non-caster mix — leave any stray block for enforce_rules to police

    sc = character.get("spellcasting")
    if not isinstance(sc, dict):
        sc = {}
        character["spellcasting"] = sc
    primary = caster_entries[0]
    if not sc.get("ability"):
        sc["ability"] = CASTER_RULES[primary["class"]]["ability"]

    if len(cls_list) == 1:
        # single class -> its OWN native table (byte-for-byte with forge-time derivation)
        block = spell_slots(repo, primary["class"], primary["level"]) or {}
        _merge_slots(sc, "slots", _block_to_totals(block))
        sc.pop("perClass", None)
        sc.pop("pactSlots", None)
        return

    # multiclass: combined caster level -> wizard table; warlock pact kept separate
    _merge_slots(sc, "slots", multiclass_slots(repo, combined_caster_level(cls_list)))
    warlock_level = next((e["level"] for e in cls_list if e["class"] == "warlock"), 0)
    if warlock_level:
        _merge_slots(sc, "pactSlots", pact_slots(repo, warlock_level))
    else:
        sc.pop("pactSlots", None)
    sc["perClass"] = [
        {
            "class": e["class"],
            "ability": CASTER_RULES[e["class"]]["ability"],
            "saveDc": 8 + pb + mods.get(CASTER_RULES[e["class"]]["ability"].upper(), 0),
            "attackBonus": pb + mods.get(CASTER_RULES[e["class"]]["ability"].upper(), 0),
        }
        for e in caster_entries
    ]


# -- class features -----------------------------------------------------------
def features_by_level(repo, cls_list: list[dict]) -> list[dict]:
    """[{name, class, level}] — base-class features granted up to each class's level.

    Subclass-specific feature text lives in the Subclasses data; the Levels table marks
    the *slot* where a subclass feature is gained (e.g. 'Martial Archetype' at fighter 3).
    """
    levels = repo.all("levels")
    out: list[dict] = []
    for e in cls_list:
        ci, cl = e["class"], int(e["level"])
        for entry in levels:
            if entry.get("class", {}).get("index") == ci and 1 <= int(entry.get("level", 0)) <= cl:
                for f in entry.get("features", []) or []:
                    if f.get("name"):
                        out.append({"name": f["name"], "class": ci, "level": int(entry["level"])})
    out.sort(key=lambda f: (f["class"], f["level"], f["name"]))
    return out


# -- snapshot / diff ----------------------------------------------------------
def _pb_from_level(level) -> int | None:
    try:
        return proficiency_bonus(int(level))
    except Exception:
        return None


def _snapshot(character: dict) -> dict:
    pc = character.get("pc") or {}
    sc = character.get("spellcasting") or {}
    return {
        "level": pc.get("level"),
        "hp": character.get("hp"),
        "pb": _pb_from_level(pc.get("level")),
        "hitDice": dict(pc.get("hitDice") or {}),
        "slots": {k: (v or {}).get("total") for k, v in (sc.get("slots") or {}).items()},
        "pactSlots": {k: (v or {}).get("total") for k, v in (sc.get("pactSlots") or {}).items()},
        "saveDc": sc.get("saveDc"),
        "attackBonus": sc.get("attackBonus"),
    }


def _feature_keys(repo, cls_list) -> set:
    return {(f["class"], f["level"], f["name"]) for f in features_by_level(repo, cls_list)}


def _diff(before: dict, after: dict) -> dict:
    changes: dict = {}
    for key in ("level", "hp", "pb", "saveDc", "attackBonus"):
        if before.get(key) != after.get(key):
            changes["proficiencyBonus" if key == "pb" else key] = {
                "from": before.get(key), "to": after.get(key)
            }
    if before["hitDice"] != after["hitDice"]:
        changes["hitDice"] = {"from": before["hitDice"].get("total"),
                              "to": after["hitDice"].get("total")}
    for key in ("slots", "pactSlots"):
        if before[key] != after[key]:
            changes["spellSlots" if key == "slots" else "pactSlots"] = {
                "from": before[key], "to": after[key]
            }
    return changes


# -- orchestrator -------------------------------------------------------------
def rederive(character: dict, *, level=None, classes=None) -> tuple[dict, list, dict]:
    """Re-derive the level-dependent numbers in place. Returns (character, warnings, changes).

    A no-op-shaped re-derive (no level/classes change) is idempotent: it reproduces the
    current numbers. Single-class characters are never given a ``pc.classes`` field.
    """
    warnings: list[dict] = []
    pc = character.get("pc")
    if character.get("kind") != "character" or not isinstance(pc, dict):
        return character, warnings, {}

    before = _snapshot(character)
    old_cls_list = normalize_classes(pc)  # the stored mix, to diff features-gained against
    cls_list = normalize_classes(pc, level=level, classes=classes)
    if not cls_list or not cls_list[0]["class"]:
        warnings.append({"level": "error", "message": "no class to derive from"})
        return character, warnings, {}

    edition = _edition_for(character)
    repo = _repo(edition)
    before_features = _feature_keys(repo, old_cls_list) if old_cls_list[0]["class"] else set()

    total = total_level(cls_list)
    if total > 20:
        warnings.append({"level": "warning",
                         "message": f"total character level {total} exceeds 20"})
    for e in cls_list:
        if repo.get("classes", e["class"]) is None:
            warnings.append({"level": "error", "message": f"unknown class '{e['class']}'"})

    _apply_classes(character, pc, cls_list)

    ab = character.get("abilities") or {}
    mods: dict[str, int] = {}  # keyed UPPERCASE (the contract's ability casing)
    for k, v in ab.items():
        try:
            mods[str(k).upper()] = modifier(int(v))
        except (TypeError, ValueError):
            pass
    pb = proficiency_bonus(total)

    # HP + hit dice (con mod across all levels)
    con_mod = mods.get("CON", 0)
    hp_total = average_hp_multiclass(repo, cls_list, con_mod)
    character["hp"] = _hp_string(repo, cls_list, con_mod, hp_total)
    _set_hit_dice(repo, pc, cls_list)

    # class features (engine-owned list; traits[] is left untouched)
    pc["classFeatures"] = features_by_level(repo, cls_list)

    # spell slots + per-class DC/attack
    _derive_spellcasting(character, pc, cls_list, repo, pb, mods)

    # proficiencies (multiclass-aware) + rules-mode enforcement (advisory/strict)
    resolve_pc_proficiencies(character)
    warnings.extend(enforce_rules(character))

    # derived strings + headline spell save DC / attack
    apply_derived(character)

    after = _snapshot(character)
    changes = _diff(before, after)
    gained = sorted(_feature_keys(repo, cls_list) - before_features)
    if gained:
        changes["featuresGained"] = [{"class": c, "level": lv, "name": nm} for c, lv, nm in gained]
    return character, warnings, changes
