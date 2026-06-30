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


@lru_cache(maxsize=1)
def _text_fix_pairs() -> tuple:
    """Flat [bad, good] OCR fixes applied to description text at read-time: the corrections file's
    ``text_fixes`` (so documented fixes take effect without re-running the extractor; good=None
    truncates at the bad span) plus a few unambiguous global patterns. The bad spans are unique OCR
    garbage, so applying them anywhere is safe."""
    pairs = [["Yl)u", "You"], ["tl)e ", "the "], ["Tl)e ", "The "], ["  ", " "]]
    tf = (_load("phb2024_corrections.json") or {}).get("text_fixes", {})
    for by_index in (tf.values() if isinstance(tf, dict) else []):
        for fixes in (by_index.values() if isinstance(by_index, dict) else []):
            for pair in (fixes or []):
                if isinstance(pair, list) and pair:
                    pairs.append([pair[0], pair[1] if len(pair) > 1 else None])
    return tuple(tuple(p) for p in pairs)


def _fix_text(text: str) -> str:
    """Apply the OCR text-fixes to a description string."""
    if not text:
        return text
    for bad, good in _text_fix_pairs():
        if bad in text:
            text = text.split(bad)[0] if good is None else text.replace(bad, good)
    return text


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
            return [{"name": _fix_name(t["name"]), "desc": _fix_text(t.get("desc", ""))}
                    for t in (s.get("traits") or [])
                    if isinstance(t, dict) and t.get("name") and not _is_fragment_trait(t["name"])]
    return []


def feats() -> list:
    return _names(_load("feats_2024_phb.json"))


def feats_full() -> list:
    """Full 2024 feat records [{index, name, type, prerequisites_text, description}] for the feat
    picker (the `feats()` accessor returns names only for optionLists)."""
    out = []
    for f in _load("feats_2024_phb.json") or []:
        if isinstance(f, dict) and f.get("index"):
            out.append({"index": f["index"], "name": f.get("name") or f["index"],
                        "type": f.get("type") or "general",
                        "prerequisites_text": f.get("prerequisites_text") or "None",
                        "description": _fix_text(f.get("description") or "")})
    return out


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
            feat = {"index": _slug(feat_name), "name": feat_name, "text": _fix_text((rec or {}).get("description", ""))}
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
    return {ci: [{**f, "name": _fix_name(f.get("name", "")), "desc": _fix_text(f.get("desc", ""))} for f in feats]
            for ci, feats in by.items()}


def subclass_records() -> list:
    """The 48 local subclasses, each with a ``features: [{name, level, desc}]`` list (names + text tidied)."""
    out = []
    for s in _load("subclasses_2024_phb.json") or []:
        feats = [{**f, "name": _fix_name(f.get("name", "")), "desc": _fix_text(f.get("desc", ""))}
                 for f in (s.get("features") or [])]
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


@lru_cache(maxsize=1)
def _weapon_mastery_map() -> dict:
    wm = weapon_masteries()
    prop_name = {p.get("index"): p.get("name") for p in wm.get("properties", []) if p.get("index")}
    out = {}
    for w in wm.get("weapons", []):
        wi, mi = w.get("weapon"), w.get("mastery")
        if wi and mi:
            out[wi] = prop_name.get(mi, str(mi).title())
    return out


def weapon_mastery(weapon_index: str) -> str | None:
    """The 2024 mastery property name for a weapon (e.g. 'longsword' -> 'Sap'); None if none."""
    return _weapon_mastery_map().get(weapon_index)


@lru_cache(maxsize=1)
def mastery_classes() -> frozenset:
    """The 2024 classes that gain the Weapon Mastery feature — and so may APPLY a weapon's mastery
    property (a non-warrior can wield the weapon but not use its mastery). Derived from the
    class-features data rather than hardcoded: barbarian, fighter, paladin, ranger, rogue."""
    cfb = class_features_by_class()
    return frozenset(ci for ci, feats in cfb.items()
                     if any("weapon mastery" in (f.get("name", "").lower()) for f in (feats or [])))


def languages() -> list:
    """19 language records (10 standard, 9 rare); Druidic/Thieves' Cant flagged secret."""
    return _load("languages_2024_phb.json") or []


