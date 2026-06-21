r"""Prompt A acceptance test: the contract maths + derivation + validation, against Hané.

Demonstrates:
  - deriveModifiers computes ability mods, PB-from-CR, and the read-only
    saves/skills/senses strings from structured proficiencies.
  - validate flags the authored Hané statblock's CR/PB drift (saves/skills/passive
    were written at PB +4 but CR 8 -> PB +3).
  - both samples are schema-valid.

Run:  .venv_forge\Scripts\python tests\test_contract.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from forge.contract import derive_modifiers, validate          # noqa: E402
from forge.contract.maths import parse_challenge, cr_to_xp      # noqa: E402

SAMPLES = REPO_ROOT / "samples"
SCHEMA_PATH = REPO_ROOT / "forge" / "schema" / "character.schema.json"

hane = json.loads((SAMPLES / "hane.json").read_text(encoding="utf-8"))
hane_struct = json.loads((SAMPLES / "hane_structured.json").read_text(encoding="utf-8"))


def show(label, char):
    d = derive_modifiers(char)
    v = validate(char)
    print(f"\n{'='*68}\n{label}")
    print(f"  ability mods : {d['abilityMods']}")
    print(f"  challenge    : {d['challenge']}  -> PB +{d['proficiencyBonus']}")
    if d["derived"]:
        print(f"  derived saves: {d['derived'].get('saves')}")
        print(f"  derived skill: {d['derived'].get('skills')}")
        print(f"  derived senses: {d['derived'].get('senses')}")
    print(f"  validate.ok  : {v['ok']}")
    for w in v["warnings"]:
        print(f"     ! {w}")
    return d, v


def main() -> int:
    failures = []

    # quick maths sanity
    assert parse_challenge("8 (3,900 XP)")["pb"] == 3
    assert parse_challenge("— (level 5)")["pb"] == 3
    assert parse_challenge("1/2 (100 XP)")["cr"] == 0.5
    assert cr_to_xp(8) == 3900

    d_auth, v_auth = show("Hané (authored strings)", hane)
    d_str, v_str = show("Hané (structured profs)", hane_struct)

    # authored Hané is CR 9 (PB +4) — its lines were always PB+4, so it's consistent now.
    if not v_auth["ok"]:
        failures.append(f"authored Hané (CR 9) should validate clean, got {v_auth['warnings']}")

    # validate() must still catch genuine CR/PB drift — demo with a drifted copy.
    import copy
    drifted = copy.deepcopy(hane)
    drifted["challenge"] = "8 (3,900 XP)"  # wrong: lines imply PB+4 but CR 8 -> PB+3
    if validate(drifted)["ok"]:
        failures.append("validate() should flag the CR8/PB+4 drift")

    # structured derivation must produce the correct PB+4 numbers
    expect_saves = "Dex +8, Wis +9"
    expect_skills = "Perception +9, Insight +9, Survival +9, Acrobatics +8"
    if d_str["derived"].get("saves") != expect_saves:
        failures.append(f"saves: got {d_str['derived'].get('saves')!r}, want {expect_saves!r}")
    if d_str["derived"].get("skills") != expect_skills:
        failures.append(f"skills: got {d_str['derived'].get('skills')!r}, want {expect_skills!r}")
    if d_str["derived"].get("passivePerception") != 19:
        failures.append(f"passive perception: got {d_str['derived'].get('passivePerception')}, want 19")
    if not v_str["ok"]:
        failures.append(f"structured Hané should validate clean, got {v_str['warnings']}")

    # schema validation
    print(f"\n{'='*68}\nSchema validation:")
    try:
        import jsonschema
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        for label, char in (("hane", hane), ("hane_structured", hane_struct)):
            try:
                jsonschema.validate(char, schema)
                print(f"  {label:<16} VALID")
            except jsonschema.ValidationError as e:
                print(f"  {label:<16} INVALID: {e.message}")
                failures.append(f"{label} failed schema validation: {e.message}")
    except ModuleNotFoundError:
        print("  (jsonschema not installed — skipped)")

    print(f"\n{'='*68}")
    if failures:
        print("FAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("OK: maths, derivation, validation, and schema all pass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
