"""Load and resolve a ruleset config.

A ruleset is base + (optional) `extends` patch — a homebrew adaption declares
`extends: "dnd5e-2014"` and overrides deltas only. The engine honours the Character's
`ruleset` slug and falls back to dnd5e-2014 on an unknown slug.

The config drives BOTH the monster side (creature types, conditions, sizes, statblock
field order/labels, CR/XP) and the PC side (class / subclass-by-class / species /
subspecies / background / feat dropdowns, the Race↔Species label flip, ability-score
rules). Big option lists are derived from the canonical SRD for the ruleset's edition
rather than hard-coded.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_RULESET_DIR = _REPO_ROOT / "config" / "rulesets"
_DATA_ROOT = _REPO_ROOT / "data" / "srd"
DEFAULT_SLUG = "dnd5e-2014"

# fixed 5e lists (no SRD file backs these)
CREATURE_TYPES = [
    "aberration", "beast", "celestial", "construct", "dragon", "elemental", "fey",
    "fiend", "giant", "humanoid", "monstrosity", "ooze", "plant", "undead",
]
SIZES = ["Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan"]


def _read(slug: str) -> dict | None:
    path = _RULESET_DIR / f"{slug}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _deep_merge(base: dict, patch: dict) -> dict:
    out = deepcopy(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = deepcopy(v)
    return out


def load_ruleset(slug: str, *, _seen: set | None = None) -> dict:
    """Resolved config for `slug` (base + extends patches). Unknown slug -> 2014."""
    _seen = _seen or set()
    raw = _read(slug)
    if raw is None:
        if slug == DEFAULT_SLUG:
            raise FileNotFoundError(f"default ruleset {DEFAULT_SLUG!r} is missing")
        return load_ruleset(DEFAULT_SLUG)

    parent = raw.get("extends")
    if parent and parent not in _seen:
        _seen.add(slug)
        merged = _deep_merge(load_ruleset(parent, _seen=_seen), raw)
        # the child keeps its own identity, not the parent's
        merged["slug"] = raw.get("slug", slug)
        merged["label"] = raw.get("label", merged.get("label"))
        merged["extends"] = parent
        return merged
    return raw


class Ruleset:
    """Convenience wrapper over a resolved ruleset config."""

    def __init__(self, slug: str) -> None:
        self.config = load_ruleset(slug)
        self.slug = self.config.get("slug", slug)

    @property
    def label(self) -> str:
        return self.config.get("label", self.slug)

    @property
    def labels(self) -> dict:
        return self.config.get("labels", {})

    @property
    def ability_rules(self) -> dict:
        return self.config.get("abilityRules", {})

    @property
    def statblock(self) -> dict:
        return self.config.get("statblock", {})

    def option_lists(self) -> dict:
        """Dropdown option lists derived from the canonical SRD for this edition."""
        from ..canon import SRDRepository

        repo = SRDRepository(self.config.get("srdEdition", "2014"), data_root=_DATA_ROOT)

        def names(category: str) -> list:
            try:
                return [{"index": e.get("index"), "name": e.get("name")} for e in repo.all(category)]
            except Exception:
                return []

        subclasses_by_class: dict[str, list] = {}
        try:
            for s in repo.all("subclasses"):
                ci = (s.get("class") or {}).get("index")
                if ci:
                    subclasses_by_class.setdefault(ci, []).append(
                        {"index": s.get("index"), "name": s.get("name")}
                    )
        except Exception:
            pass

        return {
            "classes": names("classes"),
            "subclassesByClass": subclasses_by_class,
            "species": names("species"),
            "subspecies": names("subspecies"),
            "backgrounds": names("backgrounds"),
            "feats": names("feats"),
            "conditions": names("conditions"),
            "creatureTypes": CREATURE_TYPES,
            "sizes": SIZES,
        }