def multiclassing() -> dict:
    """{prerequisites, proficiencies_gained, spellcaster_slot_table, notes, spellcasting_level_formula}."""
    data = _load("multiclassing_2024_phb.json") or {}
    return {k: data.get(k) for k in ("prerequisites", "proficiencies_gained", "spellcaster_slot_table",
                                     "notes", "spellcasting_level_formula") if k in data}


# bucket key -> display category for the equipment picker
_EQUIP_BUCKETS = {"weapons": "Weapon", "armor": "Armor", "tools": "Tools", "adventuring_gear": "Adventuring Gear"}


def equipment() -> list:
    """2024 PHB equipment as picker-ready catalog cards: [{index, name, category, local, mastery?,
    eligibilityNote?}]. Flattens the weapons/armor/tools/adventuring_gear buckets; the bucket is the
    category. `eligibilityNote` (Musket/Pistol) drives the firearm-proficiency gate in the picker."""
    data = _load("equipment_2024_phb.json") or {}
    out = []
    for bucket, label in _EQUIP_BUCKETS.items():
        for e in (data.get(bucket) or []):
            if not isinstance(e, dict) or not e.get("index"):
                continue
            card = {"index": e["index"], "name": _clean(e.get("name") or e["index"]),
                    "category": label, "local": True}
            if e.get("mastery"):
                card["mastery"] = e["mastery"]
            if e.get("eligibility_note"):
                card["eligibilityNote"] = e["eligibility_note"]
                card["firearm"] = True  # A.5: gated — needs DEX 13+ or Firearms proficiency
            out.append(card)
    # A.4: a single "Trinket" item whose + Action rolls the d100 trinket table (not a creation step).
    if data.get("weapons") is not None or _load("trinkets_2024_phb.json"):
        out.append({"index": "trinket", "name": "Trinket", "category": "Adventuring Gear",
                    "local": True, "trinketRoller": True})
    return out


def spells(class_index: str | None = None) -> list:
    """2024 PHB spells as picker rows: [{index, name, level, classes, ocrSuspect}]. When `class_index`
    is given, only spells whose `classes[]` includes it (case-insensitive). `ocrSuspect` flags the 69
    records with possible OCR artifacts (shown with a warning icon, not hidden)."""
    ci = (class_index or "").strip().lower()
    out = []
    for s in _load("spells_2024_phb.json") or []:
        if not isinstance(s, dict) or not s.get("index"):
            continue
        classes = [str(c).lower() for c in (s.get("classes") or [])]
        if ci and ci not in classes:
            continue
        out.append({"index": s["index"], "name": _clean(s.get("name") or s["index"]),
                    "level": s.get("level"), "classes": classes,
                    "ocrSuspect": bool(s.get("ocr_suspect")),
                    "atHigherLevels": (s.get("at_higher_levels") or "").strip()})
    return out


@lru_cache(maxsize=1)
def _spells_by_index() -> dict:
    return {s["index"]: s for s in (_load("spells_2024_phb.json") or [])
            if isinstance(s, dict) and s.get("index")}


def spell(index: str) -> dict | None:
    """One full 2024 spell record by index (for the detail view — carries description + the separate
    `at_higher_levels` string)."""
    return _spells_by_index().get(index)


def trinkets() -> list:
    """The 2024 d100 trinket table: [{roll, description}] (100 entries). Drives the Trinket item's
    randomiser action (roll on the table), not a creation-step wizard."""
    data = _load("trinkets_2024_phb.json") or {}
    return data.get("trinkets") or []


