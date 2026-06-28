"""Derive weapon attack actions from a PC's gear (the deterministic 'engine disposes' half).

The forge/Studio store a PC's weapons in ``pc.equipment`` as names (now catalog-backed,
some carrying structured ``modes`` — e.g. the kender Hoopak's staff/sling). This module
turns those into the **attack actions** a sheet shows: hit bonus and damage worked out
from the character's ability scores, proficiency bonus and the weapon's SRD data — never
invented.

Public API:
- :func:`derive_weapon_actions` — list of ``{name, source, text}`` attack actions for the
  whole equipment list (one per damaging weapon/mode).
- :func:`weapon_actions_for_item` — the attack(s) for a single named item (the "Add as
  action" button calls this).

Generated actions are tagged ``source = "weapon:<index>"`` so the front-end can tell an
engine-derived attack from a hand-written one, and regeneration can replace only its own.
"""
from __future__ import annotations

import re

import json
from functools import lru_cache
from pathlib import Path

from .abilities import modifier
from .derive import proficiency_bonus
from .equipment import _repo, canonical_item

_HOMEBREW_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "srd" / "_homebrew"


@lru_cache(maxsize=1)
def _flavour_actions() -> dict:
    """Hand-authored flavour actions for ordinary gear, keyed by SRD index or lower-cased name."""
    path = _HOMEBREW_ROOT / "item_actions.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {k.lower(): v for k, v in data.items() if not k.startswith("_")}
    except Exception:
        return {}


@lru_cache(maxsize=1)
def standard_actions() -> list[dict]:
    """The universal actions + reactions any creature can take (Dash, Dodge, Grapple, Opportunity
    Attack…) as a flat ``[{name, text, kind}]`` list, for the 'Common actions' picker."""
    try:
        data = json.loads((_HOMEBREW_ROOT / "standard_actions.json").read_text(encoding="utf-8"))
    except Exception:
        return []
    return (data.get("actions") or []) + (data.get("reactions") or [])


_DICE = re.compile(r"(\d+)d(\d+)")


def _avg_dice(dice: str) -> float:
    """Average roll of the first ``NdM`` in a string ('1d6' -> 3.5; '1d6 (1d8…)' -> 3.5)."""
    m = _DICE.search(dice or "")
    if not m:
        return 0.0
    n, faces = int(m.group(1)), int(m.group(2))
    return n * (faces + 1) / 2.0


def _first_dice(dice: str) -> str:
    m = _DICE.search(dice or "")
    return m.group(0) if m else (dice or "")


def _ability_for(properties: list[str], is_ranged: bool, abilities: dict) -> str:
    """Which ability swings this weapon: finesse -> better of STR/DEX, ranged -> DEX, else STR."""
    props = {p.lower() for p in properties}
    str_mod = modifier(abilities.get("STR", abilities.get("str", 10)))
    dex_mod = modifier(abilities.get("DEX", abilities.get("dex", 10)))
    if "finesse" in props:
        return "DEX" if dex_mod >= str_mod else "STR"
    if is_ranged:
        return "DEX"
    return "STR"


def _is_proficient(weapon_category: str, profs: dict) -> bool:
    """Proficient if the character's weapon proficiencies cover this weapon's category.

    PC weapon proficiencies are SRD category strings ('Simple Weapons', 'Martial Weapons').
    Defaults to True when we can't tell — most PCs are proficient with the gear they carry,
    and a missing-proficiency penalty is more surprising than a generous default.
    """
    weapons = " ".join(profs.get("weapons", []) if isinstance(profs, dict) else []).lower()
    cat = (weapon_category or "").lower()
    if not weapons:
        return True
    if cat == "simple":
        return "simple" in weapons or "all weapons" in weapons
    if cat == "martial":
        return "martial" in weapons or "all weapons" in weapons
    return True


def _sign(n: int) -> str:
    return ("+" if n >= 0 else "−") + str(abs(n))


def _attack_text(*, is_ranged: bool, reach_or_range: str, to_hit: int,
                 dice: str, dmg_mod: int, dtype: str, mastery: str | None) -> str:
    kind = "Ranged Weapon Attack" if is_ranged else "Melee Weapon Attack"
    avg = int(_avg_dice(dice) + dmg_mod)
    dmg_dice = _first_dice(dice)
    dmg_str = f"{dmg_dice}{_sign(dmg_mod).replace('+', ' + ').replace('−', ' − ')}".strip() if dmg_mod else dmg_dice
    hit = f"{max(1, avg)} ({dmg_str}) {dtype} damage" if dtype else f"{max(1, avg)} ({dmg_str}) damage"
    txt = f"{kind}: {_sign(to_hit)} to hit, {reach_or_range}, one target. Hit: {hit}."
    if mastery:
        txt += f" Mastery: {mastery}."
    return txt


