#!/usr/bin/env python
"""LOCAL-ONLY extractor: 2024 PHB beyond-SRD options -> data/local/*.json (+ a gaps report).

⚠ Reads a copyrighted rulebook PDF the user supplies locally and writes ONLY to data/local/
(gitignored). Output is BEYOND-SRD content for personal prototyping — NEVER commit or ship it.
The tool itself holds no book text, only parsing logic.

The source PDF is an OCR'd scan, so output is "prototype quality": prose extracts well, but
stylised header names and precise numbers (dice / DCs / ability scores) carry OCR noise. Every
uncertain entry/field is flagged and listed in data/local/EXTRACTION-GAPS.md so the user can
paste/screenshot the exact bits that need a human eye.

Sections: feats, species, backgrounds. (Subclasses are interleaved with features/tables and too
OCR-noisy to auto-structure reliably; see the gaps report.)

Each record is tagged "srd": false, "local": true, source = PHB 2024, schema-aligned to the
matching data/srd/2024/*.json file.

Usage: .venv_forge/Scripts/python.exe scripts/extract_phb2024_local.py "PDFs/<file>.pdf"
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
SOURCE = {"name": "Player's Handbook (2024)", "publisher": "Wizards of the Coast",
          "license": "All rights reserved (local prototyping only)"}
GAPS: list[str] = []

# ----------------------------------------------------------------- shared helpers
OCR_DICE = re.compile(r"\bl(d(?:4|6|8|10|12|20|100))\b")
OCR_ORD = re.compile(r"\bl(st|nd|rd|th)\b")


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")


def _clean(text: str) -> str:
    text = re.sub(r"-\s*\n\s*", "", text)
    text = text.replace("\n", " ")
    # rejoin words split by line-break hyphens that survived into space-joined output
    text = re.sub(r"([a-z])-\s+([a-z])", r"\1\2", text)
    # strip OCR'd running page furniture ("CH \PTE R 5 I FEATS 20x", "CHAPTER 4 | ...")
    text = re.sub(r"\bCH\s*\\?\s*[APT]{1,2}TE?\s*R\b.{0,4}\d.{0,40}?(?:FEATS|SPECIES|ORIGINS?|BACKGROUNDS?)\b\s*\S*",
                  " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    text = OCR_DICE.sub(r"1\1", text)
    text = OCR_ORD.sub(r"1\1", text)
    text = text.replace("ﬁ", "fi").replace("ﬂ", "fl")
    # strip trailing divider artifacts ("~--------", ";::::==", "~")
    text = re.sub(r"[\s~^|;:=_•\-]{2,}$", "", text)
    return text.strip()


def _bold_subheads(text: str) -> str:
    return re.sub(r"(?<=[.!]) ([A-Z][A-Za-z'/ ]{2,40}?\.) (?=[A-Z])", r" **\1** ", text)


def _despace(s: str) -> str:
    """Collapse OCR letter-spacing/drop-caps: 'A LERT'->'ALERT', 'GOLIAT H'->'GOLIATH'."""
    prev = None
    while s != prev:
        prev = s
        s = re.sub(r"\b([A-Z]) (?=[A-Z])", r"\1", s)     # single letter + following cap
        s = re.sub(r"(?<=[A-Z]) ([A-Z])\b", r"\1", s)    # trailing single cap
    return s


def _key(s: str) -> str:
    # fold common OCR digit-for-letter swaps so '0RC'~='ORC', 'T1EFLING'~='TIEFLING'
    s = s.lower().replace("0", "o").replace("1", "l")
    return re.sub(r"[^a-z]", "", s)


# ----------------------------------------------------------------- feats
FEAT_CAT = re.compile(r"^(Origin|General|Fighting Style|Epic Boon)\s+Feat\b(.*)$")
FEAT_SECTIONS = {"ORIGIN FEATS": "origin", "GENERAL FEATS": "general",
                 "FIGHTING STYLE FEATS": "fighting-style", "EPIC BOON FEATS": "epic-boon"}
# canonical 2024 PHB feat names (for OCR name repair via space-insensitive match)
CANON_FEATS = [
    "Alert", "Crafter", "Healer", "Lucky", "Magic Initiate", "Musician",
    "Savage Attacker", "Skilled", "Tavern Brawler", "Tough",
    "Ability Score Improvement", "Actor", "Athlete", "Charger", "Chef",
    "Crossbow Expert", "Crusher", "Defensive Duelist", "Dual Wielder", "Durable",
    "Elemental Adept", "Fey Touched", "Grappler", "Great Weapon Master",
    "Heavily Armored", "Heavy Armor Master", "Inspiring Leader", "Keen Mind",
    "Lightly Armored", "Mage Slayer", "Martial Weapon Training", "Medium Armor Master",
    "Moderately Armored", "Mounted Combatant", "Observant", "Piercer", "Poisoner",
    "Polearm Master", "Resilient", "Ritual Caster", "Sentinel", "Shadow Touched",
    "Sharpshooter", "Shield Master", "Skill Expert", "Slasher", "Speedy",
    "Spell Sniper", "Telekinetic", "Telepathic", "War Caster", "Weapon Master",
    "Archery", "Blind Fighting", "Defense", "Dueling", "Great Weapon Fighting",
    "Interception", "Protection", "Thrown Weapon Fighting", "Two-Weapon Fighting",
    "Unarmed Fighting",
    "Boon of Combat Prowess", "Boon of Dimensional Travel", "Boon of Energy Resistance",
    "Boon of Fate", "Boon of Fortitude", "Boon of Irresistible Offense",
    "Boon of Recovery", "Boon of Skill", "Boon of Speed", "Boon of Spell Recall",
    "Boon of the Night Spirit", "Boon of Truesight",
    "Skulker", "Mounted Combatant",
]
CANON_BY_KEY = {_key(n): n for n in CANON_FEATS}


def _repair_feat_name(raw: str) -> tuple[str, str]:
    """-> (best-effort name, status) where status in {'exact','fuzzy','suspect'}.

    Matches the OCR'd name to the canonical PHB feat list space-insensitively, then falls
    back to fuzzy matching (OCR mangles 'KEEN MIND' -> 'KE EN Mr N D' etc.)."""
    dkey = _key(_despace(raw))
    if dkey in CANON_BY_KEY:
        return CANON_BY_KEY[dkey], "exact"
    close = get_close_matches(dkey, list(CANON_BY_KEY), n=1, cutoff=0.66)
    if close:
        return CANON_BY_KEY[close[0]], "fuzzy"
    return _despace(raw.strip()).title(), "suspect"


def extract_feats(doc) -> list[dict]:
    hdr_pages = [p for p in range(doc.page_count) if any(s in doc[p].get_text() for s in FEAT_SECTIONS)]
    if not hdr_pages:
        return []
    # the last section (Epic Boon) spills onto pages with no section header — extend the range
    # to the last page that still carries a "<cat> Feat" category line.
    def _has_cat(p: int) -> bool:
        return any(FEAT_CAT.match(l.strip()) for l in doc[p].get_text().splitlines())
    cat_pages = [p for p in range(min(hdr_pages), min(max(hdr_pages) + 6, doc.page_count)) if _has_cat(p)]
    last = max(cat_pages) if cat_pages else max(hdr_pages)
    lines: list[str] = []
    for p in range(min(hdr_pages), max(max(hdr_pages), last) + 1):
        lines.extend(doc[p].get_text().splitlines())
    # category-line driven: the line above each "<cat> Feat" is the (possibly garbled) name
    feats: list[dict] = []
    cur = "origin"
    n = len(lines)
    for i, raw in enumerate(lines):
        s = raw.strip()
        if s in FEAT_SECTIONS:
            cur = FEAT_SECTIONS[s]
            continue
        cat = FEAT_CAT.match(s)
        if not cat:
            continue
        # name = previous non-empty line
        j = i - 1
        while j >= 0 and not lines[j].strip():
            j -= 1
        if j < 0:
            continue
        raw_name = lines[j].strip()
        if FEAT_CAT.match(raw_name) or raw_name in FEAT_SECTIONS:
            continue
        ftype = {"Origin": "origin", "General": "general",
                 "Fighting Style": "fighting-style", "Epic Boon": "epic-boon"}[cat.group(1)]
        # prerequisite (may wrap across lines until ')')
        tail = s
        k = i + 1
        while "(" in tail and ")" not in tail and k < n:
            tail += " " + lines[k].strip()
            k += 1
        # body until next category's name OR section header
        body: list[str] = []
        m = k
        while m < n:
            ss = lines[m].strip()
            if ss in FEAT_SECTIONS:
                break
            nxt = lines[m + 1].strip() if m + 1 < n else ""
            if FEAT_CAT.match(nxt):       # ss is the next feat's name
                break
            body.append(lines[m])
            m += 1
        name, status = _repair_feat_name(raw_name)
        feat = {
            "index": _slug(name), "name": name,
            "description": _bold_subheads(_clean("\n".join(body))),
            "type": ftype, "url": f"/local/2024/feats/{_slug(name)}",
            "srd": False, "local": True, "source": SOURCE,
        }
        pre = re.search(r"\(Pre.{0,3}equisite:\s*(.+?)\)", tail, re.S)
        if pre:
            feat["prerequisites_text"] = re.sub(r"\s+", " ", pre.group(1)).strip()
        if re.search(r"Repeatable\.", feat["description"]):
            feat["repeatable"] = True
        if status == "fuzzy":
            feat["name_ocr_raw"] = raw_name      # auto-corrected from a garbled scan
        elif status == "suspect":
            feat["name_ocr_suspect"] = raw_name
            GAPS.append(f"FEAT name unsure ({ftype}): OCR='{raw_name}' -> guessed '{name}'")
        feats.append(feat)
    # de-dup
    seen, out = set(), []
    for f in feats:
        if f["index"] in seen:
            continue
        seen.add(f["index"])
        out.append(f)
    return out


# ----------------------------------------------------------------- species
CANON_SPECIES = ["Aasimar", "Dragonborn", "Dwarf", "Elf", "Gnome", "Goliath",
                 "Halfling", "Human", "Orc", "Tiefling"]


def _species_pages(doc) -> tuple[int, int]:
    starts = [p for p in range(doc.page_count) if "SPECIES DESCRIPTIONS" in doc[p].get_text()]
    start = starts[0] if starts else 184
    return start, min(start + 13, doc.page_count)


def extract_species(doc) -> list[dict]:
    lo, hi = _species_pages(doc)
    text = "\n".join(doc[p].get_text() for p in range(lo, hi))
    lines = text.splitlines()
    # locate each canonical species' header line (a caps line whose key matches), in order
    marks: list[tuple[int, str]] = []
    for i, raw in enumerate(lines):
        s = raw.strip()
        if not s or len(s) > 32 or not re.match(r"^[A-Z0-9].*[A-Z]\s*$", s):
            continue
        k = _key(_despace(s).replace(" TRAITS", ""))
        for canon in CANON_SPECIES:
            if k == _key(canon):
                marks.append((i, canon))
                break
    # keep first mark per species, in document order
    seen, ordered = set(), []
    for i, canon in marks:
        if canon not in seen:
            seen.add(canon)
            ordered.append((i, canon))
    out: list[dict] = []
    for idx, (i, canon) in enumerate(ordered):
        end = ordered[idx + 1][0] if idx + 1 < len(ordered) else len(lines)
        block = "\n".join(lines[i:end])
        rec = {"index": _slug(canon), "name": canon,
               "url": f"/local/2024/species/{_slug(canon)}",
               "srd": False, "local": True, "source": SOURCE}
        ct = re.search(r"Creature Type:\s*(.+)", block)
        sz = re.search(r"Size:\s*(.+)", block)
        sp = re.search(r"Speed:\s*(.+)", block)
        if ct:
            rec["creature_type"] = _clean(ct.group(1))
        if sz:
            rec["size"] = _clean(sz.group(1))
        if sp:
            rec["speed"] = _clean(sp.group(1))
        tstart = re.search(r"special traits\.", block)
        traits_txt = block[tstart.end():] if tstart else block
        traits = [{"name": _clean(tm.group(1)), "desc": _clean(tm.group(2))}
                  for tm in re.finditer(
                      r"(?m)^([A-Z][A-Za-z'/ ]{2,40})\.\s+(.+?)(?=^\s*[A-Z][A-Za-z'/ ]{2,40}\.\s|\Z)",
                      traits_txt, re.S)]
        if traits:
            rec["traits"] = traits
        else:
            GAPS.append(f"SPECIES '{canon}': traits not parsed cleanly — paste the traits block.")
        if not (ct and sz and sp):
            GAPS.append(f"SPECIES '{canon}': missing Creature Type/Size/Speed line(s).")
        out.append(rec)
    for canon in CANON_SPECIES:
        if canon not in seen:
            GAPS.append(f"SPECIES '{canon}': not found in PDF — paste its block.")
    return out


# ----------------------------------------------------------------- backgrounds
# 2024 PHB backgrounds are listed alphabetically; names sit in mangled headers, but the
# field blocks ("Ability Scores:" ...) are clean. Split on the field blocks and assign
# canonical names in order, flagging the count so the order can be verified.
CANON_BG = ["Acolyte", "Artisan", "Charlatan", "Criminal", "Entertainer", "Farmer",
            "Guard", "Guide", "Hermit", "Merchant", "Noble", "Sage", "Sailor",
            "Scribe", "Soldier", "Wayfarer"]
BG_FIELDS = [("Ability Scores", "ability_scores"), ("Feat", "feat"),
             ("Skill Proficiencies", "skill_proficiencies"),
             ("Tool Proficiency", "tool_proficiency"),
             ("Tool Proficiencies", "tool_proficiency"), ("Equipment", "equipment")]


def extract_backgrounds(doc) -> list[dict]:
    pages = [p for p in range(doc.page_count) if "Ability Scores:" in doc[p].get_text()
             and "Background" not in doc[p].get_text()[:60]]
    # background section = the run of pages carrying the field blocks
    bg_pages = [p for p in range(doc.page_count) if re.search(r"Ability Scores:.*\n.*Feat:",
                doc[p].get_text())]
    if not bg_pages:
        bg_pages = pages
    lo, hi = min(bg_pages), max(bg_pages) + 1
    text = "\n".join(doc[p].get_text() for p in range(lo, hi))
    # OCR mangles the drop-cap "A" of some "Ability Scores:" lines (e.g. "r===~bility Scores:");
    # normalise any "<junk>bility Scores:" back so every entry splits cleanly.
    text = re.sub(r"(?m)^.{0,10}?bility Scores:", "Ability Scores:", text)
    blocks = re.split(r"(?=Ability Scores:)", text)
    blocks = [b for b in blocks if "Feat:" in b]
    out: list[dict] = []
    for i, block in enumerate(blocks):
        name = CANON_BG[i] if i < len(CANON_BG) else f"Background {i + 1}"
        # description = text after Equipment line up to next block (already cut)
        rec = {"index": _slug(name), "name": name,
               "url": f"/local/2024/backgrounds/{_slug(name)}",
               "srd": False, "local": True, "source": SOURCE, "name_assigned_by_order": True}
        next_field = (r"(?=\n\s*(?:Ability Scores|Feat|Skill Proficiencies|"
                      r"Tool Proficiency|Tool Proficiencies|Equipment)\s*:|\Z)")
        for label, key in BG_FIELDS:
            fm = re.search(re.escape(label) + r"\s*:\s*(.+?)" + next_field, block, re.S)
            if fm and key not in rec:
                rec[key] = _clean(fm.group(1))
        if "ability_scores" not in rec:
            GAPS.append(f"BACKGROUND '{name}' (block {i + 1}): Ability Scores line garbled — verify.")
        out.append(rec)
    if len(out) != len(CANON_BG):
        GAPS.append(f"BACKGROUNDS: found {len(out)} blocks but expected {len(CANON_BG)} "
                    f"({', '.join(CANON_BG)}). Order-based names may be off — verify.")
    return out


# ----------------------------------------------------------------- subclasses
# 2024 PHB: 4 subclasses per class, in book order. Names drive reliable detection despite OCR.
CANON_SUBCLASSES: dict[str, list[str]] = {
    "barbarian": ["Path of the Berserker", "Path of the Wild Heart", "Path of the World Tree", "Path of the Zealot"],
    "bard": ["College of Dance", "College of Glamour", "College of Lore", "College of Valor"],
    "cleric": ["Life Domain", "Light Domain", "Trickery Domain", "War Domain"],
    "druid": ["Circle of the Land", "Circle of the Moon", "Circle of the Sea", "Circle of the Stars"],
    "fighter": ["Battle Master", "Champion", "Eldritch Knight", "Psi Warrior"],
    "monk": ["Warrior of Mercy", "Warrior of Shadow", "Warrior of the Elements", "Warrior of the Open Hand"],
    "paladin": ["Oath of Devotion", "Oath of Glory", "Oath of the Ancients", "Oath of Vengeance"],
    "ranger": ["Beast Master", "Fey Wanderer", "Gloom Stalker", "Hunter"],
    "rogue": ["Arcane Trickster", "Assassin", "Soulknife", "Thief"],
    "sorcerer": ["Aberrant Sorcery", "Clockwork Sorcery", "Draconic Sorcery", "Wild Magic Sorcery"],
    "warlock": ["Archfey Patron", "Celestial Patron", "Fiend Patron", "Great Old One Patron"],
    "wizard": ["Abjurer", "Diviner", "Evoker", "Illusionist"],
}
CLASS_TITLE = {c: c.title() for c in CANON_SUBCLASSES}
LEVEL_FEAT = re.compile(r"(?im)^\s*LEVEL\s+(\d+)\s*:\s*(.+?)\s*$")


def _subclass_section_pages(doc) -> dict[str, int]:
    """class slug -> first page of its '<CLASS> SUBCLASSES' section."""
    out: dict[str, int] = {}
    for p in range(doc.page_count):
        t = doc[p].get_text()
        for slug in CANON_SUBCLASSES:
            if slug not in out and re.search(slug.upper() + r"\s+SUBCL", t):
                out[slug] = p
    return out


def extract_subclasses(doc) -> list[dict]:
    sec = _subclass_section_pages(doc)
    ordered = [s for s in CANON_SUBCLASSES if s in sec]
    out: list[dict] = []
    for ci, slug in enumerate(ordered):
        start = sec[slug]
        end = sec[ordered[ci + 1]] if ci + 1 < len(ordered) else min(start + 16, doc.page_count)
        lines: list[str] = []
        for p in range(start, end):
            lines.extend(doc[p].get_text().splitlines())
        # locate each canonical subclass name as a header line (space-insensitive, then fuzzy
        # for OCR-garbled headers). Caps-dominant, short, not a "LEVEL N:" feature line.
        remaining = {_key(n): n for n in CANON_SUBCLASSES[slug]}
        marks: list[tuple[int, str]] = []
        for i, raw in enumerate(lines):
            s = raw.strip()
            if not s or len(s) > 40 or s.upper().startswith("LEVEL"):
                continue
            letters = [c for c in s if c.isalpha()]
            if not letters or sum(c.isupper() for c in letters) / len(letters) < 0.6:
                continue
            k = _key(_despace(s))
            hit = k if k in remaining else None
            if not hit:
                close = get_close_matches(k, list(remaining), n=1, cutoff=0.78)
                hit = close[0] if close else None
            if hit:
                marks.append((i, remaining.pop(hit)))
        canon_order = CANON_SUBCLASSES[slug]
        found_names = [n for _, n in marks]
        for mi, (i, canon) in enumerate(marks):
            blk_end = marks[mi + 1][0] if mi + 1 < len(marks) else len(lines)
            text = "\n".join(lines[i + 1:blk_end])
            cut = re.search(r"(?im)^\s*LEVEL\s+[12]\s*:", text)  # next class's features
            if cut:
                text = text[: cut.start()]
            # canon siblings that come after this one but before the next MATCHED one: these
            # have garbled headers and bled into this block (their features follow, restarting
            # at a lower level). Names for the split-out groups, in order.
            ci0 = canon_order.index(canon)
            ci1 = canon_order.index(found_names[mi + 1]) if mi + 1 < len(found_names) else len(canon_order)
            names = [canon] + canon_order[ci0 + 1:ci1]
            out.extend(_build_subclasses_from_block(text, names, slug))
        produced = {r["name"] for r in out if r["class"]["index"] == slug}
        for canon in canon_order:
            if canon not in produced:
                GAPS.append(f"SUBCLASS '{canon}' ({CLASS_TITLE[slug]}): not recovered — paste this subclass.")
    return out


def _build_subclasses_from_block(text: str, names: list[str], slug: str) -> list[dict]:
    """One header-block may contain several subclasses (siblings whose own headers were too
    OCR-garbled to match). Split where the feature level resets downward, and assign `names`."""
    feats = list(LEVEL_FEAT.finditer(text))
    spans = [(int(f.group(1)), _despace(f.group(2).strip()).title(),
              f.start(), f.end(),
              feats[k + 1].start() if k + 1 < len(feats) else len(text))
             for k, f in enumerate(feats)]
    # partition into groups at each downward level reset
    groups: list[list] = []
    cur: list = []
    for sp in spans:
        if cur and sp[0] < cur[-1][0]:
            groups.append(cur)
            cur = []
        cur.append(sp)
    if cur:
        groups.append(cur)
    if not groups:
        groups = [[]]
    recs = []
    for gi, grp in enumerate(groups):
        canon = names[gi] if gi < len(names) else f"{names[0]} (unsplit {gi})"
        head_start = 0 if gi == 0 else groups[gi - 1][-1][4]
        head_text = text[head_start: grp[0][2]] if grp else text[head_start:]
        head = [h.strip() for h in head_text.splitlines() if h.strip()]
        # drop a garbled header line for recovered (non-first) groups
        if gi > 0 and head and _key(_despace(head[0])) not in {_key(canon)}:
            head = head[1:] if len(head) > 1 else head
        summary = _clean(head[0]) if head else ""
        description = _clean(" ".join(head[1:])) if len(head) > 1 else ""
        features = [{"name": nm, "level": lvl, "desc": _clean(text[e:nx])}
                    for (lvl, nm, st, e, nx) in grp]
        recs.append({
            "index": _slug(canon), "name": canon,
            "class": {"index": slug, "name": CLASS_TITLE[slug]},
            "summary": summary, "description": description, "features": features,
            "url": f"/local/2024/subclasses/{_slug(canon)}",
            "srd": False, "local": True, "source": SOURCE,
            **({"recovered_from_bleed": True} if gi > 0 else {}),
        })
        if not features:
            GAPS.append(f"SUBCLASS '{canon}' ({CLASS_TITLE[slug]}): no LEVEL features parsed — verify.")
    return recs


# ----------------------------------------------------------------- corrections + QA
CORRECTIONS = OUT / "phb2024_corrections.json"
# markers of OCR garble left in body text: replacement char, stray punct clusters, a word
# broken by punctuation (e.g. "increa :;cd"), pipe/caret/tilde noise.
OCR_JUNK = re.compile(r"�|[:;]{2,}|[a-z][:;~^|][a-z]|\s[:;~^|]\s|[~^|]{1,}|\(cid:")


def _apply_corrections(records: list[dict], section: str) -> list[dict]:
    if not CORRECTIONS.exists():
        return records
    data = json.loads(CORRECTIONS.read_text(encoding="utf-8"))
    by_idx = {r["index"]: r for r in records}
    # 1) full-record overrides (user-pasted clean text or partial field patches)
    for idx, patch in data.get(section, {}).items():
        if idx in by_idx:
            by_idx[idx].update(patch)
            by_idx[idx]["corrected_from_paste"] = True
            by_idx[idx].pop("name_ocr_raw", None)
            by_idx[idx].pop("name_ocr_suspect", None)
    # 2) targeted description substring fixes (bad->null means truncate at that point)
    for idx, repls in data.get("text_fixes", {}).get(section, {}).items():
        rec = by_idx.get(idx)
        if not rec:
            continue
        for bad, good in repls:
            if bad in rec.get("description", ""):
                if good is None:
                    pos = rec["description"].index(bad)
                    rec["description"] = rec["description"][:pos].rstrip()
                else:
                    rec["description"] = rec["description"].replace(bad, good)
                rec["corrected_from_paste"] = True
    # 3) feature-level fixes (name rename, desc truncation, desc substring fixes)
    #    and feature injection (_add_features list inserts new features in level order)
    for sc_idx, feat_dict in data.get("feature_fixes", {}).get(section, {}).items():
        rec = by_idx.get(sc_idx)
        if not rec:
            continue
        # inject missing features (paste from book — not recoverable from OCR)
        if "_add_features" in feat_dict:
            existing = {f["name"] for f in rec.get("features", [])}
            for nf in feat_dict["_add_features"]:
                if nf["name"] not in existing:
                    rec.setdefault("features", []).append(dict(nf))
                    existing.add(nf["name"])
            rec["features"].sort(key=lambda f: (f["level"], f["name"]))
            rec["corrected_from_paste"] = True
        # existing per-feature fixes
        for feat_idx, fixes in feat_dict.items():
            if feat_idx == "_add_features":
                continue
            for feat in rec.get("features", []):
                if _slug(feat.get("name", "")) == feat_idx:
                    if "name" in fixes:
                        feat["name"] = fixes["name"]
                    if "desc_truncate_at" in fixes:
                        marker = fixes["desc_truncate_at"]
                        pos = feat.get("desc", "").find(marker)
                        if pos >= 0:
                            feat["desc"] = feat["desc"][:pos].rstrip()
                    for bad, good in fixes.get("desc_fixes", []):
                        feat["desc"] = feat["desc"].replace(bad, good)
                    rec["corrected_from_paste"] = True
    return records


def _scan_ocr_junk(records: list[dict], label: str) -> None:
    for r in records:
        if r.get("corrected_from_paste"):
            continue
        for field in ("description",):
            val = r.get(field, "")
            m = OCR_JUNK.search(val)
            if m:
                ctx = val[max(0, m.start() - 25): m.start() + 25].replace("\n", " ")
                GAPS.append(f"{label} '{r['name']}' OCR-suspect text near: \"...{ctx}...\"")
                break


# ----------------------------------------------------------------- main
def main(argv: list[str]) -> int:
    if not argv:
        print("usage: extract_phb2024_local.py <path-to-PHB-2024.pdf>", file=sys.stderr)
        return 2
    pdf = Path(argv[0])
    if not pdf.exists():
        print(f"not found: {pdf}", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf)

    feats = extract_feats(doc)
    species = extract_species(doc)
    backgrounds = extract_backgrounds(doc)
    subclasses = extract_subclasses(doc)

    # apply local manual corrections (user-pasted book text), then scan for OCR junk
    feats = _apply_corrections(feats, "feats")
    species = _apply_corrections(species, "species")
    backgrounds = _apply_corrections(backgrounds, "backgrounds")
    subclasses = _apply_corrections(subclasses, "subclasses")
    _scan_ocr_junk(feats, "FEAT")
    _scan_ocr_junk(species, "SPECIES")
    _scan_ocr_junk(backgrounds, "BACKGROUND")

    _scan_ocr_junk(subclasses, "SUBCLASS")

    for fn, data in (("feats_2024_phb.json", feats),
                     ("species_2024_phb.json", species),
                     ("backgrounds_2024_phb.json", backgrounds),
                     ("subclasses_2024_phb.json", subclasses)):
        (OUT / fn).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    ftypes: dict[str, int] = {}
    for f in feats:
        ftypes[f["type"]] = ftypes.get(f["type"], 0) + 1
    feat_counts: dict[str, int] = {}
    for s in subclasses:
        feat_counts[s["class"]["name"]] = feat_counts.get(s["class"]["name"], 0) + 1
    print(f"feats:        {len(feats):>3}  {ftypes}")
    print(f"species:      {len(species):>3}  {[s['name'] for s in species]}")
    print(f"backgrounds:  {len(backgrounds):>3}  {[b['name'] for b in backgrounds]}")
    print(f"subclasses:   {len(subclasses):>3}  ({sum(len(s['features']) for s in subclasses)} features) {feat_counts}")

    # gaps report
    gaps_md = ["# 2024 PHB local extraction — gaps needing a human eye", "",
               f"Generated from `{pdf.name}` (OCR scan). These are the bits the parser is unsure",
               "about — paste or screenshot the exact text and I'll patch them.", "",
               f"## Flagged items ({len(GAPS)})", ""]
    gaps_md += [f"- {g}" for g in GAPS] or ["- (none)"]
    autoc = [(f["name"], f["name_ocr_raw"]) for f in feats if "name_ocr_raw" in f]
    if autoc:
        gaps_md += ["", "## Feat names auto-corrected from heavy OCR (worth a glance)", ""]
        gaps_md += [f"- '{name}'  (raw OCR: `{raw}`)" for name, raw in autoc]
    gaps_md += ["", "## Reminder", "Every dice value / DC / number came from an OCR scan — "
                "spot-check the mechanical bits before relying on them. Body text is verbatim "
                "where the scan was clean."]
    (OUT / "EXTRACTION-GAPS.md").write_text("\n".join(gaps_md), encoding="utf-8")
    print(f"gaps flagged: {len(GAPS)}  -> data/local/EXTRACTION-GAPS.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

# ── ADDITIONAL 2024 PHB EXTRACTIONS (run separately) ──────────────────────
# scripts/extract_phb2024_classes.py          -> data/local/class_features_2024_phb.json
#   167 records (flat list); also writes class_features_2024_phb_by_class.json (grouped).
#   Per-class: barbarian=19, bard=12, cleric=11, druid=12, fighter=15, monk=20,
#   paladin=17, ranger=16, rogue=18, sorcerer=10, warlock=8, wizard=9.
#   Known gap: Barbarian L4 ASI header OCR-garbled ('I.~') — that single entry is missing.
#
# scripts/extract_phb2024_weapon_masteries.py -> data/local/weapon_masteries_2024_phb.json
#   46 records: 8 mastery property definitions + 38 weapon-to-mastery mappings.
#   3 of 8 property descriptions (Nick, Topple, Vex) used canon-fallback text due to OCR garble.
#
# scripts/extract_phb2024_languages.py        -> data/local/languages_2024_phb.json
#   19 records: 10 standard + 9 rare. Common Sign Language flagged new_in_2024=true.
#   Druidic and Thieves' Cant flagged secret=true. Primordial includes dialect list.
#   No gaps.
#
# scripts/extract_phb2024_multiclassing.py    -> data/local/multiclassing_2024_phb.json
#   44 logical records: 12 prerequisites + 12 proficiency blocks + 20-row spell-slot table.
#   Spell-slot table uses canonical fallback values (OCR column-confusion on 11 rows).
#
# Run all: pass the PDF path as the first argument to each script, e.g.
#   python scripts/extract_phb2024_classes.py "PDFs/D&D 5E [2024] PHB.pdf"
