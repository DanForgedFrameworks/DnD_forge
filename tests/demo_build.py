"""End-to-end demo of the deterministic rules engine.

Builds several characters from plain *intent* dicts and prints computed sheets +
legality issues. Validates each against the character JSON Schema if `jsonschema`
is installed. No LLM, no randomness.

Run:  python tests/demo_build.py        (use the venv python for schema validation)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from forge.canon import SRDRepository                      # noqa: E402
from forge.engine import build_character                   # noqa: E402
from forge.engine.abilities import ABILITIES               # noqa: E402
from forge.engine.derive import class_skill_choice         # noqa: E402

DATA_ROOT = REPO_ROOT / "data" / "srd"
# NOTE: legacy POC. `character.schema.json` is now the front-end CONTRACT shape;
# this demo exercises the internal PC builder, which validates against the v0 schema.
SCHEMA_PATH = REPO_ROOT / "forge" / "schema" / "legacy_pc_v0.schema.json"

repo2014 = SRDRepository("2014", data_root=DATA_ROOT)
repo2024 = SRDRepository("2024", data_root=DATA_ROOT)


def auto_skills(repo, class_index, n_override=None):
    """Pick the first N legal skill choices for a class (keeps demo characters legal)."""
    cls = repo.get("classes", class_index)
    choice = class_skill_choice(cls)
    if not choice:
        return []
    n, allowed = choice
    n = n_override if n_override is not None else n
    return sorted(allowed)[:n]


def summarise(label, char):
    idn = char["identity"]
    print(f"\n{'='*70}\n{label}: {idn['name']}  —  {idn['species']} {idn['class']} "
          f"L{idn['level']} ({char['meta']['ruleset']}, {char['meta']['ability_method']})")
    abil = " ".join(
        f"{a.upper()} {char['ability_scores'][a]['total']:>2}"
        f"({char['ability_scores'][a]['modifier']:+d})" for a in ABILITIES
    )
    print(f"  abilities : {abil}")
    if char["ability_bonuses_applied"]:
        bumps = ", ".join(f"{x['ability'].upper()}+{x['bonus']} ({x['source']})"
                          for x in char["ability_bonuses_applied"])
        print(f"  bonuses   : {bumps}")
    d = char["derived"]
    print(f"  PB +{d['proficiency_bonus']} | HP {d['max_hp']} ({d['hit_dice']}) | "
          f"AC {d['armor_class']} | init {d['initiative']:+d} | speed {d['speed']} | "
          f"passive perc {d['passive_perception']}")
    profs = [a.upper() for a in ABILITIES if d["saving_throws"][a]["proficient"]]
    print(f"  save profs: {', '.join(profs) or '(none)'}")
    sk = [f"{s} {d['skills'][s]['modifier']:+d}" for s in d["skills"] if d["skills"][s]["proficient"]]
    print(f"  skills    : {', '.join(sk) or '(none)'}")
    sc = char["spellcasting"]
    if sc:
        l1 = sc["slots"].get("spell_slots_level_1") if sc.get("slots") else None
        l2 = sc["slots"].get("spell_slots_level_2") if sc.get("slots") else None
        print(f"  spells    : ability {sc['spellcasting_ability']} | save DC {sc['spell_save_dc']} | "
              f"atk {sc['spell_attack_bonus']:+d} | slots L1={l1} L2={l2}")
        if sc.get("note"):
            print(f"              ({sc['note']})")
    if char["legality_issues"]:
        print("  ISSUES    :")
        for i in char["legality_issues"]:
            print(f"     - {i}")
    else:
        print("  ISSUES    : none")


# --- intents -----------------------------------------------------------------
fighter_2014 = {
    "ruleset": "2014", "name": "Bran the Steady", "species": "human", "class": "fighter",
    "level": 3, "background": "acolyte", "alignment": "Lawful Neutral",
    "ability_method": "standard_array",
    "ability_scores": {"str": 15, "dex": 13, "con": 14, "int": 10, "wis": 12, "cha": 8},
    "skill_proficiencies": auto_skills(repo2014, "fighter"),
}
wizard_2014 = {
    "ruleset": "2014", "name": "Maelith Dawnwhisper", "species": "elf", "class": "wizard",
    "level": 3, "background": "acolyte", "alignment": "Neutral Good",
    "ability_method": "point_buy",
    "ability_scores": {"str": 8, "dex": 14, "con": 13, "int": 15, "wis": 12, "cha": 10},
    "skill_proficiencies": auto_skills(repo2014, "wizard"),
}
wizard_2024 = {
    "ruleset": "2024", "name": "Sable Quill", "species": "human", "class": "wizard",
    "level": 3, "background": "acolyte", "alignment": "Chaotic Good",
    "ability_method": "manual",
    "ability_scores": {"str": 8, "dex": 14, "con": 13, "int": 15, "wis": 12, "cha": 10},
    "ability_allocation_2024": {"int": 2, "wis": 1},
    "skill_proficiencies": auto_skills(repo2024, "wizard"),
}
broken_2014 = {  # deliberately illegal — exercises the legality checker
    "ruleset": "2014", "name": "Grog (broken on purpose)", "species": "half-orc",
    "class": "barbarian", "level": 1, "background": "acolyte", "ability_method": "manual",
    "ability_scores": {"str": 16, "dex": 13, "con": 15, "int": 8, "wis": 12, "cha": 10},
    "skill_proficiencies": ["athletics", "stealth", "made-up-skill"],
}


def main() -> int:
    builds = [
        ("2014 martial   ", build_character(fighter_2014, repo2014, levels_repo=repo2014, class_repo=repo2014)),
        ("2014 caster    ", build_character(wizard_2014, repo2014, levels_repo=repo2014, class_repo=repo2014)),
        ("2024 caster    ", build_character(wizard_2024, repo2024, levels_repo=repo2014, class_repo=repo2014)),
        ("2014 INVALID   ", build_character(broken_2014, repo2014, levels_repo=repo2014, class_repo=repo2014)),
    ]
    for label, char in builds:
        summarise(label, char)

    # schema validation (optional)
    print(f"\n{'='*70}\nSchema validation:")
    try:
        import jsonschema
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        for label, char in builds:
            try:
                jsonschema.validate(char, schema)
                print(f"  {label} schema VALID")
            except jsonschema.ValidationError as e:
                print(f"  {label} schema INVALID: {e.message}")
    except ModuleNotFoundError:
        print("  (jsonschema not installed — skipped; run with the .venv_forge python)")

    # expectations: first three clean, fourth flags issues
    clean = all(not c["legality_issues"] for _, c in builds[:3])
    broken_flagged = bool(builds[3][1]["legality_issues"])
    ok = clean and broken_flagged
    print(f"\n{'OK' if ok else 'FAIL'}: valid builds clean={clean}, broken flagged={broken_flagged}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