def _weapon_actions_from_entry(entry: dict, abilities: dict, pb: int, profs: dict,
                               display_name: str | None = None) -> list[dict]:
    """Attack action(s) for one resolved catalog/SRD weapon entry (handles multi-mode items).

    ``display_name`` (the player's own wording for the item) titles the action when given,
    so a player's "Light Crossbow" isn't shown back as the SRD's "Crossbow, light".
    """
    index = entry.get("index") or entry.get("name")
    name = display_name or entry.get("name") or index
    category = entry.get("weapon_category") or ""          # "Simple" | "Martial" | ""
    proficient = _is_proficient(category, profs)
    pb_add = pb if proficient else 0
    out: list[dict] = []

    modes = entry.get("modes")
    if isinstance(modes, list) and modes:
        for mode in modes:
            dice = mode.get("damage")
            if not dice:
                # non-attack mode (e.g. the Hoopak's bullroarer) — emit as a utility action
                # carrying its own description, so the whole item is usable, not just its blades.
                out.append({
                    "name": f"{name} ({mode.get('name', 'Use')})",
                    "source": f"weapon:{index}:{(mode.get('name') or '').lower()}",
                    "text": mode.get("summary") or f"Use the {mode.get('name', 'item').lower()}.",
                })
                continue
            is_ranged = (mode.get("type") == "ranged") or bool(mode.get("range"))
            props = ["finesse"] if is_ranged and "finesse" in (name or "").lower() else []
            abil = "DEX" if is_ranged else _ability_for(props, False, abilities)
            amod = modifier(abilities.get(abil, abilities.get(abil.lower(), 10)))
            reach = f"range {mode['range']} ft." if mode.get("range") else "reach 5 ft."
            out.append({
                "name": f"{name} ({mode.get('name', 'Attack')})",
                "source": f"weapon:{index}:{(mode.get('name') or '').lower()}",
                "text": _attack_text(is_ranged=is_ranged, reach_or_range=reach, to_hit=amod + pb_add,
                                     dice=dice, dmg_mod=amod, dtype=mode.get("damageType", ""),
                                     mastery=mode.get("mastery")),
            })
        return out

    # plain single-profile weapon from SRD fields
    dmg = entry.get("damage") or {}
    dice = dmg.get("damage_dice")
    if not dice:
        return []  # not a damaging weapon (gear, focus, etc.)
    props = [p.get("index", "") for p in entry.get("properties", []) if isinstance(p, dict)]
    cat_range = (entry.get("category_range") or "") + " " + (entry.get("weapon_range") or "")
    is_ranged = "ranged" in cat_range.lower() or "ammunition" in [p.lower() for p in props]
    abil = _ability_for(props, is_ranged, abilities)
    amod = modifier(abilities.get(abil, abilities.get(abil.lower(), 10)))
    rng = entry.get("range") or {}
    if is_ranged and rng.get("long"):
        reach = f"range {rng.get('normal', 0)}/{rng['long']} ft."
    elif is_ranged:
        reach = f"range {rng.get('normal', 0)} ft."
    else:
        reach = f"reach {rng.get('normal', 5)} ft."
    dtype = (dmg.get("damage_type") or {}).get("name", "")
    mastery = (entry.get("mastery") or {}).get("name") if isinstance(entry.get("mastery"), dict) else None
    return [{
        "name": name,
        "source": f"weapon:{index}",
        "text": _attack_text(is_ranged=is_ranged, reach_or_range=reach, to_hit=amod + (pb if _is_proficient(category, profs) else 0),
                             dice=dice, dmg_mod=amod, dtype=dtype, mastery=mastery),
    }]


@lru_cache(maxsize=4)
def _weapon_word_patterns(edition: str):
    """Compiled (pattern, entry) for every SRD weapon, longest-name-first — to spot a weapon
    type hidden inside a flavour name ('Whisperleaf (Shortsword)', 'Two daggers'). Plus a
    'knife' -> dagger alias. Only true weapons (with damage) are indexed, so non-weapon items
    aren't dragged in by a coincidental word."""
    pairs = []
    try:
        for e in _repo(edition).all("equipment"):
            if not (e.get("damage") or e.get("two_handed_damage")):
                continue
            nm = (e.get("name") or "").strip().lower()
            if nm:
                pairs.append((nm, e))
    except Exception:
        return ()
    dagger = _repo(edition).get("equipment", "dagger")
    if dagger:
        pairs.append(("knife", dagger))
    pairs.sort(key=lambda t: -len(t[0]))
    return tuple((re.compile(r"\b" + re.escape(w) + r"s?\b"), e) for w, e in pairs)


