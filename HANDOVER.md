# Session Handover — D&D Character Forge

Orientation for a fresh chat to continue with **no breaks**. A new chat opened in this
project auto-loads the memory files; also read `ARCHITECTURE.md` and
`Claude Code - Bridge Handover.md`. The GitHub `main` branch is the source of truth.

---

## 0. How to work with this user (READ FIRST)
- **The user is not a coder. Explain in plain English; do not dump jargon** (no commit SHAs,
  `§`-references, or code key-names in user-facing prose — keep those in the "relay to Design"
  blocks only). When a decision is needed, frame it plainly and recommend a default.
- **Make engineering calls yourself.** Only ask the user for genuine product/judgement choices.
- Build with momentum, but **stop and interview at real decision points.** The user consistently
  chose the maximal/ambitious option.
- The user is the **relay** between you (the engine) and "Claude Design" (the front-end author).
  You can't see Design's project; Design can't see your repo edits. The user is now **stepping
  back from Design** — this is coding-adaptation work from here; Design watches format via GitHub.

## 1. What this is
An agentic pipeline that turns a player's brain-dump (or manual input) into a **rules-legal D&D 5e
character/creature** — a canonical statblock (or full PC sheet) **plus a four-state portrait set**.
Local Flask backend + Python rules engine. Built for a friend (not commercial), so canonical data
stays within the openly-licensed SRD.

## 2. Architecture (locked)
- **Agents propose, the engine disposes:** the LLM picks *choices + prose*; a deterministic Python
  engine computes every number and validates. The LLM never invents the maths.
- **Generation vs rendering split:** the engine emits a `Character` JSON; the front-end renders it.
- **Two rulesets (2014 / 2024), never merged** — a config-driven switch.
- The **`Character` JSON is the shared contract**: a universal statblock for all `kind`s
  (monster/npc/creature/companion/pet/character); PC-only data lives in optional `pc{}` +
  `spellcasting{}`; `schemaVersion` stays 1 (all additions are additive-optional).

## 3. Repo & layout
- GitHub (public): **https://github.com/DanForgedFrameworks/DnD_forge**, branch `main`.
- `forge/canon/` SRD access · `forge/engine/` legacy PC maths engine (REUSE for PC derivation) ·
  `forge/contract/` maths + derive/validate/apply_derived · `forge/agents/` autofill + art ·
  `forge/ruleset/` ruleset loader · `forge/web/app.py` the Flask bridge · `forge/schema/` the contract schema.
