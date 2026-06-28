# SRD Data Rebuild & Completion — brief for a separate chat

**Goal:** rebuild and *complete* the D&D 5e **SRD** datasets the Character Forge runs on, for **both editions**
(2014 + 2024), from **legal, openly-licensed sources only**. The headline gap is **2024 monsters** (currently 3;
should be ~300+). This is a **DATA-ONLY** task — do not touch engine/front-end code.

> Run this in its own chat. It's the established pattern: data work is delegated so it can't collide with the
> single-file front-end build chat.

---

## ⚖️ Legal boundary — READ FIRST (this is the whole point)

This tool is shareable **only because it ships SRD content**. Stay strictly inside that line:

- **ALLOWED (shareable, committable):** the official **System Reference Documents**
  - **2014 → SRD 5.1**, released by Wizards of the Coast under **CC-BY-4.0** (2023) *and* OGL 1.0a.
  - **2024 → SRD 5.2.1**, released under **CC-BY-4.0**.
  - Plus **already-open derived datasets** that are themselves SRD-only: **5e-bits/5e-database** (MIT-licensed JSON,
    the shape this project already uses) and **downfallx/dnd-5e-srd-markdown** (CC-BY, the 2024 markdown the owner
    found). Verify each source's licence before use.
- **FORBIDDEN:** anything beyond the SRD — full Monster Manual / PHB / Tasha's / Xanathar's content, and **stat
  blocks scraped from fan wikis** (D&D Beyond, Roll20 compendium, fandom wikis, etc.). That reproduces copyrighted
  material. If a spell/monster/subclass isn't in the SRD, **leave it out** — do not hand-type it from memory or
  scrape it. ("Where possible" in the request = *where the SRD covers it*.)
- **CC-BY requires attribution.** Keep/extend `data/srd/2024/ATTRIBUTION.md` (and add a 2014 one if missing).

If a source's licence is unclear, **do not use it** — flag it in the handback instead.

---

## Current state (audited 2026-06-27) — where the gaps are

Counts via the engine's repo loader (`forge.engine.rules_mode._repo(edition).all(key)`):

| dataset | 2014 | 2024 | note |
|---|---|---|---|
| spells | 319 | 339 | both fine |
| **monsters** | 334 | **3** | ⚠ **2024 is the big gap** (file 22 KB vs 2014's 1.34 MB) |
| classes | 12 | 12 | fine |
| subclasses | 66 | 12 | 2024 thin — but 2024 SRD genuinely ships few; **verify against SRD 5.2.1**, don't pad |
| backgrounds | 13 | 4 | verify vs SRD 5.2.1 |
| feats | 57 | 17 | verify vs SRD 5.2.1 |
| equipment | 237 | 182 | fine-ish; verify |
| magic-items | (present) | (present, smaller) | verify |
| species/races | present | present (`5e-SRD-Species.json`) | fine |

**Priority order:** (1) **2024 monsters** — the one real, glaring hole. (2) Verify 2024 backgrounds / feats /
subclasses / magic-items are *complete to what SRD 5.2.1 actually contains* (don't invent beyond-SRD). (3) Spot-check
2014 for any missing SRD entries. Do **not** "pad" 2024 to match 2014 counts — 2024's SRD is legitimately smaller in
places; completeness means *matching the official SRD*, not matching 2014.

---

## Data layout & loader contract (match this EXACTLY)

Files live in `data/srd/2014/` and `data/srd/2024/`, named `5e-SRD-<Thing>.json`. The engine reads them via
`forge/canon/srd_repository.py`'s `_FILES` map — **do not rename files or change the schema**, or the engine breaks.

- Each file is a **JSON array of entity objects**. Every entity has at least `index` (kebab-case id) + `name`.
- **The 2014 files are the canonical schema reference.** Any 2024 file you build/extend must use the **same field
  shape** as its 2014 counterpart so the engine consumes it unchanged. Key fields the engine relies on:
  - **spells:** `index`, `name`, `level` (0 = cantrip), `classes: [{index,name}]` (drives the class spell list +
    picker), `school`, casting fields.
  - **monsters:** `index`, `name`, `size`, `type`, `armor_class`, `hit_points`, `hit_dice`, `speed`, ability scores,
    `challenge_rating`, `actions`, `special_abilities`, etc. — mirror the 2014 monster object exactly.
  - **levels:** per-class `spellcasting` block with `cantrips_known` / `spells_known` / `spell_slots_level_N`
    (drives slot tables + the spell-count limits). 2024 must be edition-native (SRD 5.2.1 tables).
- 2024 uses some **renamed files**: `5e-SRD-Species.json` (was Races), `5e-SRD-Subspecies.json` (was Subraces),
  `5e-SRD-Weapon-Mastery-Properties.json`, `5e-SRD-Poisons.json`. Keep those names.

**Edition routing note:** the front-end/engine already route by edition (2024 native data switch is done). This task
just makes the 2024 files *complete*; no code changes needed.

---

## Suggested approach

1. **Confirm sources + licences** (SRD 5.1 PDF/CC-BY, SRD 5.2.1 PDF/CC-BY, 5e-bits/5e-database, downfallx markdown).
   List each + its licence in the handback.
2. **2024 monsters first.** Source the SRD 5.2.1 monster set (e.g. from the official SRD 5.2.1 doc or a CC-BY/MIT
   dataset derived from it). Transform into the **2014 monster JSON shape**. Write `data/srd/2024/5e-SRD-Monsters.json`.
3. **Verify the other 2024 files** against SRD 5.2.1 — add only genuinely-missing SRD entries, in-schema.
4. **Spot-check 2014** for SRD 5.1 gaps.
5. **Update `ATTRIBUTION.md`** for every source used (CC-BY requirement).
6. **Validate** (see below) before handing back.

## Validation (must pass before handback)

- `python -c "from forge.engine import rules_mode as rm; print(len(rm._repo('2024').all('monsters')))"` → ~300+.
- The engine's existing tests still pass: `tests/test_ruleset.py`, `tests/test_rules_mode.py`, `tests/test_art.py`.
- Sanity: a 2024 caster's `class_spells_detailed` + `spell_limits` still resolve (don't regress spells/levels).
- JSON is valid, UTF-8, same field shape as 2014 (load every file through the repo without KeyErrors).

## Constraints / definition of done

- **DATA ONLY** — no edits to `forge/`, the `.dc.html`, or tests (beyond running them).
- **SRD-only**, in-schema, attributed. Nothing copyrighted beyond the SRD; no fan-wiki scraping.
- Deliver: updated `data/srd/2024/*.json` (+ any 2014 fixes), updated `ATTRIBUTION.md`, and a **handback note**
  listing sources used + their licences, what was added per file, and anything left out (and why).
