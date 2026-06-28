#!/usr/bin/env python
"""LOCAL-ONLY extractor: 2024 PHB base class features -> data/local/class_features_2024_phb.json

Strategy
--------
For each of the 12 classes we:
  1. Find the intro page (CORE <CLASS> TRAITS block / class flavour text).
  2. Find the '<CLASS> SUBCLASSES' header page and stop collection there.
  3. Concatenate all text lines from intro page up to (but not including) subclasses page.
  4. Extract every 'LEVEL N: <name>' block from that text, tolerating OCR artefacts:
       - 'LEVEL l:' (lowercase l for digit 1)
       - 'L EVEL 5:' (OCR letter-spacing)
       - 'LEVEL 9 :' (space before colon)
       - Leading junk characters like '| LEVEL 1:'
  5. Fuzzy-repair feature names against canonical lists.
  6. Deduplicate, sort by level, write JSON.

⚠ Reads a copyrighted PDF the user supplies locally. Output goes to data/local/ (gitignored).
NEVER commit the JSON.
"""
from __future__ import annotations

import json
import re
import sys
from difflib import get_close_matches
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "local"
SOURCE = {
    "name": "Player's Handbook (2024)",
    "publisher": "Wizards of the Coast",
    "license": "All rights reserved (local prototyping only)",
}

# ------------------------------------------------------------------ shared helpers
# (adapted from extract_phb2024_local.py)

def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def _clean(text: str) -> str:
    # rejoin hyphenated line breaks
    text = re.sub(r"-\s*\n\s*", "", text)
    text = text.replace("\n", " ")
    text = re.sub(r"([a-z])-\s+([a-z])", r"\1\2", text)
    # strip OCR'd page-furniture lines ("CHAPTER 3 | CHARACTER CLASSES 52" etc.)
    text = re.sub(
        r"\bCH(?:APTER?)?\s*[0-9]\s*[|I]\s*(?:CHARACTER\s+)?CLASS(?:ES)?\b.{0,40}",
        " ", text, flags=re.I,
    )
    text = re.sub(r"\s+", " ", text)
    # fix OCR digit/letter swaps in dice notation
    text = re.sub(r"\bl(d(?:4|6|8|10|12|20|100))\b", r"1\1", text)
    text = re.sub(r"\bl(st|nd|rd|th)\b", r"1\1", text)
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl")
    # strip trailing noise
    text = re.sub(r"[\s~^|;:=_•\-]{2,}$", "", text)
    # strip leading noise (commas, semicolons, pipes, lone letters from OCR column artifacts)
    text = re.sub(r"^[,;|.~\s]+", "", text)
    return text.strip()


def _despace(s: str) -> str:
    """Collapse OCR letter-spacing: 'L EVE L' -> 'LEVEL', 'RA GE' -> 'RAGE'."""
    prev = None
    while s != prev:
        prev = s
        s = re.sub(r"\b([A-Z]) (?=[A-Z])", r"\1", s)
        s = re.sub(r"(?<=[A-Z]) ([A-Z])\b", r"\1", s)
    return s


def _key(s: str) -> str:
    """Fold common OCR substitutions and strip non-alpha for fuzzy matching."""
    s = s.lower().replace("0", "o").replace("1", "l")
    return re.sub(r"[^a-z]", "", s)


