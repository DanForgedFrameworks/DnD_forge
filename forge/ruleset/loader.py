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

# SRD proficiency `type` values that count as a "tool" on a PC sheet (everything that
# isn't Armor / Weapons / Skills / Saving Throws). "Other" covers thieves' tools,
# navigator's tools, kits, etc.
_TOOL_PROF_TYPES = {"Artisan's Tools", "Gaming Sets", "Musical Instruments", "Vehicles", "Other"}


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

    def skill_names(self) -> dict:
        """{skill_index: canonical_name} for this edition (e.g. sleight-of-hand -> 'Sleight of Hand')."""
        from ..canon import SRDRepository

        repo = SRDRepository(self.config.get("srdEdition", "2014"), data_root=_DATA_ROOT)
        try:
            return {s.get("index"): s.get("name") for s in repo.all("skills")}
        except Exception:
            return {}

    def option_lists(self) -> dict:
        """Dropdown option lists derived from the canonical SRD for this edition.

        `classes[]` and `backgrounds[]` are ENRICHED with the proficiency grants the
        engine needs (and the front-end's skill-choice picker reads) so the front-end
        never has to know the rules — the engine derives saveProfs/skillProfs from them.
        """
        from ..canon import SRDRepository

        repo = SRDRepository(self.config.get("srdEdition", "2014"), data_root=_DATA_ROOT)

        def names(category: str) -> list:
            try:
                return [{"index": e.get("index"), "name": e.get("name")} for e in repo.all(category)]
            except Exception:
                return []

        # index -> SRD proficiency `type`, used to bucket class/background profs.
        try:
            prof_type = {p.get("index"): p.get("type") for p in repo.all("proficiencies")}
        except Exception:
            prof_type = {}

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

        lists = {
            "classes": self._classes_enriched(repo, prof_type),
            "subclassesByClass": subclasses_by_class,
            "species": names("species"),
            "subspecies": names("subspecies"),
            "subspeciesBySpecies": self._subspecies_by_species(repo),
            "backgrounds": self._backgrounds_enriched(repo, prof_type),
            "feats": names("feats"),
            "conditions": names("conditions"),
            "creatureTypes": CREATURE_TYPES,
            "sizes": SIZES,
        }
        # Opt-in local (non-SRD) 2024 PHB overlay — only when the ruleset config asks for it
        # (optionLists.source contains "local"), so the shippable SRD-only build is untouched.
        if "local" in str((self.config.get("optionLists") or {}).get("source", "")):
            self._merge_local(lists)
        return lists

    @staticmethod
    def _merge_local(lists: dict) -> None:
        """Overlay the richer local 2024 PHB content onto the SRD-derived optionLists, and add the
        local-only blocks (classFeaturesByClass, weaponMasteries, languages, multiclassing)."""
        from . import local_data as L
        if not L.available():
            return

        def union(base, extra):  # merge {index,name} lists; local wins / adds, by index
            by = {e["index"]: e for e in (base or []) if e.get("index")}
            for e in (extra or []):
                if e.get("index"):
                    by[e["index"]] = e
            return list(by.values())

        if L.species():
            lists["species"] = union(lists.get("species"), L.species())
        if L.feats():
            lists["feats"] = union(lists.get("feats"), L.feats())
        local_sub = L.subclasses_by_class()
        if local_sub:
            merged = dict(lists.get("subclassesByClass") or {})
            for ci, subs in local_sub.items():
                merged[ci] = union(merged.get(ci), subs)
            lists["subclassesByClass"] = merged
        local_bg = L.backgrounds()
        if local_bg:
            lists["backgrounds"] = local_bg  # 2024 shape (Origin Feat + ability prose; no fixed skills)
        # local-only blocks (new contract keys)
        cfb = L.class_features_by_class()
        if cfb:
            lists["classFeaturesByClass"] = cfb
        wm = L.weapon_masteries()
        if wm.get("properties") or wm.get("weapons"):
            lists["weaponMasteries"] = wm
        langs = L.languages()
        if langs:
            lists["languages"] = langs
        mc = L.multiclassing()
        if mc:
            lists["multiclassing"] = mc

    @staticmethod
    def _classes_enriched(repo, prof_type: dict) -> list:
        """classes[] += {saves, skillChoose, skillFrom, armor, weapons, tools}."""
        from ..engine.derive import class_skill_choice

        out = []
        try:
            classes = repo.all("classes")
        except Exception:
            return out
        for cls in classes:
            armor, weapons, tools = [], [], []
            for p in cls.get("proficiencies", []) or []:
                t = prof_type.get(p.get("index"))
                if t == "Armor":
                    armor.append(p.get("name"))
                elif t == "Weapons":
                    weapons.append(p.get("name"))
                elif t in _TOOL_PROF_TYPES:
                    tools.append(p.get("name"))
            choice = class_skill_choice(cls)
            skill_choose, skill_from = (0, [])
            if choice:
                n, allowed = choice
                skill_choose = n or 0
                skill_from = sorted(allowed)
            out.append({
                "index": cls.get("index"),
                "name": cls.get("name"),
                "saves": [s.get("index", "").upper() for s in cls.get("saving_throws", []) or []],
                "skillChoose": skill_choose,
                "skillFrom": skill_from,
                "armor": armor,
                "weapons": weapons,
                "tools": tools,
            })
        return out

    @staticmethod
    def _backgrounds_enriched(repo, prof_type: dict) -> list:
        """backgrounds[] += {skills, tools, languages, abilityOptions, feat}.

        2014 backgrounds carry `starting_proficiencies` + `language_options`; 2024
        backgrounds carry `proficiencies` + `ability_scores` + `feat`. Absorb both.
        """
        out = []
        try:
            backgrounds = repo.all("backgrounds")
        except Exception:
            return out
        for bg in backgrounds:
            skills, tools = [], []
            for p in (bg.get("starting_proficiencies") or bg.get("proficiencies") or []):
                idx = p.get("index", "") or ""
                if idx.startswith("skill-"):
                    skills.append(idx[len("skill-"):])
                elif idx.startswith("tool-"):
                    tools.append(idx[len("tool-"):])
                elif prof_type.get(idx) in _TOOL_PROF_TYPES:
                    tools.append(idx)
            out.append({
                "index": bg.get("index"),
                "name": bg.get("name"),
                "skills": skills,
                "tools": tools,
                "languages": int((bg.get("language_options") or {}).get("choose", 0) or 0),
                "abilityOptions": [a.get("index", "").upper() for a in bg.get("ability_scores", []) or []],
                "feat": (bg.get("feat") or {}).get("index"),
            })
        return out

    @staticmethod
    def _subspecies_by_species(repo) -> dict:
        """{<speciesIndex>: [{index,name}]} — 2014 subraces ref `.race`, 2024 `.species`."""
        out: dict[str, list] = {}
        try:
            for s in repo.all("subspecies"):
                ref = (s.get("species") or s.get("race") or {}).get("index")
                if ref:
                    out.setdefault(ref, []).append({"index": s.get("index"), "name": s.get("name")})
        except Exception:
            pass
        return out
