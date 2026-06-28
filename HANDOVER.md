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
- `.env` holds `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`. **Image generation works** —
  provider is **OpenAI `gpt-image-1.5`** (config `image.provider == "openai"`); it renders the locked
  Rutkowski/Tyler-Jacobson house style as a gritty painterly oil-painting. The Gemini image backends were
  removed (Gemini rendered the same prompt too cartoony). Set-conditioning uses OpenAI `images.edit`.
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

### PENDING BACKLOG — build in this order
**Latest commit: `3d29ae9`** (everything below is committed locally; nothing pushed). The full-5e-**DATA** work
is **DELEGATED to SEPARATE chats** (do NOT do data extraction in this build chat). There are now TWO data sources,
split by edition:
- **2024 ← open CC-BY markdown** (NEW, 2026-06-21): the owner found `downfallx/dnd-5e-srd-markdown` = the official
  **2024 SRD 5.2.1** under **CC-BY-4.0** (legally redistributable/committable). This is the missing "legal free
  dataset" item-10 flagged. A separate chat converts it → `data/srd/2024/*.json` — see the new
  `docs/SRD-2024-MARKDOWN-CONVERSION-BRIEF.md`. Headline win: complete + correct **2024 spells/spell-lists/slot
  tables** (engine currently fakes 2024 casters by borrowing 2014). SRD is a baseline only (subclasses still 1/class,
  4 backgrounds, 9 species).
