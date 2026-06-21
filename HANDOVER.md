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

## 7. The PC batch — BUILT (engine + front-end), local commits only (not pushed yet)
Status 2026-06-21: the user took over BOTH design and coding (Design is stepping back).
All four engine jobs + the front-end jobs are done and verified; only optional polish + a
push to GitHub remain. What shipped this batch:
- (B) Proficiency grants on `optionLists` + `engine/grants.resolve_pc_proficiencies` — DONE.
- (§5c) `optionLists.subspeciesBySpecies` — DONE.
- (A) PC forge path `POST /forge {kind:"character"}` → full PC — DONE, verified LIVE (Claude
  forge + Gemini 4-state portrait set on a kender rogue). PC object overflows the strict
  structured-output grammar → PC path uses loose JSON (`LLMClient.complete_json_loose`,
  template + repair). Homebrew species grounded to nearest SRD, flavour name kept.
- NEW product decision (user): **Rules mode** — `strict` vs `relaxed` (default relaxed),
  stored at `pc.rulesMode`, passed to `/forge` as `rulesMode`. `engine/rules_mode.py`:
  per-class spell lists, prepared/known + cantrip limits, by-the-book gear. Strict corrects+
  errors; relaxed notes only. BOTH fully built.
- NEW: the Forge is reframed as the "surprise me with a great character" door — `/forge` takes
  optional `details` (flavour notes). Front-end (`web/frontend/`, the re-vendored v2) gained a
  Strict/Relaxed toggle + a collapsible "Add some flavour" panel (age/experience, origin,
  memory). Verified live in a browser against the bridge (`.claude/launch.json` runs both).
- Cleanup: v2 re-vendored to `web/frontend/`. Still TODO: retire `web/forge-bridge.js` +
  `web/fallback-data.js` + the v1 `frontend/` (user to confirm deletion); push to GitHub.

Original spec (now satisfied) kept below for reference:

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

## 9. Immediate context at handover (Session 1)
The user asked for (1) this handover, (2) a plain-English answer to "what does forge a PC from a sentence look
like?", then to step back from Design. The PC batch in §7 is now BUILT (see §7 status + §10).

---