- `config/forge_config.json` + `config/rulesets/*.json` · `samples/` (incl. `sample_pc.json` = Lyra,
  `hane*.json`, `live_brakkin-ironeye.json`) · `tests/` · `frontend/` (Design's vendored prototype) ·
  `web/forge-bridge.js` + `web/fallback-data.js` (standalone adapter — slated to retire).
- Gitignored (not in repo): `.env`, `.venv_forge/`, `data/srd/`, `output/`, the local
  `D&D 5e character generator*/` download scratch.

## 4. Run & test
- venv python: `.venv_forge/Scripts/python.exe` (Python 3.13; deps installed from `requirements.txt`).
- `.env` holds `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`. **Gemini billing is ON →
  image generation works** (provider `gemini-flash` = `gemini-2.5-flash-image`, ~$0.04/image).
- Pull SRD data (gitignored): `python scripts/fetch_srd_data.py`.
- Run the bridge: `python -m forge.web.app` → `http://127.0.0.1:5000`.
- Tests (all green): `test_contract.py`, `test_art.py`, `test_autofill.py`, `test_ruleset.py`,
  `smoke_srd.py`, `demo_build.py`.

## 5. Built & verified (engine A–E + bridge + images)
- **A** schema + maths (`forge/contract/`): `derive_modifiers`, `validate → {ok, warnings:[{level,message}]}`,
  `apply_derived`. Canonical schema `forge/schema/character.schema.json`.
- **B** statblock auto-fill (`forge/agents/autofill.py`, `output_schema.py`, `specs/autofill_system.txt`)
  via Claude structured outputs (Opus 4.8). LLM picks choices+prose; engine derives the strings.
- **C** art (`forge/agents/art.py`): `build_prompt` matches the front-end's `computePrompt()`
  **byte-for-byte** (per-state act/cam/envPrefix triple; statblock cues opt-in, off by default).
  `generate_portrait` via a pluggable backend.
- **D** PC schema delta in the contract (`pc{}`/`spellcasting{}`); worked sample `samples/sample_pc.json`.
- **E** ruleset switch (`forge/ruleset/` + `config/rulesets/` 2014/2024/homebrew; option lists derived from SRD).
- **Flask bridge** (`forge/web/app.py`): 9 endpoints, permissive CORS, character store `output/characters/`,
  image serving. Verified live end-to-end — Brakkin Ironeye got a full 4-state portrait set.

## 6. The contract on current `main` (what the front-end binds to)
`GET /rulesets` → `{rulesets:[{slug,label,extends}]}` · `GET /ruleset/<slug>` →
`{slug,label,labels,abilityRules,statblock,optionLists}` (optionLists keys:
`classes, subclassesByClass, species, subspecies, backgrounds, feats, conditions, creatureTypes, sizes`;
entries `{index,name}` except sizes/creatureTypes plain strings) · `POST /forge {dump,ruleset,kind}` →
`{character, warnings:[{level,message}]}` · `POST /art {id|character,state}` → `{prompt,imageUrl,seed}`
(absolute `http://localhost:5000/art/<id>/<state>.png`) · `GET /character` →
`{characters:[{id,name,kind,challenge,accent,ruleset,level}]}` · `GET /character/<id>` → full Character ·
`POST /character` → save (runs `apply_derived`) · `GET /art/<id>/<state>.png` → PNG bytes.

## 7. NEXT deliverable — the PC batch (awaiting user greenlight; they had questions first)
Build in one batch, then push + pin the new `main` SHA for Design:

**(B) Proficiency grants — ENGINE derives (agreed with Design).**
- Enrich `optionLists`: `classes[]` += `{saves:[ABBR], skillChoose:N, skillFrom:[index], armor:[], weapons:[], tools:[]}`;
  `backgrounds[]` += `{skills:[index], tools:[], languages, abilityOptions:[ABBR] (2024), feat (2024)}`.
  Sources: SRD `class.saving_throws`, `proficiency_choices` (→ `forge/engine/derive.class_skill_choice`),
  `class.proficiencies`; background skills/proficiencies/ability_scores/feat.
- Front-end sends `pc.class`, `pc.background`, `pc.skillChoices:[<skill index>,…]`. Extend `apply_derived`
  to resolve + set `saveProfs` (class saves), `skillProfs` (`pc.skillChoices` + background skills, as
  `[{skill,expertise:false}]`, names title-cased), and `pc.proficiencies` (`{armor,weapons,tools}` from class
  + tools/languages from background). Runs on `POST /character` **and** inside the PC `/forge` path.

**(§5c) Subspecies map.** Add `optionLists.subspeciesBySpecies = {<speciesIndex>:[{index,name}]}`.
Data supports it: 2014 subraces carry a `.race` ref, 2024 subspecies a `.species` ref (2024 has 24, 2014 has 4).

**(A) PC auto-fill — `POST /forge {kind:"character"}` → a full PC** (currently it returns a statblock).
- Add a **PC output schema** variant (strict, `additionalProperties:false`) adding `pc{}` + `spellcasting{}`
  (LLM authors lists: cantrips/known/prepared) + feature `source` + `challenge:"— (level N)"`. Use it when
  `kind=="character"`; else the existing statblock schema.
- New PC system prompt: LLM picks class/subclass/species/subspecies/background/level; fills `pc{}` (hitDice,
  feats, equipment, currency, personality{traits,ideals,bonds,flaws}), spellcasting lists, `pc.skillChoices`,
  features with `source`. Ground non-SRD races (e.g. kender) to the closest SRD species or flag.
- Post-process via the legacy engine (`forge/engine/`) + `apply_derived`: PB from level, saves/skills/senses,
  spell save DC/attack + **slots** (class+level via the 2014 Levels data; borrow 2014 for 2024 casters), and
  the edition ASI (2014 species / 2024 background). LLM proposes, engine disposes.
- **Acceptance test:** forge `"a kender rogue who steals everything and fears nothing"` → `kind:"character"`,
  `pc.class==rogue`, `pc{}` + personality present, level-based `challenge` — a PC sheet, not a CR block.
  Add a fake-model assembly test + a live test behind the API key.

**Cleanup.**
- Retire `web/forge-bridge.js` + `web/fallback-data.js` (the front-end's integrated adapter is canonical).
- Re-vendor the **v2** front-end at `web/frontend/` (from the local `D&D 5e character generator v2/handover/`),
  replacing the v1 `frontend/`. v2 adds `FRONTEND-INTEGRATION-BRIEF (for Claude Code).md`.

**Decisions LOCKED** (no rework): integrated adapter canonical; ability rules advisory (validate warnings,
no hard enforcement); `/art/preview` off (cues off → preview == generated); `/forge` replaces the whole draft
and switches to Studio.

## 8. Anti-drift protocol with Design
Cite the engine `main` SHA before the front-end binds live. An engine shape change names the **endpoint +
exact key**. A front-end change is **one re-exported `.dc.html`**. Live mode = open the front-end `.dc.html`
locally (`file://`) with the bridge running (CORS handles it); an HTTPS-hosted copy stays in fallback (mixed content).

## 9. Immediate context at handover
The user asked for (1) this handover, (2) a plain-English answer to "what does forge a PC from a sentence look
like?", then to step back from Design. After that they'll likely greenlight the PC batch in §7 — but wanted
questions answered first. Nothing in §7 is built yet.
