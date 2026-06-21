# Brief: extract full D&D 5e (2024) character data from the owner's PDFs → SRD JSON

**This is a self-contained task brief for a dedicated chat.** You do not need the rest of the
project's conversation history. Read this top to bottom, confirm the two inputs in §8, then work
the passes in §7. Your job is **data extraction + structuring only** — you are NOT changing the app
or the engine code; you are producing JSON data files the existing engine already knows how to read.

---

## 1. What this project is (one paragraph)
The **D&D Character Forge** (repo root: `C:\Users\celt_\OneDrive\VLE e-Learning Documents\D&D Character Forge`,
GitHub `DanForgedFrameworks/DnD_forge`) is a local Flask + Python tool that turns a description into a
rules-legal D&D 5e character sheet + portrait. **Core principle: the engine is data-driven** — it reads
canonical rules from JSON files under `data/srd/<edition>/` and derives everything from them. The app
currently looks "sparse" (only one subclass per class, few species lineages, few backgrounds) **because
it only ships the openly-licensed SRD subset.** Your job fixes that by adding the full content from the
owner's books, in the *same JSON shape* the engine already reads — so the dropdowns and rules just fill out.

## 2. The mission
Extract the **character-creation-relevant** D&D 5e (2024) rules from the owner's **legally-owned PDFs**
(Player's Handbook, Tasha's, Monster Manuals, etc.) and write them into `data/srd/2024/*.json` using the
**existing file shapes** documented in §5. Result: the engine's class/subclass/species/lineage/background/
feat/spell lists become complete, and caster legality (spell lists + slots) works fully for 2024.

## 3. Decisions already made (do not re-litigate)
- **Edition: 2024 PRIMARY.** Build full 2024 data. **Leave the 2014 SRD (`data/srd/2014/`) untouched** as a
  secondary fallback — do not edit or expand it.
- **Scope order: PC OPTIONS FIRST** (see passes §7). Monster Manual statblocks are a later pass.
- **Format: EXTEND the existing SRD JSON shape** in place (`data/srd/2024/*.json`) — no new pack format, no
  engine changes. Match the keys in §5 exactly so `option_lists()` and `rules_mode.py` pick the data up
  automatically.
- **Legal/placement:** the owner owns the books; this is a personal, non-commercial tool. **`data/srd/` is
  gitignored** (confirm: it is NOT tracked by git) — so this extracted book data **stays local and is never
  committed or pushed** to the public repo. Keep it that way. Do not `git add` anything under `data/srd/`.

## 4. How the engine consumes the data (so you know what's load-bearing)
- `forge/canon/srd_repository.py` — `_CATEGORY_FILES["2024"]` maps category → filename. The reader is keyed
  on each entry's **`index`** (a kebab-case slug) and **`name`**.
