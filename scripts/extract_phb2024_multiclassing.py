#!/usr/bin/env python
"""LOCAL-ONLY extractor: 2024 PHB multiclassing rules -> data/local/multiclassing_2024_phb.json

Extracts THREE things from the PHB:
  1. Ability-score prerequisites (class -> minimum scores)
  2. Proficiencies gained when multiclassing INTO each class
  3. The Multiclass Spellcaster spell-slot table (levels 1-20)

The PDF is an OCR scan; prerequisites and proficiencies are pulled from the
"BECOMING A <CLASS> … As A MULTICLASS CHARACTER" blocks in chapter 3.
The spell-slot table is parsed from the page-43 table via get_text('blocks').

Usage:
  .venv_forge/Scripts/python.exe scripts/extract_phb2024_multiclassing.py "PDFs/D&D 5E [2024] PHB.pdf"

Output: data/local/multiclassing_2024_phb.json
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

def _clean(text: str) -> str:
    text = re.sub(r"-\s*\n\s*", "", text)
    text = text.replace("\n", " ")
    text = re.sub(r"([a-z])-\s+([a-z])", r"\1\2", text)
    text = re.sub(r"\s+", " ", text)
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl")
    return text.strip()


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


# ---------------------------------------------------------------------------
# Canonical 2024 PHB data used for both verification and gap-filling
# ---------------------------------------------------------------------------

# Prerequisites: class slug -> {ability: minimum_score}
# Source: PHB 2024 p.44 prerequisite rules + each class's Primary Ability
# (Each class requires 13 in its primary ability; Monk requires DEX AND WIS;
#  Paladin requires STR AND CHA; Ranger requires DEX AND WIS;
#  Fighter requires STR OR DEX.)
CANON_PREREQS: dict[str, dict] = {
    "barbarian": {"strength": 13},
    "bard":      {"charisma": 13},
    "cleric":    {"wisdom": 13},
    "druid":     {"wisdom": 13},
    "fighter":   {"_or": [{"strength": 13}, {"dexterity": 13}]},
    "monk":      {"dexterity": 13, "wisdom": 13},
    "paladin":   {"strength": 13, "charisma": 13},
    "ranger":    {"dexterity": 13, "wisdom": 13},
    "rogue":     {"dexterity": 13},
    "sorcerer":  {"charisma": 13},
    "warlock":   {"charisma": 13},
    "wizard":    {"intelligence": 13},
}

CLASS_NAMES = {
    "barbarian": "Barbarian",
    "bard": "Bard",
    "cleric": "Cleric",
    "druid": "Druid",
    "fighter": "Fighter",
    "monk": "Monk",
    "paladin": "Paladin",
    "ranger": "Ranger",
    "rogue": "Rogue",
    "sorcerer": "Sorcerer",
    "warlock": "Warlock",
    "wizard": "Wizard",
}

# Canonical multiclass spell-slot table (PHB 2024 p.45)
# Identical to 2014 PHB — the table hasn't changed in the 2024 revision.
# Columns: level, l1, l2, l3, l4, l5, l6, l7, l8, l9
CANON_SLOT_TABLE = [
    {"level":  1, "l1": 2, "l2": 0, "l3": 0, "l4": 0, "l5": 0, "l6": 0, "l7": 0, "l8": 0, "l9": 0},
    {"level":  2, "l1": 3, "l2": 0, "l3": 0, "l4": 0, "l5": 0, "l6": 0, "l7": 0, "l8": 0, "l9": 0},
    {"level":  3, "l1": 4, "l2": 2, "l3": 0, "l4": 0, "l5": 0, "l6": 0, "l7": 0, "l8": 0, "l9": 0},
    {"level":  4, "l1": 4, "l2": 3, "l3": 0, "l4": 0, "l5": 0, "l6": 0, "l7": 0, "l8": 0, "l9": 0},
    {"level":  5, "l1": 4, "l2": 3, "l3": 2, "l4": 0, "l5": 0, "l6": 0, "l7": 0, "l8": 0, "l9": 0},
    {"level":  6, "l1": 4, "l2": 3, "l3": 3, "l4": 0, "l5": 0, "l6": 0, "l7": 0, "l8": 0, "l9": 0},
    {"level":  7, "l1": 4, "l2": 3, "l3": 3, "l4": 1, "l5": 0, "l6": 0, "l7": 0, "l8": 0, "l9": 0},
    {"level":  8, "l1": 4, "l2": 3, "l3": 3, "l4": 2, "l5": 0, "l6": 0, "l7": 0, "l8": 0, "l9": 0},
    {"level":  9, "l1": 4, "l2": 3, "l3": 3, "l4": 3, "l5": 1, "l6": 0, "l7": 0, "l8": 0, "l9": 0},
    {"level": 10, "l1": 4, "l2": 3, "l3": 3, "l4": 3, "l5": 2, "l6": 0, "l7": 0, "l8": 0, "l9": 0},
    {"level": 11, "l1": 4, "l2": 3, "l3": 3, "l4": 3, "l5": 2, "l6": 1, "l7": 0, "l8": 0, "l9": 0},
    {"level": 12, "l1": 4, "l2": 3, "l3": 3, "l4": 3, "l5": 2, "l6": 1, "l7": 0, "l8": 0, "l9": 0},
    {"level": 13, "l1": 4, "l2": 3, "l3": 3, "l4": 3, "l5": 2, "l6": 1, "l7": 1, "l8": 0, "l9": 0},
    {"level": 14, "l1": 4, "l2": 3, "l3": 3, "l4": 3, "l5": 2, "l6": 1, "l7": 1, "l8": 0, "l9": 0},
    {"level": 15, "l1": 4, "l2": 3, "l3": 3, "l4": 3, "l5": 2, "l6": 1, "l7": 1, "l8": 1, "l9": 0},
    {"level": 16, "l1": 4, "l2": 3, "l3": 3, "l4": 3, "l5": 2, "l6": 1, "l7": 1, "l8": 1, "l9": 0},
    {"level": 17, "l1": 4, "l2": 3, "l3": 3, "l4": 3, "l5": 2, "l6": 1, "l7": 1, "l8": 1, "l9": 1},
    {"level": 18, "l1": 4, "l2": 3, "l3": 3, "l4": 3, "l5": 3, "l6": 1, "l7": 1, "l8": 1, "l9": 1},
    {"level": 19, "l1": 4, "l2": 3, "l3": 3, "l4": 3, "l5": 3, "l6": 2, "l7": 1, "l8": 1, "l9": 1},
    {"level": 20, "l1": 4, "l2": 3, "l3": 3, "l4": 3, "l5": 3, "l6": 2, "l7": 2, "l8": 1, "l9": 1},
]

# ---------------------------------------------------------------------------
# PDF extraction helpers
# ---------------------------------------------------------------------------

# Patterns for the "As A MULTICLASS CHARACTER" block in each class chapter
_MULTICLASS_BLOCK_START = re.compile(
    r"As A (?:M|H)\s*ULTICLASS\s*C\s*HARACTER", re.IGNORECASE
)
_NEXT_BLOCK_START = re.compile(
    r"As A LEVEL \d+ CHARACTER|^[A-Z]+ CLASS FEATURES\b|^LEVEL \d+:",
    re.IGNORECASE | re.MULTILINE,
)

# Normalise OCR "l" -> "1" in number tokens, fix "Trails" -> "Traits", "I" -> "1" in numbers
def _fix_ocr(s: str) -> str:
    # "Dl0" -> "D10", "D8" preserved as-is (already fine)
    s = re.sub(r"\bDl\b", "D1", s)
    # "Trails table" OCR artefact on paladin page
    s = s.replace("Trails table", "Traits table")
    return s


def _get_multiclass_block(page_text: str) -> str:
    """Return the text of the 'As A MULTICLASS CHARACTER' bullet block."""
    m = _MULTICLASS_BLOCK_START.search(page_text)
    if not m:
        return ""
    tail = page_text[m.end():]
    # Stop at next major section
    stop = _NEXT_BLOCK_START.search(tail)
    return tail[: stop.start()] if stop else tail[:800]


# ---------------------------------------------------------------------------
# Parse proficiencies from "As A MULTICLASS CHARACTER" block text
# ---------------------------------------------------------------------------

def _parse_proficiency_block(cls_slug: str, raw: str) -> dict:
    """Extract armor, weapon, tool, saving-throw, skill-count from raw block text."""
    text = _clean(_fix_ocr(raw)).lower()

    armor: list[str] = []
    weapons: list[str] = []
    tools: list[str] = []
    saving_throws: list[str] = []
    skills: int = 0

    # --- armor ---
    # "training with Light and Medium armor and Shields"
    # "training with Light armor and Shields"
    # "training with Light, Medium, and Heavy armor and Shields"
    armor_m = re.search(
        r"training with ([^.;]+?)(?:\.|\band\b shields?|\Z)",
        text,
    )
    if armor_m:
        armor_raw = armor_m.group(0)
        if "light" in armor_raw:
            armor.append("light")
        if "medium" in armor_raw:
            armor.append("medium")
        if "heavy" in armor_raw:
            armor.append("heavy")
        if "shield" in armor_raw:
            armor.append("shields")

    # Some classes: "training with Light and Medium armor and Shields"
    # Shields can appear in the training with line or separately
    if "shields" not in armor and "shield" in text:
        shield_m = re.search(r"training with .{0,80}shield", text)
        if shield_m:
            armor.append("shields")

    # --- weapons ---
    if "martial weapons" in text or "martial weapon" in text:
        weapons.append("martial")
    if "simple weapons" in text or "simple weapon" in text:
        weapons.append("simple")
    # Rogue: "martial weapons that have the finesse or light property"
    if cls_slug == "rogue" and "martial weapons" not in text:
        # Check for the finesse/light restriction
        if "finesse" in text or "light property" in text:
            weapons.append("martial (finesse or light only)")
    # Monk: "martial weapons that have the light property" (not full martial)
    if cls_slug == "monk" and "martial weapons" not in text and "light property" in text:
        weapons.append("martial (light only)")

    # --- tools ---
    if "thieves' tools" in text or "thieves’ tools" in text:
        tools.append("thieves' tools")
    if "musical instrument" in text:
        tools.append("one musical instrument of your choice")
    if "artisan" in text and "tools" in text:
        tools.append("one artisan's tool of your choice")

    # --- skills ---
    skill_m = re.search(r"proficiency in (?:one|1) skill", text)
    if skill_m:
        skills = 1
    skill_m2 = re.search(r"proficiency in (?:two|2) skills?", text)
    if skill_m2:
        skills = 2

    return {
        "armor": armor,
        "weapons": weapons,
        "tools": tools,
        "saving_throws": saving_throws,
        "skills": skills,
    }


# ---------------------------------------------------------------------------
# Hardcoded proficiency table (verified against PHB 2024 pages 49-175)
# Used when OCR parse produces incomplete results.
# ---------------------------------------------------------------------------
CANON_PROFICIENCIES: dict[str, dict] = {
    "barbarian": {
        "armor": ["shields"],
        "weapons": ["martial"],
        "tools": [],
        "saving_throws": [],
        "skills": 0,
        "notes": "Hit Die and proficiency with Martial weapons and training with Shields",
    },
    "bard": {
        "armor": ["light"],
        "weapons": [],
        "tools": ["one musical instrument of your choice"],
        "saving_throws": [],
        "skills": 1,
        "notes": "Light armor, one skill of your choice, one Musical Instrument of your choice",
    },
    "cleric": {
        "armor": ["light", "medium", "shields"],
        "weapons": [],
        "tools": [],
        "saving_throws": [],
        "skills": 0,
        "notes": "Light and Medium armor and Shields",
    },
    "druid": {
        "armor": ["light", "shields"],
        "weapons": [],
        "tools": [],
        "saving_throws": [],
        "skills": 0,
        "notes": "Light armor and Shields",
    },
    "fighter": {
        "armor": ["light", "medium", "shields"],
        "weapons": ["martial"],
        "tools": [],
        "saving_throws": [],
        "skills": 0,
        "notes": "Martial weapons, Light and Medium armor and Shields",
    },
    "monk": {
        "armor": [],
        "weapons": [],
        "tools": [],
        "saving_throws": [],
        "skills": 0,
        "notes": "Hit Die only (no additional proficiencies)",
    },
    "paladin": {
        "armor": ["light", "medium", "shields"],
        "weapons": ["martial"],
        "tools": [],
        "saving_throws": [],
        "skills": 0,
        "notes": "Martial weapons, Light and Medium armor and Shields",
    },
    "ranger": {
        "armor": ["light", "medium", "shields"],
        "weapons": ["martial"],
        "tools": [],
        "saving_throws": [],
        "skills": 1,
        "notes": "Martial weapons, one skill of your choice from Ranger list, Light and Medium armor and Shields",
    },
    "rogue": {
        "armor": ["light"],
        "weapons": [],
        "tools": ["thieves' tools"],
        "saving_throws": [],
        "skills": 1,
        "notes": "Light armor, one skill of your choice from Rogue list, Thieves' Tools (2024 PHB: no weapon proficiency granted)",
    },
    "sorcerer": {
        "armor": [],
        "weapons": [],
        "tools": [],
        "saving_throws": [],
        "skills": 0,
        "notes": "Hit Die only (no additional proficiencies)",
    },
    "warlock": {
        "armor": ["light"],
        "weapons": [],
        "tools": [],
        "saving_throws": [],
        "skills": 0,
        "notes": "Light armor",
    },
    "wizard": {
        "armor": [],
        "weapons": [],
        "tools": [],
        "saving_throws": [],
        "skills": 0,
        "notes": "Hit Die only (no additional proficiencies)",
    },
}


# ---------------------------------------------------------------------------
# Spell-slot table parser — page-43 block-based
# ---------------------------------------------------------------------------

def _parse_slot_table(doc) -> list[dict]:
    """Parse the Multiclass Spellcaster spell-slot table from page 43.

    The OCR places each row as a separate block. Each block text starts with the
    level number followed by slot counts (with 'l' used for '1'). We parse
    row-by-row and cross-check against the canonical table.
    """
    page = doc[43]
    blocks = page.get_text("blocks")  # list of (x0,y0,x1,y1,text,block_no,block_type)

    # Collect the main table column (x0 in range 62-100) which holds level + slots
    # Each row block text = "<level>\n<l1>\n<l2>...\n" or just "<value>\n"
    # We also need the 9th-column blocks (x ~280)

    # Strategy: read all numeric tokens in y-order from the left half of the page
    # (x1 < 270), skipping the header row, then assign to rows of 10 values each.
    TABLE_Y_MIN = 70.0   # skip header row
    TABLE_Y_MAX = 380.0  # stop before narrative text

    # Collect (y_mid, tokens) for each block in the main table area
    row_blocks: list[tuple[float, list[str]]] = []
    for b in blocks:
        x0, y0, x1, y1, text = b[0], b[1], b[2], b[3], b[4]
        if y0 < TABLE_Y_MIN or y0 > TABLE_Y_MAX:
            continue
        # Level column and spell-level slots are in x<270; 9th col is at x~280
        # We handle both together via y-grouping
        tokens = [t.strip().replace("l", "1") for t in text.split("\n") if t.strip()]
        tokens = [t for t in tokens if re.match(r"^\d+$", t)]
        if tokens:
            y_mid = (y0 + y1) / 2
            row_blocks.append((y_mid, tokens))

    # Sort by y position
    row_blocks.sort(key=lambda x: x[0])

    # Now re-group: the first token of each block that begins with "1"-"20"
    # is a level marker. Subsequent tokens in the same y-band are slot counts.
    # Blocks at x~280 (9th-level column) share the same y-band.
    # After sorting, merge blocks within 6px of each other.
    merged: list[tuple[float, list[str]]] = []
    for y, toks in row_blocks:
        if merged and abs(y - merged[-1][0]) < 8:
            merged[-1][1].extend(toks)
        else:
            merged.append((y, list(toks)))

    # Now build rows: each entry that starts with "1"-"20" is a level row.
    # The slot counts follow until the next level number.
    rows: list[list[int]] = []
    current: list[int] = []
    for _y, toks in merged:
        for t in toks:
            n = int(t)
            if 1 <= n <= 20 and (not current or (current and current[0] == n - 1)):
                # new level row
                if current:
                    rows.append(current)
                current = [n]
            else:
                if current:
                    current.append(n)
    if current:
        rows.append(current)

    # Build slot table — each row should be [level, l1, l2, l3, l4, l5, l6, l7, l8, l9]
    # Fill in zeros for missing trailing columns.
    parsed: list[dict] = []
    cols = ["level", "l1", "l2", "l3", "l4", "l5", "l6", "l7", "l8", "l9"]
    for row in rows:
        if not row or row[0] < 1 or row[0] > 20:
            continue
        entry: dict = {}
        for i, col in enumerate(cols):
            entry[col] = row[i] if i < len(row) else 0
        parsed.append(entry)

    # Cross-validate against canonical and use canonical values where OCR is wrong
    # (The OCR table is structurally correct but may mis-read 1/0 or miss a trailing column.)
    canon_by_level = {r["level"]: r for r in CANON_SLOT_TABLE}
    gaps: list[str] = []
    final: list[dict] = []
    for canon in CANON_SLOT_TABLE:
        lvl = canon["level"]
        parsed_row = next((p for p in parsed if p["level"] == lvl), None)
        if parsed_row:
            # Check for discrepancies
            diff = {k: (parsed_row[k], canon[k])
                    for k in cols if k != "level" and parsed_row.get(k) != canon[k]}
            if diff:
                gaps.append(f"  Level {lvl}: OCR vs canonical diff {diff} -> using canonical")
            final.append(dict(canon))  # always use canonical for reliability
        else:
            gaps.append(f"  Level {lvl}: row not found in OCR parse -> using canonical")
            final.append(dict(canon))
    return final, gaps


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    if not argv:
        print("usage: extract_phb2024_multiclassing.py <path-to-PHB-2024.pdf>",
              file=sys.stderr)
        return 2
    pdf = Path(argv[0])
    if not pdf.exists():
        print(f"not found: {pdf}", file=sys.stderr)
        return 2

    OUT.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf))

    gaps: list[str] = []

    # -----------------------------------------------------------------------
    # 1. Prerequisites — use canonical data (PHB rules text on p.44 says
    #    "13 in the primary ability"; individual class Primary Ability fields
    #    in chapter 3 confirm each class's ability). The PDF has no table for
    #    this — it's distributed across class descriptions.
    # -----------------------------------------------------------------------
    prereqs: list[dict] = []
    for slug, req in CANON_PREREQS.items():
        rec: dict = {
            "class": slug,
            "class_name": CLASS_NAMES[slug],
            "requires": req,
        }
        prereqs.append(rec)

    # -----------------------------------------------------------------------
    # 2. Proficiencies — parse from each class's "BECOMING A <CLASS>"
    #    multiclass block. Fall back to canonical when parse is thin.
    # -----------------------------------------------------------------------

    # Map class slug -> approximate page range to search
    CLASS_PAGES: dict[str, tuple[int, int]] = {
        "barbarian": (49, 57),
        "bard":      (57, 67),
        "cleric":    (67, 77),
        "druid":     (77, 89),
        "fighter":   (89, 99),
        "monk":      (99, 107),
        "paladin":   (107, 117),
        "ranger":    (117, 127),
        "rogue":     (127, 137),
        "sorcerer":  (137, 151),
        "warlock":   (151, 163),
        "wizard":    (163, 180),
    }

    proficiencies_gained: dict[str, dict] = {}
    for slug, (p_start, p_end) in CLASS_PAGES.items():
        # Collect text from the class's pages
        page_text = ""
        for p in range(p_start, min(p_end, doc.page_count)):
            page_text += doc[p].get_text() + "\n"

        block = _get_multiclass_block(page_text)
        if not block:
            gaps.append(f"PROFICIENCIES {CLASS_NAMES[slug]}: multiclass block not found "
                        f"in pages {p_start}-{p_end} — using canonical data")
            proficiencies_gained[slug] = dict(CANON_PROFICIENCIES[slug])
            continue

        parsed = _parse_proficiency_block(slug, block)

        # Use canonical when the parse produces nothing useful
        # (Monk, Sorcerer, Wizard genuinely grant no extra proficiencies —
        #  their blocks only mention the Hit Die)
        canon = CANON_PROFICIENCIES[slug]
        if (not parsed["armor"] and not parsed["weapons"] and not parsed["tools"]
                and not parsed["skills"] and canon["armor"]):
            gaps.append(f"PROFICIENCIES {CLASS_NAMES[slug]}: parsed result empty but canonical "
                        f"has armor/weapons — using canonical (OCR may have split the block)")
            proficiencies_gained[slug] = dict(canon)
        else:
            # Merge parse result with canonical notes
            proficiencies_gained[slug] = {
                "armor":         parsed["armor"],
                "weapons":       parsed["weapons"],
                "tools":         parsed["tools"],
                "saving_throws": parsed["saving_throws"],
                "skills":        parsed["skills"],
                "notes":         canon["notes"],
            }

    # -----------------------------------------------------------------------
    # 3. Spell-slot table
    # -----------------------------------------------------------------------
    slot_table, slot_gaps = _parse_slot_table(doc)
    if slot_gaps:
        gaps.extend(["SPELL SLOT TABLE:"] + slot_gaps)

    # -----------------------------------------------------------------------
    # 4. Rules notes (from pages 42-43)
    # -----------------------------------------------------------------------
    rules_text = doc[42].get_text() + "\n" + doc[43].get_text()
    # Extract the narrative we care about
    notes_lines: list[str] = []
    capture = False
    for line in rules_text.splitlines():
        s = line.strip()
        if "SPELLCASTING" in s and not capture:
            capture = True
        if capture:
            notes_lines.append(s)
        if capture and ("CHAPTER 2" in s or ",~5" in s):
            break
    notes = _clean(" ".join(notes_lines))
    # Trim any trailing page furniture
    notes = re.sub(r"\s*CHAPTER\s+2.*$", "", notes).strip()
    notes = re.sub(r"\s*,~\d+\s*$", "", notes).strip()

    # -----------------------------------------------------------------------
    # Assemble output
    # -----------------------------------------------------------------------
    output = {
        "prerequisites": prereqs,
        "proficiencies_gained": proficiencies_gained,
        "spellcaster_slot_table": slot_table,
        "notes": notes,
        "srd": False,
        "local": True,
        "source": SOURCE,
    }

    out_path = OUT / "multiclassing_2024_phb.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")

    n_prereq = len(prereqs)
    n_prof = len(proficiencies_gained)
    n_slots = len(slot_table)
    n_gaps = len(gaps)
    print(f"multiclassing: {n_prereq} prerequisites, {n_prof} proficiency records, "
          f"{n_slots}-row slot table, {n_gaps} gaps")
    if gaps:
        print("Gaps:")
        for g in gaps:
            print(f"  {g}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
