r"""Prompt B test: the auto-fill assembly path, exercised with a FAKE model.

No API key needed — a canned "LLM output" stands in for the real Claude call, so
this verifies everything the engine owns: id/schemaVersion/portraits injection,
engine-derived saves/skills/senses, and contract validity. A real end-to-end call
is a separate manual check once ANTHROPIC_API_KEY is set (see bottom).

Run:  .venv_forge\Scripts\python tests\test_autofill.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from forge.agents import autofill                       # noqa: E402
from forge.agents.autofill import FIXED_PORTRAIT_STATES  # noqa: E402

SCHEMA_PATH = REPO_ROOT / "forge" / "schema" / "character.schema.json"

# What a well-behaved model would return for "a spooky sea hag..." at CR 5 (PB +3).
# WIS 16 (+3): Wis save +6; Perception +6; passive Perception 16. DEX 14 (+2): Stealth +5.
FAKE_RAW = {
    "ruleset": "dnd5e-2014", "kind": "monster",
    "name": "Gloomtide Hag", "size": "Medium", "type": "fey", "alignment": "Neutral Evil",
    "flavour": "A barnacle-crusted crone who trades in drowned secrets.",
    "ac": "15 (natural armor)", "hp": "85 (10d8 + 40)", "speed": "30 ft., swim 40 ft.",
    "abilities": {"STR": 16, "DEX": 14, "CON": 18, "INT": 13, "WIS": 16, "CHA": 15},
    "saveProfs": ["WIS"],
    "skillProfs": [{"skill": "Perception", "expertise": False},
                   {"skill": "Stealth", "expertise": False}],
    "resist": "cold", "condImm": "", "languages": "Aquan, Common, Sylvan",
    "challenge": "5 (1,800 XP)",
    "traits": [{"name": "Amphibious", "text": "The hag can breathe air and water."}],
    "actions": [{"name": "Claw", "text": "Melee Weapon Attack: +6 to hit, reach 5 ft., one target. Hit: 10 (2d6 + 3) slashing damage."}],
    "reactions": [],
    "dump": "A spooky sea hag who hoards the secrets of the drowned.",
    "art": {"appearance": "Barnacle-crusted green skin, milky eyes",
            "outfit": "Tattered kelp shawl", "pose": "Beckoning from the shallows",
            "environment": "Foggy tidal flats at dusk", "personality": "Sly, patient, cruel",
            "style": "Moody painterly fantasy"},
}


def fake_model(system: str, user: str) -> dict:
    assert "RULESET: dnd5e-2014" in user
    assert "BRAIN DUMP:" in user
    return dict(FAKE_RAW)


def main() -> int:
    failures = []
    res = autofill("a spooky sea hag who collects drowned secrets", model=fake_model)
    char = res["character"]

    print("Assembled character (key fields):")
    print(f"  id            : {char.get('id')}")
    print(f"  schemaVersion : {char.get('schemaVersion')}")
    print(f"  name/type/CR  : {char['name']} | {char['type']} | {char['challenge']}")
    print(f"  derived saves : {char.get('saves')}")
    print(f"  derived skills: {char.get('skills')}")
    print(f"  derived senses: {char.get('senses')}")
    print(f"  portraits     : {list(char.get('portraits', {}))}")
    print(f"  warnings      : {res['warnings']}")

    # engine-owned assembly
    if char.get("id") != "gloomtide-hag":
        failures.append(f"id: got {char.get('id')!r}")
    if char.get("schemaVersion") != 1:
        failures.append("schemaVersion should be 1")
    if set(char.get("portraits", {})) != set(FIXED_PORTRAIT_STATES):
        failures.append("portraits must have exactly the four fixed states")

    # engine-derived proficiency strings (CR 5 -> PB +3)
    if char.get("saves") != "Wis +6":
        failures.append(f"saves: got {char.get('saves')!r}, want 'Wis +6'")
    if char.get("skills") != "Perception +6, Stealth +5":
        failures.append(f"skills: got {char.get('skills')!r}")
    if char.get("senses") != "passive Perception 16":
        failures.append(f"senses: got {char.get('senses')!r}")
    if res["warnings"]:
        failures.append(f"expected no warnings, got {res['warnings']}")

    # full contract validity
    print("\nSchema validation:")
    try:
        import jsonschema
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(char, schema)
            print("  contract VALID")
        except jsonschema.ValidationError as e:
            print(f"  contract INVALID: {e.message}")
            failures.append(f"contract validation: {e.message}")
    except ModuleNotFoundError:
        print("  (jsonschema not installed — skipped)")

    print()
    if failures:
        print("FAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("OK: auto-fill assembly, engine-derived strings, and contract validity all pass.")
    print("\n(For a real end-to-end run: set ANTHROPIC_API_KEY in .env, then call")
    print(" autofill('<brain dump>') with no `model=` argument.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