- `forge/ruleset/loader.py` → `Ruleset("dnd5e-2024").option_lists()` builds the dropdowns from:
  - **classes**: `saving_throws[].index`, `proficiency_choices` (the class skill choice), `proficiencies[].index/name`
    (armor/weapons/tools — bucketed by the `proficiencies` file's `type`).
  - **subclasses**: `class.index` (groups subclasses under their class) — **THIS IS THE BIG GAP: only 1 per class today.**
  - **species** + **subspecies** (`subspecies[].species.index`), **backgrounds**, **feats**, **conditions**.
- `forge/engine/rules_mode.py` (Strict/Relaxed spell legality):
  - `class_spell_list()` is built from **`spells[].classes[].index`** → which class can cast each spell.
  - `spell_limits()` reads the **Levels** file: per class+level `spellcasting.{cantrips_known, spells_known,
    spell_slots_level_1..9}`. **2024 currently has NO Spells or Levels file → casters borrow 2014.** To make
    2024 fully correct you must CREATE `5e-SRD-Spells.json` and `5e-SRD-Levels.json` for 2024 (see §5/§7).
- `forge/engine/grants.py` + `forge/engine/abilities.py`: class saving throws, class skill options, background
  skills/tools/languages/ability-options/feat, species ability bonuses (2014) / background ability bonuses (2024).

**Validation after each pass (run from repo root, venv = `.venv_forge/Scripts/python.exe`):**
```
.venv_forge/Scripts/python.exe -c "from forge.ruleset import Ruleset; o=Ruleset('dnd5e-2024').option_lists(); \
print('classes',len(o['classes']),'subclasses', {k:len(v) for k,v in o['subclassesByClass'].items()}, \
'species',len(o['species']),'subspecies-keys',list(o['subspeciesBySpecies']), 'backgrounds',len(o['backgrounds']),'feats',len(o['feats']))"
.venv_forge/Scripts/python.exe -c "from forge.engine.rules_mode import class_spell_list, spell_limits; \
print('wizard spells',len(class_spell_list('wizard')), 'wiz L5', spell_limits('wizard',5,3))"
.venv_forge/Scripts/python.exe tests/test_ruleset.py   # must stay green
```
The existing tests assume the SRD baseline counts; if you add data, UPDATE `tests/test_ruleset.py` expectations
(or just confirm the new counts are higher and the structure is intact).

## 5. Exact target shapes (match these keys — real samples from current files)
All files live in `data/srd/2024/`. `index` = unique kebab slug; cross-references use `{"index","name","url"}`
objects (the `url` can be a plausible `/api/2024/<category>/<index>` string; the engine only reads `index`/`name`).

**Classes** — `5e-SRD-Classes.json` (12 entries; ADD missing subclass refs, keep these keys):
```jsonc
{ "index":"wizard","name":"Wizard","hit_die":6,
  "saving_throws":[{"index":"int","name":"INT"},{"index":"wis","name":"WIS"}],
  "proficiency_choices":[{"choose":2,"type":"proficiencies","from":{"option_set_type":"options_array",
     "options":[{"option_type":"reference","item":{"index":"skill-arcana","name":"Skill: Arcana"}}, ...]}}],
  "proficiencies":[{"index":"daggers","name":"Daggers"}, ...],   // armor/weapons/tools (type comes from Proficiencies file)
  "spellcasting":{"level":1,"spellcasting_ability":{"index":"int","name":"INT"},"info":[...]},
  "subclasses":[{"index":"evoker","name":"Evoker"}, ...] }      // list ALL subclasses here
```
**Subclasses** — `5e-SRD-Subclasses.json` (**MAIN GAP: 12 today = 1/class → add ALL of them**):
```jsonc
{ "index":"evoker","name":"Evoker","class":{"index":"wizard","name":"Wizard"},
  "summary":"...","description":[...],"features":[ /* by level, optional for dropdowns */ ] }
```
**Species** — `5e-SRD-Species.json`:
```jsonc
{ "index":"elf","name":"Elf","size":"Medium","speed":30,
  "subspecies":[{"index":"elven-lineage-high-elf","name":"High Elf"}, ...],"traits":[...] }
```
**Subspecies/lineages** — `5e-SRD-Subspecies.json` (ref the parent via `species`):
```jsonc
{ "index":"elven-lineage-high-elf","name":"High Elf","species":{"index":"elf","name":"Elf"},"traits":[...] }
```
**Backgrounds** — `5e-SRD-Backgrounds.json` (2024 shape — ADD the rest of the PHB backgrounds):
```jsonc
{ "index":"acolyte","name":"Acolyte",
  "ability_scores":[{"index":"int","name":"INT"},{"index":"wis","name":"WIS"},{"index":"cha","name":"CHA"}],
  "feat":{"index":"magic-initiate","name":"Magic Initiate"},
  "proficiencies":[{"index":"skill-insight","name":"Skill: Insight"},{"index":"tool-calligraphers-supplies","name":"Tool: ..."}],
  "equipment_options":[...] }
```
**Feats** — `5e-SRD-Feats.json`: `{ "index","name","description":[...],"type":"..." }`
**Proficiencies** — `5e-SRD-Proficiencies.json`: each `{ "index","name","type" }` where `type` ∈
`Armor | Weapons | Artisan's Tools | Gaming Sets | Musical Instruments | Vehicles | Other | Skills | Saving Throws`.
**Add new tool/weapon/armor proficiency entries here** if a class/background references an index not already present
(the engine buckets class/bg profs by looking their `index` up in this file).
**Skills** — `5e-SRD-Skills.json`: `{ "index":"arcana","name":"Arcana","ability_score":{"index":"int"} }` (already complete).

**Spells — `5e-SRD-Spells.json` (CREATE for 2024; copy the 2014 shape):**
```jsonc
{ "index":"fire-bolt","name":"Fire Bolt","level":0,"school":{"index":"evocation","name":"Evocation"},
  "classes":[{"index":"sorcerer","name":"Sorcerer"},{"index":"wizard","name":"Wizard"}],   // ENGINE-CRITICAL
  "desc":[...],"range":"120 feet","components":["V","S"],"ritual":false,"concentration":false,"casting_time":"1 action" }
```
The **`level`** and **`classes[].index`** are load-bearing (spell-list legality). Get those right for every spell.

**Levels — `5e-SRD-Levels.json` (CREATE for 2024; one entry per class+level 1–20):**
```jsonc
{ "index":"wizard-5","class":{"index":"wizard","name":"Wizard"},"level":5,"prof_bonus":3,
  "spellcasting":{ "cantrips_known":4, "spell_slots_level_1":4,"spell_slots_level_2":3,"spell_slots_level_3":2,
     "spell_slots_level_4":0,"spell_slots_level_5":0,"spell_slots_level_6":0,"spell_slots_level_7":0,
     "spell_slots_level_8":0,"spell_slots_level_9":0 } }       // known-casters also add "spells_known": N
```
Only caster classes need the `spellcasting` block. (If creating full 2024 Levels is too big initially, the
engine already borrows 2014 slot tables — so Spells is higher priority than Levels.)

## 6. Add `5e-SRD-Spells.json` + `5e-SRD-Levels.json` to the reader
After creating those two 2024 files, register them so the engine reads 2024 spells natively instead of borrowing
2014: in `forge/canon/srd_repository.py`, add to `_CATEGORY_FILES["2024"]`:
`"spells": "5e-SRD-Spells.json", "levels": "5e-SRD-Levels.json"`. (Small one-line-each edit — the ONLY code change
in scope. Then `rules_mode._repo_2014()` could optionally be pointed per-edition, but leaving the 2024 spell/level
files in place is enough for `option_lists`; coordinate with the main build chat before changing `rules_mode.py`.)

## 7. Suggested working method (passes — validate after each)
Big job → do it in passes, validating with §4 after each. **Subagents help** (one per category or per book);
have each return structured JSON validated against §5, then merge. Order:
1. **Subclasses** (the headline gap) — all subclasses for the 12 classes, with `class.index` set. Update each class's
   `subclasses[]` list to match.
2. **Backgrounds** — the full PHB background list (ability_scores, feat, proficiencies).
3. **Species + lineages** — all species + their subspecies/lineages, ability/trait data.
4. **Feats** — the full feat list.
5. **Spells** — create `5e-SRD-Spells.json` (every spell: index, name, level, school, **classes[]**). Then register it (§6).
6. **Levels** — create `5e-SRD-Levels.json` (per class+level spellcasting blocks). Register it (§6).
7. (Later) **Monsters** — Monster Manual statblocks into `5e-SRD-Monsters.json` (separate pass, not PC-critical).
Keep a running note of counts before/after so the owner can see progress.

## 8. Two inputs you need from the owner before starting
1. **The PDF folder path** (where the PHB / Tasha's / Monster Manuals live).
2. Confirm **2024-only** (you only edit `data/srd/2024/`; never `data/srd/2014/`).

## 9. Definition of done (pass 1 = PC options)
`Ruleset("dnd5e-2024").option_lists()` shows **multiple subclasses per class**, the **full background + species/
lineage + feat lists**; `class_spell_list()`/`spell_limits()` resolve from native 2024 spell+level data;
`tests/test_ruleset.py` green (update expected counts as needed). Nothing under `data/srd/` is git-committed.
