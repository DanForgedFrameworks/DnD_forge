"""Strict JSON schema for the auto-fill LLM output (structured outputs).

This is deliberately NOT the full Character contract — it's the subset the LLM
*authors* (choices + prose + art). The engine adds id/schemaVersion/portraits and
derives the saves/skills/senses strings afterward. Structured outputs require
`additionalProperties: false` and forbid min/max/const, so this stays flat.
"""
from __future__ import annotations

_FEATURE_LIST = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "text": {"type": "string"},
        },
        "required": ["name", "text"],
        "additionalProperties": False,
    },
}

# PC features add a `source` tag ("class:Wizard" | "race:Elf" | "background:Sage" | "feat:…").
_FEATURE_LIST_SOURCED = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "text": {"type": "string"},
            "source": {"type": "string"},
        },
        "required": ["name", "text", "source"],
        "additionalProperties": False,
    },
}

_ABILITY_BLOCK = {
    "type": "object",
    "properties": {
        "STR": {"type": "integer"}, "DEX": {"type": "integer"},
        "CON": {"type": "integer"}, "INT": {"type": "integer"},
        "WIS": {"type": "integer"}, "CHA": {"type": "integer"},
    },
    "required": ["STR", "DEX", "CON", "INT", "WIS", "CHA"],
    "additionalProperties": False,
}

_ART_BLOCK = {
    "type": "object",
    "properties": {
        "appearance": {"type": "string"},
        "outfit": {"type": "string"},
        "pose": {"type": "string"},
        "environment": {"type": "string"},
        "personality": {"type": "string"},
        "style": {"type": "string"},
    },
    "required": ["appearance", "outfit", "pose", "environment", "personality", "style"],
    "additionalProperties": False,
}

# PC art also carries per-state bespoke action beats (consumed deterministically by build_prompt).
_ART_BLOCK_PC = {
    "type": "object",
    "properties": {
        **_ART_BLOCK["properties"],
        "stateBeats": {
            "type": "object",
            "properties": {
                "at-rest": {"type": "string"},
                "in-conversation": {"type": "string"},
                "in-battle": {"type": "string"},
                "travelling": {"type": "string"},
            },
            "required": ["at-rest", "in-conversation", "in-battle", "travelling"],
            "additionalProperties": False,
        },
    },
    "required": [*_ART_BLOCK["required"], "stateBeats"],
    "additionalProperties": False,
}

AUTOFILL_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "ruleset": {"type": "string", "enum": ["dnd5e-2014", "dnd5e-2024"]},
        "kind": {
            "type": "string",
            "enum": ["monster", "npc", "creature", "companion", "pet", "character"],
        },
        "name": {"type": "string"},
        "size": {"type": "string"},
        "type": {"type": "string"},
        "alignment": {"type": "string"},
        "flavour": {"type": "string"},

        "ac": {"type": "string"},
        "hp": {"type": "string"},
        "speed": {"type": "string"},

        "abilities": {
            "type": "object",
            "properties": {
                "STR": {"type": "integer"}, "DEX": {"type": "integer"},
                "CON": {"type": "integer"}, "INT": {"type": "integer"},
                "WIS": {"type": "integer"}, "CHA": {"type": "integer"},
            },
            "required": ["STR", "DEX", "CON", "INT", "WIS", "CHA"],
            "additionalProperties": False,
        },

        "saveProfs": {
            "type": "array",
            "items": {"type": "string", "enum": ["STR", "DEX", "CON", "INT", "WIS", "CHA"]},
        },
        "skillProfs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "skill": {"type": "string"},
                    "expertise": {"type": "boolean"},
                },
                "required": ["skill", "expertise"],
                "additionalProperties": False,
            },
        },

        "resist": {"type": "string"},
        "condImm": {"type": "string"},
        "languages": {"type": "string"},
        "challenge": {"type": "string"},

        "traits": _FEATURE_LIST,
        "actions": _FEATURE_LIST,
        "reactions": _FEATURE_LIST,

        "dump": {"type": "string"},
        "art": {
            "type": "object",
            "properties": {
                "appearance": {"type": "string"},
                "outfit": {"type": "string"},
                "pose": {"type": "string"},
                "environment": {"type": "string"},
                "personality": {"type": "string"},
                "style": {"type": "string"},
            },
            "required": ["appearance", "outfit", "pose", "environment", "personality", "style"],
            "additionalProperties": False,
        },
    },
    "required": [
        "ruleset", "kind", "name", "size", "type", "alignment", "flavour",
        "ac", "hp", "speed", "abilities", "saveProfs", "skillProfs",
        "resist", "condImm", "languages", "challenge",
        "traits", "actions", "reactions", "dump", "art",
    ],
    "additionalProperties": False,
}