# ------------------------------------------------------------------ canonical feature names
# Used for fuzzy-repairing OCR-garbled feature names.
# Only BASE class features (not subclass features) are listed here.
CANON_FEATURES: dict[str, list[str]] = {
    "barbarian": [
        "Rage", "Unarmored Defense", "Weapon Mastery", "Danger Sense", "Reckless Attack",
        "Barbarian Subclass", "Primal Knowledge", "Ability Score Improvement",
        "Extra Attack", "Fast Movement", "Feral Instinct", "Instinctive Pounce",
        "Brutal Strike", "Relentless Rage", "Improved Brutal Strike",
        "Persistent Rage", "Indomitable Might", "Epic Boon", "Primal Champion",
    ],
    "bard": [
        "Bardic Inspiration", "Expertise", "Spellcasting", "Jack of All Trades",
        "Bard Subclass", "Ability Score Improvement", "Font of Inspiration",
        "Countercharm", "Magical Secrets", "Superior Inspiration", "Words of Creation",
        "Epic Boon",
    ],
    "cleric": [
        "Divine Order", "Spellcasting", "Cleric Subclass", "Channel Divinity",
        "Ability Score Improvement", "Smite Undead", "Blessed Strikes",
        "Divine Intervention", "Improved Divine Intervention", "Greater Divine Intervention",
        "Epic Boon",
    ],
    "druid": [
        "Primal Order", "Spellcasting", "Wild Shape", "Wild Companion",
        "Druid Subclass", "Ability Score Improvement", "Timeless Body",
        "Beast Spells", "Archdruid", "Druidic", "Wild Resurgence",
        "Elemental Fury", "Improved Elemental Fury", "Epic Boon",
    ],
    "fighter": [
        "Fighting Style", "Second Wind", "Action Surge", "Fighter Subclass",
        "Ability Score Improvement", "Extra Attack", "Indomitable",
        "Studied Attacks", "Tactical Mind", "Tactical Shift", "Weapon Mastery",
        "Tactical Master", "Epic Boon",
    ],
    "monk": [
        "Martial Arts", "Unarmored Defense", "Monk Subclass", "Uncanny Metabolism",
        "Monk's Focus", "Unarmored Movement", "Deflect Attacks", "Slow Fall",
        "Ability Score Improvement", "Stunning Strike", "Empowered Strikes",
        "Evasion", "Acrobatic Movement", "Heightened Focus", "Self-Restoration",
        "Pure Body", "Perfect Self", "Deflect Energy", "Disciplined Survivor",
        "Perfect Focus", "Superior Defense", "Body and Mind", "Epic Boon",
    ],
    "paladin": [
        "Lay on Hands", "Fighting Style", "Spellcasting", "Channel Divinity",
        "Paladin Subclass", "Divine Smite", "Paladin's Smite", "Ability Score Improvement",
        "Extra Attack", "Aura of Protection", "Aura of Courage",
        "Radiant Strikes", "Cleansing Touch", "Aura Expansion", "Epic Boon",
        "Faithful Steed", "Abjure Foes", "Restoring Touch",
    ],
    "ranger": [
        "Favored Enemy", "Weapon Mastery", "Deft Explorer", "Fighting Style",
        "Spellcasting", "Ranger Subclass", "Roving", "Ability Score Improvement",
        "Extra Attack", "Tireless", "Nature's Veil", "Precise Hunter",
        "Feral Senses", "Foe Slayer", "Relentless Hunter", "Epic Boon",
    ],
    "rogue": [
        "Expertise", "Sneak Attack", "Thieves Cant", "Cunning Action",
        "Rogue Subclass", "Steady Aim", "Ability Score Improvement",
        "Uncanny Dodge", "Evasion", "Reliable Talent", "Slippery Mind",
        "Elusive", "Stroke of Luck", "Cunning Strike", "Improved Cunning Strike",
        "Devious Strikes", "Epic Boon",
    ],
    "sorcerer": [
        "Spellcasting", "Innate Sorcery", "Font of Magic", "Metamagic",
        "Sorcerer Subclass", "Ability Score Improvement", "Sorcerous Restoration",
        "Sorcery Incarnate", "Arcane Apotheosis", "Epic Boon",
    ],
    "warlock": [
        "Eldritch Invocations", "Magical Cunning", "Pact Magic", "Warlock Subclass",
        "Ability Score Improvement", "Mystic Arcanum", "Eldritch Master",
        "Contact Patron", "Epic Boon",
    ],
    "wizard": [
        "Spellcasting", "Arcane Recovery", "Scholar", "Wizard Subclass",
        "Ability Score Improvement", "Memorize Spell", "Spell Mastery",
        "Signature Spells", "Ritual Adept", "Epic Boon",
    ],
}