# A.11: the 2024 Barbarian Features table (Rages / Rage Damage / Weapon Mastery count by level). This
# columnar data was OCR-garbled in the class-features extraction, so it's hardcoded here from the PHB
# table. ⚠️ owner-confirm these values. Indexed by character level 1-20; level 20 rages = "Unlimited".
_BARBARIAN_TABLE = {
    1: {"rages": "2", "rageDamage": 2, "weaponMastery": 2},
    2: {"rages": "2", "rageDamage": 2, "weaponMastery": 2},
    3: {"rages": "3", "rageDamage": 2, "weaponMastery": 2},
    4: {"rages": "3", "rageDamage": 2, "weaponMastery": 3},
    5: {"rages": "3", "rageDamage": 2, "weaponMastery": 3},
    6: {"rages": "4", "rageDamage": 2, "weaponMastery": 3},
    7: {"rages": "4", "rageDamage": 2, "weaponMastery": 3},
    8: {"rages": "4", "rageDamage": 2, "weaponMastery": 3},
    9: {"rages": "4", "rageDamage": 3, "weaponMastery": 3},
    10: {"rages": "4", "rageDamage": 3, "weaponMastery": 4},
    11: {"rages": "4", "rageDamage": 3, "weaponMastery": 4},
    12: {"rages": "5", "rageDamage": 3, "weaponMastery": 4},
    13: {"rages": "5", "rageDamage": 3, "weaponMastery": 4},
    14: {"rages": "5", "rageDamage": 3, "weaponMastery": 4},
    15: {"rages": "5", "rageDamage": 3, "weaponMastery": 4},
    16: {"rages": "5", "rageDamage": 4, "weaponMastery": 4},
    17: {"rages": "6", "rageDamage": 4, "weaponMastery": 4},
    18: {"rages": "6", "rageDamage": 4, "weaponMastery": 4},
    19: {"rages": "6", "rageDamage": 4, "weaponMastery": 4},
    20: {"rages": "Unlimited", "rageDamage": 4, "weaponMastery": 4},
}


def barbarian_resources(level: int) -> dict | None:
    """{rages, rageDamage, weaponMastery} for a Barbarian at `level` (1-20), else None. Hardcoded from
    the 2024 PHB Barbarian table (the OCR couldn't recover those columns)."""
    try:
        return _BARBARIAN_TABLE.get(max(1, min(20, int(level))))
    except (TypeError, ValueError):
        return None


def feat_prereq_status(feat: dict, character: dict) -> dict:
    """Evaluate a 2024 feat's `prerequisites_text` against a character → {available, reason}.

    ADVISORY, not a hard block (rule-of-cool friendly): an unparseable / unknown-feature prereq
    defaults to available with a "check" note rather than hiding the feat. Types:
    origin → always; fighting-style → needs a Fighting Style feature; epic-boon → Level 19+;
    general → free text ("Level 4+", "Strength 13+", "Spellcasting or Pact Magic Feature", a feat name).
    Alternatives joined by "or" pass if ANY clause is met.
    """
    ftype = (feat.get("type") or "").lower()
    text = (feat.get("prerequisites_text") or "").strip()
    if ftype == "origin" or not text or text.lower() == "none":
        return {"available": True, "reason": ""}
    pc = character.get("pc") or {}
    classes = pc.get("classes") if isinstance(pc.get("classes"), list) else None
    level = sum(int((c or {}).get("level") or 0) for c in classes) if classes else int(pc.get("level") or 0)
    abilities = {str(k).upper(): v for k, v in (character.get("abilities") or {}).items()}
    classes_have = {(pc.get("class") or "").lower()} | ({(c.get("class") or "").lower() for c in classes} if classes else set())
    classes_have.discard("")
    have_feats = {_slug(str(f)) for f in (pc.get("feats") or [])}
    is_caster = bool(character.get("spellcasting")) or bool(
        classes_have & {"bard", "cleric", "druid", "sorcerer", "wizard", "warlock", "paladin", "ranger"})
    has_fighting_style = bool(classes_have & {"fighter", "paladin", "ranger"})  # heuristic

    def clause_met(c: str):
        c = c.strip()
        m = re.search(r"level\s+(\d+)", c, re.I)
        if m:
            return level >= int(m.group(1))
        m = re.search(r"(strength|dexterity|constitution|intelligence|wisdom|charisma)\s+(\d+)", c, re.I)
        if m:
            return int(abilities.get(_ABILITIES[m.group(1).lower()], 0) or 0) >= int(m.group(2))
        cl = c.lower()
        if "spellcasting" in cl or "pact magic" in cl:
            return is_caster
        if "fighting style" in cl:
            return has_fighting_style
        if cl.endswith("feature"):
            return None  # an unknown class feature — can't evaluate, don't hard-block
        return True if _slug(c) in have_feats else None  # otherwise a feat-name prereq

    results = [clause_met(c) for c in re.split(r"\s+or\s+", text, flags=re.I)]
    if any(r is True for r in results):
        return {"available": True, "reason": ""}
    if results and all(r is False for r in results):
        return {"available": False, "reason": "Requires " + text}
    return {"available": True, "reason": "Check prerequisite: " + text}  # unevaluable → advisory
