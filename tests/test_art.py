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

import copy                                                  # noqa: E402

from forge.agents.art import (                              # noqa: E402
    build_prompt, generate_portrait, generate_portrait_set, stub_backend,
    lock_appearance, apply_class_beats, apply_companion, CLASS_STATE_BEATS,
    FIXED_TAIL, FIXED_PORTRAIT_STATES,
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


def test_portrait_set() -> list:
    """generate_portrait_set writes 4 PNGs, fills 4 slots; only the anchor is
    unconditioned, the other three receive the anchor's bytes as reference_image."""
    fails: list[str] = []
    c = copy.deepcopy(char)
    c["id"] = "spy-set"

    refs = []  # reference_image passed to each backend call, in order

    def spy(prompt, seed=None, *, reference_image=None, master_image=None):
        refs.append(reference_image)
        return stub_backend(prompt, seed)

    portraits = generate_portrait_set(c, backend=spy)

    for state in FIXED_PORTRAIT_STATES:
        slot = portraits.get(state) or {}
        if not slot.get("imageUrl"):
            fails.append(f"set: {state} slot not populated")
        if not (REPO_ROOT / "output" / "portraits" / "spy-set" / f"{state}.png").exists():
            fails.append(f"set: {state} png not written")

    if len(refs) != 4:
        fails.append(f"set: expected 4 backend calls, got {len(refs)}")
    if len([r for r in refs if r is None]) != 1:
        fails.append("set: the anchor should be the only unconditioned call")
    if len([r for r in refs if r is not None]) != 3:
        fails.append("set: the 3 non-anchor calls must each receive a reference_image")
    return fails


def test_class_beats() -> list:
    """apply_class_beats fills rogue beats; leaves pre-set beats and no-class chars alone."""
    fails: list[str] = []

    rogue = {"name": "Sly", "kind": "character", "pc": {"class": "rogue"}, "art": {}}
    apply_class_beats(rogue)
    sb = (rogue.get("art") or {}).get("stateBeats") or {}
    if sb.get("in-battle") != CLASS_STATE_BEATS["rogue"]["in-battle"]:
        fails.append("class beats: rogue in-battle beat not applied")
    if set(sb) != set(FIXED_PORTRAIT_STATES):
        fails.append("class beats: rogue should receive all four state beats")
    # the rogue beat must actually flow through build_prompt's {action} clause
    if CLASS_STATE_BEATS["rogue"]["in-battle"].split(",")[0] not in build_prompt(rogue, "in-battle"):
        fails.append("class beats: rogue beat should appear in build_prompt output")

    preset = {"name": "X", "kind": "character", "pc": {"class": "rogue"},
              "art": {"stateBeats": {"at-rest": "custom beat"}}}
    apply_class_beats(preset)
    if preset["art"]["stateBeats"] != {"at-rest": "custom beat"}:
        fails.append("class beats: a pre-set art.stateBeats must be left untouched")

    # byte-for-byte invariant: apply_class_beats on a no-class character changes nothing
    c = copy.deepcopy(char)
    before = build_prompt(c, "in-battle")
    apply_class_beats(c)  # monster, no class -> no-op
    after = build_prompt(c, "in-battle")
    if before != after or after != EXPECTED_BATTLE:
        fails.append("class beats: build_prompt must stay byte-for-byte for a no-class character")
    return fails


def test_lock_appearance() -> list:
    """lock_appearance makes gender explicit + stable, is idempotent, and leaves
    genderless creatures untouched."""
    fails: list[str] = []

    pc = {"name": "A", "kind": "character", "art": {"appearance": "tall, scarred"}}
    lock_appearance(pc)
    if pc["art"].get("gender") != "androgynous":
        fails.append("lock: a PC with no gender should default to androgynous")
    if "androgynous" not in pc["art"]["appearance"].lower():
        fails.append("lock: the gender clause should be prepended to appearance")

    g = {"name": "B", "kind": "character", "art": {"appearance": "a stern woman with grey eyes"}}
    lock_appearance(g)
    first = g["art"]["appearance"]
    lock_appearance(g)  # idempotent
    if g["art"].get("gender") != "female":
        fails.append("lock: should detect female from the prose")
    if g["art"]["appearance"] != first:
        fails.append("lock: should be idempotent (no double-prepend)")

    m = {"name": "C", "kind": "monster", "art": {"appearance": "a hulking stone golem"}}
    lock_appearance(m)
    if m["art"]["appearance"] != "a hulking stone golem":
        fails.append("lock: a creature with no gender signal should be left untouched")
    return fails


def test_companion() -> list:
    """apply_companion weaves art.companion into appearance so it appears in EVERY state,
    is idempotent, and is a no-op without a companion."""
    fails: list[str] = []

    c = {"name": "R", "kind": "character", "pc": {"class": "ranger"},
         "art": {"appearance": "a lean half-elf woman", "companion": "a large grey wolf"}}
    apply_companion(c)
    first = c["art"]["appearance"]
    if "grey wolf" not in first.lower():
        fails.append("companion: should be woven into appearance")
    # appears in every state because appearance is in every prompt
    for state in FIXED_PORTRAIT_STATES:
        if "grey wolf" not in build_prompt(c, state).lower():
            fails.append(f"companion: should appear in {state} prompt")
    apply_companion(c)  # idempotent
    if c["art"]["appearance"] != first:
        fails.append("companion: should be idempotent (no double-weave)")

    nob = {"name": "N", "kind": "character", "art": {"appearance": "a stout dwarf"}}
    apply_companion(nob)
    if nob["art"]["appearance"] != "a stout dwarf":
        fails.append("companion: no-op when art.companion is unset")
    return fails


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

    # Item 6 + 7 acceptance: portrait set, class beats, appearance/gender lock
    failures += test_portrait_set()
    failures += test_class_beats()
    failures += test_lock_appearance()
    failures += test_companion()

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
