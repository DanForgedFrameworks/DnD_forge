"""Prompt B — the auto-fill agent: brain-dump -> canonical Character JSON.

`autofill(brain_dump, ...)` returns {"character": <Character>, "warnings": [...]}.

Two paths, picked by `kind`:
- statblock (monster/npc/creature/companion/pet, the default): the LLM authors choices +
  statblock prose + art; the engine derives saves/skills/senses.
- PC (`kind == "character"`): the LLM authors a full player character (class/species/
  background/level, pc{}, spellcasting lists, personality, bespoke art beats); the engine
  then DISPOSES — computes final abilities (ASI), proficiencies, spell slots + save DC/
  attack, and the challenge string — and applies the chosen rules mode (strict/relaxed).

`model` is a callable(system, user) -> dict (the raw LLM character); inject a fake to test
without an API key.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..contract import derive_modifiers, validate, apply_derived
from ..ruleset import Ruleset
from ..canon import SRDRepository
from ..engine import resolve_pc_proficiencies, enforce_rules
from ..engine.abilities import apply_ability_bonuses, ABILITIES as _AB_LOWER
from ..engine.derive import spell_slots
from ..engine.rules_mode import CASTER_RULES
from .art import lock_appearance, apply_class_beats, apply_companion
from .output_schema import AUTOFILL_OUTPUT_SCHEMA

_SPEC_DIR = Path(__file__).resolve().parent / "specs"
_SYSTEM = (_SPEC_DIR / "autofill_system.txt").read_text(encoding="utf-8")
_SYSTEM_PC = (_SPEC_DIR / "autofill_pc_system.txt").read_text(encoding="utf-8")
_DATA_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "srd"

FIXED_PORTRAIT_STATES = ("at-rest", "in-conversation", "in-battle", "travelling")


def autofill(
    brain_dump: str,
    *,
    ruleset: str = "dnd5e-2014",
    kind: str | None = None,
    rules_mode: str = "relaxed",
    details: str | None = None,
    docx_text: str | None = None,
    model=None,
) -> dict:
    is_pc = kind == "character"
    if is_pc:
        user = _build_pc_user_prompt(brain_dump, ruleset=ruleset, details=details, docx_text=docx_text)
        raw = (model or _default_pc_model_call)(_SYSTEM_PC, user)
        character, extra = _assemble_pc(raw, ruleset=ruleset, rules_mode=rules_mode)
    else:
        user = _build_user_prompt(brain_dump, ruleset=ruleset, kind=kind, docx_text=docx_text)
        raw = (model or _default_model_call)(_SYSTEM, user)
        character, extra = _assemble(raw, ruleset=ruleset, kind=kind), []

    warnings = validate(character)["warnings"] + extra
    return {"character": character, "warnings": warnings}


# -- model calls (real Claude) ------------------------------------------------
def _default_model_call(system: str, user: str) -> dict:
    from ..llm import LLMClient
    return LLMClient().complete_json(system, user, AUTOFILL_OUTPUT_SCHEMA)


def _default_pc_model_call(system: str, user: str) -> dict:
    from ..llm import LLMClient
    # The PC object is too deeply nested for the strict structured-output grammar
    # compiler ('compiled grammar too large'); use loose JSON anchored by the embedded
    # template in the PC system prompt, then validate downstream.
    return LLMClient(max_tokens=16000).complete_json_loose(system, user)


# -- user prompts -------------------------------------------------------------
def _build_user_prompt(brain_dump, *, ruleset, kind, docx_text) -> str:
    parts = [f"RULESET: {ruleset}"]
    if kind:
        parts.append(f"KIND (intended): {kind}")
    parts.append("\nBRAIN DUMP:\n" + (brain_dump or "").strip())
    if docx_text:
        parts.append("\nUPLOADED DOCUMENT (extracted text):\n" + docx_text.strip())
    return "\n".join(parts)


def _build_pc_user_prompt(brain_dump, *, ruleset, details, docx_text) -> str:
    parts = [f"RULESET: {ruleset}", "KIND: character (a player character)"]
    parts.append("\nBRAIN DUMP:\n" + (brain_dump or "").strip())
    if details:
        parts.append("\nFLAVOUR NOTES (age / experience / origin / standout memories):\n" + details.strip())
    if docx_text:
        parts.append("\nUPLOADED DOCUMENT (extracted text):\n" + docx_text.strip())
    parts.append("\nVALID SRD OPTIONS (use these exact indices):\n" + _pc_options_context(ruleset))
    return "\n".join(parts)


def _pc_options_context(ruleset: str) -> str:
    """Compact menu of legal indices so the LLM grounds to real SRD options."""
    try:
        opts = Ruleset(ruleset).option_lists()
    except Exception:
        return "{}"
    ctx = {
        "classes": [
            {"index": c["index"], "skillChoose": c.get("skillChoose"), "skillFrom": c.get("skillFrom")}
            for c in opts.get("classes", [])
        ],
        "subclassesByClass": opts.get("subclassesByClass", {}),
        "species": [s["index"] for s in opts.get("species", [])],
        "subspeciesBySpecies": {
            k: [s["index"] for s in v] for k, v in opts.get("subspeciesBySpecies", {}).items()
        },
        "backgrounds": [
            {"index": b["index"], "abilityOptions": b.get("abilityOptions")}
            for b in opts.get("backgrounds", [])
        ],
    }
    return json.dumps(ctx, ensure_ascii=False)


# -- statblock assembly (unchanged behaviour) ---------------------------------
def _assemble(raw: dict, *, ruleset, kind) -> dict:
    character = dict(raw)
    character.setdefault("ruleset", ruleset)
    if kind:
        character["kind"] = kind
    character.setdefault("kind", "monster")
    character["schemaVersion"] = 1
    character["id"] = _slug(character.get("name"))

    derived = derive_modifiers(character).get("derived", {})
    for field in ("saves", "skills", "senses"):
        if derived.get(field):
            character[field] = derived[field]

    character.setdefault(
        "portraits",
        {s: {"prompt": None, "imageUrl": None, "seed": None} for s in FIXED_PORTRAIT_STATES},
    )
    # forge-time art enrichment (DATA only — keeps build_prompt == computePrompt):
    # lock an explicit, stable appearance/gender (Item 6) and class-aware beats (Item 7).
    lock_appearance(character)
    apply_companion(character)
    apply_class_beats(character)
    return character


# -- PC assembly (the engine disposes) ----------------------------------------
def _assemble_pc(raw: dict, *, ruleset, rules_mode) -> tuple[dict, list]:
    warnings: list[dict] = []
    character = dict(raw)
    character["ruleset"] = ruleset
    character["kind"] = "character"
    character["schemaVersion"] = 1
    character["id"] = _slug(character.get("name"))

    pc = dict(character.get("pc") or {})
    character["pc"] = pc
    pc["rulesMode"] = (rules_mode or "relaxed").lower()

    # The LLM emits the 2024 ASI as a compact string ("dex+2, con+1"); the contract
    # stores it as an object map {ability: bonus}. Parse once, here.
    pc["abilityAllocation2024"] = _parse_allocation(pc.get("abilityAllocation2024"))
    # Equipment authored as plain names; contract carries objects.
    pc["equipment"] = [
        {"name": e} if isinstance(e, str) else e for e in (pc.get("equipment") or [])
    ]

    # level -> challenge
    level = max(1, min(20, int(pc.get("level") or 3)))
    pc["level"] = level
    character["challenge"] = f"— (level {level})"

    edition = Ruleset(ruleset).config.get("srdEdition", "2014")
    repo = SRDRepository(edition, data_root=_DATA_ROOT)

    # homebrew grounding note
    if pc.get("lineage"):
        warnings.append({"level": "info",
                         "message": f"'{pc['lineage']}' grounded to SRD species '{pc.get('species')}' for the rules"})

    # final abilities via the edition ASI (engine disposes); fall back to LLM's abilities
    character["abilities"] = _final_abilities(raw, pc, edition, repo, warnings)

    # spellcasting: ability + slots from the edition-native level tables
    _resolve_pc_spellcasting(character, pc, level, warnings, edition)

    # proficiencies from class + background; then rules-mode enforcement
    resolve_pc_proficiencies(character)
    warnings.extend(enforce_rules(character))

    # derived strings (saves/skills/senses) + spell save DC / attack
    apply_derived(character)

    character.setdefault(
        "portraits",
        {s: {"prompt": None, "imageUrl": None, "seed": None} for s in FIXED_PORTRAIT_STATES},
    )
    # forge-time art enrichment (DATA only — keeps build_prompt == computePrompt):
    # lock an explicit, stable appearance/gender (Item 6) and class-aware beats (Item 7).
    lock_appearance(character)
    apply_companion(character)
    apply_class_beats(character)
    return character, warnings


def _parse_allocation(value) -> dict:
    """'dex+2, con+1' (or an already-parsed map) -> {'dex': 2, 'con': 1}."""
    if isinstance(value, dict):
        return {str(k).lower(): int(v) for k, v in value.items()}
    out: dict[str, int] = {}
    for token in re.findall(r"([A-Za-z]{3})\s*\+?\s*(\d+)", str(value or "")):
        out[token[0].lower()] = int(token[1])
    return out


def _final_abilities(raw, pc, edition, repo, warnings) -> dict:
    """Compute final ability scores from baseAbilities + edition ASI. Robust fallback."""
    base_u = pc.get("baseAbilities") or {}
    base_only = {a.upper(): int(base_u.get(a.upper(), 10)) for a in _AB_LOWER}
    if not pc.get("baseAbilities"):
        return base_only
    try:
        base = {a: int(base_u[a.upper()]) for a in _AB_LOWER}
        species = repo.get("species", pc.get("species")) if edition == "2014" else None
        background = repo.get("backgrounds", pc.get("background")) if edition == "2024" else None
        alloc = dict(pc.get("abilityAllocation2024") or {})  # already {ability: bonus}
        final, _applied = apply_ability_bonuses(
            base, edition=edition, species=species, background=background,
            allocation_2024=alloc or None,
        )
        return {a.upper(): final[a] for a in _AB_LOWER}
    except Exception as e:  # never 500 on a fragile allocation — keep the base scores
        warnings.append({"level": "warning", "message": f"could not apply ability bonuses ({e}); using base scores"})
        return base_only


def _resolve_pc_spellcasting(character, pc, level, warnings, edition="2014") -> None:
    sc = character.get("spellcasting")
    class_index = pc.get("class")
    if class_index not in CASTER_RULES:
        return  # non-caster: leave whatever the LLM authored to enforce_rules
    if not isinstance(sc, dict):
        sc = {}
        character["spellcasting"] = sc
    sc.setdefault("ability", CASTER_RULES[class_index]["ability"])
    if not sc.get("ability"):
        sc["ability"] = CASTER_RULES[class_index]["ability"]

    levels_repo = SRDRepository(edition, data_root=_DATA_ROOT)  # edition-native spell/slot tables
    block = spell_slots(levels_repo, class_index, level) or {}
    slots = {}
    for n in range(1, 10):
        total = int(block.get(f"spell_slots_level_{n}", 0) or 0)
        if total > 0:
            slots[str(n)] = {"total": total, "expended": 0}
    if slots:
        sc["slots"] = slots
    elif "slots" not in sc:
        sc["slots"] = {}


def _slug(name: str | None) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "creature").lower()).strip("-")
    return s or "creature"