# --- PC variant (kind:"character") -------------------------------------------
# The LLM authors choices + prose + the pc{}/spellcasting{} lists; the engine then
# computes final abilities (ASI), saveProfs/skillProfs/proficiencies, spell slots +
# save DC/attack, and the challenge string. So this schema deliberately OMITS the
# engine-owned fields (saveProfs/skillProfs/saves/skills/senses/slots/saveDc/attackBonus).

_PC_BLOCK = {
    "type": "object",
    "properties": {
        "species": {"type": "string"},        # an SRD species index (grounding target)
        "lineage": {"type": "string"},         # display name when non-SRD (e.g. "Kender"), else ""
        "subspecies": {"type": "string"},      # SRD subspecies index, or ""
        "class": {"type": "string"},
        "subclass": {"type": "string"},
        "level": {"type": "integer"},
        "background": {"type": "string"},
        "abilityMethod": {"type": "string"},   # standard_array | point_buy | rolled | manual
        "baseAbilities": _ABILITY_BLOCK,       # pre-racial; engine applies ASI -> abilities
        # 2024 background ASIs as a compact string, e.g. "dex+2, con+1"; "" for 2014.
        "abilityAllocation2024": {"type": "string"},
        "skillChoices": {"type": "array", "items": {"type": "string"}},  # class-skill picks (indices)
        "hitDice": {
            "type": "object",
            "properties": {
                "die": {"type": "string"}, "total": {"type": "integer"}, "remaining": {"type": "integer"},
            },
            "required": ["die", "total", "remaining"],
            "additionalProperties": False,
        },
        "deathSaves": {
            "type": "object",
            "properties": {"successes": {"type": "integer"}, "failures": {"type": "integer"}},
            "required": ["successes", "failures"],
            "additionalProperties": False,
        },
        "feats": {"type": "array", "items": {"type": "string"}},
        "equipment": {"type": "array", "items": {"type": "string"}},  # item names; engine objectifies
        "currency": {
            "type": "object",
            "properties": {
                "cp": {"type": "integer"}, "sp": {"type": "integer"}, "ep": {"type": "integer"},
                "gp": {"type": "integer"}, "pp": {"type": "integer"},
            },
            "required": ["cp", "sp", "ep", "gp", "pp"],
            "additionalProperties": False,
        },
        "personality": {
            "type": "object",
            "properties": {
                "traits": {"type": "array", "items": {"type": "string"}},
                "ideals": {"type": "array", "items": {"type": "string"}},
                "bonds": {"type": "array", "items": {"type": "string"}},
                "flaws": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["traits", "ideals", "bonds", "flaws"],
            "additionalProperties": False,
        },
    },
    "required": [
        "species", "lineage", "subspecies", "class", "subclass", "level", "background",
        "abilityMethod", "baseAbilities", "abilityAllocation2024", "skillChoices",
        "hitDice", "deathSaves", "feats", "equipment", "currency", "personality",
    ],
    "additionalProperties": False,
}

_SPELLCASTING_BLOCK = {
    "type": "object",
    "properties": {
        "ability": {"type": "string"},   # "int"/"wis"/"cha" for casters, "" for non-casters
        "cantrips": {"type": "array", "items": {"type": "string"}},   # spell indices
        "prepared": {"type": "array", "items": {"type": "string"}},   # known/prepared leveled spells
    },
    "required": ["ability", "cantrips", "prepared"],
    "additionalProperties": False,
}

PC_AUTOFILL_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "ruleset": {"type": "string", "enum": ["dnd5e-2014", "dnd5e-2024"]},
        "kind": {"type": "string", "enum": ["character"]},
        "name": {"type": "string"},
        "size": {"type": "string"},
        "type": {"type": "string"},        # e.g. "humanoid (elf)"
        "alignment": {"type": "string"},
        "flavour": {"type": "string"},

        "ac": {"type": "string"},
        "hp": {"type": "string"},
        "speed": {"type": "string"},

        "resist": {"type": "string"},
        "condImm": {"type": "string"},
        "languages": {"type": "string"},
        "challenge": {"type": "string"},   # "— (level N)"; engine normalises from pc.level

        "traits": _FEATURE_LIST_SOURCED,
        "actions": _FEATURE_LIST_SOURCED,
        "reactions": _FEATURE_LIST_SOURCED,

        "dump": {"type": "string"},
        "art": _ART_BLOCK_PC,

        "pc": _PC_BLOCK,
        "spellcasting": _SPELLCASTING_BLOCK,
    },
    "required": [
        "ruleset", "kind", "name", "size", "type", "alignment", "flavour",
        "ac", "hp", "speed", "resist", "condImm", "languages", "challenge",
        "traits", "actions", "reactions", "dump", "art", "pc", "spellcasting",
    ],
    "additionalProperties": False,
}
