"""Live auto-fill run: a real brain-dump -> Character JSON via Claude.

Needs ANTHROPIC_API_KEY in .env. Saves the result to samples/live_<id>.json.

Usage:
    python scripts/run_autofill.py "a grumpy one-eyed dwarf monster-hunter ..."
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from forge.agents import autofill  # noqa: E402

DEFAULT_DUMP = (
    "A grizzled dwarf blacksmith turned monster-hunter, missing one eye, carries a "
    "rune-etched warhammer that hums near the undead, gruff but secretly kind, drinks "
    "too much ale, walks with a limp from an old wyvern fight. Tough as old boots."
)


def main() -> int:
    dump = " ".join(sys.argv[1:]).strip() or DEFAULT_DUMP
    res = autofill(dump, ruleset="dnd5e-2014", kind="npc")
    char = res["character"]
    print(json.dumps(char, indent=2, ensure_ascii=False))
    print("\nWARNINGS:", res["warnings"] or "(none)")
    out = REPO / "samples" / f"live_{char['id']}.json"
    out.write_text(json.dumps(char, indent=2, ensure_ascii=False), encoding="utf-8")
    print("saved:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