# Build per-class lookup: _key(name) -> canonical name
CANON_KEYS: dict[str, dict[str, str]] = {
    cls: {_key(n): n for n in names}
    for cls, names in CANON_FEATURES.items()
}

# Flat set of all base-feature keys for cross-class fuzzy fallback
ALL_CANON_KEYS: dict[str, str] = {}
for _cls_names in CANON_FEATURES.values():
    for _n in _cls_names:
        ALL_CANON_KEYS[_key(_n)] = _n


def _repair_feature_name(raw: str, cls: str) -> tuple[str, str]:
    """-> (best-effort name, status) where status in {'exact','fuzzy','suspect'}."""
    despaced = _despace(raw.strip())
    k = _key(despaced)
    cls_lookup = CANON_KEYS.get(cls, {})
    if k in cls_lookup:
        return cls_lookup[k], "exact"
    if k in ALL_CANON_KEYS:
        return ALL_CANON_KEYS[k], "exact"
    close = get_close_matches(k, list(cls_lookup), n=1, cutoff=0.75)
    if close:
        return cls_lookup[close[0]], "fuzzy"
    close = get_close_matches(k, list(ALL_CANON_KEYS), n=1, cutoff=0.75)
    if close:
        return ALL_CANON_KEYS[close[0]], "fuzzy"
    # Fall back: title-case the despaced raw
    return despaced.strip().title(), "suspect"


# ------------------------------------------------------------------ page detection
CLASS_ORDER = [
    "barbarian", "bard", "cleric", "druid", "fighter", "monk",
    "paladin", "ranger", "rogue", "sorcerer", "warlock", "wizard",
]

# OCR-tolerant LEVEL feature header regex.
# Handles:
#   LEVEL 1: RAGE             (clean)
#   LEVEL l: RAGE             (l for 1, common OCR swap)
#   L EVEL 5: EXTRA ATTACK    (letter-spaced)
#   LEVEL 9 : BRUTAL STRIKE   (space before colon)
#   I LEVEL l: RAGE           (leading junk single-char like pipe/I)
#   L EVE L I.~ : RAGE        (heavy garble)
#
# Key design choices:
#   - Allow any prefix before LEVEL but require a word-boundary before L-E-V-E-L
#     so that "MULTICLASS LEVEL" or "Barbarian level 1" don't match.
#   - Feature names must start with an uppercase letter to filter noise.
#   - "As A LEVEL 1 CHARACTER" and "LEVEL 1 RANGER SPELLS" are filtered later.
LEVEL_FEAT = re.compile(
    r"(?m)"                              # multiline (not ignorecase — names are UPPER)
    r"^.*?"                              # any prefix (lazy)
    r"(?<![A-Za-z])"                     # not immediately preceded by alpha
    r"L\s*E\s*V\s*E\s*L"               # L-E-V-E-L possibly letter-spaced
    r"\s+"                               # required whitespace before level number
    r"([lIl1][^:\-\n]{0,3}|\d[^:\-\n]{0,3})"  # level: OCR l/I/1 or real digit, max 4 chars
    r"\s*[:\-–—]\s*"                     # colon/dash separator
    r"([A-Z][^\n]+?)"                    # feature name: MUST start uppercase
    r"\s*$"                              # end of line
)


