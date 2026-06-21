# D&D Character Forge — Architecture & Decisions

Living design doc. Updated as decisions are made.

## 1. Vision

Turn a player's input into a complete, rules-legal 5e character (+ personality,
backstory, imagery later). Multiple intake modes, one engine behind them.

## 2. The load-bearing principle: agents propose, the engine disposes

A 5e character is two kinds of data in one coat:

- **Creative / narrative** (brain dump, personality, backstory, appearance) — fuzzy,
  generative. LLMs are good at this.
- **Rules / mechanical** (proficiency bonus, HP, AC, saves, spell slots, DCs) —
  deterministic, computable from the rules. LLMs are *unreliable* here.

So: the **agent layer outputs choices + narrative only**; a deterministic **rules
engine** + local canonical DB computes all derived numbers and validates legality.
The LLM never invents a stat block.

## 3. Two locked design separations

### 3a. Generation vs. rendering (keeps the GitHub Pages door open)
The pipeline emits a single **self-contained character JSON**. The character *sheet*
is static HTML/JS that consumes that JSON. The sheet is therefore Pages-friendly from
day one; only the *generator* needs a backend. Later we can either port the rules
engine to JS (fully static) or keep it server-side. Local-first now, no design fork.

### 3b. Intake modes converge to one "intent JSON"
Brain dump, guided HTML form, conversational interview, and full/partial random are
just **different front doors that produce the same intent JSON**. Once that exists,
the downstream pipeline runs identically regardless of how it was filled.

## 4. Pipeline (the spine)

```
intent JSON
  -> resolve choices        (fill gaps: ask, or weighted-random with legality constraints)
  -> rules engine           (deterministic: compute the whole sheet from canonical DB)
  -> legality / QA gate     (code checks + optional sub-agent canonical cross-check)
  -> narrative              (personality / backstory / appearance, grounded in mechanics)
  -> image generation       (later)
  -> assemble character JSON (single accreting object, with provenance per field)
  -> static sheet renders it
```