## 10. Session 2 — front-end UX overhaul (IN PROGRESS — RESUME HERE)
The user took over BOTH design + coding (Design stepped back). Heavy front-end work done; large backlog queued.
**Run locally:** `.claude/launch.json` defines two servers — `forge-bridge` (Flask :5000) + `forge-frontend`
(`python -m http.server 8000 --directory web/frontend`). Start both via the Preview MCP, then open
`http://127.0.0.1:8000` (welcome gateway). Canonical front-end = `web/frontend/Character Forge - Prototype.dc.html`
(+ `support.js`, `image-slot.js`, `assets/portal-*.png`). All work committed LOCALLY (not pushed — user's choice).

### DONE + committed this session
- **Engine (committed):** proficiency grants on optionLists; `engine/grants.resolve_pc_proficiencies`;
  `engine/rules_mode.py` (Strict/Relaxed: per-class spell lists, prepared/known + cantrip limits, by-book gear);
  PC forge path `POST /forge {kind:character}` (loose-JSON `complete_json_loose` — strict grammar overflowed);
  soft-delete/restore/purge endpoints; `web/forge_log.py` (every /forge → `output/forge_log/`, interrogatable).
- **Front-end (web/frontend/):** Strict/Relaxed toggle + collapsible flavour box in Forge; CR→**Level** for PCs
  everywhere; Codex portrait no longer crosses the stat lines; **"My creations" library** (5 buckets PCs/NPCs/
  Monsters/Companions/Pets, Save+toast, reopen restores art, **soft-delete→Recently deleted→Restore**,
  Delete-forever, **Copy/duplicate**, click-to-enlarge **lightbox**); **welcome portal** (3 pixel-art doors,
  hover shimmer run-once, **dice-rain cleanse**, logo→gateway); **in-Forge entry chooser** (Start-from-example
  collapsible bar / Surprise me / Blank; kind toggle only when `freshStart`); **Surprise me (interim)** rolls
  legal options from `ruleset.optionLists` + forges.

### Art style — LOCKED (from user's reference images)
Primary **Greg Rutkowski**, secondary **Tyler Jacobson**. Gritty, painterly, atmospheric, **figure-in-scene**.
Lighting/palette **follow the subject** (frost druid = cold blue, fire = ember; not always warm). Bake those two
names into the default house style. (Pixel-art is ONLY the UI portal doors — deliberately a different style.)

### PENDING BACKLOG — build in this order (these are the live to-dos)
1. **Dice transition rework:** make it a **fountain UP from the bottom** that arcs over and **falls back down**
   to cleanse; **lots** of dice, varied sizes; **run LONGER** (current ~820ms reveal is too short — dice never
   cross the screen). In `runRain()` + `enterStage()` timing in the .dc.html.
2. **Surprise Me → re-rollable CONCEPT flow:** it should **populate** concept + appearance/outfit/gear/
   environment/art-style with random picks the user can **re-roll cheaply a few times**; a **scribble/"…"
   animation** plays while rolling, nothing else clickable. Only when happy → **Forge**, which shows a
   **confirmation** (token spend) + a **rules-mode confirm** (Rule-of-Cool vs by-the-book).
3. **Forge UX:** while forging, **grey-out/lock** the whole UI + loading animation; afterwards **STAY in the
   Forge** (no auto-jump to Studio) and show a progression strip: *"Happy with the concept? Happy with the
   art?" → go to Studio*.
4. **Examples redesign:** **vertical** list (not horizontal scroll), grouped **Monster / NPC / Player
   characters**, with a clear **active highlight** so the user always knows where they are.
5. **Portrait controls:** surface **"Generate all"** + **individual** per-state generate (currently hidden).
6. **Portrait-set consistency (the gender-drift fix):** generate as a **SET** — first (at-rest) = reference,
   condition the other 3 on that image (Gemini 2.5-flash is multimodal/image-input) + lock a tight appearance
   incl. explicit gender. Regenerate lets the user pick which image/prompt is the anchor. Engine: `art.py`
   backend accepts a reference image + a `generate_portrait_set()`.
7. **House art style + class-aware scenes:** lock the Rutkowski/Jacobson default; make per-state beats
   **contextual by class/role** (rogue whispers, wizard confers with a familiar, barbarian roars) — extend
   `art.stateBeats`. Atmosphere/depth/props tied to outfit/gear/appearance/environment.
8. **Studio editing + consolidation:** show & edit the **spell list** (cantrips/prepared by level), **actions**,
   **reactions** (validate via `rules_mode`); **LOCK the category (`kind`)** in Studio (set at creation only —
   shouldn't flip PC↔monster mid-edit); **consolidate** the scattered edit fields (category/type/alignment/etc).
9. **From-sheet upload:** real upload of a Word/PDF sheet → engine reads it (`autofill` already accepts
   `docx_text`) → character. Add a bridge endpoint + front-end file input + docx/pdf text extraction.
10. **DATA decision — fuller options:** SRD ships only 1 subclass/class, ~4 subraces, 1 background (2014) /
    4 (2024). **2024 does NOT add subclasses or dwarf subraces** (same limit; only more backgrounds). Full PHB
    content is copyrighted (no legal free dataset). Route = build **homebrew/enrichment data packs**
    (`source`-tagged) the user hand-populates with the options they use; build a pack loader + starter pack.
    Until then, consider a small UI note "SRD options only" so sparse dropdowns don't confuse.

### Way of working with this user (CRITICAL)
Non-coder — **plain English, no jargon**. Keep turns **TIGHT** and work strictly **IN ORDER** (user explicitly
flagged that long/slow turns make them deviate). Ship one thing → verify → commit → check in. Make engineering
calls yourself; only ask genuine product choices. **Commit locally; do NOT push unless asked.** Verify the
front-end via the **Preview MCP** (`preview_start` the two launch.json servers; screenshots time out on
image-heavy views — probe the DOM with `preview_eval` instead). The .dc.html is a template engine (`<sc-if>`,
`<sc-for>`, `{{ }}`) — app logic is a React-like class IN the .dc.html (state/handlers/`render()` props);
`support.js` is just the runtime (don't edit it).
