r"""Job 3 test: the PC auto-fill path (kind:"character") assembled with a FAKE model.

Acceptance (from the handover): forge "a kender rogue who steals everything and fears
nothing" -> kind:character, pc.class==rogue, pc{} + personality present, level-based
challenge - a PC sheet, not a CR block. Plus: homebrew grounding note, engine-applied
ASI, class-derived saves/skills, and contract validity. No API key needed.

Run:  .venv_forge\Scripts\python tests\test_autofill_pc.py
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

# A well-behaved PC model output for "a kender rogue who steals everything, fears nothing".
FAKE_PC = {
    "ruleset": "dnd5e-2014", "kind": "character",
    "name": "Pip Quickfingers", "size": "Small", "type": "humanoid (halfling)",
    "alignment": "Chaotic Good", "flavour": "A fearless kender who 'borrows' anything not nailed down.",
    "ac": "14 (leather armor)", "hp": "21 (3d8 + 6)", "speed": "25 ft.",
    "resist": "", "condImm": "", "languages": "Common, Halfling",
    "challenge": "- (level 3)",
    "traits": [
        {"name": "Sneak Attack", "text": "Once per turn, deal an extra 2d6 damage to a target you have advantage against.", "source": "class:Rogue"},
        {"name": "Brave", "text": "Advantage on saving throws against being frightened.", "source": "race:Halfling"},
    ],
    "actions": [
        {"name": "Dagger", "text": "Melee or Ranged Weapon Attack: +5 to hit, reach 5 ft. or range 20/60 ft. Hit: 1d4 + 3 piercing.", "source": "class:Rogue"},
    ],
    "reactions": [
        {"name": "Uncanny Dodge", "text": "Halve the damage from one attack you can see.", "source": "class:Rogue"},
    ],
    "dump": "A kender rogue who steals everything and fears nothing.",
    "art": {
        "appearance": "Small wiry kender, topknot of chestnut hair, bright mischievous eyes",
        "outfit": "Patchwork leather, a dozen pouches", "pose": "Mid-pickpocket, grinning",
        "environment": "A crowded fantasy market at dusk", "personality": "Fearless, curious, light-fingered",
        "style": "Painterly high fantasy",
        "stateBeats": {
            "at-rest": "cross-legged, gleefully sorting a pile of 'found' trinkets",
            "in-conversation": "leaning in close, one hand already drifting toward a pocket",
            "in-battle": "darting behind a foe to drive a dagger home",
            "travelling": "scampering ahead, peering into every roadside nook",
        },
    },
    "pc": {
        "species": "halfling", "lineage": "Kender", "subspecies": "lightfoot-halfling",
        "class": "rogue", "subclass": "thief", "level": 3, "background": "",
        "abilityMethod": "standard_array",
        "baseAbilities": {"STR": 8, "DEX": 15, "CON": 13, "INT": 12, "WIS": 10, "CHA": 14},
        "abilityAllocation2024": "",
        "skillChoices": ["stealth", "sleight-of-hand", "acrobatics", "perception"],
        "hitDice": {"die": "d8", "total": 3, "remaining": 3},
        "deathSaves": {"successes": 0, "failures": 0},
        "feats": [],
        "equipment": ["Dagger", "Dagger", "Thieves' tools", "Leather armor"],
        "currency": {"cp": 0, "sp": 0, "ep": 0, "gp": 15, "pp": 0},
        "personality": {
            "traits": ["Pockets everything that isn't bolted down"],
            "ideals": ["Curiosity - the world is full of wonderful things to handle"],
            "bonds": ["My collection of 'borrowed' treasures tells my whole life story"],
            "flaws": ["I genuinely don't understand why people get upset about it"],
        },
    },
    "spellcasting": {"ability": "", "cantrips": [], "prepared": []},
}


def fake_model(system: str, user: str) -> dict:
    assert "KIND: character" in user
    assert "VALID SRD OPTIONS" in user        # the grounding menu is injected
    assert "FLAVOUR NOTES" in user            # the optional flavour was passed through
    return json.loads(json.dumps(FAKE_PC))     # deep copy


def main() -> int:
    failures = []
    res = autofill(
        "a kender rogue who steals everything and fears nothing",
        kind="character", ruleset="dnd5e-2014",
        details="grew up on the road; a standout memory of lifting a duke's signet ring",
        model=fake_model,
    )
    char = res["character"]
    pc = char.get("pc", {})

    print(f"  kind          : {char.get('kind')}")
    print(f"  challenge     : {char.get('challenge')}")
    print(f"  pc.class      : {pc.get('class')}  lineage={pc.get('lineage')} species={pc.get('species')}")
    print(f"  abilities      : {char.get('abilities')}")
    print(f"  saveProfs     : {char.get('saveProfs')}")
    print(f"  saves/skills  : {char.get('saves')} | {char.get('skills')}")
    print(f"  proficiencies : {pc.get('proficiencies')}")
    print(f"  rulesMode     : {pc.get('rulesMode')}")
    print(f"  warnings      : {res['warnings']}")

    # --- acceptance criteria ----------------------------------------------
    if char.get("kind") != "character":
        failures.append("kind should be 'character'")
    if pc.get("class") != "rogue":
        failures.append(f"pc.class should be rogue, got {pc.get('class')}")
    if char.get("challenge") != "— (level 3)":
        failures.append(f"challenge should be '— (level 3)', got {char.get('challenge')!r}")
    if not pc.get("personality", {}).get("traits"):
        failures.append("pc.personality.traits should be present")

    # engine disposed the rules:
    if char.get("saveProfs") != ["DEX", "INT"]:
        failures.append(f"rogue saveProfs should be [DEX, INT], got {char.get('saveProfs')}")
    skills = [s["skill"] for s in char.get("skillProfs", [])]
    if "Sleight of Hand" not in skills or "Stealth" not in skills:
        failures.append(f"skillProfs not derived/title-cased: {skills}")
    # 2014 halfling species grants +2 DEX -> 15 base becomes 17 final
    if char.get("abilities", {}).get("DEX") != 17:
        failures.append(f"engine ASI should make DEX 17 (15 base +2 halfling), got {char.get('abilities',{}).get('DEX')}")
    if pc.get("rulesMode") != "relaxed":
        failures.append(f"default rulesMode should be relaxed, got {pc.get('rulesMode')}")
    if (pc.get("proficiencies") or {}).get("armor") != ["Light Armor"]:
        failures.append(f"rogue armor proficiency missing: {pc.get('proficiencies')}")
    # homebrew grounding noted
    if not any("Kender" in w["message"] for w in res["warnings"]):
        failures.append("expected a grounding note for the homebrew 'Kender' lineage")
    if set(char.get("portraits", {})) != set(FIXED_PORTRAIT_STATES):
        failures.append("portraits must have the four fixed states")

    # --- contract validity -------------------------------------------------
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
        print("  (jsonschema not installed - skipped)")

    print()
    if failures:
        print("FAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("OK: PC forge path - kind/class/level/personality + engine-disposed rules + contract valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
