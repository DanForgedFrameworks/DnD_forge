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

# PHB multiclassing proficiency grants — the REDUCED set a class hands a character when
# taken as a SECONDARY class (no saving throws, usually no skills). Labels match the
# ruleset option-list strings ("Light Armor", "Simple Weapons", "Thieves' Tools", ...).
# Classes that grant nothing on multiclass (sorcerer, wizard) are simply absent.
MULTICLASS_PROFICIENCIES: dict[str, dict] = {
    "barbarian": {"armor": ["Shields"], "weapons": ["Simple Weapons", "Martial Weapons"]},
    "bard":      {"armor": ["Light Armor"]},
    "cleric":    {"armor": ["Light Armor", "Medium Armor", "Shields"]},
    "druid":     {"armor": ["Light Armor", "Medium Armor", "Shields"]},
    "fighter":   {"armor": ["Light Armor", "Medium Armor", "Shields"],
                  "weapons": ["Simple Weapons", "Martial Weapons"]},
    "monk":      {"weapons": ["Simple Weapons", "Shortswords"]},
    "paladin":   {"armor": ["Light Armor", "Medium Armor", "Shields"],
                  "weapons": ["Simple Weapons", "Martial Weapons"]},
    "ranger":    {"armor": ["Light Armor", "Medium Armor", "Shields"],
                  "weapons": ["Simple Weapons", "Martial Weapons"]},
    "rogue":     {"armor": ["Light Armor"], "tools": ["Thieves' Tools"]},
    "warlock":   {"armor": ["Light Armor"], "weapons": ["Simple Weapons"]},
}


def _humanize(index: str) -> str:
    return " ".join(w.capitalize() for w in (index or "").split("-")) or index


def _merge_unique(target: list, extras) -> list:
    for v in extras or []:
        if v and v not in target:
            target.append(v)
    return target


def _class_list(pc: dict) -> list[dict]:
    """The effective class mix: pc.classes (2+) or a single entry from pc.class."""
    classes = pc.get("classes")
    if isinstance(classes, list) and any((c or {}).get("class") for c in classes):
        return [c for c in classes if (c or {}).get("class")]
    return [{"class": pc.get("class"), "subclass": pc.get("subclass"), "level": pc.get("level")}]


def resolve_pc_proficiencies(character: dict) -> dict:
    pc = character.get("pc")
    if character.get("kind") != "character" or not isinstance(pc, dict) or not pc.get("class"):
        return character

    rs = Ruleset(character.get("ruleset") or "dnd5e-2014")
    opts = rs.option_lists()
    skill_names = rs.skill_names()

    class_list = _class_list(pc)
    by_index = {c["index"]: c for c in opts["classes"]}
    cls = by_index.get(class_list[0].get("class"))                  # primary class
    secondaries = [by_index.get(e.get("class")) for e in class_list[1:]]
    secondaries = [c for c in secondaries if c]
    bg = next((b for b in opts["backgrounds"] if b["index"] == pc.get("background")), None)

    # --- saving throws: granted by the PRIMARY class only (multiclass rule) ---
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
    # Primary class grants its FULL starting proficiencies; each secondary class adds
    # only its reduced PHB multiclass set. Background tools/languages always apply.
    if cls or bg or secondaries:
        bg_tools = [_humanize(t) for t in ((bg or {}).get("tools") or [])]
        proficiencies = {
            "armor": list((cls or {}).get("armor") or []),
            "weapons": list((cls or {}).get("weapons") or []),
            "tools": list((cls or {}).get("tools") or []) + bg_tools,
            "languages": int((bg or {}).get("languages") or 0),  # # of free background languages
        }
        for sec in secondaries:
            grant = MULTICLASS_PROFICIENCIES.get(sec["index"], {})
            _merge_unique(proficiencies["armor"], grant.get("armor"))
            _merge_unique(proficiencies["weapons"], grant.get("weapons"))
            _merge_unique(proficiencies["tools"], grant.get("tools"))
        # preserve any feat/manual extras already on pc.proficiencies
        existing = pc.get("proficiencies") or {}
        for k, v in existing.items():
            if k not in proficiencies and v:
                proficiencies[k] = v
        pc["proficiencies"] = proficiencies

    return character
