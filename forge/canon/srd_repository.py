"""Edition-aware access layer over the local SRD canonical data.

Generation never invents rules values; everything mechanical is resolved against this
canonical data. Data is pulled by ``scripts/fetch_srd_data.py`` from the open
5e-bits/5e-database (SRD 5.1 / 5.2, CC-BY-4.0 / OGL).

The 2024 edition renames some categories (Races -> Species, Subraces -> Subspecies)
and adds others (Poisons, Weapon Mastery). We expose a *stable* set of canonical
category keys so callers don't have to care which edition they're on; the mapping
below absorbs the filename differences.
"""
from __future__ import annotations

import json
from pathlib import Path

# canonical category key -> SRD filename, per edition.
_CATEGORY_FILES: dict[str, dict[str, str]] = {
    "2014": {
        "ability_scores": "5e-SRD-Ability-Scores.json",
        "alignments": "5e-SRD-Alignments.json",
        "backgrounds": "5e-SRD-Backgrounds.json",
        "classes": "5e-SRD-Classes.json",
        "conditions": "5e-SRD-Conditions.json",
        "damage_types": "5e-SRD-Damage-Types.json",
        "equipment": "5e-SRD-Equipment.json",
        "equipment_categories": "5e-SRD-Equipment-Categories.json",
        "feats": "5e-SRD-Feats.json",
        "features": "5e-SRD-Features.json",
        "languages": "5e-SRD-Languages.json",
        "levels": "5e-SRD-Levels.json",
        "magic_items": "5e-SRD-Magic-Items.json",
        "magic_schools": "5e-SRD-Magic-Schools.json",
        "monsters": "5e-SRD-Monsters.json",
        "proficiencies": "5e-SRD-Proficiencies.json",
        "rule_sections": "5e-SRD-Rule-Sections.json",
        "rules": "5e-SRD-Rules.json",
        "skills": "5e-SRD-Skills.json",
        "species": "5e-SRD-Races.json",        # renamed -> Species in 2024
        "spells": "5e-SRD-Spells.json",
        "subclasses": "5e-SRD-Subclasses.json",
        "subspecies": "5e-SRD-Subraces.json",  # renamed -> Subspecies in 2024
        "traits": "5e-SRD-Traits.json",
        "weapon_properties": "5e-SRD-Weapon-Properties.json",
    },
    "2024": {
        "ability_scores": "5e-SRD-Ability-Scores.json",
        "alignments": "5e-SRD-Alignments.json",
        "backgrounds": "5e-SRD-Backgrounds.json",
        "classes": "5e-SRD-Classes.json",
        "conditions": "5e-SRD-Conditions.json",
        "damage_types": "5e-SRD-Damage-Types.json",
        "equipment": "5e-SRD-Equipment.json",
        "equipment_categories": "5e-SRD-Equipment-Categories.json",
        "feats": "5e-SRD-Feats.json",
        "features": "5e-SRD-Features.json",
        "languages": "5e-SRD-Languages.json",
        "levels": "5e-SRD-Levels.json",       # native 2024 slot tables (CC-BY SRD 5.2.1)
        "magic_items": "5e-SRD-Magic-Items.json",
        "magic_schools": "5e-SRD-Magic-Schools.json",
        "monsters": "5e-SRD-Monsters.json",
        "poisons": "5e-SRD-Poisons.json",
        "proficiencies": "5e-SRD-Proficiencies.json",
        "skills": "5e-SRD-Skills.json",
        "species": "5e-SRD-Species.json",
        "spells": "5e-SRD-Spells.json",        # native 2024 spell list (CC-BY SRD 5.2.1)
        "subclasses": "5e-SRD-Subclasses.json",
        "subspecies": "5e-SRD-Subspecies.json",
        "traits": "5e-SRD-Traits.json",
        "weapon_mastery_properties": "5e-SRD-Weapon-Mastery-Properties.json",
        "weapon_properties": "5e-SRD-Weapon-Properties.json",
    },
}

SUPPORTED_EDITIONS: tuple[str, ...] = tuple(_CATEGORY_FILES.keys())


class SRDRepository:
    """Lazy, cached, edition-aware reader over the local SRD JSON files."""

    def __init__(self, edition: str, data_root: Path | str = "data/srd") -> None:
        if edition not in _CATEGORY_FILES:
            raise ValueError(
                f"Unsupported edition {edition!r}; expected one of {SUPPORTED_EDITIONS}"
            )
        self.edition = edition
        self.root = Path(data_root) / edition
        # Edition-shared homebrew overlay. Files here are keyed by canonical
        # category (e.g. `equipment.json`) and merged over the SRD data by
        # `index`. Kept outside the per-edition dirs so `fetch_srd_data.py`
        # re-imports never clobber it.
        self._homebrew_root = Path(data_root) / "_homebrew"
        self._cache: dict[str, list] = {}

    # -- introspection -------------------------------------------------------
    def categories(self) -> list[str]:
        """Canonical category keys available for this edition."""
        return sorted(_CATEGORY_FILES[self.edition])

    def summary(self) -> dict[str, int | None]:
        """{category: entry_count}; None where the data file is missing."""
        out: dict[str, int | None] = {}
        for cat in self.categories():
            try:
                out[cat] = len(self._load(cat))
            except FileNotFoundError:
                out[cat] = None
        return out

    # -- core access ---------------------------------------------------------
    def all(self, category: str) -> list:
        """All entries for a canonical category."""
        return self._load(category)

    def index(self, category: str) -> dict:
        """Map of {slug: entry} keyed by the SRD 'index' (falls back to name)."""
        return {e.get("index", e.get("name")): e for e in self._load(category)}

    def get(self, category: str, key: str) -> dict | None:
        """Fetch one entry by its 'index' slug or exact name."""
        for e in self._load(category):
            if e.get("index") == key or e.get("name") == key:
                return e
        return None

    # convenience aliases for the edition-renamed categories
    def species(self) -> list:
        return self._load("species")

    def classes(self) -> list:
        return self._load("classes")

    # -- internals -----------------------------------------------------------
    def _load(self, category: str) -> list:
        if category not in self._cache:
            files = _CATEGORY_FILES[self.edition]
            if category not in files:
                raise KeyError(
                    f"Category {category!r} is not available for edition {self.edition}. "
                    f"Available: {sorted(files)}"
                )
            path = self.root / files[category]
            if not path.exists():
                raise FileNotFoundError(
                    f"Missing SRD file: {path}\n"
                    f"Run `python scripts/fetch_srd_data.py {self.edition}` to pull the data."
                )
            with path.open(encoding="utf-8") as fh:
                entries = json.load(fh)
            self._cache[category] = self._apply_homebrew(category, entries)
        return self._cache[category]

    def _apply_homebrew(self, category: str, entries: list) -> list:
        """Merge an optional `_homebrew/<category>.json` overlay over SRD data.

        Overlay entries replace any base entry sharing their `index` (else
        `name`), and otherwise append. Returns the base list unchanged when no
        overlay file exists.
        """
        overlay_path = self._homebrew_root / f"{category}.json"
        if not overlay_path.exists():
            return entries
        with overlay_path.open(encoding="utf-8") as fh:
            overlay = json.load(fh)
        merged = list(entries)
        by_key = {e.get("index", e.get("name")): i for i, e in enumerate(merged)}
        for item in overlay:
            key = item.get("index", item.get("name"))
            if key in by_key:
                merged[by_key[key]] = item
            else:
                by_key[key] = len(merged)
                merged.append(item)
        return merged
