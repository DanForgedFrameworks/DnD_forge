"""Prompt B — the auto-fill agent: brain-dump -> canonical Character JSON.

`autofill(brain_dump, ...)` returns {"character": <Character>, "warnings": [...]}.

The LLM authors choices + statblock prose + art fields; the engine then derives
the saves/skills/senses strings (so the numbers are internally consistent) and
runs validate(). The `model` parameter is a callable(system, user) -> dict (the raw
LLM character) — defaults to the real Claude client; inject a fake to test without
an API key.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..contract import derive_modifiers, validate
from .output_schema import AUTOFILL_OUTPUT_SCHEMA

_SYSTEM = (Path(__file__).resolve().parent / "specs" / "autofill_system.txt").read_text(
    encoding="utf-8"
)

FIXED_PORTRAIT_STATES = ("at-rest", "in-conversation", "in-battle", "travelling")


def autofill(
    brain_dump: str,
    *,
    ruleset: str = "dnd5e-2014",
    kind: str | None = None,
    docx_text: str | None = None,
    model=None,
) -> dict:
    call = model or _default_model_call
    user = _build_user_prompt(brain_dump, ruleset=ruleset, kind=kind, docx_text=docx_text)
    raw = call(_SYSTEM, user)
    character = _assemble(raw, ruleset=ruleset, kind=kind)
    return {"character": character, "warnings": validate(character)["warnings"]}


def _default_model_call(system: str, user: str) -> dict:
    from ..llm import LLMClient  # lazy: only needed for a real run

    return LLMClient().complete_json(system, user, AUTOFILL_OUTPUT_SCHEMA)


def _build_user_prompt(brain_dump, *, ruleset, kind, docx_text) -> str:
    parts = [f"RULESET: {ruleset}"]
    if kind:
        parts.append(f"KIND (intended): {kind}")
    parts.append("\nBRAIN DUMP:\n" + (brain_dump or "").strip())
    if docx_text:
        parts.append("\nUPLOADED DOCUMENT (extracted text):\n" + docx_text.strip())
    return "\n".join(parts)


def _assemble(raw: dict, *, ruleset, kind) -> dict:
    """Turn the LLM's authored subset into a full, contract-shaped Character."""
    character = dict(raw)
    character.setdefault("ruleset", ruleset)
    if kind:
        character["kind"] = kind
    character.setdefault("kind", "monster")
    character["schemaVersion"] = 1
    character["id"] = _slug(character.get("name"))

    # The engine owns the derived proficiency strings — overwrite whatever prose
    # the model may have produced so the displayed numbers can't drift.
    derived = derive_modifiers(character).get("derived", {})
    for field in ("saves", "skills", "senses"):
        if derived.get(field):
            character[field] = derived[field]

    # Fixed four portrait states; prompts are filled later by the art stage.
    character.setdefault(
        "portraits",
        {s: {"prompt": None, "imageUrl": None, "seed": None} for s in FIXED_PORTRAIT_STATES},
    )
    return character


def _slug(name: str | None) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "creature").lower()).strip("-")
    return s or "creature"