def _parse_level(raw: str) -> int | None:
    """Convert OCR level strings like 'l', 'I', '1', '9 ', '17' to int, or None.

    Only single-character OCR swaps are trusted (l->1, I->1).  Multi-character
    strings that contain non-numeric garbage (like 'I.~' for a garbled '4') are
    rejected, which filters out heavily mangled OCR level numbers.
    """
    s = raw.strip()
    # Single-char OCR swaps for digit 1
    if s in ("l", "I", "i", "|"):
        return 1
    # Replace known single-digit OCR swaps, then require the remainder is all digits
    s2 = s.replace("l", "1").replace("I", "1").replace("i", "1").replace("O", "0").replace("o", "0")
    # Reject if there are any non-digit characters remaining (e.g. 'I.~' -> '1.~')
    if not re.match(r"^\d+$", s2):
        return None
    try:
        n = int(s2)
        return n if 1 <= n <= 20 else None
    except ValueError:
        return None


def _find_class_page_ranges(doc) -> dict[str, tuple[int, int]]:
    """
    Returns {class_slug: (start_page, end_page_exclusive)}.

    start_page: the intro/core-traits page (one or two pages before the features table).
    end_page:   the page where '<CLASS> SUBCLASSES' header appears (exclusive).
    """
    features_table: dict[str, int] = {}
    subclasses_page: dict[str, int] = {}

    for p in range(doc.page_count):
        t = doc[p].get_text()
        for cls in CLASS_ORDER:
            CLS = cls.upper()
            # Features table marker: '<CLASS> FEATURES' in the first ~600 chars
            if CLS + " FEATURES" in t[:600] and cls not in features_table:
                features_table[cls] = p
            # Subclasses section = page that has the introductory paragraph
            # "A <Class> subclass is a specialization that grants you features..."
            # This sentence only appears once, on the true section header page.
            if cls not in subclasses_page:
                if re.search(
                    r"A\s+" + cls.title() + r"\s+subclass\s+is\s+a\s+specialization",
                    t, re.I
                ):
                    subclasses_page[cls] = p

    ranges: dict[str, tuple[int, int]] = {}
    for i, cls in enumerate(CLASS_ORDER):
        if cls not in features_table:
            continue
        ft_page = features_table[cls]
        # Start two pages before the features table (intro + art pages)
        start = max(0, ft_page - 2)
        if cls in subclasses_page:
            end = subclasses_page[cls]  # exclusive: stop before this page
        else:
            # Fallback: use the next class's features-table page - 2
            for j in range(i + 1, len(CLASS_ORDER)):
                nxt = CLASS_ORDER[j]
                if nxt in features_table:
                    end = features_table[nxt] - 2
                    break
            else:
                end = min(ft_page + 12, doc.page_count)
        ranges[cls] = (start, end)

    return ranges


# ------------------------------------------------------------------ skip-list detection
# These subclass-name patterns let us detect when the LEVEL header is a subclass feature
# (i.e. on a subclass named page) rather than a base class feature.
# We DON'T skip the generic "Barbarian Subclass" / "Cleric Subclass" features
# (those are base class features that unlock the subclass choice).
SUBCLASS_FEAT_NAMES: set[str] = set()
for _cls, _names in {
    "barbarian": ["Frenzy", "Mindless Rage", "Retaliation", "Intimidating Presence",
                  "Animal Speaker", "Rage Of The Wilds", "Aspect Of The Wilds",
                  "Nature Speaker", "Power Of The Wilds",
                  "Vitality Of The Tree", "Branches Of The Tree", "Battering Roots",
                  "Travel Along The Tree", "Divine Fury", "Fanatical Focus",
                  "Zealous Presence", "Rage Of The Gods"],
}.items():
    for _n in _names:
        SUBCLASS_FEAT_NAMES.add(_key(_n))


# ------------------------------------------------------------------ feature extraction

