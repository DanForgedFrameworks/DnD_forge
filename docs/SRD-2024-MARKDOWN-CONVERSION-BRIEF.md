# Brief: convert the CC-BY 2024 SRD markdown → engine SRD JSON (data/srd/2024)

**This is a self-contained task brief for a dedicated chat.** You do not need the rest of the
project's conversation history. Read top to bottom, confirm the inputs in §9, then work the passes
in §8. Your job is **writing a deterministic markdown→JSON converter + the resulting data files** —
you are NOT changing the app or the engine's behaviour; you are producing JSON data files in the
shape the existing engine already reads.

This brief is the **2024-SRD-from-open-data** counterpart to `docs/PDF-RULES-EXTRACTION-BRIEF.md`
(which extracts the *owner's PDFs*). The two are complementary — see §3.

---

## 1. What this project is (one paragraph)
The **D&D Character Forge** (repo root: `C:\Users\celt_\OneDrive\VLE e-Learning Documents\D&D Character Forge`,
GitHub `DanForgedFrameworks/DnD_forge`) is a local Flask + Python tool that turns a description into a
rules-legal D&D 5e character sheet + portrait. **Core principle: the engine is data-driven** — it reads
canonical rules from JSON files under `data/srd/<edition>/` and derives everything from them. Today the
2024 ruleset is *sparse and partly faked*: it has no native spell or level data, so 2024 casters
**borrow the 2014 slot/spell tables**. Your job replaces that with complete, correct, openly-licensed
2024 data.

## 2. The source (your input)
- Repo: **https://github.com/downfallx/dnd-5e-srd-markdown**
- Pin to commit **`1b4b99dcb786cdd1a2fb26f8acec1551191f1ca4`** (record the actual commit you use).
- It is the official **D&D 5e (2024) SRD 5.2.1**, converted to clean markdown.
- **Licence: Creative Commons Attribution 4.0 (CC-BY-4.0).** This is the important part: unlike the
  owner's PDFs, this content **may be redistributed and committed** — provided we credit Wizards of the
  Coast. (Attribution handling: §7.)
- Files you will parse: `spells.md`, `classes.md`, `character-origins.md` (species + backgrounds),
  `feats.md`, `equipment.md`, `monsters-A-Z.md` / `animals.md` (later pass).

## 3. What this source DOES and DOES NOT give you (read this — sets expectations)
The SRD 5.2.1 is the *open subset*, not the full Player's Handbook. Confirmed contents of this repo:
- **Spells: COMPLETE — 339 spells**, each tagged with level, school, **and the classes that can cast
  it** (see §5). This is the headline win: it makes 2024 caster legality fully correct and native
  (no more borrowing 2014).
- **Classes: all 12**, with per-class+level **spell-slot tables** (HTML tables inside `classes.md`)
  → lets you build a native 2024 Levels file.
- **Subclasses: exactly 1 per class (12 total).** The SRD does **not** expand subclasses. The full
  subclass libraries still come from the owner's PDFs (the `PDF-RULES-EXTRACTION-BRIEF` chats).
- **Backgrounds: 4** (Acolyte, Criminal, Sage, Soldier). **Species: 9** (Dragonborn, Dwarf, Elf, Gnome,
  Goliath, Halfling, Human, Orc, Tiefling) with their lineages. **Feats: the SRD set** (origin / general
  / fighting-style / epic-boon).

**So the division of labour is:** this brief gives the Forge a **complete, correct, legally-shippable
2024 baseline** (especially spells + slots). The owner's PDF chats *augment* that baseline with the
extra subclasses/backgrounds/species that the SRD omits (copyrighted → those stay local). Don't try to
invent content beyond the SRD here — that's the PDF chats' job.

## 4. How the engine consumes the data (so you know what's load-bearing)
- `forge/canon/srd_repository.py` — `_CATEGORY_FILES["2024"]` maps category → filename. The reader is
  keyed on each entry's **`index`** (a kebab-case slug) and **`name`**.
- `forge/ruleset/loader.py` → `Ruleset("dnd5e-2024").option_lists()` builds the dropdowns from:
  - **classes**: `saving_throws[].index`, `proficiency_choices` (the class skill choice),
    `proficiencies[].index/name` (armor/weapons/tools — bucketed by the Proficiencies file's `type`).
  - **subclasses**: `class.index` groups subclasses under their class.
  - **species** + **subspecies** (`subspecies[].species.index`), **backgrounds**, **feats**, **conditions**.
- `forge/engine/rules_mode.py` (Strict/Relaxed spell legality):
  - `class_spell_list()` is built from **`spells[].classes[].index`** → which class can cast each spell.
  - `spell_limits()` reads the **Levels** file: per class+level `spellcasting.{cantrips_known,
    spells_known, spell_slots_level_1..9}`. **2024 currently has NO Spells or Levels file → casters
    borrow 2014.** Creating native 2024 `5e-SRD-Spells.json` + `5e-SRD-Levels.json` is the core deliverable.
- `forge/engine/grants.py` + `forge/engine/abilities.py`: class saving throws, class skill options,
  background skills/tools/languages/ability-options/feat, species/background ability bonuses.

**Validation after each pass (run from repo root, venv = `.venv_forge/Scripts/python.exe`):**
```
.venv_forge/Scripts/python.exe -c "from forge.ruleset import Ruleset; o=Ruleset('dnd5e-2024').option_lists(); \
print('classes',len(o['classes']),'subclasses',{k:len(v) for k,v in o['subclassesByClass'].items()}, \
'species',len(o['species']),'backgrounds',len(o['backgrounds']),'feats',len(o['feats']))"
.venv_forge/Scripts/python.exe -c "from forge.engine.rules_mode import class_spell_list, spell_limits; \
print('wizard spells',len(class_spell_list('wizard')),'wiz L5',spell_limits('wizard',5,3))"
.venv_forge/Scripts/python.exe tests/test_ruleset.py   # must stay green (update expected counts as data grows)
```

## 5. Source → target parse map (the heart of the job)
Each row: the engine JSON file (in `data/srd/2024/`) ← which markdown, with the parse rule. The exact
target key shapes are in `docs/PDF-RULES-EXTRACTION-BRIEF.md` §5 — **match those keys exactly**; this
section tells you where in the markdown each field comes from.

**`5e-SRD-Spells.json`** ← `spells.md`. Each spell is a `#### <Name>` block whose first italic line is
the load-bearing one:
```
#### Fireball

_Level 3 Evocation (Sorcerer, Wizard)_
**Casting Time:** Action
**Range:** 150 feet
**Components:** V, S, M (a ball of bat guano and sulfur)
**Duration:** Instantaneous
<desc paragraphs…>
```
Parse the italic line `_Level N <School> (<Class>, <Class>…)_` (cantrips read `_<School> Cantrip
(<Classes>)_` → `level: 0`). From it set **`level`**, **`school`**, and **`classes:[{index,name}]`**
(the parenthesised list — ENGINE-CRITICAL). Bold fields → `casting_time`, `range`, `components`,
`duration`; remaining paragraphs → `desc[]`. ~339 spells. **`level` + `classes[].index` must be right
for every spell** — that is what spell-list legality runs on.

**`5e-SRD-Levels.json`** ← the per-class **HTML `<table>`** features tables inside `classes.md` (columns
include `Cantrips`, `Prepared Spells` / `Spells Known`, and `——Spell Slots per Spell Level——` ×9). Parse
the HTML table (it's literal `<table><thead><tr><th>…` markup embedded in the markdown) into one entry
per **caster** class+level 1–20: `{index:"wizard-5", class:{index,name}, level, prof_bonus,
spellcasting:{cantrips_known, spells_known?, spell_slots_level_1..9}}`. Half-casters (Paladin/Ranger)
and Warlock (Pact Magic) have their own tables — map them faithfully. Non-casters need no `spellcasting`
block.

**`5e-SRD-Classes.json`** ← `classes.md` `## <Class>` sections. Pull `hit_die`, `saving_throws`,
starting `proficiencies` (armor/weapons/tools/skills) from the "Core <Class> Traits" / "Becoming a
<Class>" blocks, the class skill choice → `proficiency_choices`, and list the one SRD subclass in
`subclasses[]`.

**`5e-SRD-Subclasses.json`** ← `classes.md` `### <Class> Subclass: <Name>` sections (12 total). Set
`class:{index,name}` from the heading; capture `name`, `summary`/`description`, features by level.

**`5e-SRD-Species.json`** + **`5e-SRD-Subspecies.json`** ← `character-origins.md` → `## Character
Species` → `#### <Species>` (9). Pull creature type, `size`, `speed`, traits; the lineages within each
species become subspecies entries referencing the parent via `species:{index,name}`.

**`5e-SRD-Backgrounds.json`** ← `character-origins.md` → `## Character Backgrounds` → `#### <Background>`
(4). Pull `ability_scores[]`, `feat`, skill `proficiencies[]`, tool proficiency, `equipment_options`.

**`5e-SRD-Feats.json`** ← `feats.md` `#### <Feat>` blocks → `{index,name,description[],type}` (type from
the section: Origin / General / Fighting Style / Epic Boon).

**`5e-SRD-Proficiencies.json`** — ensure every armor/weapon/tool/skill `index` referenced by a class or
background **exists** here as `{index,name,type}` (`type` ∈ `Armor | Weapons | Artisan's Tools | Gaming
Sets | Musical Instruments | Vehicles | Other | Skills | Saving Throws`). Source names from `equipment.md`.
The engine buckets class/bg profs by looking their `index` up in this file, so a missing entry = a
silently-dropped proficiency.

**`5e-SRD-Skills.json`** — already complete; leave it.

**Register the two new files** so the engine reads 2024 spells/levels natively instead of borrowing
2014: in `forge/canon/srd_repository.py`, add to `_CATEGORY_FILES["2024"]`:
`"spells": "5e-SRD-Spells.json", "levels": "5e-SRD-Levels.json"`. (One line each — the **only** code
change in scope. Coordinate with the main build chat before touching `rules_mode.py` itself.)

## 6. Build a converter, don't hand-transcribe
Write a deterministic Python script (suggest `scripts/convert_srd2024_md.py`) that reads the markdown
and emits the JSON. Reasons: 339 spells × correctness, repeatability, and — because the source is
CC-BY and public — **anyone can regenerate the data from one command** (this is what lets us keep the
generated JSON out of git if we choose; see §7). Use subagents per category if helpful, but the output
must be a single rerunnable script + the JSON it produces. Validate with §4 after each pass.

## 7. Legal & placement (decided — CC-BY changes the rules vs the PDF brief)
The PDF brief says "never commit data" because the PDFs are copyrighted. **This source is CC-BY, so that
restriction does not apply here.** Decisions:
- **Commit the converter script + an attribution/credit file.** Add `data/srd/2024/ATTRIBUTION.md` (and
  a short credit line in the repo README) crediting "System Reference Document 5.2.1, © Wizards of the
  Coast LLC, CC-BY-4.0" and linking the source repo + pinned commit. This satisfies the licence.
- **Output the generated JSON to `data/srd/2024/`** (the existing engine path, currently gitignored).
  This works immediately and stays consistent with the 2014 data layout — **no `.gitignore` surgery,
  no engine path change.** The data is fully reproducible via the committed converter.
- **Optional follow-up (owner's call, not required now):** because it's legal, the generated 2024 JSON
  *may* later be committed too (so a fresh clone has working 2024 data without running the converter).
  That needs a `.gitignore` carve-out (`data/srd/` ignored but `!data/srd/2024/` tracked) and must keep
  `data/srd/2014/` ignored (those PDFs *are* copyrighted). **Leave this for the owner to decide; don't
  commit the JSON unless they say so.**

## 8. Suggested passes (validate with §4 after each)
1. **Spells** — `5e-SRD-Spells.json` from `spells.md` (level, school, **classes[]**). Register it (§5).
   Check: `class_spell_list('wizard')` is non-trivial and pulled from 2024, not 2014.
2. **Levels** — `5e-SRD-Levels.json` from the `classes.md` HTML slot tables. Register it (§5).
   Check: `spell_limits('wizard',5,3)` returns correct 2024 cantrips/slots.
3. **Classes + Subclasses** — `5e-SRD-Classes.json` / `5e-SRD-Subclasses.json` (1 subclass each).
4. **Species + lineages** — `5e-SRD-Species.json` / `5e-SRD-Subspecies.json`.
5. **Backgrounds** — `5e-SRD-Backgrounds.json` (4).
6. **Feats** — `5e-SRD-Feats.json`. **Proficiencies** — backfill any referenced index.
7. **Attribution** — write `ATTRIBUTION.md` + README credit line (§7).
8. (Later, separate) **Monsters** — `monsters-A-Z.md` / `animals.md` → `5e-SRD-Monsters.json`.
Keep a running before/after count so the owner can see progress.

## 9. Inputs to confirm before starting
1. Clone the source repo at the pinned commit (§2); confirm it's SRD **5.2.1 (2024)**, CC-BY.
2. Confirm **2024-only**: you only write under `data/srd/2024/` and the two converter/attribution files.
   **Never touch `data/srd/2014/`.**
3. Confirm the venv runs: `.venv_forge/Scripts/python.exe tests/test_ruleset.py` is green before you start.

## 10. Definition of done (PC-options pass)
`Ruleset("dnd5e-2024").option_lists()` shows the SRD baseline (12 classes each with their 1 subclass,
9 species + lineages, 4 backgrounds, the SRD feats); `class_spell_list()` / `spell_limits()` resolve
from **native 2024** spell + level data (not borrowed 2014); `tests/test_ruleset.py` green (counts
updated); the converter script + `ATTRIBUTION.md` committed; generated JSON present under
`data/srd/2024/` (kept out of git unless the owner opts in per §7).
