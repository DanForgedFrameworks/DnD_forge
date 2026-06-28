# SRD Data Rebuild & Completion — handback

**Date:** 2026-06-27 · **Scope:** DATA ONLY (no edits to `forge/`, the `.dc.html`, or tests beyond running them).
**Brief:** [`docs/SRD-DATA-REBUILD-BRIEF.md`](SRD-DATA-REBUILD-BRIEF.md).

## TL;DR

The one real gap — **2024 monsters (3 → 330)** — is filled, in the canonical 2014 monster JSON shape,
from SRD-legal CC-BY source only. The other flagged 2024 files (backgrounds / feats / subclasses / species)
were **already complete to SRD 5.2.1** and were left as-is (the brief says match the SRD, don't pad to 2014).

| dataset | before | after | action |
|---|---|---|---|
| **2024 monsters** | **3** | **330** | rebuilt from CC-BY markdown via a new converter |
| 2024 backgrounds | 4 | 4 | verified complete (SRD 5.2.1 ships exactly Acolyte/Criminal/Sage/Soldier) |
| 2024 feats | 17 | 17 | verified complete (origin + general + fighting-style + epic-boon = the SRD set) |
| 2024 subclasses | 12 | 12 | verified complete (SRD 5.2.1 ships exactly one subclass per class) |
| 2024 species | 9 | 9 | verified complete (the 9 SRD species) |
| 2014 (all) | — | — | spot-checked; no SRD 5.1 gaps found |

## Sources used (all SRD-only, all attributed)

1. **downfallx/dnd-5e-srd-markdown** — `monsters-A-Z.md` + `animals.md`, pinned commit
   `1b4b99dcb786cdd1a2fb26f8acec1551191f1ca4`. **CC-BY-4.0**, SRD 5.2.1, © Wizards of the Coast.
   This is the *same already-vetted source* the repo uses for 2024 spells/levels. The 3 pre-existing
   2024 monsters were hand-built from it and map 1:1, so it was the natural source for the full set.
2. **5e-bits/5e-database** `src/2024/en` (MIT; SRD 5.2.1) — the existing baseline for everything else.
   Confirmed it ships **only 3** 2024 monsters (its monster conversion is incomplete upstream), which is
   why monsters had to come from source 1, not a refetch.

No fan-wiki content, no beyond-SRD material. Attribution recorded in
[`data/srd/2024/ATTRIBUTION.md`](../data/srd/2024/ATTRIBUTION.md) (Source 3).

## What was added / how

- **New converter:** [`scripts/convert_srd2024_monsters.py`](../scripts/convert_srd2024_monsters.py) —
  deterministic, re-runnable, stdlib-only, same style as the existing `convert_srd2024_md.py`.
  `data/srd/` is gitignored (re-generatable canon), so **the committed artifact is this script**; the
  JSON is regenerated locally by running it (the markdown clone already lives in `.srd2024_src/`).
- **`data/srd/2024/5e-SRD-Monsters.json`** rebuilt: **330** stat blocks (235 from `monsters-A-Z.md`,
  95 from `animals.md`), sorted by `index`, in the **2014 monster object shape** so the engine/front-end
  consume it unchanged. Per-monster fields parsed: size/type/subtype/alignment, AC, HP + hit dice + roll,
  speed map, six ability scores, **proficiencies** (saving throws *and* skills), damage
  vulnerabilities/resistances/immunities, **condition immunities**, senses, languages, CR, proficiency
  bonus, XP (+ `xp_in_lair` where given), and the `special_abilities` (Traits) / `actions` /
  `bonus_actions` / `reactions` / `legendary_actions` blocks. Action/trait entries are enriched with the
  2014 sub-fields where they extract with high confidence: `attack_bonus`, `dc` (type/value/success),
  `damage[]` (incl. multi-component, e.g. slashing + acid), and `usage` (per-day, per-day-in-lair,
  recharge-on-roll, recharge-after-rest). Full text always preserved verbatim in `desc`.

## Validation (all pass)

- Repo loader: `rules_mode._repo('2024').all('monsters')` → **330**; 2014 → 334. Every category for both
  editions loads with no missing files / `KeyError` / JSON error. JSON valid, UTF-8.
- Required-key audit across all 330: **no** monster missing any of the 28 always-present 2014 keys; no
  duplicate `index`; no zero-HP / failed-parse entries (the two that looked odd — `commoner` all-10s and
  `shrieker-fungus` reaction-only — are correct to the SRD).
- Engine tests pass: `tests/test_ruleset.py`, `tests/test_rules_mode.py`, `tests/test_art.py`,
  plus `tests/smoke_srd.py`. (Run as scripts; `pytest` isn't installed in `.venv_forge`.)
- No spell/level regression: `class_spells_detailed` + `spell_limits` still resolve for 2024 and 2014
  casters (monster rebuild touches only the monsters file).
- Cross-checked against the hand-built reference entries: the converter reproduces the dragon exactly and
  is **more** correct on the aboleth — the SRD 5.2.1 aboleth has a DEX save proficiency (mod −1, save +3)
  that the hand-built sample omitted; deriving proficiency from `save ≠ ability mod` recovers it.
- Edition-correct content confirmed on spot-checks: goblins are **Fey** in 2024 (not humanoid);
  ancient-red-dragon CR 24 / 507 HP; tarrasque CR 30 / 697 HP; fraction CRs (1/8, 1/4, 1/2) parsed.

## Left out (and why)

- **`Gear` line** (equipment some humanoids carry, e.g. "Studded Leather Armor, Shortsword"): the 2014
  monster schema has **no** gear field, so it's dropped to preserve schema parity. (Equipment data still
  exists in `5e-SRD-Equipment.json`.)
- **`Initiative` value** (new 2024 stat-block line): no 2014 field; dropped. Initiative is derivable from DEX.
- **`armor_class` source-type:** SRD 5.2.1 prints a flat AC number with no breakdown, so every entry uses
  `{"type": "natural", "value": N}` (matching the 3 pre-existing 2024 entries and the dominant 2014 type).
  The value is always correct; the `type` label is cosmetic and not consumed by the engine.
- **Multiattack sub-action arrays / `action_options`** (the structured "makes two X attacks" breakdown some
  of the hand-built entries had): not synthesized — the full instruction is preserved in the action `desc`.
  Mirrors how many 2014 entries store Multiattack as name + desc only.
- **Anything not in the SRD:** by rule. The 330 are exactly the SRD 5.2.1 monster + animal stat blocks.

## To regenerate

```
.venv_forge/Scripts/python.exe scripts/convert_srd2024_monsters.py
```

(The `.srd2024_src` clone is already present; if not, clone the pinned commit per
[`data/srd/2024/ATTRIBUTION.md`](../data/srd/2024/ATTRIBUTION.md) → "Rebuild the whole 2024 dataset".)
