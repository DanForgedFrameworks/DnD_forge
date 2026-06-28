"""Deterministic 5e rules engine — the 'engine disposes' half of the design.

Given resolved choices it computes every derived number from the canonical SRD
data. It never invents values; the LLM/agent layer only supplies *choices*.
"""

from .builder import build_character
from .grants import resolve_pc_proficiencies
from .rules_mode import enforce_rules, spell_limits, class_spell_list, starting_gear
from .progression import rederive, normalize_classes, total_level
from .equipment import equipment_catalog, canonical_item, resolve_gear
from .actions import (
    derive_weapon_actions, weapon_actions_for_item, item_actions,
    item_is_actionable, annotate_equipment_actions, standard_actions,
)
from .features import (
    derive_class_features, derive_species_traits, derive_background_feature,
    pc_features_for_display, OPPORTUNITY_ATTACK,
)
from .languages import derive_languages, languages_display
from . import abilities, derive

__all__ = [
    "build_character", "resolve_pc_proficiencies",
    "enforce_rules", "spell_limits", "class_spell_list", "starting_gear",
    "rederive", "normalize_classes", "total_level",
    "equipment_catalog", "canonical_item", "resolve_gear",
    "derive_weapon_actions", "weapon_actions_for_item", "item_actions",
    "item_is_actionable", "annotate_equipment_actions", "standard_actions",
    "derive_class_features", "derive_species_traits", "derive_background_feature",
    "pc_features_for_display", "OPPORTUNITY_ATTACK",
    "derive_languages", "languages_display",
    "abilities", "derive",
]
