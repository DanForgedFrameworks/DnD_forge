"""Deterministic 5e rules engine — the 'engine disposes' half of the design.

Given resolved choices it computes every derived number from the canonical SRD
data. It never invents values; the LLM/agent layer only supplies *choices*.
"""

from .builder import build_character
from .grants import resolve_pc_proficiencies
from .rules_mode import enforce_rules, spell_limits, class_spell_list, starting_gear
from .progression import rederive, normalize_classes, total_level
from . import abilities, derive

__all__ = [
    "build_character", "resolve_pc_proficiencies",
    "enforce_rules", "spell_limits", "class_spell_list", "starting_gear",
    "rederive", "normalize_classes", "total_level",
    "abilities", "derive",
]