def _resolve_weapon_entry(name: str, edition: str) -> dict | None:
    """An item name -> a weapon SRD entry, directly OR by spotting a weapon type inside a flavour
    name ('Two daggers' -> dagger, 'Whisperleaf (Shortsword)' -> shortsword). None if not a weapon."""
    card = canonical_item(name, edition)
    entry = _repo(edition).get("equipment", card["index"]) if card else _repo(edition).get("equipment", name)
    if card and card.get("modes") and entry and not entry.get("modes"):
        entry = dict(entry, modes=card["modes"])
    if entry and (entry.get("damage") or entry.get("modes")):
        return entry
    lname = (name or "").lower()
    for pat, went in _weapon_word_patterns(edition):
        if pat.search(lname):
            return went
    return None


def weapon_actions_for_item(name: str, character: dict, edition: str = "2014") -> list[dict]:
    """Attack/use action(s) for a single equipment item by name (the 'Add action' path).

    For a weapon (named plainly OR via flavour, e.g. 'Whisperleaf (Shortsword)'): its attack(s)
    plus any utility mode (the Hoopak's bullroarer). For a non-weapon: [] — callers wanting a
    guaranteed action use :func:`item_actions`.
    """
    entry = _resolve_weapon_entry(name, edition)
    if not entry:
        return []
    abilities = character.get("abilities") or {}
    pc = character.get("pc") or {}
    pb = proficiency_bonus(int(pc.get("level") or 1))
    # keep the player's wording for a plain weapon's title (modes already carry their own names)
    display = name if not entry.get("modes") else None
    return _weapon_actions_from_entry(entry, abilities, pb, pc.get("proficiencies") or {}, display)


def item_actions(name: str, character: dict, edition: str = "2014") -> list[dict]:
    """An action (or several) for ANY equipment item — weapon or not.

    Order of preference:
      1. Weapon attacks + utility modes (the Hoopak's staff/sling/bullroarer).
      2. The item's own descriptive text (homebrew ``special`` or SRD ``desc``) as a "use" action.
      3. A blank stub named after the item, so the player can describe a contextual use of their
         own (lighting a candle, reading a map, etc.). This is why "Add action" works on anything.
    """
    weap = weapon_actions_for_item(name, character, edition)
    if weap:
        return weap
    card = canonical_item(name, edition)
    idx = (card["index"] if card else name)
    # hand-authored flavour action(s)? match on SRD index first, then the plain name.
    table = _flavour_actions()
    flavour = table.get(str(idx).lower()) or table.get((name or "").strip().lower())
    if flavour:
        return [{"name": f.get("name", name), "source": f"item:{str(idx).lower()}",
                 "text": f.get("text", "")} for f in flavour]
    return []  # no weapon profile, no flavour entry -> not an action (armour, focuses, packs, …)


def item_is_actionable(name: str, edition: str = "2014") -> bool:
    """True if an item yields a real action — a weapon (attack/modes) or a flavour-table entry.

    Used to decide whether the Studio shows a "+ Action" button: armour, ammunition, focuses,
    clothing and the like have no action of their own (armour is already in AC), so they don't.
    Cheap (no ability scores needed); safe to call per equipment row.
    """
    card = canonical_item(name, edition)
    idx = str((card["index"] if card else name) or "").lower()
    table = _flavour_actions()
    if table.get(idx) or table.get((name or "").strip().lower()):
        return True
    return _resolve_weapon_entry(name, edition) is not None


def annotate_equipment_actions(character: dict, edition: str = "2014") -> dict:
    """Tag each ``pc.equipment`` item with ``hasAction`` so the UI shows "+ Action" only where
    there's actually one to add. Mutates and returns the character."""
    pc = character.get("pc")
    if isinstance(pc, dict):
        for it in pc.get("equipment") or []:
            if isinstance(it, dict):
                it["hasAction"] = item_is_actionable(it.get("name", ""), edition)
    return character


def derive_weapon_actions(character: dict, edition: str = "2014") -> list[dict]:
    """All attack actions derived from a PC's ``pc.equipment`` (one+ per damaging weapon)."""
    pc = character.get("pc")
    if not isinstance(pc, dict):
        return []
    abilities = character.get("abilities") or {}
    pb = proficiency_bonus(int(pc.get("level") or 1))
    profs = pc.get("proficiencies") or {}
    out: list[dict] = []
    seen = set()
    for it in pc.get("equipment") or []:
        nm = it.get("name") if isinstance(it, dict) else str(it)
        if not nm:
            continue
        entry = _resolve_weapon_entry(nm, edition)  # resolves flavour names too (Two daggers, etc.)
        if not entry:
            continue
        if isinstance(it, dict) and it.get("modes") and not entry.get("modes"):
            entry = dict(entry, modes=it["modes"])
        display = nm if not entry.get("modes") else None
        for act in _weapon_actions_from_entry(entry, abilities, pb, profs, display):
            if act["source"] in seen:
                continue
            seen.add(act["source"])
            out.append(act)
    return out
