#!/usr/bin/env python
"""Deterministic converter: CC-BY 2024 SRD markdown -> engine SRD JSON (data/srd/2024).

Source: https://github.com/downfallx/dnd-5e-srd-markdown @ 1b4b99dcb786cdd1a2fb26f8acec1551191f1ca4
        (SRD 5.2.1, (c) Wizards of the Coast LLC, CC-BY-4.0 -- see data/srd/2024/ATTRIBUTION.md)

Per docs/SRD-2024-MARKDOWN-CONVERSION-BRIEF.md this produces the two files the engine
currently lacks for 2024 (so casters stop borrowing the 2014 tables):

    5e-SRD-Spells.json   <- spells.md   (339 spells; level + school + classes[])
    5e-SRD-Levels.json   <- classes.md  (per-caster class+level slot tables)

Output JSON keys match the existing 2014 files / PDF-RULES-EXTRACTION-BRIEF.md s5.
Re-runnable: `.venv_forge/Scripts/python.exe scripts/convert_srd2024_md.py`.
"""
from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / ".srd2024_src"
OUT = ROOT / "data" / "srd" / "2024"

# 8 base spellcasting classes (matches engine CASTER_RULES). Warlock uses Pact Magic.
CASTERS = ["bard", "cleric", "druid", "paladin", "ranger", "sorcerer", "warlock", "wizard"]


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


# --------------------------------------------------------------------------- spells
DESCRIPTOR = re.compile(
    r"^_(?:Level (?P<lvl>\d+) )?(?P<school>[A-Z][a-z]+)(?P<cantrip> Cantrip)? \((?P<classes>[^)]+)\)_$"
)
BOLD_FIELD = re.compile(r"^\*\*(?P<key>[^:]+):\*\*\s*(?P<val>.*)$")


def _parse_components(raw: str) -> tuple[list[str], str | None]:
    """'V, S, M (a ball of bat guano)' -> (['V','S','M'], 'a ball of bat guano')."""
    material = None
    m = re.search(r"\(([^)]*)\)", raw)
    if m:
        material = m.group(1).strip()
        raw = raw[: m.start()]
    comps = [c.strip() for c in raw.split(",") if c.strip() in ("V", "S", "M")]
    return comps, material


def parse_spells(text: str) -> list[dict]:
    lines = text.splitlines()
    spells: list[dict] = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if line.startswith("#### "):
            name = line[5:].strip()
            # next non-empty line must be the italic descriptor for this to be a spell
            j = i + 1
            while j < n and not lines[j].strip():
                j += 1
            md = DESCRIPTOR.match(lines[j].strip()) if j < n else None
            if md:
                spells.append(_parse_spell_block(name, md, lines, j + 1))
                # advance to the next #### / ## heading
                i = j + 1
                while i < n and not (lines[i].startswith("#### ") or lines[i].startswith("## ")):
                    i += 1
                continue
        i += 1
    return spells


def _parse_spell_block(name: str, md: re.Match, lines: list[str], start: int) -> dict:
    level = 0 if md.group("cantrip") else int(md.group("lvl"))
    school = md.group("school")
    classes = [
        {"index": _slug(c), "name": c.strip(), "url": f"/api/2024/classes/{_slug(c)}"}
        for c in md.group("classes").split(",")
        if c.strip()
    ]
    spell = {
        "index": _slug(name),
        "name": name,
        "level": level,
        "school": {"index": school.lower(), "name": school,
                   "url": f"/api/2024/magic-schools/{school.lower()}"},
        "classes": classes,
        "desc": [],
        "higher_level": [],
        "ritual": False,
        "concentration": False,
        "casting_time": None,
        "range": None,
        "components": [],
        "duration": None,
    }
    n = len(lines)
    k = start
    while k < n and (lines[k].startswith("#### ") or lines[k].startswith("## ")) is False:
        raw = lines[k].rstrip()
        stripped = raw.strip()
        if not stripped:
            k += 1
            continue
        bm = BOLD_FIELD.match(stripped)
        if bm:
            key, val = bm.group("key").strip(), bm.group("val").strip()
            if key == "Casting Time":
                spell["casting_time"] = val
                spell["ritual"] = "Ritual" in val
            elif key == "Range":
                spell["range"] = val
            elif key == "Components":
                comps, material = _parse_components(val)
                spell["components"] = comps
                if material:
                    spell["material"] = material
            elif key == "Duration":
                spell["duration"] = val
                spell["concentration"] = "Concentration" in val
        elif re.match(r"^_(Using a Higher-Level Spell Slot|Cantrip Upgrade)\._", stripped):
            spell["higher_level"].append(re.sub(r"^_[^_]+\._\s*", "", stripped))
        else:
            spell["desc"].append(stripped)
        k += 1
    if not spell["higher_level"]:
        del spell["higher_level"]
    if not spell.get("material"):
        spell.pop("material", None)
    return spell


