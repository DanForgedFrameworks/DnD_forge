r"""Prompt E test (ruleset abstraction) + the two PC contract additions.

Covers: load 2014/2024, Race↔Species label flip, ASI source, 2024 initiative line,
homebrew `extends` inheritance (base + patch), unknown-slug fallback, SRD-derived
option lists; plus initiative / spell DC / spell attack derivation and the PC art
subject framing. No API needed.

Run:  .venv_forge\Scripts\python tests\test_ruleset.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from forge.ruleset import Ruleset, load_ruleset                # noqa: E402
from forge.contract import derive_modifiers, apply_derived     # noqa: E402
from forge.agents.art import build_prompt                      # noqa: E402

pc_char = json.loads((REPO_ROOT / "samples" / "sample_pc.json").read_text(encoding="utf-8"))


def main() -> int:
    failures = []

    # --- ruleset configs ----------------------------------------------------
    r2014 = Ruleset("dnd5e-2014")
    r2024 = Ruleset("dnd5e-2024")
    if r2014.labels.get("species") != "Race":
        failures.append("2014 should label species 'Race'")
    if r2024.labels.get("species") != "Species":
        failures.append("2024 should label species 'Species'")
    if r2014.ability_rules.get("asiSource") != "species":
        failures.append("2014 ASI source should be species")
    if r2024.ability_rules.get("asiSource") != "background":
        failures.append("2024 ASI source should be background")
    if r2024.statblock.get("showInitiativeLine") is not True:
        failures.append("2024 statblock should show the initiative line")

    # --- inheritance (base + patch) ----------------------------------------
    hb = Ruleset("homebrew-grimdark")
    if hb.labels.get("species") != "Bloodline":
        failures.append("homebrew override (species label) not applied")
    if hb.ability_rules.get("pointBuyBudget") != 32:
        failures.append("homebrew override (point-buy budget) not applied")
    if hb.ability_rules.get("asiSource") != "species":
        failures.append("homebrew should INHERIT asiSource from dnd5e-2014")
    if hb.config.get("srdEdition") != "2014":
        failures.append("homebrew should inherit srdEdition 2014")

    # --- unknown slug falls back to 2014 -----------------------------------
    fb = load_ruleset("totally-made-up")
    if fb.get("slug") != "dnd5e-2014":
        failures.append(f"unknown slug should fall back to 2014, got {fb.get('slug')}")

    # --- option lists derived from SRD -------------------------------------
    opts = r2014.option_lists()
    print(f"2014 option lists: {len(opts['classes'])} classes, {len(opts['species'])} species, "
          f"{len(opts['backgrounds'])} backgrounds, {len(opts['feats'])} feats, "
          f"{len(opts['conditions'])} conditions, {len(opts['sizes'])} sizes")
    if len(opts["classes"]) != 12:
        failures.append(f"expected 12 classes, got {len(opts['classes'])}")
    if len(opts["sizes"]) != 6 or len(opts["creatureTypes"]) != 14:
        failures.append("fixed size/creature-type lists wrong")
    if not opts["subclassesByClass"].get("wizard"):
        failures.append("subclassesByClass should include wizard subclasses")

    # --- PC maths (initiative, spell DC/attack) ----------------------------
    d = derive_modifiers(pc_char)["derived"]
    print(f"\nPC derived: initiative {d.get('initiative')}, "
          f"spell {d.get('spellcasting')}")
    if d.get("initiative") != 2:  # DEX 14 -> +2
        failures.append(f"initiative should be +2, got {d.get('initiative')}")
    if d.get("spellcasting", {}).get("saveDc") != 14:  # 8 + PB3 + INT+3
        failures.append(f"spell save DC should be 14, got {d.get('spellcasting')}")
    if d.get("spellcasting", {}).get("attackBonus") != 6:  # PB3 + INT+3
        failures.append(f"spell attack should be +6, got {d.get('spellcasting')}")

    # apply_derived writes DC/attack back onto the character
    apply_derived(pc_char)
    if pc_char["spellcasting"]["saveDc"] != 14 or pc_char["spellcasting"]["attackBonus"] != 6:
        failures.append("apply_derived did not write spellcasting DC/attack back")

    # --- PC art subject framing (pulls from pc{}) --------------------------
    subj = build_prompt(pc_char, "in-battle")
    print("\nPC art subject:", subj.split(". ")[0])
    if "a Dungeons & Dragons player character, a High-Elf Wizard (Evocation) named" not in subj:
        failures.append("PC art subject framing should pull TitleCase species/class/subclass from pc{}")

    print()
    if failures:
        print("FAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("OK: ruleset config + inheritance + fallback + option lists + PC maths + PC art framing all pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
