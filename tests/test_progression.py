r"""PC progression (levelling) + multiclass re-derivation tests. No API needed.

Covers: single-class re-level (slots/HP/PB/features change, player spells preserved),
idempotent re-derive (single-class stays byte-for-byte, no pc.classes added), multiclass
spell slots (combined caster level -> wizard table), warlock Pact Magic kept separate,
mixed hit dice + HP, and multiclass proficiency reduction (saves from primary only).

Run:  .venv_forge\Scripts\python tests\test_progression.py
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from forge.engine import rederive   # noqa: E402

SAMPLE = json.loads((REPO_ROOT / "samples" / "sample_pc.json").read_text(encoding="utf-8"))


def _totals(sc, key="slots"):
    return {k: v.get("total") for k, v in (sc.get(key) or {}).items()}


def main() -> int:
    failures = []

    # --- idempotent re-derive: single-class stays byte-for-byte --------------
    base = copy.deepcopy(SAMPLE)
    char, warns, changes = rederive(base)
    if "classes" in char["pc"]:
        failures.append("single-class re-derive must NOT add pc.classes")
    if _totals(char["spellcasting"]) != {"1": 4, "2": 3, "3": 2}:
        failures.append(f"L5 wizard slots changed on idempotent re-derive: {_totals(char['spellcasting'])}")
    if char["hp"] != "32 (5d6 + 10)":
        failures.append(f"L5 wizard HP drifted: {char['hp']}")
    # player's hand-picked spells are untouched
    if char["spellcasting"]["prepared"] != SAMPLE["spellcasting"]["prepared"]:
        failures.append("re-derive must not clobber the player's chosen spells")

    # --- single-class LEVELLING: 5 -> 9 -------------------------------------
    char, warns, changes = rederive(copy.deepcopy(SAMPLE), level=9)
    if char["pc"]["level"] != 9:
        failures.append(f"level should be 9, got {char['pc']['level']}")
    if _totals(char["spellcasting"]) != {"1": 4, "2": 3, "3": 3, "4": 3, "5": 1}:
        failures.append(f"L9 wizard slots wrong: {_totals(char['spellcasting'])}")
    # HP: d6 max(6)+con2 at L1, then 8 levels of (4+2) => 8 + 48 = 56
    if char["hp"] != "56 (9d6 + 18)":
        failures.append(f"L9 wizard HP wrong: {char['hp']}")
    if changes.get("proficiencyBonus", {}).get("to") != 4:
        failures.append(f"PB should rise to +4 at L9, changes={changes.get('proficiencyBonus')}")
    if "spellSlots" not in changes:
        failures.append("levelling should report a spellSlots change")
    # features gained between L5 and L9 should be reported (e.g. wizard L8 ASI / subclass feats)
    if not changes.get("featuresGained"):
        failures.append("levelling 5->9 should report features gained")
    # chosen spells preserved (relaxed); advisory note only
    if char["spellcasting"]["prepared"] != SAMPLE["spellcasting"]["prepared"]:
        failures.append("levelling must not drop the player's chosen spells (relaxed)")

    # --- MULTICLASS slots: Wizard 5 / Cleric 3 -> caster level 8 ------------
    mc = copy.deepcopy(SAMPLE)
    char, warns, changes = rederive(mc, classes=[
        {"class": "wizard", "subclass": "evocation", "level": 5},
        {"class": "cleric", "level": 3},
    ])
    if char["pc"]["level"] != 8 or char["pc"]["class"] != "wizard":
        failures.append(f"multiclass primary/level wrong: {char['pc'].get('class')} L{char['pc'].get('level')}")
    if len(char["pc"].get("classes") or []) != 2:
        failures.append("multiclass should materialise pc.classes with 2 entries")
    if _totals(char["spellcasting"]) != {"1": 4, "2": 3, "3": 3, "4": 2}:
        failures.append(f"Wiz5/Cleric3 should give wizard-L8 slots, got {_totals(char['spellcasting'])}")
    if not char["spellcasting"].get("perClass"):
        failures.append("multiclass should list per-class spell DC/attack")

    # --- WARLOCK Pact Magic stays separate: Warlock 3 / Sorcerer 3 ---------
    wl = copy.deepcopy(SAMPLE)
    char, warns, changes = rederive(wl, classes=[
        {"class": "sorcerer", "level": 3},
        {"class": "warlock", "level": 3},
    ])
    # combined caster level = 3 (sorcerer only) -> wizard L3 slots
    if _totals(char["spellcasting"]) != {"1": 4, "2": 2}:
        failures.append(f"Sorc3/Warlock3 combined slots wrong: {_totals(char['spellcasting'])}")
    if _totals(char["spellcasting"], "pactSlots") != {"2": 2}:
        failures.append(f"warlock pact slots should be separate {{2:2}}, got {_totals(char['spellcasting'],'pactSlots')}")

    # --- MIXED hit dice + HP: Fighter 2 (d10) / Wizard 3 (d6), CON +1 -------
    fw = copy.deepcopy(SAMPLE)
    fw["abilities"] = {"STR": 14, "DEX": 12, "CON": 12, "INT": 14, "WIS": 10, "CHA": 8}  # CON 12 -> +1
    char, warns, changes = rederive(fw, classes=[
        {"class": "fighter", "level": 2},
        {"class": "wizard", "level": 3},
    ])
    # fighter L1 max(10)+1=11; fighter L2 (6+1)=7; wizard 3*(4+1)=15 => 33
    if char["hp"] != "33 (2d10 + 3d6 + 5)":
        failures.append(f"mixed-HP wrong: {char['hp']}")
    if not char["pc"].get("hitDicePools"):
        failures.append("multiclass should expose hitDicePools breakdown")

    # --- MULTICLASS proficiency reduction: saves from PRIMARY only ----------
    # Wizard (primary) / Fighter: saves stay INT/WIS (wizard), NOT fighter's STR/CON.
    mp = copy.deepcopy(SAMPLE)
    char, warns, changes = rederive(mp, classes=[
        {"class": "wizard", "subclass": "evocation", "level": 5},
        {"class": "fighter", "level": 2},
    ])
    if sorted(char.get("saveProfs") or []) != ["INT", "WIS"]:
        failures.append(f"multiclass saves should be primary (wizard) INT/WIS, got {char.get('saveProfs')}")
    profs = char["pc"].get("proficiencies") or {}
    if "Martial Weapons" not in (profs.get("weapons") or []):
        failures.append(f"fighter multiclass should grant Martial Weapons, got {profs.get('weapons')}")
    if "Medium Armor" not in (profs.get("armor") or []):
        failures.append(f"fighter multiclass should grant Medium Armor, got {profs.get('armor')}")

    print()
    if failures:
        print("FAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("OK: levelling re-derive, idempotence, multiclass slots, pact-magic split, "
          "mixed hit dice and multiclass proficiency rules all pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
