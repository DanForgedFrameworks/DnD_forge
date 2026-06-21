"""Resolve a PC's granted proficiencies from class + background (engine disposes).

The front-end / LLM supplies only the *choices* a player makes — `pc.class`,
`pc.background`, and `pc.skillChoices` (the N class-skill picks). The engine fills the
rest deterministically from the ruleset's enriched option lists, so `saveProfs`,
`skillProfs`, and `pc.proficiencies` can never drift from the rules.

`resolve_pc_proficiencies(character)` mutates the character in place and returns it.
It is a no-op unless the character is a PC (`kind == "character"` with a `pc.class`),
so it is safe to call on every `POST /character` and inside the PC forge path.
"""
from __future__ import annotations

from ..ruleset import Ruleset


def _humanize(index: str) -> str:
    return " ".join(w.capitalize() for w in (index or "").split("-")) or index


def resolve_pc_proficiencies(character: dict) -> dict:
    pc = character.get("pc")
    if character.get("kind") != "character" or not isinstance(pc, dict) or not pc.get("class"):
        return character

    rs = Ruleset(character.get("ruleset") or "dnd5e-2014")
    opts = rs.option_lists()
    skill_names = rs.skill_names()

    cls = next((c for c in opts["classes"] if c["index"] == pc.get("class")), None)
    bg = next((b for b in opts["backgrounds"] if b["index"] == pc.get("background")), None)

    # --- saving throws: granted by class ------------------------------------
    if cls:
        character["saveProfs"] = list(cls.get("saves") or [])

    # --- skills: the player's class picks + the background's fixed grants -----
    skill_indices: list[str] = []
    for idx in (pc.get("skillChoices") or []):
        if idx not in skill_indices:
            skill_indices.append(idx)
    for idx in ((bg or {}).get("skills") or []):
        if idx not in skill_indices:
            skill_indices.append(idx)
    if cls or bg:
        character["skillProfs"] = [
            {"skill": skill_names.get(idx, _humanize(idx)), "expertise": False}
            for idx in skill_indices
        ]

    # --- armor / weapons / tools (+ background tools & languages) -------------
    if cls or bg:
        bg_tools = [_humanize(t) for t in ((bg or {}).get("tools") or [])]
        proficiencies = {
            "armor": list((cls or {}).get("armor") or []),
            "weapons": list((cls or {}).get("weapons") or []),
            "tools": list((cls or {}).get("tools") or []) + bg_tools,
            "languages": int((bg or {}).get("languages") or 0),  # # of free background languages
        }
        # preserve any feat/manual extras already on pc.proficiencies
        existing = pc.get("proficiencies") or {}
        for k, v in existing.items():
            if k not in proficiencies and v:
                proficiencies[k] = v
        pc["proficiencies"] = proficiencies

    return character