def _extract_class_features(doc, cls: str, start: int, end: int) -> list[dict]:
    """Extract base class features from PDF pages [start, end) for the given class."""
    # Collect all text from the page range
    lines: list[str] = []
    for p in range(start, min(end, doc.page_count)):
        lines.extend(doc[p].get_text().splitlines())

    joined = "\n".join(lines)
    matches = list(LEVEL_FEAT.finditer(joined))

    if len(matches) < 3:
        return []  # too few matches; page range likely wrong

    features: list[dict] = []
    seen_keys: set[tuple[int, str]] = set()

    for idx, m in enumerate(matches):
        raw_level_str = m.group(1).strip()
        raw_name = m.group(2).strip()

        level = _parse_level(raw_level_str)
        if level is None:
            continue

        # Reject spell-list table headers ("LEVEL 3: CLERIC SPELLS", "LEVEL 7 CLERIC SPELLS")
        if re.search(r"(?i)\bSPELLS?\b\s*$", raw_name):
            continue
        # Reject slot/table headers
        if re.search(r"(?i)\bSPELL\s+(LEVEL|SLOT|SCHOOL)\b", raw_name):
            continue

        name, status = _repair_feature_name(raw_name, cls)

        # Skip known subclass features
        if _key(name) in SUBCLASS_FEAT_NAMES:
            continue

        dedup_key = (level, _key(name))
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        # Body text: from end of this header to start of next match
        body_start = m.end()
        body_end = matches[idx + 1].start() if idx + 1 < len(matches) else len(joined)
        raw_body = joined[body_start:body_end]

        desc = _clean(raw_body)

        rec: dict = {
            "index": f"{cls}-{_slug(name)}",
            "name": name,
            "class": {"index": cls, "name": cls.title()},
            "level": level,
            "desc": desc,
            "srd": False,
            "local": True,
            "source": SOURCE,
        }
        if status == "fuzzy":
            rec["name_ocr_raw"] = raw_name
        elif status == "suspect":
            rec["name_ocr_suspect"] = raw_name

        features.append(rec)

    features.sort(key=lambda r: (r["level"], r["name"]))
    return features


# ------------------------------------------------------------------ main
def main(argv: list[str]) -> int:
    if not argv:
        print("usage: extract_phb2024_classes.py <path-to-PHB-2024.pdf>", file=sys.stderr)
        return 2

    pdf = Path(argv[0])
    if not pdf.exists():
        print(f"not found: {pdf}", file=sys.stderr)
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf))

    ranges = _find_class_page_ranges(doc)
    if not ranges:
        print("ERROR: could not locate class sections in PDF.", file=sys.stderr)
        return 1

    all_records: list[dict] = []
    by_class: dict[str, list[dict]] = {}
    gaps: list[str] = []

    for cls in CLASS_ORDER:
        if cls not in ranges:
            gaps.append(f"CLASS '{cls}': page range not detected.")
            continue

        start, end = ranges[cls]
        feats = _extract_class_features(doc, cls, start, end)

        for f in feats:
            if "name_ocr_suspect" in f:
                gaps.append(
                    f"CLASS '{cls}' L{f['level']}: name OCR suspect — "
                    f"raw='{f['name_ocr_suspect']}' -> guessed '{f['name']}'"
                )

        if len(feats) < 4:
            gaps.append(
                f"CLASS '{cls}': only {len(feats)} features found "
                f"(pages {start}–{end}) — manual review needed."
            )

        all_records.extend(feats)
        by_class[cls] = [
            {"level": f["level"], "name": f["name"], "desc": f["desc"]}
            for f in feats
        ]

    # ---- write flat list
    flat_path = OUT / "class_features_2024_phb.json"
    flat_path.write_text(
        json.dumps(all_records, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # ---- write grouped form
    grouped_path = OUT / "class_features_2024_phb_by_class.json"
    grouped_path.write_text(
        json.dumps({"by_class": by_class}, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # ---- summary
    total = len(all_records)
    print(f"class_features: {total} records, {len(gaps)} gaps")
    for cls in CLASS_ORDER:
        n = len(by_class.get(cls, []))
        rng = ranges.get(cls, ("?", "?"))
        print(f"  {cls:<12}: {n:>2} features, pages {rng[0]}–{rng[1]}")

    if gaps:
        print(f"\nGAPS ({len(gaps)}):")
        for g in gaps:
            print(f"  - {g}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
