# Handback: native 2024 spell + slot data is now in place

**From:** the 2024-SRD-conversion chat (per `docs/SRD-2024-MARKDOWN-CONVERSION-BRIEF.md`)
**To:** the main engine/build chat
**Status:** data delivered + loadable natively; the engine still *borrows 2014* until the switch below is made.

## What was delivered (this chat's scope — done)

Generated from the CC-BY **SRD 5.2.1** markdown (repo `downfallx/dnd-5e-srd-markdown`, pinned commit
`1b4b99dcb786cdd1a2fb26f8acec1551191f1ca4`) by a single re-runnable converter:

- `scripts/convert_srd2024_md.py` — deterministic markdown→JSON converter.
- `data/srd/2024/5e-SRD-Spells.json` — **339 spells**; each has `level`, `school`, and the
  engine-critical `classes[].index` (8 casters; 0 classless, 0 unknown class refs, indexes unique).
- `data/srd/2024/5e-SRD-Levels.json` — **160 entries** = 8 caster classes × levels 1–20, with
  `prof_bonus` + `spellcasting{cantrips_known, spells_known, spell_slots_level_1..9}`. Half-casters
  (Paladin/Ranger, colspan-5 tables) and Warlock Pact Magic (`Spell Slots` + `Slot Level`) handled.
- Registered both in `forge/canon/srd_repository.py` → `_CATEGORY_FILES["2024"]` (`spells`, `levels`).
- `data/srd/2024/ATTRIBUTION.md` + README credit line (CC-BY requirement).

Proof it loads natively (not from 2014):
```
SRDRepository("2024").all("spells")  -> 339
SRDRepository("2024").all("levels")  -> 160
```
All 8 existing test suites stay green.

## What remains (engine chat's scope — the brief said coordinate before touching these)

The data is now native, but three call sites still hardcode/borrow 2014. To make 2024 casters use the
native data, switch each to the active edition:

1. **`forge/engine/rules_mode.py`** — `_spell_list_by_class()` (line ~62), `_levels_block()` (~79) and
   the gear path call `_repo_2014()` directly. Make the spell-list/slot helpers edition-aware (thread the
   character's `ruleset`/edition through `enforce_rules` → `class_spell_list` / `spell_limits`, or cache a
   repo per edition). Today the 2024 caster legality police runs against the 2014 list.
2. **`forge/engine/builder.py`** — `_resolve_spellcasting()` (lines ~164–187) deliberately overrides 2024
   spellcasting metadata with the borrowed 2014 class entry and tags a "borrowed 2014" note. With native
   2024 data present, drop the override for 2024 (or guard it on "2024 data missing") and pass a **2024**
   `levels_repo`/`class_repo`.
3. **`forge/agents/autofill.py:251`** — `levels_repo = SRDRepository("2014", …)` is hardcoded. For a 2024
   character, construct the 2024 repo instead.

Note: 2024 spell *counts per class* differ from 2014 (e.g. wizard 218 vs 204) — expected; the 2024 list is
its own. Subclasses, backgrounds (4) and species (9) in 2024 remain the SRD baseline; the fuller libraries
come from the owner's PDF chats, not here.

## Pre-existing failing test (NOT caused by this data work — flagging it)

`tests/test_grants.py` fails on its wizard case. It asserts the **2014** Sage background is "absent in
2014 SRD" and expects wizard skills `["Arcana", "Investigation"]`. But the 5e-database **2014** set
genuinely includes Sage (Arcana + History), so the result is `["Arcana", "Investigation", "History"]`.
The test premise is stale; the data is correct. This is in the 2014 path and is independent of the 2024
spells/levels/baseline work (which only added 2024 `spells`/`levels` keys). It surfaced now only because
the 2014 backgrounds file was (re)materialised mid-session. Fix is one line — either update the expected
list to include `History`, or point the test at a background actually absent from the 2014 SRD.

## Regenerate the data
```
git -C .srd2024_src init && git -C .srd2024_src remote add origin https://github.com/downfallx/dnd-5e-srd-markdown.git
git -C .srd2024_src fetch --depth 1 origin 1b4b99dcb786cdd1a2fb26f8acec1551191f1ca4 && git -C .srd2024_src checkout FETCH_HEAD
.venv_forge/Scripts/python.exe scripts/convert_srd2024_md.py
```