# --------------------------------------------------------------------------- levels
class _TableParser(HTMLParser):
    """Parse a single <table> into head rows [(text,colspan)] and body rows [text]."""

    def __init__(self) -> None:
        super().__init__()
        self.section = None  # 'head' | 'body'
        self.head_rows: list[list[tuple[str, int]]] = []
        self.body_rows: list[list[str]] = []
        self._row: list = []
        self._cell: list[str] = []
        self._colspan = 1
        self._in_cell = False

    def handle_starttag(self, tag, attrs):
        if tag == "thead":
            self.section = "head"
        elif tag == "tbody":
            self.section = "body"
        elif tag == "tr":
            self._row = []
        elif tag in ("th", "td"):
            self._in_cell = True
            self._cell = []
            self._colspan = int(dict(attrs).get("colspan", 1))

    def handle_endtag(self, tag):
        if tag == "tr":
            if self.section == "head":
                self.head_rows.append([(c if isinstance(c, str) else c[0],
                                        c[1] if isinstance(c, tuple) else 1) for c in self._row])
            elif self.section == "body":
                self.body_rows.append([c if isinstance(c, str) else c[0] for c in self._row])
        elif tag in ("th", "td"):
            text = "".join(self._cell).strip()
            if self.section == "head":
                self._row.append((text, self._colspan))
            else:
                self._row.append(text)
            self._in_cell = False

    def handle_data(self, data):
        if self._in_cell:
            self._cell.append(data)


def _tables(section_text: str) -> list[_TableParser]:
    out = []
    for block in re.findall(r"<table>.*?</table>", section_text, re.DOTALL):
        p = _TableParser()
        p.feed(block)
        out.append(p)
    return out


def _class_sections(text: str) -> dict[str, str]:
    """Map class slug -> its '## Class' .. next '## ' section text."""
    out: dict[str, str] = {}
    matches = list(re.finditer(r"^## (.+)$", text, re.MULTILINE))
    for i, m in enumerate(matches):
        name = m.group(1).strip()
        slug = _slug(name)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out[slug] = text[m.start():end]
    return out


def _num(cell: str) -> int:
    cell = cell.strip().lstrip("+")
    if cell in ("", "—", "-", "–"):
        return 0
    try:
        return int(cell)
    except ValueError:
        return 0


def _features_table(section: str) -> _TableParser | None:
    for t in _tables(section):
        head_flat = " ".join(txt for row in t.head_rows for txt, _ in row)
        if "Spell Slots per Spell Level" in head_flat or "Slot Level" in head_flat:
            return t
    return None


def _empty_slots() -> dict[str, int]:
    return {f"spell_slots_level_{i}": 0 for i in range(1, 10)}


def parse_levels(text: str) -> list[dict]:
    sections = _class_sections(text)
    entries: list[dict] = []
    for slug in CASTERS:
        section = sections.get(slug)
        if not section:
            print(f"  WARN: no section for {slug}", file=sys.stderr)
            continue
        table = _features_table(section)
        if not table:
            print(f"  WARN: no features table for {slug}", file=sys.stderr)
            continue
        name = slug.capitalize()
        if slug == "warlock":
            entries += _warlock_levels(table, slug, name)
        else:
            entries += _standard_levels(table, slug, name)
    return entries


def _header_index(row1: list[tuple[str, int]], needle: str) -> int | None:
    for i, (txt, _) in enumerate(row1):
        if needle.lower() in txt.lower():
            return i
    return None


