# Character Forge — Bridge Handover (engine ↔ front-end)

Status: **alignment in progress.** Lock §3 + the Prompt C strings, then build Flask.

## Contract invariants (must hold — see ARCHITECTURE.md §4)
- `Character` JSON, `schemaVersion: 1`. All PC/ruleset additions are additive-optional.
- Structured proficiencies are source of truth: `saveProfs`/`skillProfs` → engine derives
  `saves`/`skills`/`senses` (read-only display).
- Engine-derived, read-only in UI: PB; Initiative (= DEX mod); Spell save DC (= 8+PB+mod);
  Spell attack (= PB+mod). Engine writes `spellcasting.saveDc/attackBonus`.
- Four fixed portrait keys: `at-rest`, `in-conversation`, `in-battle`, `travelling`.
  `portraits[state] = {prompt, imageUrl, seed}`, null until generated.
- `imageUrl` = stable, content-typed, `<img src>`-able URL
  (`http://localhost:5000/art/{id}/{state}.png`) — never a filesystem path.
- Art preview == generated. PC subject pulls from `pc{}`. **build_prompt must match
  Prompt C segments 3–4 exactly (per-state scene w/ camera+lighting + per-state envPrefix)
  — STRINGS PENDING from front-end.**
- Ruleset config-driven; `extends` inheritance; unknown slug → `dnd5e-2014`.

## §3 decisions — engine proposal
1. **CORS:** enable permissive CORS for local dev (`http://localhost:*` and `null`/file origin)
   so the standalone HTML keeps working as-is. (Serving the HTML from Flask remains an option
   but isn't required; `<img>` loads aren't CORS-gated regardless.)
2. **Sync vs async:** **synchronous, block-until-done** for `/forge` and `/art`. Single local
   user; a spinner over a 10–30s wait is fine. Add a job-id/poll path later only if needed.
3. **Preview on draft:** `POST /art/preview {character, state} → {prompt}` (no saved id assumed).
   Client keeps per-keystroke preview; this endpoint is the canonical generate-time check.
4. **Shapes:** see endpoint list below. `/art` is **one state per call** (avoids a 4×30s block;
   per-slot spinners + single-state regenerate).
5. **warnings:** **`[{level, message}]`** (`level` ∈ error|warning|info) — error = illegal/unknown,
   warning = consistency drift. (validate() will emit this shape.)
6. **Generated vs drop-slot:** engine just serves `GET /art/{id}/{state}.png` (content-typed);
   no engine awareness of the manual drop-slot.

## Endpoint list (proposed — confirm, then locked)
| Method · Path | Request | Response |
|---|---|---|
| `GET /rulesets` | — | `{ rulesets: [{slug, label, extends}] }` |
| `GET /ruleset/{slug}` | — (unknown → 2014) | `{ slug, label, labels, abilityRules, statblock:{fieldOrder, showInitiativeLine}, optionLists:{classes, subclassesByClass, species, subspecies, backgrounds, feats, conditions, sizes, creatureTypes} }` |
| `POST /forge` | `{ dump, ruleset?, kind? }` | `{ character, warnings:[{level,message}] }` |
| `POST /art/preview` | `{ character, state }` | `{ prompt }` |
| `POST /art` | `{ id? \| character?, state, tweak?, seed? }` | `{ imageUrl, seed, prompt }` |
| `GET /character` | — | `{ characters: [{id, name, kind, ruleset, level?}] }` |
| `GET /character/{id}` | — | `Character` (404 if missing) |
| `POST /character` | `{ character }` | `{ id, character }` (runs apply_derived; id = slug) |
| `GET /art/{id}/{state}.png` | — | `image/png` bytes (404 if not generated) |

Storage: characters as JSON under `output/characters/{id}.json`; portraits under
`output/portraits/{id}/{state}.png`.

## Status
- [x] §3 confirmed (CORS permissive / sync / preview-on-draft / one-state-per-call /
      `{level,message}` warnings / drop-slot fallback).
- [x] Prompt C segments 3–4 locked; `build_prompt` == `computePrompt()` byte-for-byte (tests green).
- [x] Flask bridge built + verified (`forge/web/app.py`, all 9 endpoints). Run `python -m forge.web.app`.
      Smoke: `/rulesets`, `/ruleset/<slug>` option lists, `/forge`→Brakkin, `/art/preview` canonical prompt.
- [x] **Live images WORKING** (Gemini billing enabled): provider `gemini-flash`
      (`gemini-2.5-flash-image`, ~$0.04/image). Brakkin's full 4-state set generated + served.
      Switch to `gemini` (Imagen) in `config/forge_config.json` for higher quality/cost.
- [ ] Front-end wires ruleset dropdowns (`GET /ruleset/<slug>`) + live portraits
      (`POST /art` → render `portraits[state].imageUrl`) against the locked endpoints.
