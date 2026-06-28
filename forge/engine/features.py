"""Derive a PC's class + subclass features (with rules text) from the SRD.

The progression engine already lists the *names* of base-class features gained by level
(``pc.classFeatures`` = ``[{name, class, level}]``). This module produces the fuller view
a sheet needs: every base-class **and subclass** feature the character has earned, with its
**rules text**, and a rough ``kind`` (passive / action / bonus / reaction) read from that
text so the front-end can file reaction-style features under Reactions.

Public API:
- :func:`derive_class_features` — ``[{name, text, source, level, kind}]`` for the whole
  class mix at the character's levels (base + subclass), de-duplicated, level-ordered.

Edition-aware via :class:`SRDRepository`; never invents text — unmatched features are
listed name-only rather than fabricated.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ..canon import SRDRepository

_HOMEBREW_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "srd" / "_homebrew"


@lru_cache(maxsize=1)
def _species_trait_table() -> dict:
    """Homebrew species/lineage traits (kender Taunt, aarakocra Flight…), keyed by lower-cased
    lineage or species name."""
    try:
        data = json.loads((_HOMEBREW_ROOT / "species_traits.json").read_text(encoding="utf-8"))
        return {k.lower(): v for k, v in data.items() if not k.startswith("_")}
    except Exception:
        return {}


@lru_cache(maxsize=4)
def _repo(edition: str = "2014") -> SRDRepository:
    return SRDRepository(edition)


def _class_mix(pc: dict) -> list[tuple[str, str, int]]:
    """[(class_index, subclass_index, class_level)] for the character's class mix."""
    classes = pc.get("classes")
    if isinstance(classes, list) and any((c or {}).get("class") for c in classes):
        return [((c.get("class") or "").lower(), (c.get("subclass") or "").lower(), int(c.get("level") or 1))
                for c in classes if (c or {}).get("class")]
    return [((pc.get("class") or "").lower(), (pc.get("subclass") or "").lower(), int(pc.get("level") or 1))]


def _kind_of(text: str) -> str:
    """Rough use-type from the feature's own wording (so reactions land under Reactions)."""
    t = (text or "").lower()
    if "reaction" in t:
        return "reaction"
    if "bonus action" in t:
        return "bonus"
    if "as an action" in t or "you can take the" in t or "use your action" in t:
        return "action"
    return "passive"


def _text_of(feature: dict) -> str:
    desc = feature.get("desc")
    if isinstance(desc, list):
        return "\n".join(d for d in desc if d).strip()
    return str(desc or "").strip()


def _granted_base_names(repo, ci: str, clvl: int) -> set:
    """Names of the base-class features actually GRANTED up to ``clvl`` (from the Levels table).

    The standalone features data also carries every *option* in a choose-from pool (e.g. all 18
    Eldritch Invocations, every Metamagic) — those aren't granted, they're picked. The Levels
    table lists only what's auto-granted (incl. the umbrella "Eldritch Invocations"), so we use
    it to keep option-pool entries out of the sheet.
    """
    names: set = set()
    try:
        levels = repo.all("levels")
    except Exception:
        return names
    for entry in levels:
        if (entry.get("class") or {}).get("index") == ci and 1 <= int(entry.get("level", 0)) <= clvl:
            for f in entry.get("features", []) or []:
                if f.get("name"):
                    names.add(f["name"].lower())
    return names