def _standard_levels(table: _TableParser, slug: str, name: str) -> list[dict]:
    row1 = table.head_rows[0]
    # the "Spell Slots per Spell Level" header spans the slot columns: full casters
    # colspan=9, half-casters (Paladin/Ranger) colspan=5. Use the actual span.
    slot_start = slot_cols = None
    for i, (txt, cs) in enumerate(row1):
        if "Spell Slots per Spell Level" in txt:
            slot_start, slot_cols = i, cs
            break
    lvl_i = _header_index(row1, "Level")
    prof_i = _header_index(row1, "Proficiency")
    cant_i = _header_index(row1, "Cantrip")
    known_i = _header_index(row1, "Prepared Spells")
    if known_i is None:
        known_i = _header_index(row1, "Spells Known")
    out = []
    for cells in table.body_rows:
        if slot_start is None or len(cells) < slot_start + slot_cols:
            continue
        level = _num(cells[lvl_i])
        if not 1 <= level <= 20:
            continue
        sc = _empty_slots()
        for s in range(slot_cols):
            sc[f"spell_slots_level_{s + 1}"] = _num(cells[slot_start + s])
        sc["cantrips_known"] = _num(cells[cant_i]) if cant_i is not None else 0
        if known_i is not None:
            sc["spells_known"] = _num(cells[known_i])
        out.append({
            "index": f"{slug}-{level}",
            "class": {"index": slug, "name": name, "url": f"/api/2024/classes/{slug}"},
            "level": level,
            "prof_bonus": _num(cells[prof_i]) if prof_i is not None else 2 + (level - 1) // 4,
            "spellcasting": _order_sc(sc),
        })
    return out


def _warlock_levels(table: _TableParser, slug: str, name: str) -> list[dict]:
    row1 = table.head_rows[0]
    lvl_i = _header_index(row1, "Level")
    prof_i = _header_index(row1, "Proficiency")
    cant_i = _header_index(row1, "Cantrip")
    known_i = _header_index(row1, "Prepared Spells")
    slots_i = _header_index(row1, "Spell Slots")
    slotlvl_i = _header_index(row1, "Slot Level")
    out = []
    for cells in table.body_rows:
        if lvl_i is None or len(cells) <= max(filter(None, [slots_i, slotlvl_i, known_i, cant_i, prof_i])):
            continue
        level = _num(cells[lvl_i])
        if not 1 <= level <= 20:
            continue
        sc = _empty_slots()
        n_slots = _num(cells[slots_i]) if slots_i is not None else 0
        slot_lvl = _num(cells[slotlvl_i]) if slotlvl_i is not None else 0
        if 1 <= slot_lvl <= 9:
            sc[f"spell_slots_level_{slot_lvl}"] = n_slots
        sc["cantrips_known"] = _num(cells[cant_i]) if cant_i is not None else 0
        if known_i is not None:
            sc["spells_known"] = _num(cells[known_i])
        out.append({
            "index": f"{slug}-{level}",
            "class": {"index": slug, "name": name, "url": f"/api/2024/classes/{slug}"},
            "level": level,
            "prof_bonus": _num(cells[prof_i]) if prof_i is not None else 2 + (level - 1) // 4,
            "spellcasting": _order_sc(sc),
        })
    return out


def _order_sc(sc: dict) -> dict:
    out: dict[str, int] = {"cantrips_known": sc.get("cantrips_known", 0)}
    if "spells_known" in sc:
        out["spells_known"] = sc["spells_known"]
    for i in range(1, 10):
        out[f"spell_slots_level_{i}"] = sc[f"spell_slots_level_{i}"]
    return out


# --------------------------------------------------------------------------- main
def main() -> int:
    if not SRC.exists():
        print(f"ERROR: source clone not found at {SRC}", file=sys.stderr)
        print("Clone it first:\n"
              "  git -C .srd2024_src init && git -C .srd2024_src remote add origin "
              "https://github.com/downfallx/dnd-5e-srd-markdown.git\n"
              "  git -C .srd2024_src fetch --depth 1 origin "
              "1b4b99dcb786cdd1a2fb26f8acec1551191f1ca4 && "
              "git -C .srd2024_src checkout FETCH_HEAD", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)

    spells_md = (SRC / "spells.md").read_text(encoding="utf-8")
    spells = parse_spells(spells_md)
    (OUT / "5e-SRD-Spells.json").write_text(
        json.dumps(spells, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Spells: {len(spells)} -> 5e-SRD-Spells.json")

    classes_md = (SRC / "classes.md").read_text(encoding="utf-8")
    levels = parse_levels(classes_md)
    (OUT / "5e-SRD-Levels.json").write_text(
        json.dumps(levels, indent=2, ensure_ascii=False), encoding="utf-8")
    by_class = {}
    for e in levels:
        by_class[e["class"]["index"]] = by_class.get(e["class"]["index"], 0) + 1
    print(f"Levels: {len(levels)} -> 5e-SRD-Levels.json  {by_class}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
