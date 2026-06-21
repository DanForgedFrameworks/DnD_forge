r"""Prompt C test: build_prompt matches the authoritative computePrompt() byte-for-byte.

Uses the stub backend (no image API). Checks the per-state act/cam/envPrefix triple,
clean() handling, the closing-quote-after-suffix wrap, opt-in cues, and that
generate_portrait writes {prompt, imageUrl, seed} with a usable <img src> URL.

Run:  .venv_forge\Scripts\python tests\test_art.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from forge.agents.art import (                              # noqa: E402
    build_prompt, generate_portrait, stub_backend, FIXED_TAIL, FIXED_PORTRAIT_STATES,
)

char = json.loads((REPO_ROOT / "samples" / "hane_structured.json").read_text(encoding="utf-8"))
NAME = char["name"]

# the authoritative in-battle prompt, assembled by hand from the spec
EXPECTED_BATTLE = (
    "“Medium Wind-Kin (Path-Keeper) — a Dungeons & Dragons monster named “" + NAME + "”. "
    "Anthropomorphic falcon, slate-grey and cream plumage, amber eyes. "
    "wearing Layered blue travelling robes, rope belts. "
    "characteristic pose: Hovering, wings spread. "
    "in the thick of combat, caught mid-action with real weight and motion; "
    "dramatic low angle, harsh rim light, dust and embers, high tension. "
    "amid the chaos and wreckage of Above misty island peaks, soft daylight, a high-fantasy world. "
    "mood: Calm, watchful, never still. "
    "Painterly high fantasy, soft natural light. "
    + FIXED_TAIL + ". — in battle variant.”"
)


def main() -> int:
    failures = []

    for state in FIXED_PORTRAIT_STATES:
        if build_prompt(char, state) != build_prompt(char, state):
            failures.append(f"{state}: not deterministic")

    battle = build_prompt(char, "in-battle")
    print("=" * 78)
    print("build_prompt(Hané, 'in-battle'):\n")
    print(battle)
    print("=" * 78)

    if battle != EXPECTED_BATTLE:
        failures.append("in-battle prompt does NOT match the authoritative assembly byte-for-byte")
        # show first divergence to aid debugging
        for i, (a, b) in enumerate(zip(battle, EXPECTED_BATTLE)):
            if a != b:
                print(f"  first diff at index {i}: got {battle[i:i+30]!r} vs {EXPECTED_BATTLE[i:i+30]!r}")
                break

    # opt-in cues append OUTSIDE the closing quote (base stays byte-identical)
    with_cues = build_prompt(char, "in-battle", include_cues=True)
    if not with_cues.startswith(battle):
        failures.append("include_cues should append AFTER the base, leaving it unchanged")
    if "airborne" not in with_cues.lower():
        failures.append("include_cues should add the flying motif for a flyer")

    # generate_portrait writes a usable <img src> URL + persists bytes
    cid = char["id"]
    for state in FIXED_PORTRAIT_STATES:
        slot = generate_portrait(char, state, backend=stub_backend)
        if slot["imageUrl"] != f"http://localhost:5000/art/{cid}/{state}.png":
            failures.append(f"{state}: bad imageUrl {slot['imageUrl']!r}")
        if not (REPO_ROOT / "output" / "portraits" / cid / f"{state}.png").exists():
            failures.append(f"{state}: image not saved")

    tweaked = generate_portrait(char, "at-rest", adjustment="warmer palette, dawn light",
                                seed=42, backend=stub_backend)
    if tweaked["seed"] != 42:
        failures.append(f"seed not round-tripped: {tweaked['seed']}")
    if "Adjustment: warmer palette, dawn light" not in tweaked["prompt"]:
        failures.append("adjustment not appended")

    print("\nimageUrl example:", char["portraits"]["in-battle"]["imageUrl"])
    print()
    if failures:
        print("FAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("OK: build_prompt matches computePrompt byte-for-byte; cues opt-in; URLs usable.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
