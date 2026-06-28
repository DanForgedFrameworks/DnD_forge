# PC Progression (levelling) + Multiclass — brief for a separate (engine) chat

**Goal:** two related ENGINE features the front-end currently has no hook for —
1. **Levelling** — let a player change a PC's **level** and have the engine **re-derive** the level-dependent
   numbers (hit points / hit dice, proficiency bonus, spell slots, spells-known/prepared counts, save DC + attack,
   class features for the new level).
2. **Multiclass** — real 5e multiclassing (two+ classes): combined spell-slot table, per-class features at their own
   class-levels, mixed hit dice, multiclass proficiency rules.

> Run in its own chat. These are deeper than the front-end build work and share the **PC derivation engine**, so do
> them together. Front-end wiring is small once the engine exposes a clean derive endpoint.

---

## Why now / current state (audited 2026-06-27)

- The Studio's PC editor (`web/frontend/Character Forge - Prototype.dc.html`) edits class/subclass/species/background/
  skills via `setPcFields`, **but those changes are LOCAL only — nothing re-derives.** There is **no Level control**
  anywhere, and the Codex is display-only. So a PC's level is whatever the forge set, and can't be changed.
- Derivation lives in the engine: `forge/agents/autofill.py` `_assemble_pc` / `_resolve_pc_spellcasting`,
  `forge/engine/builder.py` `_resolve_spellcasting`, `forge/engine/derive.py` `spell_slots(...)`,
  `forge/engine/rules_mode.py` `spell_limits(...)` + `class_spell_list(...)`. These already compute level-dependent
  values at forge time — the task is to make them **re-runnable on demand** for a chosen level / class mix.
- Edition-native already works (2014 vs 2024 SRD tables) — keep that intact.

---

## Feature 1 — Levelling + re-derive

**Engine:** a deterministic re-derivation entry point, e.g. `POST /character/derive` (or extend the save path) that
takes a character + (new) `pc.level` and returns the character with re-derived: `hp` (+`pc.hitDice.total`),
proficiency bonus (where surfaced), `spellcasting.slots` / `saveDc` / `attackBonus`, spells-known/prepared **counts**
(don't silently drop the player's chosen spells — warn if over the new limit, advisory), and ideally class
**features** gained by that level. Pure/deterministic; no LLM. Reuse the existing derive helpers.

**Front-end (small, once the endpoint exists):** add a **Level** control to the Studio PC editor; on change call the
derive endpoint and update the draft (mirrors how the spell picker calls `/spells`). Show what changed.

**Rules-mode aware:** Relaxed = re-derive + advisory notes; Strict = enforce counts. Honour the existing
ability-score/spell overrides (don't clobber player-set spells; re-derive only the counts/slots/HP).

## Feature 2 — Multiclass

**Data model:** today `pc.class`/`pc.subclass`/`pc.level` are single. Introduce a multiclass shape WITHOUT breaking
single-class characters — e.g. `pc.classes = [{class, subclass, level}, ...]` with `pc.class`/`pc.level` kept as the
primary for back-compat, or a clearly-versioned new field the engine + front-end both read. Decide and document.

**Engine:** combined **caster level** → multiclass spell-slot table (PHB multiclass spellcaster rules); each class's
features resolved at its own class-level; hit dice = the mix; multiclass proficiency grants (reduced vs single-class).
SRD has the tables needed. This is the bulk of the work.

**Front-end:** the Studio class picker becomes add/remove-classes (each with its own subclass + level); the Codex /
Play / spell picker read the class list. The Concept Sheet already accepts a free-text multiclass string (e.g.
"Ranger (Fey Wanderer) / Druid (Circle of Dreams)") and currently just flags it — wire that to seed `pc.classes`.

**Interop:** the **spell picker** (`GET /spells`) and the **Play tab** slot pips should reflect the *combined*
caster level once multiclass lands.

---

## Constraints / definition of done

- **Single-class characters must keep working byte-for-byte** — multiclass is additive.
- Deterministic engine maths (no LLM in derivation). Edition-native (2014 + 2024) preserved.
- Don't clobber player overrides (exact ability scores, hand-picked spells/equipment) — re-derive the *derived* bits
  only, warn on conflicts (advisory in Relaxed).
- Tests: extend `tests/test_ruleset.py` / `tests/test_rules_mode.py`; keep `tests/test_art.py` green.
- Deliver: the derive endpoint + (optional) multiclass model, front-end Level control + class-list editor, a handback
  note. Coordinate the front-end contract (request/response shape) so the build chat can wire it without collisions.

## Note for the front-end build chat (already done there, 2026-06-27)
The **fidelity** half is handled front-end: a **Studio equipment editor** (edit/add/remove gear + currency) and a
**Concept-Sheet "Equipment / gear" field** honoured exactly at forge (deterministic `pc.equipment` override, plus
paste-to-parse of an "Equipment:" outline section). So gear is now retained + correctable; this brief is the
*progression/multiclass* engine work only.
