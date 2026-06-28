#!/usr/bin/env python
"""LOCAL-ONLY extractor: 2024 PHB Weapon Mastery properties + weapon-to-mastery table.

Output: data/local/weapon_masteries_2024_phb.json
  {
    "mastery_properties": [ {index, name, desc, srd, local, source}, ... ],
    "weapon_masteries":   [ {weapon, mastery, weapon_type}, ... ]
  }

All 8 mastery properties live on page 212 (immediately after VERSATILE) under the
"MASTERY PROPERTIES" heading.  The weapons table with the Mastery column is on
page 213.

Usage:
  .venv_forge\\Scripts\\python.exe scripts\\extract_phb2024_weapon_masteries.py "PDFs/D&D 5E [2024] PHB.pdf"
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "local"
SOURCE = {
    "name": "Player's Handbook (2024)",
    "publisher": "Wizards of the Coast",
    "license": "All rights reserved (local prototyping only)",
}

# ------------------------------------------------------------------ helpers (copied from extract_phb2024_local.py)

def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def _clean(text: str) -> str:
    """Strip OCR artifacts, rejoin hyphenated line-breaks, normalise whitespace."""
    text = re.sub(r"-\s*\n\s*", "", text)
    text = text.replace("\n", " ")
    text = re.sub(r"([a-z])-\s+([a-z])", r"\1\2", text)
    # strip page furniture ("CHAPTER 6 | EQUIPMENT ...")
    text = re.sub(
        r"\bCH\s*\\?\s*[APT]{1,2}TE?\s*R\b.{0,4}\d.{0,60}?EQUIPMENT\b\s*\S*",
        " ", text, flags=re.I,
    )
    text = re.sub(r"\s+", " ", text)
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl")
    text = re.sub(r"[\s~^|;:=_•\-]{2,}$", "", text)
    return text.strip()


# ------------------------------------------------------------------ known property data
# The property text from the PDF is OCR-noisy in places (Topple and Vex especially).
# We keep an authoritative fallback for each property so OCR noise never silently
# corrupts the output; the extractor tries the PDF first and falls back if it looks bad.

CANON_PROPERTIES: dict[str, str] = {
    "Cleave": (
        "If you hit a creature with a melee attack roll using this weapon, you can make "
        "a melee attack roll with the weapon against a second creature within 5 feet of "
        "the first that is also within your reach. On a hit, the second creature takes "
        "the weapon's damage, but don't add your ability modifier to that damage unless "
        "that modifier is negative. You can make this extra attack only once per turn."
    ),
    "Graze": (
        "If your attack roll with this weapon misses a creature, you can deal damage to "
        "that creature equal to the ability modifier you used to make the attack roll. "
        "This damage is the same type dealt by the weapon, and the damage can be "
        "increased only by increasing the ability modifier."
    ),
    "Nick": (
        "When you make the extra attack of the Light property, you can make it as part "
        "of the Attack action instead of as a Bonus Action. You can make this extra "
        "attack only once per turn."
    ),
    "Push": (
        "If you hit a creature with this weapon, you can push the creature up to 10 feet "
        "straight away from yourself if it is Large or smaller."
    ),
    "Sap": (
        "If you hit a creature with this weapon, that creature has Disadvantage on its "
        "next attack roll before the start of your next turn."
    ),
    "Slow": (
        "If you hit a creature with this weapon and deal damage to it, you can reduce its "
        "Speed by 10 feet until the start of your next turn. If the creature is hit more "
        "than once by weapons that have this property, the Speed reduction doesn't exceed "
        "10 feet."
    ),
    "Topple": (
        "If you hit a creature with this weapon, you can force the creature to make a "
        "Constitution saving throw (DC 8 plus the ability modifier used to make the attack "
        "roll and your Proficiency Bonus). On a failed save, the creature has the Prone "
        "condition."
    ),
    "Vex": (
        "If you hit a creature with this weapon and deal damage to the creature, you have "
        "Advantage on your next attack roll against that creature before the end of your "
        "next turn."
    ),
}

PROPERTY_ORDER = ["Cleave", "Graze", "Nick", "Push", "Sap", "Slow", "Topple", "Vex"]

# ------------------------------------------------------------------ mastery property extractor

def _extract_mastery_properties(doc) -> tuple[list[dict], list[str]]:
    """Find and parse the MASTERY PROPERTIES section (page 212 in the 2024 PHB scan).

    Returns (records, gaps).  For each property, the OCR text is used when it is clean
    enough; otherwise the canon fallback is used and a gap entry is written.
    """
    gaps: list[str] = []

    # Locate the page carrying "MASTERY PROPERTIE" heading
    target_page: int | None = None
    for p in range(doc.page_count):
        t = doc[p].get_text()
        if "MASTERY PROPERTIE" in t.upper():
            # Make sure it's the properties definition page, not a class features table
            if any(name in t for name in ("CLEAVE", "GRAZE", "NICK", "PUSH")):
                target_page = p
                break
    if target_page is None:
        # Fallback: use page 212 (0-indexed) which is where the section lives in this scan
        target_page = 212
        gaps.append("MASTERY PROPERTIES: heading page not auto-located — using page 212 fallback.")

    raw_text = doc[target_page].get_text()

    # Slice out only the MASTERY PROPERTIES block (everything from "MASTERY PROPERTIE" onward)
    mp_start = raw_text.upper().find("MASTERY PROPERTIE")
    if mp_start == -1:
        gaps.append("MASTERY PROPERTIES: section not found on target page — falling back to canon text.")
        section_text = "\n".join(f"{n.upper()}\n{d}" for n, d in CANON_PROPERTIES.items())
    else:
        section_text = raw_text[mp_start:]

    # Split section into per-property blocks on ALL-CAPS property name lines.
    # Pattern: a line that is exactly one of the 8 property names (in caps, possibly
    # with stray whitespace/punctuation).
    prop_pattern = re.compile(
        r"(?im)^\s*(CLEAVE|GRAZE|NICK|PUSH|SAP|SLOW|TOPPLE|VEX)\s*$"
    )
    splits = list(prop_pattern.finditer(section_text))

    ocr_blocks: dict[str, str] = {}
    for i, m in enumerate(splits):
        name_key = m.group(1).title()  # e.g. "CLEAVE" -> "Cleave"
        start = m.end()
        end = splits[i + 1].start() if i + 1 < len(splits) else len(section_text)
        body = _clean(section_text[start:end])
        ocr_blocks[name_key] = body

    records: list[dict] = []
    for name in PROPERTY_ORDER:
        ocr_body = ocr_blocks.get(name, "")

        # Accept OCR text only if it is long enough and doesn't look obviously garbled.
        # Key signals of garble:
        #   - replacement char (U+FFFD)
        #   - stray punctuation clusters ("[:;]{2,}")
        #   - punctuation embedded mid-word between alpha chars ("[a-z][;:~|,•][a-z]")
        #   - middle-dot / interpunct within a word ("prop·", "ver·")
        #   - non-ASCII non-typographic chars mid-word
        #   - short length
        looks_garbled = (
            len(ocr_body) < 60
            or "�" in ocr_body          # replacement char
            or "·" in ocr_body               # middle dot (OCR soft-hyphen artifact)
            or re.search(r"[a-z][;:~|,•][a-z]", ocr_body)   # punct between letters
            or re.search(r"[:;]{2,}", ocr_body)              # punct run
            or re.search(r"[a-z]\d[a-z]", ocr_body)         # digit embedded mid-word
            # known broken tokens in this scan
            or "ver,pon" in ocr_body       # Vex: "weapon" garbled
            or ("Ad" in ocr_body and "rntage" in ocr_body)  # Vex: "Advantage" garbled
            or "P, one condition" in ocr_body   # Topple: "Prone condition" garbled
        )

        if ocr_body and not looks_garbled:
            desc = ocr_body
            used_canon = False
        else:
            desc = CANON_PROPERTIES[name]
            used_canon = True
            if ocr_body:
                gaps.append(
                    f"MASTERY '{name}': OCR body looked garbled — used canon text. "
                    f"OCR was: '{ocr_body[:80]}...'"
                )
            else:
                gaps.append(f"MASTERY '{name}': not found in OCR — used canon text.")

        rec: dict = {
            "index": _slug(name),
            "name": name,
            "desc": desc,
            "srd": False,
            "local": True,
            "source": SOURCE,
        }
        if used_canon:
            rec["desc_source"] = "canon-fallback"
        records.append(rec)

    if len(records) != 8:
        gaps.append(
            f"MASTERY PROPERTIES: expected 8, got {len(records)} — "
            "check the section parse."
        )
    return records, gaps


# ------------------------------------------------------------------ weapons table extractor

# Canonical weapon names in book order (for disambiguation of OCR noise).
# The weapons table is on page 213 in this scan.
CANON_WEAPONS: list[tuple[str, str]] = [
    # (name, weapon_type)  -- weapon_type mirrors D&D Open5e slug conventions
    ("Club",           "simple-melee"),
    ("Dagger",         "simple-melee"),
    ("Greatclub",      "simple-melee"),
    ("Handaxe",        "simple-melee"),
    ("Javelin",        "simple-melee"),
    ("Light Hammer",   "simple-melee"),
    ("Mace",           "simple-melee"),
    ("Quarterstaff",   "simple-melee"),
    ("Sickle",         "simple-melee"),
    ("Spear",          "simple-melee"),
    ("Dart",           "simple-ranged"),
    ("Light Crossbow", "simple-ranged"),
    ("Shortbow",       "simple-ranged"),
    ("Sling",          "simple-ranged"),
    ("Battleaxe",      "martial-melee"),
    ("Flail",          "martial-melee"),
    ("Glaive",         "martial-melee"),
    ("Greataxe",       "martial-melee"),
    ("Greatsword",     "martial-melee"),
    ("Halberd",        "martial-melee"),
    ("Lance",          "martial-melee"),
    ("Longsword",      "martial-melee"),
    ("Maul",           "martial-melee"),
    ("Morningstar",    "martial-melee"),
    ("Pike",           "martial-melee"),
    ("Rapier",         "martial-melee"),
    ("Scimitar",       "martial-melee"),
    ("Shortsword",     "martial-melee"),
    ("Trident",        "martial-melee"),
    ("Warhammer",      "martial-melee"),
    ("War Pick",       "martial-melee"),
    ("Whip",           "martial-melee"),
    ("Blowgun",        "martial-ranged"),
    ("Hand Crossbow",  "martial-ranged"),
    ("Heavy Crossbow", "martial-ranged"),
    ("Longbow",        "martial-ranged"),
    ("Musket",         "martial-ranged"),
    ("Pistol",         "martial-ranged"),
]

MASTERY_NAMES = {"Cleave", "Graze", "Nick", "Push", "Sap", "Slow", "Topple", "Vex"}

# Regex to recognise a mastery property name appearing in a line
_MASTERY_RE = re.compile(
    r"\b(Cleave|Graze|Nick|Push|Sap|Slow|Topple|Vex)\b", re.I
)

# Weapon name lookup: normalised key -> canonical name
_WPN_KEY = {re.sub(r"[^a-z]", "", n.lower()): (n, wt) for n, wt in CANON_WEAPONS}


def _wpn_key(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


def _extract_weapon_masteries(doc) -> tuple[list[dict], list[str]]:
    """Parse the weapons table from page 213, returning weapon-mastery mappings."""
    gaps: list[str] = []

    # Locate the weapons table page (should be page 213, 0-indexed)
    table_page: int | None = None
    for p in range(doc.page_count):
        t = doc[p].get_text()
        if (
            "Simple Melee Weapons" in t
            and "Martial Melee Weapons" in t
            and "Mastery" in t
        ):
            table_page = p
            break

    if table_page is None:
        gaps.append("WEAPONS TABLE: page not found — no weapon mappings extracted.")
        return [], gaps

    raw = doc[table_page].get_text()
    lines = raw.splitlines()

    # Strategy: scan each line; if it starts with (or contains) a known weapon name
    # followed later (within 1-3 lines) by a mastery property name, record the pair.
    # The OCR lays out the table in reading order: Name / Damage / Properties / Mastery / Weight / Cost
    # but column values sometimes wrap across lines.

    found: dict[str, dict] = {}  # canonical_name -> {weapon, mastery, weapon_type}

    # Build a fast lookup: key -> (canonical_name, weapon_type)
    # Detect current section from section headers
    section_map = {
        "simplemeleew": "simple-melee",
        "simplerangedw": "simple-ranged",
        "martialmeleew": "martial-melee",
        "martialrangedw": "martial-ranged",
    }
    current_type = "simple-melee"

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Update section type
        lk = _wpn_key(line)
        for hdr, wtype in section_map.items():
            if lk.startswith(hdr[:12]):
                current_type = wtype
                break

        # Try to match weapon name at start of line
        # Weapon names can be 1-3 words; try matching progressively
        matched_wpn: str | None = None
        matched_wtype: str | None = None

        for word_count in (3, 2, 1):
            # grab up to `word_count` whitespace-separated tokens from this line
            tokens = line.split()
            if len(tokens) < word_count:
                continue
            candidate = " ".join(tokens[:word_count])
            ck = _wpn_key(candidate)
            if ck in _WPN_KEY:
                matched_wpn, matched_wtype = _WPN_KEY[ck]
                break

        if matched_wpn:
            # Look for mastery property in this line and the next 3 lines
            window = " ".join(lines[i: i + 4])
            m = _MASTERY_RE.search(window)
            if m:
                mastery = m.group(1).title()  # normalise case
                found[matched_wpn] = {
                    "weapon": _slug(matched_wpn),
                    "weapon_name": matched_wpn,
                    "mastery": _slug(mastery),
                    "weapon_type": matched_wtype or current_type,
                }
            else:
                gaps.append(
                    f"WEAPON '{matched_wpn}': found in table but mastery property not detected in window."
                )

        i += 1

    # Fill in any missing weapons from the canon list
    missing = [n for n, _ in CANON_WEAPONS if n not in found]
    if missing:
        gaps.append(
            f"WEAPONS TABLE: {len(missing)} weapon(s) not matched from OCR — "
            f"check manually: {', '.join(missing)}"
        )

    # Build output in canonical order
    records: list[dict] = []
    for canon_name, wtype in CANON_WEAPONS:
        if canon_name in found:
            rec = found[canon_name]
            records.append({
                "weapon": rec["weapon"],
                "weapon_name": rec["weapon_name"],
                "mastery": rec["mastery"],
                "weapon_type": rec["weapon_type"],
            })
        # (missing weapons are already reported in gaps above)

    return records, gaps


# ------------------------------------------------------------------ main

def main(argv: list[str]) -> int:
    if not argv:
        print(
            "usage: extract_phb2024_weapon_masteries.py <path-to-PHB-2024.pdf>",
            file=sys.stderr,
        )
        return 2
    pdf = Path(argv[0])
    if not pdf.exists():
        print(f"not found: {pdf}", file=sys.stderr)
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf)

    props, gaps1 = _extract_mastery_properties(doc)
    mappings, gaps2 = _extract_weapon_masteries(doc)
    all_gaps = gaps1 + gaps2

    output = {
        "mastery_properties": props,
        "weapon_masteries": mappings,
    }
    out_path = OUT / "weapon_masteries_2024_phb.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    n_props = len(props)
    n_wpns = len(mappings)
    n_gaps = len(all_gaps)
    print(f"weapon_masteries: {n_props} mastery properties, {n_wpns} weapon mappings, {n_gaps} gaps")
    if all_gaps:
        print("Gaps:")
        for g in all_gaps:
            print(f"  - {g}")
    print(f"Output: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
