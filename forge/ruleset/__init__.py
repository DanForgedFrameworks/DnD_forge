"""Ruleset abstraction: 2014 / 2024 / homebrew adaptions as base + extends patches."""

from .loader import Ruleset, load_ruleset, DEFAULT_SLUG

__all__ = ["Ruleset", "load_ruleset", "DEFAULT_SLUG"]
