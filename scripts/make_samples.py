"""Emit real sample character JSONs into samples/ — the shared contract artifact.

Hand these (plus forge/schema/character.schema.json) to the design side so the sheet
is built against the exact shape the generator emits.

Run:  python scripts/make_samples.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from forge.canon import SRDRepository                 # noqa: E402
from forge.engine import build_character              # noqa: E402
from forge.engine.derive import class_skill_choice    # noqa: E402

DATA_ROOT = REPO_ROOT / "data" / "srd"
OUT_DIR = REPO_ROOT / "samples"

repo2014 = SRDRepository("2014", data_root=DATA_ROOT)
repo2024 = SRDRepository("2024", data_root=DATA_ROOT)


def auto_skills(repo, class_index):
    cls = repo.get("classes", class_index)
    choice = class_skill_choice(cls)
    if not choice:
        return []
    n, allowed = choice
    return sorted(allowed)[:n]


SAMPLES = [
    ("sample_2014_fighter.json", repo2014, repo2014, {
        "ruleset": "2014", "name": "Bran the Steady", "species": "human", "class": "fighter",
        "level": 3, "background": "acolyte", "alignment": "Lawful Neutral",
        "ability_method": "standard_array",
        "ability_scores": {"str": 15, "dex": 13, "con": 14, "int": 10, "wis": 12, "cha": 8},
        "skill_proficiencies": auto_skills(repo2014, "fighter"),
    }),
    ("sample_2014_wizard.json", repo2014, repo2014, {
        "ruleset": "2014", "name": "Maelith Dawnwhisper", "species": "elf", "class": "wizard",
        "level": 5, "background": "acolyte", "alignment": "Neutral Good",
        "ability_method": "point_buy",
        "ability_scores": {"str": 8, "dex": 14, "con": 13, "int": 15, "wis": 12, "cha": 10},
        "skill_proficiencies": auto_skills(repo2014, "wizard"),
    }),
    ("sample_2024_wizard.json", repo2024, repo2014, {
        "ruleset": "2024", "name": "Sable Quill", "species": "human", "class": "wizard",
        "level": 5, "background": "acolyte", "alignment": "Chaotic Good",
        "ability_method": "manual",
        "ability_scores": {"str": 8, "dex": 14, "con": 13, "int": 15, "wis": 12, "cha": 10},
        "ability_allocation_2024": {"int": 2, "wis": 1},
        "skill_proficiencies": auto_skills(repo2024, "wizard"),
    }),
]


def main() -> int:
    OUT_DIR.mkdir(exist_ok=True)
    for filename, repo, levels_repo, intent in SAMPLES:
        char = build_character(intent, repo, levels_repo=levels_repo, class_repo=repo2014)
        path = OUT_DIR / filename
        path.write_text(json.dumps(char, indent=2), encoding="utf-8")
        print(f"wrote {path}  ({len(char['legality_issues'])} legality issues)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
