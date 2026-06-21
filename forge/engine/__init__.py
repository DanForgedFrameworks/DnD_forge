"""Deterministic 5e rules engine — the 'engine disposes' half of the design.

Given resolved choices it computes every derived number from the canonical SRD
data. It never invents values; the LLM/agent layer only supplies *choices*.
"""

from .builder import build_character
from . import abilities, derive

__all__ = ["build_character", "abilities", "derive"]
