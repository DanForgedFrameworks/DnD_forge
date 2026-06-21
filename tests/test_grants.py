r"""Job 2 test: the engine resolves PC proficiencies from class + background grants.

The front-end sends only choices (pc.class, pc.background, pc.skillChoices); the engine
must produce saveProfs / skillProfs / pc.proficiencies deterministically. No API needed.

Run:  .venv_forge\Scripts\python tests\test_grants.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from forge.engine import resolve_pc_proficiencies   # noqa: E402


def main() -> int:
    failures = []

    # --- 2024 rogue + criminal background: class picks + background grants merge ---
    pc = {
        "kind": "character", "ruleset": "dnd5e-2024",
        "pc": {
            "class": "rogue", "background": "criminal",
            # rogue chooses 4; deliberately overlap one with the background (stealth)
            "skillChoices": ["acrobatics", "perception", "stealth", "investigation"],
        },
    }
    resolve_pc_proficiencies(pc)
    print("rogue saveProfs:", pc.get("saveProfs"))
    print("rogue skillProfs:", [s["skill"] for s in pc.get("skillProfs", [])])
    print("rogue proficiencies:", pc["pc"].get("proficiencies"))

    if pc.get("saveProfs") != ["DEX", "INT"]:
        failures.append(f"rogue saveProfs should be [DEX, INT], got {pc.get('saveProfs')}")
    skills = [s["skill"] for s in pc.get("skillProfs", [])]
    # 4 picks + criminal's {sleight-of-hand, stealth}; stealth dedups -> 5 distinct, title-cased
    if "Sleight of Hand" not in skills or "Stealth" not in skills:
        failures.append(f"background skills not merged/title-cased: {skills}")
    if skills.count("Stealth") != 1:
        failures.append(f"overlapping skill not deduped: {skills}")
    if any(s.get("expertise") for s in pc["skillProfs"]):
        failures.append("derived skillProfs should all be expertise:false")
    profs = pc["pc"]["proficiencies"]
    if profs.get("armor") != ["Light Armor"]:
        failures.append(f"rogue armor should be ['Light Armor'], got {profs.get('armor')}")
    if "Thieves Tools" not in profs.get("tools", []):
        failures.append(f"criminal's thieves' tools should land in pc.proficiencies.tools: {profs.get('tools')}")

    # --- 2014 wizard (class-only; sage background absent in 2014 SRD) ------------
    wiz = {
        "kind": "character", "ruleset": "dnd5e-2014",
        "pc": {"class": "wizard", "background": "sage", "skillChoices": ["arcana", "investigation"]},
    }
    resolve_pc_proficiencies(wiz)
    if wiz.get("saveProfs") != ["INT", "WIS"]:
        failures.append(f"wizard saveProfs should be [INT, WIS], got {wiz.get('saveProfs')}")
    if [s["skill"] for s in wiz["skillProfs"]] != ["Arcana", "Investigation"]:
        failures.append(f"wizard skills wrong: {[s['skill'] for s in wiz['skillProfs']]}")

    # --- non-PC is a strict no-op ----------------------------------------------
    monster = {"kind": "monster", "saveProfs": ["WIS"], "abilities": {}}
    before = dict(monster)
    resolve_pc_proficiencies(monster)
    if monster != before:
        failures.append("resolve_pc_proficiencies must be a no-op for non-PCs")

    print()
    if failures:
        print("FAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("OK: PC proficiency resolution (saves, skill merge/dedup, profs) + non-PC no-op pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
