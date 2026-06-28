#!/usr/bin/env python
"""LOCAL-ONLY extractor: 2024 PHB Languages -> data/local/languages_2024_phb.json

Reads the STANDARD LANGUAGES and RARE LANGUAGES tables from the 2024 PHB (page 35
in the OCR'd PDF).  The 2024 edition uses an "Origin" column rather than the
2014 "Typical Speakers" column, and has dropped the "Script" column entirely.
We map "Origin" -> typical_speakers for schema compatibility and leave "script"
as an empty string (not present in this edition).

Notable 2024 changes captured:
  * Common Sign Language is NEW (2024 addition)
  * Druidic and Thieves' Cant are listed under Rare Languages (secret languages)
  * Primordial has four dialects: Aquan, Auran, Ignan, Terran

Usage:
    .venv_forge/Scripts/python.exe scripts/extract_phb2024_languages.py "PDFs/D&D 5E [2024] PHB.pdf"

Output: data/local/languages_2024_phb.json
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

# ---------------------------------------------------------------------------
# Helpers (minimal subset from extract_phb2024_local.py)
# ---------------------------------------------------------------------------

def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def _despace(s: str) -> str:
    """Collapse OCR letter-spacing artefacts: 'D RA C O N IC' -> 'DRACONIC'."""
    prev = None
    while s != prev:
        prev = s
        s = re.sub(r"\b([A-Z]) (?=[A-Z])", r"\1", s)
        s = re.sub(r"(?<=[A-Z]) ([A-Z])\b", r"\1", s)
    return s


def _clean(text: str) -> str:
    text = re.sub(r"-\s*\n\s*", "", text)
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl")
    return text.strip()


# ---------------------------------------------------------------------------
# Canonical language data (ground-truth for OCR verification / gap detection)
# ---------------------------------------------------------------------------

# Each entry: (name, type, notes)
# "typical_speakers" and "script" will be filled from the PDF.
CANON_STANDARD = [
    ("Common",               "standard", ""),
    ("Common Sign Language", "standard", "New in 2024 PHB"),
    ("Draconic",             "standard", ""),
    ("Dwarvish",             "standard", ""),
    ("Elvish",               "standard", ""),
    ("Giant",                "standard", ""),
    ("Gnomish",              "standard", ""),
    ("Goblin",               "standard", ""),
    ("Halfling",             "standard", ""),
    ("Orc",                  "standard", ""),
]

CANON_RARE = [
    ("Abyssal",      "rare", ""),
    ("Celestial",    "rare", ""),
    ("Deep Speech",  "rare", ""),
    ("Druidic",      "rare", "Secret language; known only by Druids"),
    ("Infernal",     "rare", ""),
    ("Primordial",   "rare", "Includes dialects: Aquan, Auran, Ignan, Terran"),
    ("Sylvan",       "rare", ""),
    ("Thieves' Cant","rare", "Secret language; known only by Rogues and criminal guilds"),
    ("Undercommon",  "rare", ""),
]

# Key helpers for matching OCR text to canon names
def _key(s: str) -> str:
    s = s.lower().replace("0", "o").replace("1", "l")
    return re.sub(r"[^a-z]", "", s)


CANON_ALL = CANON_STANDARD + CANON_RARE
CANON_BY_KEY = {_key(n): (n, t, notes) for n, t, notes in CANON_ALL}


# ---------------------------------------------------------------------------
# Table extraction via positional (block-level) PDF parsing
# ---------------------------------------------------------------------------

def _extract_two_col_table(blocks: list, header_kw: str) -> list[dict]:
    """Extract Language/Origin pairs from a two-column table block.

    The PDF renders table text as separate positioned blocks.  We locate the
    'Language' header block and the 'Origin' header block, measure their x
    extents, then collect all text blocks that fall within those columns below
    the header row.
    """
    # Find the Language and Origin header blocks
    lang_hdr = origin_hdr = None
    for b in blocks:
        txt = b[4].strip()
        if txt.lower() == "language":
            lang_hdr = b
        if txt.lower() == "origin":
            origin_hdr = b

    if lang_hdr is None or origin_hdr is None:
        return []

    # Define column x-ranges (generous tolerance)
    lang_x0 = lang_hdr[0] - 5
    lang_x1 = lang_hdr[2] + 80      # language names can be wide
    origin_x0 = origin_hdr[0] - 5
    origin_x1 = origin_hdr[2] + 200  # origins can be long

    # Header y position — collect rows below it
    hdr_y = lang_hdr[1]

    # Gather (y_centre, text, column) for all sub-header blocks
    rows: list[tuple[float, str, str]] = []
    for b in blocks:
        bx0, by0, bx1, by1, txt, *_ = b
        txt = txt.strip()
        if not txt:
            continue
        by_mid = (by0 + by1) / 2
        if by_mid <= hdr_y:
            continue
        # Determine column membership
        bx_mid = (bx0 + bx1) / 2
        if lang_x0 <= bx_mid <= lang_x1:
            rows.append((by_mid, txt, "lang"))
        elif origin_x0 <= bx_mid <= origin_x1:
            rows.append((by_mid, txt, "origin"))

    if not rows:
        return []

    # Sort by y position
    rows.sort(key=lambda r: r[0])

    # Pair language rows with the closest origin row
    lang_rows = [(y, t) for y, t, col in rows if col == "lang"]
    origin_rows = [(y, t) for y, t, col in rows if col == "origin"]

    # Match each language to the nearest (by y) origin
    pairs: list[tuple[str, str]] = []
    for ly, ltxt in lang_rows:
        if not origin_rows:
            pairs.append((ltxt, ""))
            continue
        closest = min(origin_rows, key=lambda r: abs(r[0] - ly))
        pairs.append((ltxt, closest[1]))

    return pairs


def _find_language_page(doc) -> int | None:
    """Return the 0-indexed page number of the CHOOSE LANGUAGES section."""
    for p in range(doc.page_count):
        t = doc[p].get_text()
        if "CHOOSE LANGUAGES" in t or ("STANDARD LANGUAGES" in t and "RARE LANGUAGES" in t):
            return p
    return None


def _ocr_fix_name(raw: str) -> str:
    """Fix common OCR garbling in language names."""
    # 'Ore' -> 'Orc' (common OCR swap)
    raw = raw.strip()
    if raw.lower() == "ore":
        return "Orc"
    # Remove stray footnote markers like '*', '•~', '~'
    raw = re.sub(r"[*•~†‡]+.*$", "", raw).strip()
    return raw


def _ocr_fix_origin(raw: str) -> str:
    """Fix common OCR garbling in origin/typical-speakers text."""
    # 'Ores' -> 'Orcs', 'lgnan' -> 'Ignan' etc.
    fixes = {
        "Ores": "Orcs",
        "lgnan": "Ignan",  # OCR confuses 'I' with 'l'
    }
    for bad, good in fixes.items():
        raw = raw.replace(bad, good)
    return raw


def extract_languages(doc) -> tuple[list[dict], list[str]]:
    """Extract language records from the PDF.  Returns (records, gaps)."""
    gaps: list[str] = []

    page_num = _find_language_page(doc)
    if page_num is None:
        gaps.append("LANGUAGES: CHOOSE LANGUAGES / STANDARD LANGUAGES section not found in PDF.")
        return [], gaps

    page = doc[page_num]
    blocks = page.get_text("blocks")

    # The page has TWO tables side-by-side: Standard (left) and Rare (right).
    # We split blocks by their x midpoint to isolate each table.
    page_width = page.rect.width
    mid_x = page_width / 2

    left_blocks  = [b for b in blocks if (b[0] + b[2]) / 2 < mid_x]
    right_blocks = [b for b in blocks if (b[0] + b[2]) / 2 >= mid_x]

    std_pairs  = _extract_two_col_table(left_blocks,  "standard")
    rare_pairs = _extract_two_col_table(right_blocks, "rare")

    records: list[dict] = []
    seen: set[str] = set()

    def _make_record(raw_name: str, raw_origin: str, lang_type: str) -> dict | None:
        name = _ocr_fix_name(raw_name)
        origin = _ocr_fix_origin(_clean(raw_origin))

        # Skip noise rows (dice roll values, table section headers, footnotes, etc.)
        if re.match(r"^[\d\-\s]+$", name):
            return None
        # Strip section title prefix that OCR may merge with dice-roll header
        # e.g. "STANDARD LANGUAGES\nldl2" or "RARE LANGUAGES\nLanguage"
        name = re.sub(r"(?i)^(STANDARD|RARE)\s+LANGUAGES\s*\n?\s*.*", "", name).strip()
        if not name:
            return None
        # Skip remaining header/footnote noise
        if name.lower() in ("language", "origin", "ld12", "1d12", "ldl2"):
            return None
        # Skip long footnote sentences (genuine language names are short)
        if len(name) > 60:
            return None
        # Skip lines starting with quote/apostrophe (footnote markers)
        if name.startswith(("'", '"', "‘", "’", "“", "”")):
            return None

        # Fuzzy-match to canonical name
        k = _key(_despace(name))
        if k in CANON_BY_KEY:
            canon_name, canon_type, canon_notes = CANON_BY_KEY[k]
        else:
            # Accept as-is with a gap note
            canon_name  = name
            canon_type  = lang_type
            canon_notes = ""
            gaps.append(f"LANGUAGES: unrecognised name '{name}' (origin='{origin}') — verify.")

        if canon_name in seen:
            return None
        seen.add(canon_name)

        # Look up notes from our canon list (overrides extracted notes)
        _, _, preset_notes = CANON_BY_KEY.get(_key(canon_name), (None, None, ""))

        # Primordial dialect footnote
        notes = preset_notes or ""
        if "dialect" in notes.lower() or "aquan" in notes.lower():
            pass  # already set

        return {
            "index":            _slug(canon_name),
            "name":             canon_name,
            "type":             canon_type,
            "typical_speakers": origin,   # 2024 PHB calls this column "Origin"
            "script":           "",       # 2024 PHB does not list a Script column
            "notes":            notes,
            "srd":              False,
            "local":            True,
            "source":           SOURCE,
        }

    for raw_name, raw_origin in std_pairs:
        rec = _make_record(raw_name, raw_origin, "standard")
        if rec:
            records.append(rec)

    for raw_name, raw_origin in rare_pairs:
        rec = _make_record(raw_name, raw_origin, "rare")
        if rec:
            records.append(rec)

    # Verify all canonical languages are present
    found_names = {r["name"] for r in records}
    for canon_name, canon_type, _ in CANON_ALL:
        if canon_name not in found_names:
            gaps.append(f"LANGUAGES: '{canon_name}' ({canon_type}) not found in extracted table "
                        f"— verify page {page_num} manually.")

    # Flag Common Sign Language as new in 2024
    for r in records:
        if r["name"] == "Common Sign Language":
            r["new_in_2024"] = True

    # Flag secret languages
    for r in records:
        if r["name"] in ("Druidic", "Thieves' Cant"):
            r["secret"] = True

    # Add Primordial dialects as sub-entries
    primordial = next((r for r in records if r["name"] == "Primordial"), None)
    if primordial:
        primordial["dialects"] = [
            {"name": "Aquan",  "index": "aquan"},
            {"name": "Auran",  "index": "auran"},
            {"name": "Ignan",  "index": "ignan"},
            {"name": "Terran", "index": "terran"},
        ]

    return records, gaps


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    if not argv:
        print("usage: extract_phb2024_languages.py <path-to-PHB-2024.pdf>", file=sys.stderr)
        return 2
    pdf = Path(argv[0])
    if not pdf.exists():
        print(f"not found: {pdf}", file=sys.stderr)
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf)

    records, gaps = extract_languages(doc)

    out_path = OUT / "languages_2024_phb.json"
    out_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")

    n_std  = sum(1 for r in records if r["type"] == "standard")
    n_rare = sum(1 for r in records if r["type"] == "rare")
    print(f"languages_2024_phb: {len(records)} records "
          f"({n_std} standard, {n_rare} rare), {len(gaps)} gaps")

    if gaps:
        print("Gaps:")
        for g in gaps:
            print(f"  - {g}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
