"""Local (non-SRD) 2024 PHB data overlay for a ruleset's optionLists.

These files were extracted from the local PHB 2024 PDF and live under ``data/local/`` —
gitignored, NEVER committed, every record tagged ``"srd": false, "local": true``. They are
merged into a ruleset's optionLists ONLY when its config opts in (``optionLists.source``
contains ``"local"`` — the ``dnd5e-2024-local`` ruleset), so the shippable SRD-only build is
never affected. Any missing file degrades gracefully to empty.

The accessors return optionLists-ready shapes. 2024 backgrounds are free-text (Origin Feat +
ability bumps as prose, no fixed skill pair) — surfaced as raw strings here for display; the
structured grant derivation is the deferred "entry-box rules alignment" task.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_LOCAL_ROOT = Path(__file__).resolve().parent.parent.parent / "data" / "local"

_ABILITIES = {"strength": "STR", "dexterity": "DEX", "constitution": "CON",
              "intelligence": "INT", "wisdom": "WIS", "charisma": "CHA"}


def _clean(s: str) -> str:
    """Tidy OCR noise: collapse runs of spaces, fix the recurring 'M agic' split, trim."""
    return re.sub(r"\s{2,}", " ", (s or "").replace("M agic", "Magic")).strip()


def _abbr(token: str) -> str | None:
    """Map an ability name (full, or OCR-truncated like 'Intellige') to its 3-letter code."""
    t = re.sub(r"[^a-z]", "", (token or "").lower())
    if not t:
        return None
    for full, ab in _ABILITIES.items():
        if full.startswith(t) or t.startswith(full):
            return ab
    return None


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")


# --- OCR cleanup for the local PHB extraction ------------------------------------------------
# Exact-match fixes for the handful of genuine word-splits the OCR produced.
_NAME_FIXES = {
    "Life Doma In Spells": "Life Domain Spells",
    "Trickery Domain Sp Ells": "Trickery Domain Spells",
    "Nature'Ssanct Ua Ry": "Nature's Sanctuary",
    "Stride Of The Elem Ents": "Stride of the Elements",
    "Psion Ic Power": "Psionic Power",
    "Telepath Ic Speech": "Telepathic Speech",
    "Revelation In Flesh": "Revelation in Flesh",
}
# connector words the extractor wrongly Title-Cased ("Rage Of The Wilds" -> "Rage of the Wilds").
_SMALL_WORDS = {"of", "the", "in", "a", "an", "to", "for", "and", "with", "on", "at", "by",
                "from", "into", "or", "as"}


def _fix_name(name: str) -> str:
    """Tidy an OCR'd feature/trait name: fix known word-splits, then lower-case mis-capitalised
    connector words (but never the first word)."""
    n = _NAME_FIXES.get((name or "").strip(), name or "")
    words = n.split()
    return " ".join(w.lower() if (i > 0 and w.lower() in _SMALL_WORDS) else w
                    for i, w in enumerate(words))


def _is_fragment_trait(name: str) -> bool:
    """A split-off sub-bullet, not a real trait name (real trait names are nouns, e.g. 'Darkvision';
    these read as sentences: 'You also know the Dancing Lights cantrip')."""
    n = (name or "").strip().lower()
    return n.startswith("you ") or (bool(n) and n[0].islower())


@lru_cache(maxsize=16)
def _load(name: str):
    try:
        return json.loads((_LOCAL_ROOT / name).read_text(encoding="utf-8"))
    except Exception:
        return None


@lru_cache(maxsize=1)
def available() -> bool:
    """True when the local 2024 PHB extraction is present on this machine."""
    return (_LOCAL_ROOT / "class_features_2024_phb.json").exists()


def _names(records) -> list:
    return [{"index": r.get("index"), "name": r.get("name")}
            for r in (records or []) if isinstance(r, dict) and r.get("index")]


def species() -> list:
    return _names(_load("species_2024_phb.json"))


def species_traits(index: str) -> list:
    """[{name, desc}] traits for a 2024 species (Darkvision, Fey Ancestry…); [] if unknown.
    OCR fragment sub-bullets are dropped and names tidied."""
    for s in _load("species_2024_phb.json") or []:
        if s.get("index") == index:
            return [{"name": _fix_name(t["name"]), "desc": t.get("desc", "")}
                    for t in (s.get("traits") or [])
                    if isinstance(t, dict) and t.get("name") and not _is_fragment_trait(t["name"])]
    return []


def feats() -> list:
    return _names(_load("feats_2024_phb.json"))


def subclasses_by_class() -> dict:
    """{classIndex: [{index, name}]} from the 48 local subclasses."""
    out: dict[str, list] = {}
    for s in _load("subclasses_2024_phb.json") or []:
        cls = s.get("class")
        ci = cls.get("index") if isinstance(cls, dict) else cls
        if ci and s.get("index"):
            out.setdefault(str(ci), []).append({"index": s.get("index"), "name": s.get("name")})
    return out


@lru_cache(maxsize=1)
def _feats_by_slug() -> dict:
    return {_slug(f.get("name", "")): f for f in (_load("feats_2024_phb.json") or []) if f.get("name")}


def backgrounds() -> list:
    """2024 backgrounds, with the free-text PHB fields PARSED into structured grants the engine
    consumes (skills/tools lists, ability-boost options, the Origin Feat) plus the original prose
    kept as ``*Text`` fields for display. 2024 backgrounds grant no languages (Origin Feat instead),
    so ``languages`` is 0 — keeping the engine's grants.py happy across both editions."""
    out = []
    feats = _feats_by_slug()
    for b in _load("backgrounds_2024_phb.json") or []:
        if not b.get("index"):
            continue
        # ability-boost options (player picks +2/+1 from these three)
        ability_options: list[str] = []
        for tok in re.split(r"[,/]", b.get("ability_scores", "")):
            ab = _abbr(tok)
            if ab and ab not in ability_options:
                ability_options.append(ab)
        # the two fixed skills (e.g. "Insight and Religion") -> skill indices
        skills = [_slug(t) for t in re.split(r"\s+and\s+|,", b.get("skill_proficiencies", "")) if t.strip()]
        tools = [_clean(t) for t in re.split(r"\s+and\s+|,", b.get("tool_proficiency", "")) if t.strip()]
        # the Origin Feat (strip the "(see chapter N)" pointer + OCR noise)
        feat_name = _clean(re.sub(r"\(see chapte.*?\)", "", b.get("feat", "")))
        feat = {}
        if feat_name:
            rec = feats.get(_slug(feat_name)) or feats.get(_slug(feat_name.split("(")[0]))
            feat = {"index": _slug(feat_name), "name": feat_name, "text": (rec or {}).get("description", "")}
        out.append({
            "index": b.get("index"), "name": b.get("name"),
            "skills": skills, "tools": tools, "languages": 0,
            "abilityOptions": ability_options, "feat": feat,
            # original prose, kept for display
            "abilityScoresText": _clean(b.get("ability_scores", "")),
            "skillsText": _clean(b.get("skill_proficiencies", "")),
            "featText": feat_name,
            "equipment": b.get("equipment", ""),
            "local": True,
        })
    return out


