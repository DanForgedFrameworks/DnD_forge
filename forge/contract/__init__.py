"""The shared Character contract layer (front-end <-> engine).

The contract `Character` JSON is THE interface. This package owns the canonical
5e maths and the derive/validate functions that operate on that shape.
"""

from .character import derive_modifiers, validate, apply_derived
from . import maths

__all__ = ["derive_modifiers", "validate", "apply_derived", "maths"]
