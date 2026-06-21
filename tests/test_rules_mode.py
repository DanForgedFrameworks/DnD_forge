r"""Job 5 test: Strict vs Relaxed rules-mode enforcement (spells + gear). No API needed.

Run:  .venv_forge\Scripts\python tests\test_rules_mode.py
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from forge.engine import enforce_rules   # noqa: E402


def _wizard(mode):
    # L5 wizard, INT 17 (+3) -> 4 cantrips, 8 prepared, max spell level 3.
    return {
        "kind": "character", "ruleset": "dnd5e-2014",
        "abilities": {"STR": 8, "DEX": 14, "CON": 14, "INT": 17, "WIS": 12, "CHA": 10},
        "pc": {"class": "wizard", "level": 5, "rulesMode": mode},
        "spellcasting": {
            "ability": "int",
            # 5 cantrips (limit 4) incl. cure-wounds (off the wizard list)
            "cantrips": ["fire-bolt", "mage-hand", "light", "prestidigitation", "cure-wounds"],
            # 'wish' is on the wizard list but level 9 — above the L5 max of 3
            "prepared": ["magic-missile", "shield", "fireball", "wish"],
        },
    }


def main() -> int:
    failures = []

    # --- STRICT: illegal picks corrected, errors reported -------------------
    strict = _wizard("strict")
    w = enforce_rules(strict)
    sc = strict["spellcasting"]
    print("STRICT cantrips:", sc["cantrips"])
    print("STRICT prepared:", sc["prepared"])
    print("STRICT warnings:", [x["message"] for x in w])
    if "cure-wounds" in sc["cantrips"]:
        failures.append("strict should drop off-list cantrip cure-wounds")
    if len(sc["cantrips"]) != 4:
        failures.append(f"strict cantrips should trim to 4, got {sc['cantrips']}")
    if "wish" in sc["prepared"]:
        failures.append("strict should drop too-high-level spell 'wish'")
    if not any(x["level"] == "error" for x in w):
        failures.append("strict corrections should be error-level")

    # --- RELAXED: nothing removed, notes only -------------------------------
    relaxed = _wizard("relaxed")
    w2 = enforce_rules(relaxed)
    sc2 = relaxed["spellcasting"]
    if "cure-wounds" not in sc2["cantrips"] or "wish" not in sc2["prepared"]:
        failures.append("relaxed must NOT remove the AI's picks")
    if any(x["level"] == "error" for x in w2):
        failures.append("relaxed should emit info notes, not errors")
    if not w2:
        failures.append("relaxed should still note the non-standard picks")
    print("RELAXED warnings:", [x["level"] for x in w2])

    # --- non-caster with spells: strict strips the block --------------------
    rogue = {
        "kind": "character", "ruleset": "dnd5e-2014",
        "abilities": {"STR": 10, "DEX": 16, "CON": 12, "INT": 12, "WIS": 10, "CHA": 14},
        "pc": {"class": "rogue", "level": 3, "rulesMode": "strict"},
        "spellcasting": {"cantrips": ["fire-bolt"]},
    }
    wr = enforce_rules(rogue)
    if "spellcasting" in rogue:
        failures.append("strict should strip spellcasting from a non-caster")
    if not any(x["level"] == "error" for x in wr):
        failures.append("non-caster-with-spells should error in strict")

    # --- strict gear comes from the book ------------------------------------
    g = _wizard("strict")
    g["pc"]["background"] = "acolyte"
    enforce_rules(g)
    names = [e["name"] for e in g["pc"].get("equipment", [])]
    print("STRICT gear:", names, "| gold:", g["pc"].get("currency"))
    if "Spellbook" not in names:
        failures.append(f"strict wizard gear should include the Spellbook, got {names}")
    if (g["pc"].get("currency") or {}).get("gp") != 15:  # acolyte starting gold
        failures.append(f"strict acolyte gold should be 15 gp, got {g['pc'].get('currency')}")

    print()
    if failures:
        print("FAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("OK: strict corrections, relaxed notes, non-caster strip, and by-book gear all pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