The character is **one coherent object** (unlike curriculum's 5-doctype fan-out), so
it accretes through stages as a single versioned JSON rather than many parallel files.

### Provenance
Every field records whether it was `user`, `ai`, or `rules` derived. Powers trust and
the "tweak just this one field and re-resolve" UX.

## 5. Editions: 2014 + 2024, never merged

`ruleset: "2014" | "2024"` is a first-class parameter selecting both the dataset and
the resolution logic. The data genuinely diverges (2024 renames Races→Species,
Subraces→Subspecies; adds Weapon Mastery, Poisons; backgrounds grant ability bumps).
The canonical layer adapts per edition; the rules engine branches per edition where
rules differ. (Mirrors Catalyst's `spec_profile` switching mechanism.)

## 6. Canonical data

- **Source:** `5e-bits/5e-database` (the data behind dnd5eapi.co), English, both
  editions, pulled by `scripts/fetch_srd_data.py` into `data/srd/<edition>/`.
- **Licence:** CC-BY-4.0 / OGL — fine for local / non-commercial use.
- **Enrichment fallback:** web / sub-agent lookups for homebrew or edge cases, NOT a
  core dependency. Homebrew / campaign content arrives later as tagged JSON packs
  (`source` field) via a separate interview-style panel.

### Known data constraints (verified on first pull, 2026-06-20)
The open SRD source is asymmetric across editions:
- **2014:** rich (319 spells, full level/slot tables, 334 monsters) but sparse on
  character options the SRD never released — **1 background (Acolyte), 1 feat (Grappler)**.
- **2024:** richer options (4 backgrounds, 17 feats, weapon mastery) but **no spell
  list and no level/slot-progression tables yet**, and only 3 monsters.
- **Implication:** 2024 spellcasters can't be fully resolved from this source alone.
  Needs a fallback (borrow 2014 spell + level data as a stopgap, defer 2024 casters,
  or source 2024 caster data separately). This is an open decision.
- The enrichment/sub-agent layer is the long-term answer to all of these gaps.

## 7. Reuse from the Catalyst pipeline

Skeleton lifted from `..\Python - Test\Catalyst - Agent`:
- **Copy ~as-is:** `llm_factory.py` (multi-provider, retries, refusal handling),
  resume + housekeeping patterns, the deterministic integrity-gate idea, Flask
  dashboard (re-brand).
- **Adapt:** the stage orchestrator (swap the stage list), the spec = prompt +
  embedded JSON template pattern (for creative stages), the `json_repair` loop.
- **Build new (no Catalyst equivalent):** the **rules engine** (Catalyst validates but
  never *computes* domain values), the weighted-random/auto-choice picker, the image
  sub-pipeline, and conversational interview mode.

## 8. Status

- [x] Decisions locked: both editions, full PC-grade engine, pull open SRD data
- [x] Project scaffold + reproducible SRD fetch + edition-aware canonical layer
- [x] Front-end **Character contract** is now THE schema (`forge/schema/character.schema.json`):
      universal statblock + ext blocks (`pc{}`, `spellcasting{}`, `saveProfs`/`skillProfs`).
      Old PC schema preserved as `legacy_pc_v0.schema.json`.
- [x] Prompt A (`forge/contract/`): canonical maths (PB by CR/level, CR↔XP),
      `derive_modifiers()`, `validate()→{ok,warnings}`. Tested vs Hané
      (`tests/test_contract.py`): flags the sample's CR/PB drift; derives corrected
      proficiency lines from structured data.
- [x] Internal PC rules engine (`forge/engine/`): ability methods, edition-aware
      bonuses, PB/saves/skills/HP/spellcasting, legality (`tests/demo_build.py`).
      Feeds the contract `pc{}` generator later.
- [x] Prompt B — auto-fill agent (`forge/agents/autofill.py` + `forge/llm/client.py`):
      brain-dump → Character via Claude **structured outputs** (Opus 4.8, adaptive
      thinking). LLM authors choices + statblock prose + art fields; engine derives
      saves/skills/senses and validates. Assembly tested with a fake model
      (`tests/test_autofill.py`). Real run needs `ANTHROPIC_API_KEY` in `.env`.
- [x] Live auto-fill verified end-to-end (Opus 4.8 + `.env` key): brain-dump → full,
      rules-consistent NPC (`samples/live_brakkin-ironeye.json`), no warnings.
- [x] Prompt C — `build_prompt` (`forge/agents/art.py`): reproduces the prototype's
      `computePrompt()` byte-for-byte (curly-quote wrap, segment order, kindWord map,
      per-state scene phrases, fixed tail; statblock cues appended AFTER the suffix so
      leading text stays stable). Verified `tests/test_art.py`. `generate_portrait()`
      saves PNG bytes and returns `http://localhost:5000/art/{id}/{state}.png`.
      Backends: stub (tested) + **Gemini Imagen** `gemini_backend` (code written, not yet
      run live). `seed` is a round-tripped bookkeeping token — the Gemini Developer API
      has no image seed (Vertex-only). State labels confirmed: sentence case, suffix
      lowercased (" — at rest variant.").
- [x] Front-end confirmations applied: sentence-case state labels (suffix lowercased);
      Hané corrected to CR 9 (PB +4 — its lines were always right); both rulesets confirmed
      (2014 default now, 2024 activates with Prompt E config); preview source = `/art/preview`.
- [x] Prompt D — PC mode EXTENDS the Character (no separate sub-schema; no blocker found).
      `pc{}` + `spellcasting{}` delta defined in the schema (additive, schemaVersion 1);
      feature items gain optional `source`. Sample: `samples/sample_pc.json` (Elf Wizard
      L5) validates; statblock samples still validate.
- [x] Prompt E — ruleset abstraction (`forge/ruleset/`, `config/rulesets/`): 2014 + 2024
      base configs + a homebrew `extends` demo; `load_ruleset()` resolves base+patch,
      unknown slug → 2014; `Ruleset.option_lists()` derives class/subclass/species/
      background/feat/condition lists from the SRD per edition; labels (Race↔Species),
      ASI source, point-buy/array/bounds, statblock order + 2024 initiative line all in
      config. Verified `tests/test_ruleset.py`. (Config-only — schemaVersion stays 1.)
- [x] §2 maths + PC additions: initiative = DEX mod; spell save DC = 8+PB+mod; spell
      attack = PB+mod (engine writes `spellcasting.saveDc/attackBonus` via `apply_derived`).
      PC art subject framing pulls from `pc{}` (species/class/subclass).
- [x] Flask bridge built + verified (`forge/web/app.py`): all 9 endpoints — `/rulesets`,
      `/ruleset/<slug>`, `/forge`, `/art/preview`, `/art`, `/character` (list/get/save),
      `/art/<id>/<state>.png` — permissive CORS, char store `output/characters/`,
      `validate()` now returns `{level, message}`. Smoke-tested live: rulesets + SRD option
      lists, forge-seeded Brakkin, `/art/preview` canonical prompt. Run: `python -m forge.web.app`.
- [x] Live image render WORKING (Gemini billing enabled): provider `gemini-flash`
      (`gemini-2.5-flash-image` via generate_content, ~$0.04/image). Brakkin's full 4-state
      portrait set generated + served (consistent character, clear per-state scene variance)
      and written back onto the stored Character. Imagen backend (`gemini`) also available.
- [x] **FULL PIPELINE proven end-to-end:** brain-dump → autofill (Claude) → engine-derived
      rules-legal statblock → per-state art prompts → image (Gemini) → served URL → stored
      Character, all via the Flask bridge. A–E + bridge + images all green.
- [ ] PC follow-ups: widen autofill output for kind=character (emit pc/spellcasting);
      PC Codex view; deeper PC ability-rule validation (point-buy/array via ruleset config)
- [ ] Choice-resolution + randomisation (emits the contract shape)
- [ ] Intake → intent JSON (brain dump / form / interview / random)
- [ ] Stage orchestrator (adapt Catalyst)
- [ ] Narrative stage (LLM) + Flask backend + static sheet renderer
- [ ] Engine follow-ups: armored/shield AC, subspecies bonuses, multiclassing,
      background skill grants, feats
- [ ] Image generation, interview mode, homebrew packs

## 9. Decisions resolved + still open

Resolved:
- Ability-score generation: **all methods + manual entry** (standard array, point-buy,
  4d6-drop-lowest rolled, manual).
- Multiclassing: **single-class first**; schema/engine shaped to extend later.
- 2024 spellcasters: **borrow 2014 spell + slot data** (flagged in output).
- Scope: **data-driven over all SRD** species/classes (no curated subset).
- **Front-end `Character` JSON is the I/O contract** (engine serialises into it); it's a
  universal statblock for all `kind`s. PC-only data → optional `pc{}`/`spellcasting{}`.
  **Structured proficiencies** (`saveProfs`/`skillProfs`); engine derives the
  saves/skills/senses strings. Transport = Flask `/character`, `/forge`, `/art`;
  `validate()` returns a `warnings[]` channel; custom portrait states reserved (not built).

Still open (next interview points):
- **LLM provider** default for the creative stages (Anthropic / Gemini / OpenAI) —
  reuse Catalyst's `llm_factory`.
- **Randomisation weighting** — pure-uniform vs. theme/role-weighted auto-choices.
- **Sheet design** — arriving from Claude Design (claude.ai, not Canva); relay via staged prompts.
- **Hané sample CR** — intended CR 8 (PB +3) or ~CR 9 (PB +4)? (its lines were written at PB +4.)
- Confirm the front-end will also carry `dnd5e-2024`, not just `dnd5e-2014`.