def background(index: str) -> dict | None:
    """One parsed 2024 background by index (used by the Origin Feat lookup)."""
    return next((b for b in backgrounds() if b.get("index") == index), None)


def class_features_by_class() -> dict:
    """{classIndex: [{level, name, desc}]} — level-by-level base features (OCR names tidied)."""
    data = _load("class_features_2024_phb_by_class.json") or {}
    by = data.get("by_class", {}) if isinstance(data, dict) else {}
    return {ci: [{**f, "name": _fix_name(f.get("name", ""))} for f in feats]
            for ci, feats in by.items()}


def subclass_records() -> list:
    """The 48 local subclasses, each with a ``features: [{name, level, desc}]`` list (names tidied)."""
    out = []
    for s in _load("subclasses_2024_phb.json") or []:
        feats = [{**f, "name": _fix_name(f.get("name", ""))} for f in (s.get("features") or [])]
        out.append({**s, "features": feats})
    return out


def weapon_masteries() -> dict:
    """{properties: [{index,name,desc}], weapons: [{weapon,mastery,…}]} — the 8 mastery
    properties + 38 weapon→mastery mappings."""
    data = _load("weapon_masteries_2024_phb.json") or {}
    return {
        "properties": data.get("mastery_properties", []),
        "weapons": data.get("weapon_masteries", []),
    }


def languages() -> list:
    """19 language records (10 standard, 9 rare); Druidic/Thieves' Cant flagged secret."""
    return _load("languages_2024_phb.json") or []


def multiclassing() -> dict:
    """{prerequisites, proficiencies_gained, spellcaster_slot_table, notes}."""
    data = _load("multiclassing_2024_phb.json") or {}
    return {k: data.get(k) for k in ("prerequisites", "proficiencies_gained", "spellcaster_slot_table", "notes")
            if k in data}