- **2014 ← owner's PDFs** (the owner's books turned out to be 2014): a separate chat extracts those into
  `data/srd/2014/*.json` per `docs/PDF-RULES-EXTRACTION-BRIEF.md`. PDFs are copyrighted → that data stays
  gitignored/**LOCAL, never committed**. (The PDF brief still says "2024" internally — superseded for edition
  routing by the discovery above; the owner's PDFs feed 2014.)

**PARALLELIZATION RULE (why work is split the way it is):** the entire front-end is ONE file
(`web/frontend/Character Forge - Prototype.dc.html`), so **all front-end/UX items stay SERIAL in this build
chat** (items 3, 4, 5, 8 — two chats editing that file would collide). **Back-end/engine work parallelizes**
into its own chats (separate Python modules, no collisions). Currently delegated to parallel chats: 2024 data,
2014 data, **art engine (items 6+7 → `docs/ART-ENGINE-BRIEF.md`)**, **from-sheet ingestion (item 9 →
`docs/FROM-SHEET-INGESTION-BRIEF.md`)**. Each back-end brief documents a front-end *contract* (request/response)
so this build chat wires the small UI hook later without the two chats overlapping.

**PARALLEL CHATS LANDED (2026-06-21) — lock-in status + what the BUILD CHAT must now WIRE:**
- **Art engine (items 6+7) DONE.** Image provider is now **OpenAI `gpt-image-1.5`** (Gemini removed entirely;
  `_BACKENDS = {stub, openai}`, NO silent fallback — errors clearly if OpenAI can't deliver). `generate_portrait_set()`
  set-conditioning works (OpenAI `images.edit` on the anchor PNG → all 4 portraits stay the same person, fixes the
  gender-drift). DATA-only prompt fixes (invariant intact): a companion rides through all 4 states via **`art.companion`**;
  in-conversation now reads as actively talking; class beats no longer conjure a phantom pet. `tests/test_art.py` green;
  `build_prompt == computePrompt` byte-for-byte intact. Docs: `docs/ART-ENGINE-HANDBACK.md`. **WIRE (front-end, this chat):**
  (a) ✅ **DONE 2026-06-21** — **"✦ Generate all 4 (one consistent character)"** button in the Portrait-set panel →
  `genArtSet()` → `POST /art/set` (fills all 4 slots, folds into draft, saves; `artSetBusy` guard; 240s timeout). Per-state
  ⟳ buttons still there for single regens. (b) ✅ **DONE 2026-06-21** — bonded-creature → **`art.companion`**: `doForge`
  sets `ch.art.companion` (via `companionShortForm` — strips the name) and weaves it into `art.appearance` with `applyCompanion()`,
  a byte-for-byte mirror of the engine's `apply_companion` ("accompanied by … always at their side") → appears in all 4
  portraits, preview == generated **verified across all 4 states**. BONUS FIX: `computePrompt`'s PC-subject title helper now
  preserves hyphens (capitalize each run) to match the engine's `_title`, fixing a pre-existing invariant break for
  hyphenated species (Half-Elf/Half-Orc/High-Elf). (c) per-kind scene **labels** (①) — still TODO.
- **2024 data DONE** (339 spells + 160 slot tables, native from the CC-BY markdown, + full SRD baseline from 5e-database).
  Uncommitted. **WIRE (engine, small):** switch 3 call sites off the 2014 borrow → native 2024 per
  `docs/SRD-2024-DATA-HANDBACK.md` (`rules_mode.py`, `builder.py`, `autofill.py`). Committable items: `scripts/
  convert_srd2024_md.py` + `data/srd/2024/ATTRIBUTION.md` (needs a `.gitignore` `!` carve-out — owner's call).
- **2014 data DONE** (subclasses 12→**66**, backgrounds 1→**13**, subraces 4→**9**, feats 1→**57**). Engine reads them via
  `Ruleset('dnd5e-2014').option_lists()` → **the Forge dropdowns + Surprise rolls get richer automatically** (verify the
  UI handles the bigger lists). Local/uncommitted. **Remaining engine bits (from that chat):** #2 subrace ability bonuses
  (`builder.py` TODO, data ready); #3 feat prereqs + background choice-tools (`grants.py` ignores
  `starting_proficiency_options`); #4 Monster Manual 2014 statblock pass (big, not PC-critical → delegate). Skipped:
  Variant Human; 2014 spells = SRD subset (~319), not full PHB.

DONE since last handover update: dice **fountain** cleanse (285ea11); **house art style** (Greg Rutkowski + Tyler
Jacobson) baked into `art.py` `FIXED_TAIL` + the front-end `computePrompt` (engine == live preview); **Surprise Me
re-rollable bones concept** (83076ce) — Surprise me now rolls FREE legal bones (class/subclass/species/subspecies/
background/level) into a "Your surprise concept" panel (Re-roll / Forge-this / Discard); the AI look + stat block
only happen when you press **Forge this character** (`forgeFromConcept()`).

**>>> NEXT LIVE ITEM = item 3 below (Forge UX) — it closes the create→sheet loop. <<<**

✅ **Item 3 (Forge UX) BUILT + wired + verified live (2026-06-21), uncommitted.** `web/frontend/Character Forge
- Prototype.dc.html` runs clean (no console errors; preview MCP). What shipped this turn — **log these as locked
decisions:**
- **Confirm-before-forge gate on BOTH entry points.** The brain-dump "Forge" button (`requestForge('block')`) and
  Surprise's "Forge this character" (`requestForge('concept')`) now open a **confirm dialog** before spending a
  forge. Dialog shows a "What you'll forge" summary + the plain-English "this is the AI step, re-rolling is free,
  this isn't" note + an inline **rules-mode confirm** (Relaxed–Rule-of-Cool / Strict–by-the-book, flippable right
  there). Cancel spends nothing (verified). `confirmForge()` routes to `doForge()` (block) or `forgeFromConcept()`
  (concept). The old `forgeViaBridge()` body is now `doForge()`.
- **Forging overlay = full-screen grey-out + lock.** While `forgeBusy`, a fixed z-index-320 dark+blur scrim covers
  and locks the whole UI, with an animated **ink-scribble + quill** (`pf-scribble`/`pf-quill`/`pf-dots` keyframes)
  and copy "Forging your character… / Writing the name, personality, look and spells."
- **Stay-in-Forge + progression strip.** After a forge the app **no longer auto-jumps to Studio**; it stays in the
  Forge, sets `forgeDone`, and shows a green strip: "Forged. Take a look below. Happy with the concept? Happy with
  the portraits? → **Open the character sheet ›**" (+ dismiss). `setView`/`rollConcept`/new-forge clear `forgeDone`.
- **Library "reconnecting" state (bridge-down robustness).** `componentDidMount`→`probeBridge()` now **retries every
  4s** while the bridge is down (`bridgeRetrying`). "My creations" distinguishes: connecting/reconnecting (spinner +
  "your saved creations are safe, they'll appear automatically") vs genuine local-preview vs truly-empty — no more
  scary empty library when the bridge just isn't running.
- **5-KIND Surprise split (user decision 2026-06-21, BUILT + verified).** The Forge's binary "Monster/NPC vs PC"
  toggle is replaced by a **5-way kind picker matching the My-creations buckets: Player / NPC / Monster / Companion /
  Pet** (`state.forgeKind`, `pickForgeKind()` → `setKind()`; render array `forgeKinds`). **Surprise me now rolls a
  tailored recipe per kind** (`this.SURPRISE` curated lists + `rollConcept()`/`conceptLine()`/`forgeFromConcept()`
  all branch 5 ways): PC = class/subclass/species/bg/level (existing); Monster = type/size/CR (existing); **NPC =
  role-based** (ancestry + occupation + power tier + personality hook, e.g. "Seasoned Halfling thief · fiercely
  loyal"); Companion = beast + size + temperament; Pet = familiar + quirk. Engineering call: curated JS lists now
  (instant/free, like the monster roll); can enrich from 2024 SRD `animals.md` later. All 5 verified live.
- **Confirm dialog reminder + edition (stage-2 fix, BUILT + verified 2026-06-21):** the confirm dialog now carries a
  one-line Relaxed/Strict reminder that **names the selected edition** ("…enforces legal spells, counts and gear for
  D&D 5e (2024)") — `rulesModeHint`/`editionLabel` in render, reminder `<div>` under the rules-mode buttons. Answers
  the user's "by the book — which book?" since they pick the ruleset at the top. (Verify note: the template wraps
  every `{{ }}` in `<span class="sc-interp">`, so DOM checks must NOT filter on `children.length===0`.)
- **WAY OF WORKING (user, 2026-06-21):** going **stage-by-stage through item 3, confirming each with the user**
  before moving on. Stage 1 loading overlay → **approved**. Stage 2 confirm dialog → **approved** (+ reminder added).
  Remaining to confirm: 3 progression strip · 4 library reconnecting state. Keep the handover current as we go.

1–2. (Done — see the DONE paragraph above.)
3. **Forge UX (NEXT):** add a **confirm dialog** before the token-spending forge + a **rules-mode confirm**
   (Rule-of-Cool vs by-book); while forging, **grey-out/lock** the whole UI + a loading/scribble animation;
   afterwards **STAY in the Forge** (no auto-jump) and show a progression strip *"Happy with the concept? Happy
   with the art? → go to Studio"*. Gate BOTH forge entry points behind the confirm: Surprise's
   `forgeFromConcept()` and the brain-dump `forgeViaBridge()`.
   PLUS (robustness): when the bridge is DOWN, "My creations" looks empty + scary — show a **"reconnecting…"**
   state instead of an empty library (saved files are safe on disk in `output/characters/`; the bridge just
   wasn't running). Distinguish "bridge offline" from "no creations".
3. **Forge UX:** while forging, **grey-out/lock** the whole UI + loading animation; afterwards **STAY in the
   Forge** (no auto-jump to Studio) and show a progression strip: *"Happy with the concept? Happy with the
   art?" → go to Studio*.
4. **Examples redesign:** **vertical** list (not horizontal scroll), grouped **Monster / NPC / Player
   characters**, with a clear **active highlight** so the user always knows where they are.
5. **Portrait controls:** surface **"Generate all"** + **individual** per-state generate (currently hidden).
6. **[DELEGATED → `docs/ART-ENGINE-BRIEF.md`]** **Portrait-set consistency (the gender-drift fix):** generate as a **SET** — first (at-rest) = reference,
   condition the other 3 on that image (Gemini 2.5-flash is multimodal/image-input) + lock a tight appearance
   incl. explicit gender. Regenerate lets the user pick which image/prompt is the anchor. Engine: `art.py`
   backend accepts a reference image + a `generate_portrait_set()`.
7. **[DELEGATED → `docs/ART-ENGINE-BRIEF.md`, same chat as item 6]** **House art style + class-aware scenes:** lock the Rutkowski/Jacobson default; make per-state beats
   **contextual by class/role** (rogue whispers, wizard confers with a familiar, barbarian roars) — extend
   `art.stateBeats`. Atmosphere/depth/props tied to outfit/gear/appearance/environment.
8. **Studio editing + consolidation:** show & edit the **spell list** (cantrips/prepared by level), **actions**,
   **reactions** (validate via `rules_mode`); **LOCK the category (`kind`)** in Studio (set at creation only —
   shouldn't flip PC↔monster mid-edit); **consolidate** the scattered edit fields (category/type/alignment/etc).
9. **[DELEGATED → `docs/FROM-SHEET-INGESTION-BRIEF.md`]** **From-sheet upload:** real upload of a Word/PDF sheet → engine reads it
   (`autofill` already accepts `docx_text`) → character. Bridge endpoint `POST /forge/sheet` + docx/pdf text
   extraction (back-end chat); the small **front-end file input is the build chat's** (don't double-edit the
   .dc.html). Decided: AI-upload v1 now; the structured spreadsheet/CSV template + deterministic parser is a
   **separate later chat** (batch + export round-trip).
10. **DATA decision — fuller options:** SRD ships only 1 subclass/class, ~4 subraces, 1 background (2014) /
    4 (2024). **2024 does NOT add subclasses or dwarf subraces** (same limit; only more backgrounds).
    **UPDATE 2026-06-21:** a **legal free 2024 dataset now exists** — the CC-BY `downfallx/dnd-5e-srd-markdown`
    (SRD 5.2.1), being converted into `data/srd/2024/` per `docs/SRD-2024-MARKDOWN-CONVERSION-BRIEF.md`. It gives
    complete 2024 spells/slots + a committable baseline, but is still SRD-limited (1 subclass/class etc.) — fuller
    subclass/background libraries still need the owner's PDFs (the PDF brief, → 2014). Beyond-SRD route remains
    **homebrew/enrichment data packs** (`source`-tagged) + a pack loader. Until full, consider a small UI note
    "SRD options only" so sparse dropdowns don't confuse.
12. **Per-KIND portrait scenes (user request 2026-06-21).** The four portrait states currently apply to every kind,
    but they don't all fit: an NPC "probably wouldn't be battling", a pet maybe not either. **Tailor the four scenes
    per kind** (keep 4 slots; change which scenes). Proposed: Player = at rest/in conversation/in battle/travelling
    (current); NPC = at rest/in conversation/**at their trade**/travelling; Monster = **lurking/stalking**/in battle/
    **on the prowl**; Companion = at rest/**alert·on watch**/**on the hunt**/travelling; Pet = at rest/**at play**/
    **with their keeper**/**curious·exploring**. **Belongs in the ART-ENGINE chat** (scene beats = art prompts; it
    already owns `art.stateBeats` + the 4 fixed state keys) — fold per-kind scene sets into `docs/ART-ENGINE-BRIEF.md`;
    the **front-end just relabels the 4 slots per kind** (this build chat, cosmetic). Keep the 4 state KEYS fixed to
    avoid a contract change. Awaiting user sign-off on the proposed sets.
13. **Per-KIND flavour fields (user request 2026-06-21).** The "Add some flavour" panel (age/experience · where
    from · standout memory) suits Player/NPC but not others (a monster has no "standard memory"). **Swap the fields
    per kind.** Proposed: Player/NPC = current; Monster = its nature/origin · its lair or territory · what it hungers
    for; Companion = how you two met · a favourite moment together · a quirk/habit; Pet = where you found it · its
    favourite thing · a quirk. Front-end only (this chat): adapt the flavour panel + `flavourText()` per `forgeKind`.
    **BUILT + verified 2026-06-21:** `flavourFieldDefs(kind)` + data-driven `flavourFields` render array + `<sc-for>`
    in the flavour panel; `flavourText()` reads the current kind's fields. Verified all 5 kinds show the right
    nudges and weave into `/forge` `details`.
13b. **Linked companion/pet (user request 2026-06-21, extends 13).** Player/NPC flavour gains a **"A companion or
    pet?"** free-text line (e.g. "Grey, a half-blind dire wolf"). Two jobs: (a) **weave it into the owner's forge**
    so the companion features in their story + art (esp. at-rest/travelling); (b) **springboard** — after the owner
    forges, the progression strip shows a second button **"Forge <companion> too →"** that seeds a NEW creation
    pre-filled: kind=Companion (guess Pet from words like "familiar/pet", switchable), description from the note,
    **inherited world/art-style/tone from the owner**, and "belongs to <owner>". They are **linked** (store owner↔
    companion ref, e.g. additive-optional `companionOf:{id,name}` on the companion + show "↳ <owner>'s companion" in
    the library). Build in 2 parts: P1 = the flavour line + prompt weave (with item 13, this chat); P2 = the
    springboard + link. Bonus (later, via art-engine): use the owner's portrait as a reference image so the pair
    match. **REFINED 2026-06-21 → see `docs/COMPANIONS-PETS-FAMILIARS-PACTS.md`:** the "bonded creature" field is a
    **dropdown — None / Companion / Pet / Familiar** (not free-guess). Familiar = magic (Find Familiar), caster-only,
    maps to `pet`+magical tag; Companion = a fighting beast ally (`companion`); Pet = flavour (`pet`). Awaiting
    sign-off on the 4 open questions in that doc (dropdown set · gate Familiar to casters · pact v1 scope · oaths).
13c. **Warlock PACTS / patron pop-out (user request 2026-06-21) — see `docs/COMPANIONS-PETS-FAMILIARS-PACTS.md`.**
    A warlock's pact is NOT a creature: it's their patron (Fiend/Archfey/Great Old One/…) + boon (Chain/Blade/Tome).
    When a warlock is chosen OR rolled in the randomizer, surface a **"Pact & patron" flavour pop-out**; Pact of the
    Chain → suggests a Familiar (ties to 13b). Patron data: SRD has **Fiend only** → v1 likely free-text/short list
    until the data chats land more. Paladin oath / cleric deity get a lighter "who they serve" note (later).
    **SIGN-OFF 2026-06-21 ("Yes please"):** dropdown None/Companion/Pet/Familiar = yes; Familiar = soft hint not
    hard-gate; warlock pop-out v1 = patron+boon (short list/free-text until data); oaths/deities later.
    **P1 BUILT + verified 2026-06-21:** the bonded-creature **dropdown (None/Companion/Pet/Familiar) + description +
    caster hint** live on Player/NPC flavour; woven into `/forge` details ("They have a magical familiar: …"). The
    template already shows "After forging you'll be able to make this <noun> into its own linked character."
    **P2 Task 1 BUILT + verified 2026-06-21:** the post-forge **"Forge <name> too →"** springboard. `doForge` captures
    `pendingCompanion` (type/desc/owner name+id/inherited art env+style) when a PC/NPC declared a bonded creature; the
    progression strip shows the button (`companionLabel` extracts the name); `forgeCompanionFromOwner()` seeds a fresh
    Forge draft (kind: Companion→`companion`, Pet/Familiar→`pet`), pre-fills the dump (incl. "of <owner>" + inherited
    world/style), stores **`companionOf:{name,id}`** on the new draft, lands in the Forge to review. Verified via instance.
    **P2 Task 2 BUILT + verified 2026-06-21 (library link):** `companionOf` is carried across the forge (the engine
    returns a fresh char → `doForge` re-attaches `this.state.draft.companionOf` onto `ch`), added to the backend
    summary (`forge/web/app.py` `_char_summary` now returns `companionOf`), and the library item shows
    "↳ <owner>'s companion/pet" (render: `hasOwner`/`ownerLine`; template under the meta line). Bridge restarted so the
    summary change is live. (One-directional link; an owner→companion back-ref list = optional later.)
    **P2 Task 3 BUILT + verified 2026-06-21 (warlock pacts, 13c):** Surprise rolling a **Warlock** also rolls a
    **patron + boon** (`SURPRISE.warlockPatrons`/`pactBoons`/`chainForms`); the concept panel shows it ("Pact of the
    Chain, serving a Great Old One"); `forgeFromConcept` weaves it into the dump; **Pact of the Chain auto-seeds a
    familiar** (`flavour.bonded=Familiar`) so the springboard offers to forge it too. Patrons are flavour (SRD ships
    Fiend only) — a richer/real patron list awaits the data chats. **P2 COMPLETE.** (Not yet built: a manual pact
    field for brain-dump warlocks — only the Surprise path triggers it today.)
11. **Standalone HTML export of the finished Codex sheet (user request 2026-06-21).** A "Download as HTML" option
    on the Codex that emits a **single self-contained `.html` file** — the parchment sheet + the four portraits
    **embedded** (base64 data-URIs, not bridge URLs) so it works offline / when shared, and you can flick through
    the images. Rationale: the print-to-PDF path doesn't reliably carry the portraits; a self-contained HTML is more
    portable. Front-end (this build chat) — serialize after the item-3 stages. (Possible engine helper: an endpoint
    that inlines the portrait PNGs as data-URIs, or do it client-side from the already-loaded images.)

---

## 11. MASTER ACTION LIST — locked 2026-06-21 (user stepping away; verify, then a FRESH chat blasts through)

⚠️ **COORDINATION (read first):** TWO chats edited `web/frontend/Character Forge - Prototype.dc.html` + `forge/web/app.py`
in parallel this session (this build chat = item 3 / 5-kind / flavour+bonded dropdown / P2-Task-1 springboard / art
wiring / input_fidelity / default-Player; the OTHER chat = P2-Task-2 library link + P2-Task-3 warlock pacts). The merged
file runs clean (no console errors), but **two chats on one file is fragile — from here, drive ALL front-end work from
ONE chat.**

**8-PACK PROGRESS (2026-06-21):** ✅ DONE+verified = ①Familiars group (incl. `bondType` in `_char_summary` +
`applyCreatureGuard`/bondType carried through `doForge`) · ③from-sheet file picker (`pickSheet`/`onSheetFile` →
`POST /forge/sheet` → Studio; hidden `#ff-sheet-input`) · ④examples redesign (vertical, `starterGroups` by 5 kinds,
active "● in view" highlight) · ⑤Codex HTML export (`downloadHtml()`/`fetchDataUrl()` → self-contained `.html` with
all 4 portraits as data-URIs; "Download as HTML" button on Codex) · ⑦thin-creature non-humanoid guard · ⑧warlock
Pact&patron flavour line · ②per-kind portrait scenes (`this.SCENE` labels+beats, `sceneLabel`/`applyKindBeats` →
art.stateBeats DATA; **byte-for-byte preview==generated VERIFIED for npc/monster/pet**) · ⑥Studio FULL edit
(`setListItem`/`addListItem`/`removeListItem` → Actions + Reactions editors; `setSpellList` → cantrips/prepared
comma-list editor for casters; **Category LOCKED** = display-only `kindLockLabel`; abilities render now guarded
`const abil = d.abilities||{}` so a no-abilities draft can't crash). **8-PACK COMPLETE — all verified.** Spell
editing is a lightweight comma-list (not a per-level picker — flagged for possible later upgrade).
**REVIEW SIGN-OFF (user, 2026-06-21):** ②portrait scenes = good as-is · ①Familiars own group + link = good · ④⑤③
smaller features = all good · ⑥spell editing comma-list = fine for now BUT **FOLLOW-UP REQUESTED: a richer per-level
spell picker** (dropdowns from the ruleset's `class_spell_list`/optionLists, grouped by level) for a later round.
Everything else approved as-is; user to test live next.
**BRIDGE RECONNECT UI (BUILT+verified 2026-06-21):** top bar now has a **port input + "↻ Reconnect"** (spinner) →
`refreshBridge()` saves `forgeBridgeUrl=http://localhost:<port>` to localStorage + re-probes; `bridgeBusy` drives the
spinner; pill shows ↻ Reconnecting / ● live / ○ Not connected. **Diagnosed + FIXED the "Surprise→Forge only rolls a
concept" bug:** `requestForge`/`doForge` used to **silently `setView('studio')` when bridge was down** — now they
show a clear "engine isn't connected — Reconnect" warning. (Root cause was the wedged port-5000 process; the forge
code itself is correct — verified the full concept→forge path fires when connected.) Also `forge/web/app.py` port is
now env-configurable (`FORGE_PORT`, default 5000); a 5001 bridge config added to `.claude/launch.json`.
**item ② Codex/Forge image management (user signed off: Phase A now, Phase B via brief; uploads = embedded data-URI).**
**Phase A BUILT+verified 2026-06-21 (front-end):** Codex **"✎ Add / replace image"** → routes to Forge
(`onCodexEditImage`); per-portrait **"⤒ Upload"** (`pickPortraitUpload`/`onPortraitFile` → embedded data-URI into
`draft.portraits[state]`, per-slot so originals are safe; shared hidden `#ff-portrait-input`; saves via
`saveCharacter`). Regen already existed (per-state ↻ + Generate-all). **Phase B = DELEGATED to the art chat →
`docs/CUSTOM-SCENARIO-PORTRAITS-BRIEF.md`:** allow custom-scenario portraits beyond `FIXED_PORTRAIT_STATES`
(relax the /art state guard; carry the scenario as `art.stateBeats[customKey]` DATA so build_prompt==computePrompt
holds; keep the 4 fixed + set-conditioning). Front-end "+ Add scenario" wiring is the build chat's once the engine lands.
**PORT PROBLEM — FIXED PROPERLY (2026-06-27).** Orphaned bridge processes kept grabbing ports the agent can't kill,
so the front-end (defaulting to a dead :5000) hung "reconnecting forever". Fix (front-end, `web/frontend/...dc.html`):
(a) `probeBridge()` now **auto-discovers** the engine — probes candidate ports **in parallel** (`candidateBases()` =
saved/?bridge override, then :5000/:5001/:5002) via `Promise.any`, connects to the first that answers (a wedged :5000
can't stall it), saves the winner, retries every 4s while none respond; `bridgeBase()` prefers the discovered
`_activeBase`. (b) `resolveUrl()` **heals any localhost/127.0.0.1 link to the live bridge** → baked-in `:5000` image
URLs auto-rewrite to whatever port won, fixing the broken-portrait previews. Verified: cleared saved port → app
auto-found :5001, loaded 14 saved creations, healed a `:5000` image URL → `:5001`. The manual port box + ↻ Reconnect
remain as an override (blank = re-run auto-discovery). **COMPANION ENVIRONMENT inheritance FIXED:**
`forgeCompanionFromOwner` no longer copies the owner's literal `art.environment` onto the creature (a badger got
Borin's "magical sparks from his hands"); now inherits **style only**, references the owner's world as background in
the dump, and instructs the forge to give the creature **its own** fitting scene. Verified (seed env = none).
**STUDIO "forge a bonded creature from the CURRENT character" BUILT+verified (2026-06-27, user-confirmed):** when a
PC/NPC is loaded, the Studio shows a **"Bonded creatures: ＋ Companion / ＋ Pet / ＋ Familiar"** row
(`forgeBondedForCurrent(type)`) → seeds a linked creation (kind, `bondType`, `companionOf` from the loaded char,
style inherited, dump pre-filled "the <type> of <name>") → lands in the Forge to amend + forge. Springboard "Forge X
too" deliberately LEFT as set-up-only (user choice). **SERVER-CONTROL LAUNCHER BUILT (2026-06-27, user chose "double-click console"):** `launch_forge.py` + `Forge.bat`
at repo root. Double-click `Forge.bat` → frees ports 5000+8000 (netstat+taskkill, kills orphaned processes — the
root cause of the wedged-port pain), starts engine (`FORGE_PORT` env, default 5000) + page (http.server 8000), opens
the browser, then a console menu: **[R]estart · [O]pen browser · [S]tatus · [Q]uit** (Q/close stops both cleanly →
no orphans). Child output → `output/launcher-engine.log` / `launcher-page.log`. Windows-only (netstat/taskkill).
Syntax-checked (`py_compile` OK); not run here (would kill the preview servers). This is the user's self-serve
server control so the agent doesn't have to manage them.
**LAUNCHER v2 FIX (2026-06-27):** first run hit two issues — (1) the `Forge.bat` `title D&D…` line broke on the `&`
(cmd separator) → title is now "Character Forge - launcher"; (2) PIDs 58244 & 46364 hold **:5000** and are
**unkillable even by the user** ("access denied" — clear only on reboot). So the launcher now **picks a FREE port**
(`port_is_free` socket-bind test + `pick_port` over [5000,5001,5002,5003] engine / [8000,8001,8002] page), **routes
around** the wedged :5000, and **opens the browser straight at `…/<sheet>?bridge=http://localhost:<enginePort>`** so
it connects regardless of which port won. Until a reboot frees :5000 the engine just runs on :5001.
**LAUNCHER v3 — cheesy text-RPG reskin (2026-06-27, user request):** `launch_forge.py` now prints an ASCII anvil
banner, copper/gold ANSI colours (VT enabled via `ctypes.SetConsoleMode`), a random tavern quip, and an in-character
menu ([R] Reforge · [O] Open portal · [S] Scry status · [Q] Rest at the inn). Purely cosmetic — port-routing/process
logic unchanged. Verified renders + `py_compile` OK.
**CODEX HTML EXPORT → now INTERACTIVE (2026-06-27, user request).** `downloadHtml()` rebuilt: the offline `.html` now
(a) **opens on the currently-viewed portrait** (`startIdx` from `portraitIndex`, fixing "downloaded on Travelling, got
At rest"), (b) is a **carousel** (4 thumbnails fill from an embedded `FF` data-URI array; clicking flips the sheet's
`#ffMain` image), (c) has a **click-to-zoom lightbox** (`#ffLight`, ‹ ›/arrow-key nav, click/Esc to close) via a small
inline `<script>` (written as `'<'+'script>'` to not break the .dc.html). Verified by capturing the generated doc:
script+lightbox+4 thumbs present, starts on the viewed state, ~1 image duplicated (sheet img + FF array). **Issue: the
Studio "forge a bonded creature" buttons "can't be seen" → diagnosed as almost-certainly BROWSER CACHE** (verified the
buttons DO render for a PC/NPC in the Studio); user to hard-refresh (Ctrl+Shift+R). Possible later add: an "edit this
character's pet" shortcut from the owner (currently you edit the pet by opening it from My creations).
**OWNER→CREATURE LINK now VISIBLE (2026-06-27, user request) — BUILT+verified.** A character's bonded creatures are
**derived from the library** by `companionOf` (`ownedCreatures` in render — no reverse-link to maintain). Shown in:
(a) the **Studio** "Bonded creatures" row — each existing creature listed with an **"Open / edit"** button
(`loadServer` → the edit-pet shortcut) above the ＋ add buttons; (b) the **Codex** sheet — a "Bonded creatures"
section with clickable "↳ <name> · <noun>" chips. Works for PC + NPC. Verified with a mock (Borlag NPC + Cringe
familiar).
**(D) IMAGE FIDELITY — DONE (2026-06-27, user chose "Option 1 now (by description)").** Prompt-conditioning route:
the owner's `art.appearance` is woven into the creature's portrait as a small background figure. Wiring:
`masterShortForm(desc)` (trims to ≤180 chars on a word boundary, "…") + `applyMaster(ch)` (idempotent; appends
"With their master, a small background figure further behind, looking like: <owner appearance>" to the creature's
`art.appearance`, smart sentence-join so no double period). Seeded as `masterDesc` in **both** spawn paths —
`forgeCompanionFromOwner` (springboard, uses `pc.appearance`, now carried in `pendingCompanion`) and
`forgeBondedForCurrent` (Studio buttons, uses the loaded owner's `art.appearance`); carried across the bridge in
`doForge` (`ch.masterDesc` + `this.applyMaster(ch)` alongside applyCompanion/applyCreatureGuard/applyKindBeats).
**Byte-for-byte safe** — applyMaster mutates `art.appearance` DATA after the bridge returns, prompt-assembly
unchanged, so `computePrompt == build_prompt` still holds. Verified by extracting the real source methods and running
them (trim/word-boundary/ellipsis, idempotency, empty-master no-op, blank-appearance, no double period all pass);
page compiles with zero console errors. (Option 2 — image-conditioning via OpenAI `images.edit` reference for higher
likeness — remains the later upgrade if Option 1's likeness isn't enough; needs the art-engine chat.)
**(C) HTML DOWNLOAD LINKS BOTH WAYS — DONE (2026-06-27, user: "Yes - add it, and the owner to the
creature/pet/companion").** `linkedCharsForDownload()` gathers the owner (if this char is a creature, via
`companionOf` → full record from `/character/<id>`) AND any owned creatures (serverChars filtered by `companionOf`,
each fetched full); `charPortraitData(ch)` pulls the best portrait (at-rest→…) as a data-URI. `downloadHtml()` now
renders a "Bonded characters" section (portrait + name + relation: Owner / Companion / Pet / Familiar) embedded in
the self-contained `.html`. So an owner's download shows its creatures and a creature's download shows its owner.
**NEEDS USER RE-TEST (hard-refresh first):** forge a creature from an owner → both portraits + the master-in-
background + the bidirectional HTML download.
**(D-retro) RETRO-FIT FOR ALREADY-SAVED CREATURES — DONE (2026-06-27, user asked "how do I align Cringe now?").**
A creature forged *before* the feature has no `masterDesc`, so its portrait prompt lacks the owner. You do NOT need
to re-forge the stat block — the portrait prompt is built only from `art.appearance` (computePrompt line ~1719).
Added a one-click action in the **Forge → Portrait set** panel: when a saved creature with an owner is loaded and
its appearance doesn't yet contain the master phrase, a "Add \<owner\> to the portraits" button appears
(`showMasterApply` gate). `includeMasterFromOwner()` fetches the owner's full record from `/character/<id>` (falls
back to name match in serverChars), runs `masterShortForm`+`applyMaster` on the loaded draft, and tells the user to
press "Generate all four". DATA-only mutation of `art.appearance` → preview == generated still holds. Gate verified
across 5 cases (saved-creature-with-owner ✓, already-has-master ✗, PC ✗, creature-no-owner ✗, companion-with-owner
✓); page compiles, no console errors. **So the answer to "regenerate Cringe":** load Cringe → Forge tab → click
"Add \<owner\> to the portraits" → "Generate all four". (Owner must exist in the library; if its appearance can't be
loaded, the button warns to open the owner once first.)
**"GENERATE ALL 4" SILENTLY DID NOTHING — DIAGNOSED + FIXED (2026-06-27).** User reported the set button did nothing
while per-slot ⟳ worked. **Diagnosis (from `output/launcher-engine.log`): zero `POST /art/set` ever reached the
bridge**, yet per-slot `POST /art` succeeded on the single-threaded Flask server (so nothing was blocking it) →
`genArtSet` returned early at its guard `if (!bridge || artSetBusy) return;`. Bridge was live (per-slot worked), so
`artSetBusy` was stuck `true`, which ALSO disables the button (`disabled="{{ artSetBusy }}"`) → clicks are no-ops.
**Root cause:** an earlier "Generate all 4" fired `/art/set` at the **dead zombie port 5000**; that fetch hung
(`api()` aborts only after the 240 000 ms timeout), the user hit ↻ Reconnect to 5001 for everything else, but the
in-flight 5000 request kept `artSetBusy=true` and the **catch surfaced no message**. Confirmed a fresh page load
shows the button **enabled** (`d:false`) — so a **hard refresh clears the stuck state**. **Fix:** `genArtSet`'s catch
now surfaces the failure as a `forgeWarnings` error (distinct message for an abort/timeout vs other errors) and tells
the user to Reconnect / regenerate one at a time — parity with `doForge`. Verified page compiles, no console errors,
button enabled. (The set REUSES the on-disk at-rest.png as the anchor and conditions the other 3 on it, so once
at-rest includes the master, the whole set stays consistent + master-bearing.)
**FORGE 502 DIAGNOSED (2026-06-27): NOT a code bug — Anthropic API credit balance depleted** ("Your credit balance is
too low… Plans & Billing"). Every PC forge 502'd for this reason (seen in `output/forge_log/`). Fix = top up Anthropic
credits / swap the key in `.env`, then Reconnect. (Images use OpenAI, unaffected.) **Error surfacing IMPROVED:**
`api()` now reads the bridge's JSON error body and `doForge` shows "Forge failed — <real reason>" instead of the
misleading "is the bridge running?".
**PROVIDER SPLIT (user decision 2026-06-27): FORGE TEXT → Gemini, IMAGES → OpenAI.** The Anthropic credit wall was
unblocked by moving the character forge to **Gemini 2.5 Flash**. `forge/llm/client.py` `LLMClient` is now
**provider-aware** (`gemini` | `anthropic`, dispatched on `config/forge_config.json` → `llm.provider`); Gemini path =
JSON mode (`response_mime_type:application/json`) + tolerant parse + repair retry (engine validates downstream).
Config now `llm.provider="gemini", model="gemini-2.5-flash"` (swap back to Anthropic = flip those two lines once
credits return). **Verified live:** direct autofill (elf ranger) + `POST /forge` via the bridge (halfling rogue) both
forge cleanly via Gemini, no 502. **Images stay OpenAI `gpt-image-1.5`** (locked — Gemini rendered the
Rutkowski/Jacobson style too cartoony). So: text=Gemini, images=OpenAI.
**ENGINE: 2024 native-data switch DONE+verified (background agent, 2026-06-21):** 3 call sites edition-threaded
(`rules_mode.py` `_repo(edition)`/`_edition_for`, `builder.py` `_resolve_spellcasting` 2024-fallback-only,
`autofill.py` `_resolve_pc_spellcasting(edition)`); 2024 wizard list=218 vs 2014=204 (native confirmed); test_ruleset/
test_art/test_rules_mode all PASS; 2014 unchanged. Agent's temp files removed. (Pre-existing `test_grants` wizard
failure still stale/out-of-scope.)

**NO TEXT ON IMAGES + EDITABLE IMAGE PROMPTS — DONE+verified (2026-06-27, user request).**
(1) **No text/writing in any portrait.** The model kept rendering speech bubbles/letters on the "In conversation"
state. Fix = appended a hard negative to the shared `FIXED_TAIL` (the locked house-style suffix): *"absolutely no
text, lettering, words, captions, speech bubbles, numbers, signage or writing of any kind anywhere in the image"*.
Applied to **both** `forge/agents/art.py` `FIXED_TAIL` AND the front-end `computePrompt()` tail string —
**byte-for-byte identical** (verified by a script comparing the two: MATCH). `tests/test_art.py` passes (build_prompt
== computePrompt, cues opt-in). Conversation demeanour is already alignment/role-flavoured via `CLASS_STATE_BEATS`
(barbarian "blunt force, jaw set"; warlock "quiet menace") — the text was a model artefact, now forbidden. Existing
saved characters pick this up automatically on the next regenerate (computePrompt rebuilds). NB: this lives in the
AUTO prompt; a user prompt-override (below) only includes it if they keep it.
(2) **Editable per-state image prompts.** The read-only "Generated prompt" panel is now an editable `<textarea>`
("Image prompt · <state>"). Edits are stored as an OVERRIDE at `draft.art.promptOverrides[<state-key>]` (persisted
with the character; per-state, so editing "In conversation" doesn't touch the others). A "↺ Reset to auto" button +
"· edited" tag appear when an override exists; reset deletes the key and reverts to the auto prompt. Front-end:
`promptOverrideFor/currentPromptText/hasPromptOverride/setPromptOverride/resetPromptOverride`; `genArt` sends
`promptOverride` (single state), `genArtSet` sends `promptOverrides` (map). Engine: `generate_portrait(...,
prompt_override=...)` uses it VERBATIM when non-empty else `build_prompt`; `generate_portrait_set(...,
prompt_overrides={state:str})` threads per-state (anchor incl.); endpoints `/art` (`promptOverride`) + `/art/set`
(`promptOverrides`) pass them through. **Invariant preserved:** with no override, both sides still use the identical
auto prompt (build_prompt == computePrompt). Verified live: textarea shows the no-text clause; edit → override held +
Reset/edited tag; reset → reverts to auto + button hides; engine uses override verbatim, blank override → auto.
**NEXT (user-stated): "on to some form of character sheet."** → CLARIFIED: user wants a **fillable / interactive
play-sheet** (track HP, mark spell slots, edit live during play), placed in a **new "Play" tab** (4th tab after
Forge/Studio/Codex). Test character provided by the user's DnD friend: **Renka of the Hidden Way** (Elf Ranger Fey
Wanderer / Druid Circle of Dreams, Neutral Good, Outlander; STR10 DEX18 CON14 INT13 WIS18 CHA12 — a multiclass
stress-test). Full outline in the chat log; forge her in-app to test.

**PLAY TAB — STAGE 1 (HP & vitals) DONE+verified (2026-06-27). Building in stages, stop after each.**
Plan: (1) HP & vitals ✓ · (2) spell slots & resources · (3) conditions + quick combat reference · (4) Short/Long
rest buttons · (5) persistence+export polish. Live state is a self-contained `draft.play` object (canonical forged
sheet untouched); maxima derive from the sheet (`hp` leading number, `pc.hitDice`). Persisted via `saveCharacter`.
Stage 1 ships: new **Play** tab (`isPlay`/`onPlay`/`tabPlay`, view==="play"); HP card (current/max, colour-coded bar
green→amber→red, damage absorbs temp HP first, Heal capped at max, Set-temp, Full); death-save pips (3 success/3
failure, click to fill/toggle, Clear); hit-dice spend/restore (from `pc.hitDice.total`). Methods: `playView()` (defaults
from char, non-mutating), `setPlay(patch)` (merge+save), `maxHp`/`hdInfo`/`abilMod`, `applyDamage`/`applyHeal`/
`setTempHpFromInput`/`fullHeal`, `setDeathSave`/`clearDeathSaves`, `spendHitDie`/`restoreHitDie`, `playRender()`
(spread into renderVals; shows empty-state prompt when no character loaded). **Verified live with Hané (PC, hp 85,
10d8):** 30 damage→55, heal 10→65, spend hit die→9/10, success pip→filled; **persisted** (`hane.json` gained the
`play` object). NB: testing left Hané's saved play state at 65/85 + 1 hd spent + 1 success — harmless demo data.
**PLAY TAB — STAGE 2 (spell slots & resources) DONE+verified (2026-06-27).** A "Spellcasting" card (casters only —
`hasSpellcasting` gate) added below the death-saves/hit-dice grid. Shows: **slot pips per level** (one row per level in
`spellcasting.slots`, `total` pips, leftmost = available, deplete from the right; tap to spend/restore; `avail/total`
count); **quick ref** (save DC · attack bonus · casting ability); **cantrips** + **prepared/known** as read-only
prettified lists; a **Reset slots** button (full rest logic = Stage 4). Live expended state in `play.slots {level:
expendedCount}` (canonical `spellcasting.slots` untouched), persisted via `saveCharacter`. Methods: `playView()`
extended with `slots`; `setSlotExpended(level,idx)` (tap pip i → set available=i / restore through i); `resetSlots()`;
`playRender()` adds `spellLevels[]`, `spellRef`, cantrip/prepared lists. **Verified live with Hané** (caster, slots
4/3/3/3/2): card shows "save DC 17 · attack +9 · WIS", exactly 15 pips, tap rightmost L1 pip → 3/4 (avail 15→14),
Reset → 15/15; **persisted** to `hane.json` `play.slots`; no console errors. (Cleared my test pollution from
hane.json afterwards so it opens fresh.)
**PLAY TAB — STAGE 3 (conditions + quick combat reference) DONE+verified (2026-06-27).** Added: (a) a **combat
quick-reference strip** (read-only chips just under the subtitle) — AC · Initiative (DEX mod) · Speed · Passive
Perception (`passivePerception(d)` parses the senses string, else 10+WIS mod) · Save DC (casters); (b) a **Conditions
card** (after the death/hit-dice grid, before spellcasting) — the 14 standard 5e conditions as toggle chips,
**Exhaustion** stepper 0–6, **Inspiration** toggle. Live state in `play.conditions[] / play.exhaustion / play.
inspiration` (canonical untouched), persisted. Methods: `playView()` extended; `CONDITIONS()`, `toggleCondition`,
`setExhaustion`, `toggleInspiration`, `passivePerception`; `playRender()` adds `combatRef[]`, `conditionChips[]` (each
with precomputed `style`), `exhaustion`, `inspiration`+`inspirationStyle`. **Verified live with Hané:** strip showed
"AC 15 · Init +4 · Speed 10 ft. · Pass. Perc 15 · Save DC 17"; toggled Poisoned (chip lit), exhaustion +2,
inspiration on; **persisted** (`play.conditions:["Poisoned"], exhaustion:2, inspiration:true`); no console errors;
test pollution cleared from hane.json.
**PLAY TAB — STAGE 4 (rests) DONE+verified (2026-06-27).** A rests bar (right of the combat-ref strip): **☾ Short
rest** = spend 1 hit die, heal `floor(faces/2)+1 + CON mod` (min 1); **☀ Long rest** = full HP, temp→0, all slots
restored, regain `max(1, floor(hdTotal/2))` hit dice, −1 exhaustion, clear death saves. A green note reports what
happened (`playRestNote`). Methods `shortRest`/`longRest`/`dieFaces`; `playRender` adds `onShortRest`/`onLongRest`/
`playRestNote`/`hasRestNote`. **Verified live with Hané** (d8 HD, CON 18): 40 dmg→45, short rest spent 1 HD (→9)
healed 9 (5+4)→54; long rest → HP 85, HD 9+5→10, slots restored, note correct; persisted; no console errors; hane.json
cleared after.
**NEXT: Stage 5 — export.** ⚠ SCOPE EXPANDED per user (2026-06-27): not just "carry play-state in" — the user wants
the **HTML download to be INTERACTIVE** (a playable offline sheet — HP/death/HD/slots/conditions/rests all working)
**plus microinteractions throughout, in BOTH the Play tab and the HTML download**. Feasible: the export already runs
inline JS (portrait carousel + lightbox), so we bundle a self-contained play tracker + `localStorage` persistence
(keyed per character; no bridge offline) + CSS transitions/hover/tap feedback. Plan = (5a) microinteraction polish on
the live Play tab (HP-bar ease, pip press/hover, chip toggles, button affordance — mostly CSS, low-risk); (5b) embed
the interactive tracker into `downloadHtml()` as a self-contained `<script>` + `localStorage`; (5c) microinteractions
in the export to match. **User chose FULL playable tracker for the download** (HP/death/HD/slots/conditions/exhaustion/
inspiration/rests, localStorage-persisted, offline). After the Play tab → the **spell picker** (advisory, planned above).

**STAGE 5a (Play-tab microinteractions) DONE+verified (2026-06-27).** Key realisation: the main app renders in
**LIGHT DOM** (the global `<style>` at line ~14 applies; only `image-slot` portrait elements use shadow DOM). Added
microinteraction utility classes to that `<style>` using props NOT set inline (no specificity fight): `.pl-tap`
(hover brighten / active scale .95), `.pl-pip` (hover scale 1.18 + glow / active .88), `.pl-chip` (hover brighten /
active scale), `.pl-card`, `.pl-pulse` keyframe; all gated behind `prefers-reduced-motion`. Applied: `.pl-pip` to
death-save + spell-slot pips (21), `.pl-chip` to condition chips + inspiration (15), `.pl-tap` to HP buttons + rests +
exhaustion steppers (8). Verified live: classes present (21/15/8), `.pl-pip:hover` rule confirmed in a live
stylesheet, full Play tab screenshot renders cleanly, no console errors. (Not yet classed: HD Spend/Restore, Reset
slots, Clear death — fold into 5c.)

**STAGE 5b + 5c (interactive offline HTML download + its microinteractions) DONE+verified (2026-06-27).** The
`.html` download is now a **fully playable, offline at-the-table sheet**. Implementation: `_playRuntime()` returns a
REAL self-contained function (HP/death/HD/slots/conditions/exhaustion/inspiration/rests — mirrors the live Play-tab
logic, no component deps) that is embedded into the export via `.toString()` (so it's syntax-checked, not a fragile
string): `playScript = "(" + this._playRuntime().toString() + ")(" + JSON.stringify(playExportData()) + ");"`.
`playExportData()` snapshots maxima (maxHp, hdTotal/die, CON mod, AC/init/speed/passive-perc, spell save DC/attack/
ability, slot totals, cantrip/prepared lists, the 14 conditions) + the current live state as `initial`. `downloadHtml`
now injects: the `.pl-*` microinteraction CSS into the doc `<style>` (5c), a "Live tracker" section + `<div id="ffPlay">`
into the body, and `playScript` as a 2nd `<script>`. The offline tracker **persists to `localStorage`** keyed
`ff-play-<charId>` (no bridge needed; per device). **Verified:** app compiles (runtime syntax OK); extracted the real
runtime from source + ran it isolated — renders HP/Spellcasting/Conditions, 6 death + 3 slot pips, 15 chips; 10 damage
28→18; condition toggle → saved; **localStorage save + reload both work** (reopened with Poisoned + curHp 18 from
storage); no console errors; test key + host cleaned up. **THE PLAY TAB FEATURE IS COMPLETE (Stages 1–5).**

**DOWNLOAD HTML — TABBED + RENAMED (2026-06-27, user request).** User decisions: rename "Live tracker" → **"At the
Table"**; put it on its own **tab**; **2 tabs** ("Character Sheet" · "At the Table"); portrait selection stays the
existing Codex-style carousel (thumbnails flip the sheet image + lightbox zoom); sheet image **stays in sync** with the
picked portrait (already the behaviour). Built in `downloadHtml`: a two-button tab bar (`fftab-sheet`/`fftab-table`,
Cinzel, copper active underline, `.fftab:hover` brighten) + `ffTab(n)` toggle script (shows/hides `#ffTab-sheet`
[clone+viewer+bonded] vs `#ffTab-table` [the `playSection`], defaults to sheet); tracker `<h2>` now "At the Table".
**Verified by intercepting the REAL generated download** (monkeypatched `URL.createObjectURL`, read the blob): 40 KB
doc contains the tab bar, both tab divs, `#ffPlay`, "At the Table" heading, `ffTab()`+`ffTab('sheet')` init, the play
runtime; "Live tracker" gone. Then loaded the actual doc in an iframe: Sheet shown first, clicking "At the Table"
reveals the tracker (HP + 21 pips) and hides the Sheet — tab switching works; no console errors.

**DOWNLOAD — CODEX-STYLE PORTRAIT SWITCHING ADDED (2026-06-27, user request).** User wanted the bottom thumbnails
KEPT *and* the same on-portrait switching the Codex has (‹ › arrows over the image + dots beneath). Those were
`no-print` and stripped from the clone, so the download only had the bottom thumbnails. Fix in `downloadHtml`: after
tagging `#ffMain`, inject into the cloned sheet's portrait wrapper — two `.ff-arrow` buttons (parchment circles, copper
glyph, `onclick="ffShow(cur±1)"`), a `.ff-dot` row beneath (clickable, `ffShow(i)`, active = #9a4f25 / idle = #cab792),
and an `id="ffSheetLabel"` on the codex caption. Extended `ffShow()` to also update `#ffSheetLabel` text and the
`.ff-dot` active colours (alongside the existing main img / lightbox / thumbnail sync). Added `.ff-arrow:hover` /
`.ff-dot:hover` CSS. Injection runs AFTER the no-print strip so it isn't removed; only when `gallery.length > 1`.
**Verified on the REAL generated download (Renka, 4 portraits, 12 MB doc):** capture has `#ffMain`, 2 arrows, 4 dots,
`ffSheetLabel`, 4 thumbnails kept; loaded in an iframe — arrows + dots + thumbnails all switch the portrait (src
changes), the caption follows (At rest→In conversation→In battle→Travelling), and the active dot turns copper
(`rgb(154,79,37)`); no console errors. NB: discovered `hane.json` has empty `portraits` (PNGs exist on disk but URLs
were never saved) so Hané's Codex shows the drop-slot — use Renka/Borin/Tasslehoff (which have portrait URLs) to test
the download.

**SPELL PICKER — DONE+verified (2026-06-27, user request: "spells and cantrips and anything in relation").** Advisory,
in the Studio. **Engine (needs bridge restart):** `forge/engine/rules_mode.py` `class_spells_detailed(class, edition)`
→ `[{index,name,level}]` sorted by (level,name); new `GET /spells?class=&level=&ruleset=&str=&dex=&con=&int=&wis=&cha=`
endpoint (`forge/web/app.py`) → `{spells, limits, edition}`; computes the casting-ability mod from the passed scores +
`CASTER_RULES[class].ability` so prepared-count is right. **Front-end (Studio spell block):** "✨ Pick from spell
list" button → `openSpellPicker()` fetches via the bridge using draft `pc.class`/`pc.level`/`abilities`/ruleset; panel
shows a search box, live counts ("Cantrips x/limit · Known|Prepared y/limit", turns amber + "over the by-the-book
limit — fine in Relaxed" when exceeded — ADVISORY, never blocks), spells grouped by level (Cantrips, Level 1…),
tap-to-toggle chips (picked = copper) writing to `draft.spellcasting.cantrips` (level-0) / `.prepared` (leveled);
"Done" closes. The old comma-separated boxes stay as a fallback. Methods: `openSpellPicker`/`closeSpellPicker`/
`setSpellSearch`/`toggleSpellPick`/`spellPickerRender`. **Verified:** endpoint via Flask test-client (wizard 204
spells/prepared 8/4 cantrips; ranger known 4; fighter→null) AND live against a fresh bridge on :5002 (5000 zombie,
5001=user's old bridge) — picker loaded Renka's ranger list grouped by level, "Known 6/6", toggling Alarm → "Known
7/6" + over-note + copper highlight + added to `spellcasting.prepared`, search "animal" filtered to Animal Friendship/
Messenger, Done closed it; no console errors. NB toggle does NOT auto-save (draft only, like the other Studio edits).

**SRD DATA REBUILD — DELEGATED to a separate chat (brief written 2026-06-27).** User asked to rebuild/complete the
SRD spell/monster/etc data for 2014 + 2024 from online resources. Scope decision: **official SRD only** (CC-BY/OGL,
shareable) — NOT copyrighted beyond-SRD, NO fan-wiki scraping. Wrote `docs/SRD-DATA-REBUILD-BRIEF.md` (self-contained
for a fresh chat). **Audited current state:** 2014 rich (319 spells / 334 monsters / 66 subclasses); **2024 thin —
monsters = 3 (the big gap, should be ~300+)**, plus thinner backgrounds/feats/subclasses (some SRD-inherent — verify
vs SRD 5.2.1, don't pad). Legal sources: SRD 5.1 (CC-BY), SRD 5.2.1 (CC-BY), 5e-bits/5e-database (MIT), downfallx
markdown (CC-BY). Brief = DATA-ONLY, match the 2014 JSON schema + `srd_repository._FILES` names exactly, keep
ATTRIBUTION.md, validate via the repo loader + existing tests. (This is the data-context reason the earlier "missing
cantrips" came up: beyond-SRD spells aren't legally includable; I was wrong to list specific non-SRD spell names from
training knowledge as if authoritative — corrected with the user.)

**IMAGE FIDELITY OPTION 2 — verified NOT done (sub-agent, 2026-06-27).** Only Option 1 (by-description, `masterDesc`/
`applyMaster`) exists. The `images.edit` `reference_image` path in `openai_backend` always uses the creature's OWN
at-rest anchor, never the owner's portrait. To add Option 2: pass the owner's at-rest PNG as a SECOND reference (multi-
image `images.edit`) with a two-subject instruction; server can resolve the owner PNG from `companionOf.id` (no new
request param). Threads `master_image` through `openai_backend`/`generate_portrait`/`generate_portrait_set` + `/art` +
`/art/set`. Scoped, deferred — build when the user wants higher likeness than the by-description version.

**PARTY TAB — DONE+verified (2026-06-27, user request #1).** New 6th top-level tab **"Party"** (Forge/Studio/Codex/
Play/Party). Shows every owner that has bonded creatures as a **team card**: owner header (avatar = at-rest portrait
bg over accent colour + kind glyph fallback, name, meta = kind · level · HP) + a row of member chips (each: avatar,
name, bondType/CR · HP), member count, all click-to-open (→ loads the char into Studio via `teamOpen`). Teams computed
in `renderVals` from `serverChars` grouped by `companionOf` (reuses `glyphFor`/`metaLabel`/`kindLabelFor`/`levelOf`);
portrait bg built from `bridgeBase()+/art/<id>/at-rest.png` (accent shows if PNG missing). Empty-state messaging.
Render vals: `isParty`/`onParty`/`tabParty`/`teams`/`partyEmpty`/`partyEmptyMsg`. **Engine:** added `hp`+`ac` to
`_char_summary` (app.py) so the quick-stats can show HP — **needs bridge restart**. **Verified live (fresh bridge
:5002 w/ new code):** 2 teams rendered — Borlag (NPC · HP 48) → Cringe (Pet · HP 19); Casimir (Player character ·
Level 4 · HP 31) → Soot and Ember (Pet · HP 7); clicking a member opened it in Studio; no console errors. NB the page
auto-discovered the user's OLD :5001 bridge at first (no hp in its summary) — confirms HP needs the restart; pointing
it at :5002 showed HP correctly. (#3 done above; remaining: #2 fresh-take, #4 Hané portrait backfill, #5 housekeeping.)

**FUTURE IDEA (user, 2026-06-27):** manual **team assembly** — add an existing character as a member/companion/pet of
another (build teams by hand, not only by forging a linked creature) — PLUS **separate HTML/print export for a whole
team/party** (one document for the group). Extends `companionOf` + the Party tab. Logged, not scheduled.

**#4 HANÉ PORTRAIT BACKFILL — DONE (2026-06-27).** `hane.json` had empty `portraits` though the 4 PNGs existed on
disk. Ran a one-off: set `portraits[state] = {imageUrl: http://localhost:5000/art/hane/<state>.png, prompt:
build_prompt(...), seed:null}` for all 4. Hané's Codex/download now show portraits (front-end heals the localhost port).

**#2 FRESH-TAKE ROOTING — DONE (2026-06-27).** Behaviour was already correct (per-slot `/art` roots non-at-rest to the
at-rest anchor; at-rest has no anchor → regenerates fresh). Made it EXPLICIT in the UI per the user's model ("fresh
take only on the root (at-rest); the rest branch from it"): the At-rest slot's button now reads **"✦ Fresh take"** /
"✦ Generate root" with a tooltip explaining the others branch from it; the other states' buttons keep "Regenerate"
with a tooltip "matches the At-rest root"; the Generate-all note now explains At-rest is the base (do a Fresh take then
Generate all 4 for a new look). `portraits.forEach` sets `isAnchor`/`genTitle`/`genLabel`. Front-end only, compiles clean.

**#3 IMAGE FIDELITY OPTION 2 (reference-image likeness) — BUILT+verified (2026-06-27).** The owner now appears in a
creature's portrait by REFERENCE IMAGE (visual likeness), not just by description. Engine: `openai_backend(...,
master_image=)` builds a multi-image `images.edit` — two-subject instruction when both the creature anchor AND owner
image are present ("Image 1 = main subject keep identical; Image 2 = master, render as a small distant background
figure resembling them"), owner-only instruction for a fresh anchor; `generate_portrait`/`generate_portrait_set` thread
`master_image`; `stub_backend` accepts+ignores it. `app.py`: `_master_image_for(character)` resolves the owner's
at-rest PNG from `companionOf.id` (no new request param; opt out with body `master:false`), passed by `/art` + `/art/set`.
**Automatic** whenever a creature has an owner with an at-rest portrait; falls back to Option-1 description otherwise.
Verified: syntax OK; `master_image` threads via stub through `generate_portrait`/`_set`; Flask test-client `/art` for
Cringe passed BOTH `reference_image` (anchor) + `master_image` (Borlag's portrait); `test_art`/`test_ruleset`/
`test_rules_mode` all pass (fixed the test's `spy` stub to accept `master_image`). Real two-image edit visual quality
is for the user to judge live. NO front-end change needed (server resolves from `companionOf`). **Remaining: #5
housekeeping.**

**MULTICLASS / LEVELLING / EQUIPMENT-FIDELITY REVIEW (user, 2026-06-27).** User asked: is multiclass in? can you
level in the Codex? Tasslehoff's equipment isn't pulling into Studio/Codex. **Findings:** (1) **multiclass = NOT
done** (deferred, single-class); (2) **no levelling anywhere** — Studio PC editor changes class/species/background/
skills via `setPcFields` but **nothing re-derives** (local only), and there's **no Level control**; Codex is display-
only; (3) **equipment WAS retained** (`tasslehoff-burrfoot.json` pc.equipment has 12 items, AI-generated — his dump
gave no items) and **renders on the Codex**, but the **Studio had no equipment editor** (the real gap), so it felt
lost + uncorrectable. Root insight: structured concept-sheet fields are honoured exactly, but free-form gear went
through the AI with no edit path. User chose to build all four fixes.

**EQUIPMENT FIDELITY — #1 + #2 DONE+verified (2026-06-27, front-end only).**
**#1 Studio equipment editor:** new "Equipment & coin" section in the Studio PC block (only when `char.isPc`) — edit/
add/remove items + the five currency boxes; methods `setPcEquip`/`addPcEquip`/`removePcEquip`/`setPcCurrency`; render
`char.pcEquipItems`/`pcCoinFields`/`onAddPcEquip`. **Verified live (Hané example, no bridge):** renamed an item +
added one → Codex reflected both ("Gnarled Oak Staff", "New item"); no console errors. Lets you correct any AI drift.
**#2 Concept-sheet equipment field:** new "Equipment / gear" box (`conceptSheet.equipment`), honoured EXACTLY at forge
(deterministic `pc.equipment` override in `doForge` via `opts.equipOverride`, gated on `ch.pc`), woven into
`composeConceptDump`, and picked up by **paste-to-parse** (`parseOutline` now also matches an Equipment/Gear/Inventory/
Signature-items section; `autofillFromNarrative` fills it). **Verified live:** pasting an "Equipment:" outline section +
Auto-fill pulled the 4 items into the box. Front-end only → hard refresh, no restart.

**#3 LEVELLING + #4 MULTICLASS — DELEGATED (engine chat).** Both are engine projects with no existing re-derive hook
(`setPcFields` doesn't re-derive). Wrote `docs/PC-PROGRESSION-MULTICLASS-BRIEF.md`: (3) a deterministic re-derive
endpoint (`POST /character/derive`) so a Level control re-derives HP/proficiency/slots/known-counts/features, reusing
`autofill`/`builder`/`derive`/`rules_mode`; (4) real multiclass (combined caster level + slots, per-class features,
mixed hit dice, multiclass proficiencies) via an additive `pc.classes[]` model that keeps single-class byte-for-byte.
Run in a separate chat.

**#5 HOUSEKEEPING — DONE locally (2026-06-27), push pending user OK.** (a) Retired the v1 prototype: `git rm`
`frontend/` (old dc.html + support/image-slot/README + engine-handoff) + `web/forge-bridge.js` + `web/fallback-data.js`
— superseded by `web/frontend/` + the Flask bridge; recoverable from history. (Left `scripts/build_fallback.py` +
stale doc mentions in ARCHITECTURE.md/web/README.md — minor.) (b) gitignored **`/Example images/`** (copyrighted
art-style reference JPGs — must NOT be committed/pushed). (c) Two clean LOCAL commits on `main`: `cd2507c` (retire) +
`97ac75a` (the whole session build). Working tree clean. **Verified before any push:** `git ls-files` has NO .pdf /
data/srd / data/local / Example images / PDFs / output (85 tracked files, all legit) — gitignore wall holds.
**`main` is 20 commits ahead of `origin/main` (public GitHub DanForgedFrameworks/DnD_forge) — NOT pushed.** Awaiting
explicit user go to push (outward-facing/public).

**⚠ DEPLOYMENT: spell picker + Party-tab HP + Option-2 likeness all need the BRIDGE RESTARTED** (new `/spells` endpoint + rules_mode helper) — relaunch
Forge.bat / [R]. Front-end picker UI is in the .dc.html (hard refresh). All prior Play-tab/download work was
front-end-only; this is the first engine change since the no-text/prompt-override/anchor batch.

**SPELL PICKER (forge/studio) — PLANNED, deferred until after the Play tab (user decision 2026-06-27).** Today spells
are FREE-TEXT only: concept-sheet "Spells" field (honoured exactly), Studio Cantrips/Prepared comma-separated boxes
(`showSpellEdit`/`setSpellList`), AI inference from the brain-dump. **No real picker.** Good news: the engine already
has the data + logic — `rules_mode.class_spell_list(cls, edition)`, `rules_mode.spell_limits(cls, level, abilityMod,
edition)`, `derive.spell_slots(...)`, and `data/srd/<edition>/5e-SRD-Spells.json`. **Plan:** (1) engine endpoint
`GET /spells?class=&level=&ability=&ruleset=` → spell list grouped by level + known/prepared/cantrip limits (engine →
needs restart); (2) Studio **browse + search + tick** picker with live counts ("Prepared 4/6"), free-text boxes kept
as fallback. **Decisions:** keys off the **primary class** (multiclass deferred); home = **Studio**; **ADVISORY (Rule
of Cool)** — show limits + warn on over-count/off-list, never block. Build AFTER Play Stages 3–5.

**TWO BUGS FIXED (2026-06-27, user report).**
**Bug 1 — single-state regenerate not rooted to the other portraits.** Per-slot `genArt`→`POST /art` used
`images.generate` (unconditioned) while `/art/set` conditions the 3 non-anchor states on the at-rest anchor via
`images.edit`. So a lone regenerate drifted (different face/build). **Fix (engine, `forge/web/app.py` `/art`):** when
`state != "at-rest"` and the at-rest PNG exists (and caller didn't pass `anchor:false`), load it and pass
`reference_image=` to `generate_portrait` — same anchor model as the set. Front-end unchanged (`anchor` defaults true).
Opt-out hook left for a future "fresh take" button (`POST /art {anchor:false}`).
**Bug 2 — renaming a character left the summary blurb showing the AI's generated name (e.g. "Skip").** The italic
`flavour` blurb is AI prose with the name baked in; editing the name field didn't touch it. **First tried** onFocus/
onBlur to capture+replace — but **React's onFocus/onBlur don't fire across DC's shadow-DOM boundary** (only onInput
does), so it silently no-op'd. **Final fix = render-time reconciliation** (no event dependency, updates LIVE as you
type): `renameInProse(text,old,new)` (whole-word, case-sensitive; replaces full old name then standalone first token;
safe no-op on blank/equal/short) + `displayFlavour(d)=renameInProse(d.flavour, d.proseName, d.name)`. Render uses
`flavour: this.displayFlavour(d)` (both Studio + Codex); `doForge` stamps `ch.proseName = ch.name`; `charPayload`
bakes the reconciled flavour + `proseName:d.name` so saves persist clean prose and re-loads stay stable. Verified:
"Skip"→"Tasslehoff Burrfoot" in prose, no-proseName→unchanged (safe), same-name→no-op, lowercase verb "skip" NOT
touched; page compiles, no console errors. **LIMITATION:** only applies to characters forged with this code (which
stamp `proseName`); a character already forged-and-renamed before this can't be auto-detected (we don't know its
original generated name) — re-forge, or (future) make `flavour` directly editable in Studio.

**⚠ DEPLOYMENT NOTE for the user:** front-end changes (.dc.html — Play tab, rename-sync, editable prompts UI,
concept sheet) need only a **hard refresh**. Engine changes (`forge/agents/art.py` no-text tail + prompt_override;
`forge/web/app.py` prompt overrides + per-slot anchor rooting) need the **bridge/engine restarted** (relaunch
Forge.bat, or [R] in the launcher) before they take effect.

**CONCEPT SHEET (structured forge input) — DONE+verified (2026-06-27, user request).** User wanted the kind of rich
outline they pasted (Renka of the Hidden Way) to be a *completable starter* that rolls into the forge. Confirmed
design via interview: **Hybrid** shape + **honour ability scores exactly**. FRONT-END ONLY (uses existing `/forge`;
the engine already composes from a brain-dump — autofill reads BRAIN DUMP/FLAVOUR NOTES/UPLOADED DOC). Built in the
Forge BRAIN-DUMP panel: a **mode toggle** "Quick brain-dump" | "Concept sheet" (`forgeInput` state, default "dump";
`inputTabStyle`). Sheet mode = structured boxes (Race/species, Class [multiclass free text], Subclass, Background,
Alignment, Level, 6 ability boxes) + one templated narrative `<textarea>` pre-seeded with `## Concept / ## Appearance
/ ## Outfit & gear / ## Environment / ## Art style / ## Key traits & signature abilities / ## Combat style`
(`CONCEPT_TEMPLATE` getter). State: `conceptSheet {species,klass,subclass,background,alignment,level,abilities{},
narrative}`. `composeConceptDump()` builds a labelled brief (fields + "Ability scores (USE THESE EXACTLY, do not
reroll): …" + narrative) → set as `draft.dump` → existing `/forge`. Entry gated through the same confirm dialog
(`requestForge("sheet")`→`confirmForge`→`forgeFromSheet`→`doForge({abilityOverride})`); the forge button is mode-aware.
**Ability scores honoured EXACTLY** by a deterministic post-forge override: `doForge(opts)` sets `ch.abilities =
{...ch.abilities, ...opts.abilityOverride}` + an info warning to check HP/DCs. **Multiclass** (Renka = Ranger/Druid):
passed verbatim in the brief; engine builds the primary class, multiclass carried as intent (full multiclass maths is
a later engine job — flagged not dropped). Verified live: toggle switches + hides the other mode (sc-if), 6 ability
boxes + class/race inputs + template render, data preserved across toggle, `composeConceptDump` output correct via the
confirm dialog ("Race / species: Elf · Class: Ranger (Fey Wanderer) / Druid… · Ability scores (USE THESE EXACTLY)…
STR 10, DEX 18…"), no console errors. **Renka is the go-to test case** — forge her via Concept sheet to validate.

**RENKA AUDIT (original outline → forged sheet, 2026-06-27).** Forged `renka-of-the-hidden-way.json`. **Carried well:**
name, ability scores EXACT (STR10 DEX18 CON14 INT13 WIS18 CHA12), custom traits verbatim ("Keeper of Forgotten
Roads", "Walker Between Worlds"), signature ability "Open the Hidden Way" (as an action), signature gear (Whisperleaf,
The Unwritten Map, Pathfinder Bells), all art/description fields + gender. **Wrong/lost:** (1) **multiclass dropped** —
Druid (Circle of Dreams) gone, pure Ranger/Fey-Wanderer; (2) **level guessed = 3** (outline gave none) which was the
ROOT CAUSE of (3) **spells mostly wrong** — at L3 a Ranger only knows L1 spells, so of her 6 suggested spells only
Speak with Animals (L1) fit; Misty Step (L2)/Pass Without Trace (L2)/Commune with Nature (L5) were impossible and the
engine back-filled its own. Minor: subspecies invented (wood-elf), Whisperleaf → "shortsword" (lost spirit-cutting),
`abilityMethod` mislabeled standard_array. **Lesson: most of the spell failure was the missing level, not bad parsing.**

**CONCEPT SHEET — PARSE BUNDLE DONE+verified (2026-06-27).** User decisions: **multiclass = flag & defer**;
**spells = honour exactly (like abilities)**. Built (FRONT-END only, hard-refresh): (1) **Paste-to-parse** —
`parseOutline(text)` extracts Race/Species, Class (+ first-paren → Subclass), Background, Alignment, Level, the six
ability scores, and a Spells/"Suggested spells" list; `autofillFromNarrative()` + a "⤴ Auto-fill boxes from this"
button above the narrative fills the boxes and reports "Pulled in: …" (overwrites detected fields, leaves narrative).
(2) **Spells field** (`conceptSheet.spells`) honoured EXACTLY: `doForge` slugifies (`slugifySpell`) → sets
`ch.spellcasting.prepared` deterministically + a note. (3) **Level-blank warning** + (4) **multiclass warning**
raised in `forgeFromSheet` (passed as `opts.preWarnings` → surfaced post-forge). (5) `abilityMethod="manual"` when
scores supplied. `composeConceptDump` now also emits "Spells (include exactly these…)". **Verified live:**
`parseOutline` on Renka's real outline returned every field correct (incl. subclass "Fey Wanderer" from the parens,
all 6 spells); the live button filled race/class/subclass/background/alignment + all 6 ability boxes + spells from one
paste; "Pulled in:" note rendered; no console errors. **So the recommended Renka flow now:** paste outline into the
narrative → ⤴ Auto-fill → set a sensible Level (e.g. 9+) → forge. **Multiclass + strict-spell-legality remain future
engine work** (deferred per user).

**8-PACK DECISIONS LOCKED (interview 2026-06-21) — build all eight in ONE chat, one file:**
1. **Familiars** = their OWN library group (split kind=pet by `bondType==="Familiar"`); **add `bondType` to
   `_char_summary`** (only `companionOf` is there now). 2. **Portrait scenes CHANGE per kind** (not just labels) — NPC
   at-their-trade not battle, pet at-play, monster lurking/stalking/on-the-prowl, companion alert/on-the-hunt; carry as
   per-kind **beat DATA** (keep the 4 state KEYS) so `build_prompt == computePrompt` holds — coordinate scene wording
   with the art engine. 3. **From-sheet** = wire the existing top-bar "⚒ Auto-fill from sheet" button to a REAL file
   picker → `POST /forge/sheet` → Studio (replaces the simulated button). 4. **Examples** = vertical list grouped by
   ALL 5 kinds + clear active highlight. 5. **Codex HTML export** = one self-contained `.html`, all 4 portraits embedded
   as data-URIs. 6. **Studio = FULL edit** — spells + actions + reactions editable, LOCK the category (kind set at
   creation only), consolidate the scattered fields. 7. **Thin-creature guard** = prepend "a small non-humanoid
   creature, …" to pet/companion/familiar prompts so the anchor stops drifting humanoid (keep regenerate). 8. **Manual
   warlock pact** = optional "Pact & patron" line in the flavour box for Player/NPC (typed warlocks, not just Surprise).

### ✅ DONE & verified this session (context)
Forge UX item 3 (confirm dialog +edition-named rules reminder, full-screen scribble lock, stay-in-Forge progression
strip, library "reconnecting" state) · 5-kind picker (Player/NPC/Monster/Companion/Pet) + per-kind Surprise recipes
(NPC role-based) · **default Forge kind = Player** · per-kind flavour fields + None/Companion/Pet/Familiar bonded
dropdown (woven into forge) · **P2 complete**: Task-1 springboard ("Forge <name> too"), Task-2 library "↳ belongs to
<owner>" link (`_char_summary` returns `companionOf`), Task-3 warlock pacts in Surprise (patron+boon, Chain auto-seeds a
familiar) · art wiring: "Generate all 4 (consistent set)" → `/art/set`, companion-in-portraits via `art.companion`,
hyphenated-species preview bug fixed · consistency: `input_fidelity:high` identity-lock + companion-description
garble fixed · `bondType` stored on springboard creations.

### ▶ TO DO — front-end (ONE build chat; single .dc.html → serial)
1. **Familiars distinct from Pets in the library** (user ask 2026-06-21): `bondType` is stored on the creature but NOT
   yet in the GET /character summary (only `companionOf` is) → add `bondType` to `_char_summary`, then a **Familiars
   group/label** (split kind=pet by `bondType==="Familiar"`). Existing Soot/Ember lack the tag (made pre-fix).
2. **Per-kind portrait scene LABELS** (①): relabel the 4 slots per kind (NPC "at their trade", pet "at play", monster
   "lurking/stalking/on the prowl"). Keep the 4 state KEYS fixed; scene wording coordinates with the art engine.
3. **From-sheet upload**: file-picker UI → `POST /forge/sheet` (back-end ready, see FROM-SHEET brief §10 contract).
4. **Examples redesign** (item 4): vertical, grouped Monster/NPC/Player, clear active highlight.
5. **Standalone HTML Codex export** (item 11): self-contained `.html`, portraits embedded as data-URIs.
6. **Studio editing + consolidation** (item 8): edit spell list/actions/reactions, LOCK kind, consolidate fields.
7. **Strengthen thin creature prompts** so familiar/pet ANCHORS land better (the "first roll = dragonborn" issue; the
   anchor has no reference, so a thin "two glowing cats" prompt wanders — richer subject framing / regenerate-anchor).
8. **Manual warlock pact field** for the brain-dump path (today only the Surprise path triggers pacts).

### ▶ TO DO — engine (separate files; build chat or delegate)
9. **Switch 2024 → native data** (3 call sites) per `docs/SRD-2024-DATA-HANDBACK.md`.
10. **2014 subrace ability bonuses** (#2, `builder.py`).  11. **2014 feat prereqs + background tool-choices** (#3, `grants.py`).
12. **Monster Manual 2014 data pass** (#4) — big; delegate.

### ◆ Decisions / housekeeping (owner's call)
13. **Commit/push**: only the 2024 converter script + `ATTRIBUTION.md` are committable (needs `.gitignore` `!` carve-out);
    everything else local. Nothing pushed yet. 14. **Retire** v1 `frontend/` + `web/forge-bridge.js` + `web/fallback-data.js`.

### 💡 Suggestions (logged, not scheduled)
15. **Linked characters / "team" view** (user idea 2026-06-21): link a familiar/companion/pet to its owner (PC or NPC)
    and group them into a **party/team you build up** — a "linked characters" list. Extends the existing `companionOf`.

### 🔁 For the user to re-test
- Re-run **"Generate all 4"** now that `input_fidelity:high` identity-lock is live — confirm the face/outfit holds across the set.

---

### Way of working with this user (CRITICAL)
Non-coder — **plain English, no jargon**. Keep turns **TIGHT** and work strictly **IN ORDER** (user explicitly
flagged that long/slow turns make them deviate). Ship one thing → verify → commit → check in. Make engineering
calls yourself; only ask genuine product choices. **Commit locally; do NOT push unless asked.** Verify the
front-end via the **Preview MCP** (`preview_start` the two launch.json servers; screenshots time out on
image-heavy views — probe the DOM with `preview_eval` instead). The .dc.html is a template engine (`<sc-if>`,
`<sc-for>`, `{{ }}`) — app logic is a React-like class IN the .dc.html (state/handlers/`render()` props);
`support.js` is just the runtime (don't edit it).
