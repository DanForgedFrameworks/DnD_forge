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