def derive_class_features(character: dict, edition: str = "2014") -> list[dict]:
    """All class + subclass features the PC has earned, with text and a `kind` tag."""
    pc = character.get("pc")
    if not isinstance(pc, dict):
        return []
    try:
        feats = _repo(edition).all("features")
    except Exception:
        return []

    out: list[dict] = []
    seen: set[str] = set()
    for ci, sub_idx, clvl in _class_mix(pc):
        if not ci:
            continue
        granted = _granted_base_names(_repo(edition), ci, clvl)
        for f in feats:
            fclass = (f.get("class") or {})
            if (fclass.get("index") or "").lower() != ci:
                continue
            flevel = int(f.get("level") or 0)
            if not (1 <= flevel <= clvl):
                continue
            name = f.get("name")
            if not name:
                continue
            fsub = f.get("subclass")
            if fsub:  # subclass feature — only if it's THIS character's subclass (all granted)
                if not sub_idx or (fsub.get("index") or "").lower() != sub_idx:
                    continue
                source = f"subclass:{fsub.get('name', sub_idx)}"
            else:  # base-class feature — only if the Levels table actually grants it (no option pools)
                if granted and name.lower() not in granted:
                    continue
                source = f"class:{fclass.get('name', ci)}"
            key = f"{ci}:{name.lower()}"
            if key in seen:
                continue
            seen.add(key)
            text = _text_of(f)
            out.append({"name": name, "text": text, "source": source,
                        "level": flevel, "kind": _kind_of(text)})
    out.sort(key=lambda f: (f["source"].startswith("subclass:"), f["level"], f["name"]))
    return out


def derive_species_traits(character: dict, edition: str = "2014") -> list[dict]:
    """Species/lineage traits with text — the SRD race's traits (Darkvision, Fey Ancestry…) PLUS
    any homebrew traits for the flavour species/lineage (a kender keeps halfling traits AND gains
    Taunt/Fearless; an aarakocra gains Flight/Talons since it's not in the 2014 SRD)."""
    pc = character.get("pc")
    if not isinstance(pc, dict):
        return []
    species = (pc.get("species") or "").lower()
    lineage = (pc.get("lineage") or "").strip().lower()
    out: list[dict] = []
    seen: set[str] = set()

    def add(name: str, text: str, label: str):
        key = (name or "").strip().lower()
        if not key or key in seen:
            return
        seen.add(key)
        out.append({"name": name.strip(), "text": text, "source": f"species:{label}",
                    "level": 1, "kind": _kind_of(text)})

    # SRD race traits (description resolved from the traits catalog)
    race = _repo(edition).get("species", species) or {}
    race_label = race.get("name") or species.title()
    try:
        traits_by_idx = _repo(edition).index("traits")
    except Exception:
        traits_by_idx = {}
    for t in (race.get("traits") or []):
        full = traits_by_idx.get(t.get("index")) or {}
        add(t.get("name"), _text_of(full), race_label)

    # homebrew flavour traits (by lineage first, then species)
    tbl = _species_trait_table()
    flavour_label = (lineage or species).title()
    for key in (lineage, species):
        for ht in tbl.get(key, []) if key else []:
            add(ht.get("name"), ht.get("text", ""), flavour_label)
    return out


def derive_background_feature(character: dict, edition: str = "2014") -> list[dict]:
    """The background's special feature (Wanderer, Researcher, Shelter of the Faithful…) with text."""
    pc = character.get("pc")
    if not isinstance(pc, dict) or not pc.get("background"):
        return []
    bg = _repo(edition).get("backgrounds", pc.get("background")) or {}
    feat = bg.get("feature") or {}
    if not feat.get("name"):
        return []
    text = _text_of(feat)
    return [{"name": feat["name"], "text": text, "source": f"background:{bg.get('name', pc.get('background'))}",
             "level": 1, "kind": _kind_of(text)}]


# Universal reaction every combatant has — added to the sheet's Reactions view so it isn't
# silently missing (it's never in the per-class feature data).
OPPORTUNITY_ATTACK = {
    "name": "Opportunity Attack",
    "text": ("When a hostile creature that you can see moves out of your reach, you can use your "
             "reaction to make one melee attack against it."),
    "source": "rules:combat",
    "level": 1,
    "kind": "reaction",
}


def pc_features_for_display(character: dict, edition: str = "2014") -> list[dict]:
    """The feature list to store on a PC for the sheet: class + subclass features, plus the
    universal Opportunity Attack. Empty for non-PCs (monsters keep their own actions/traits)."""
    if character.get("kind") != "character" or not isinstance(character.get("pc"), dict):
        return []
    return (derive_species_traits(character, edition)
            + derive_background_feature(character, edition)
            + derive_class_features(character, edition)
            + [dict(OPPORTUNITY_ATTACK)])
