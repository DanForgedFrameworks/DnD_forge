# Character Forge — Engine Handoff for Claude Code

This is the **contract** between the front-end (the HTML prototype, `Character Forge — Prototype.dc.html`) and the **engine** you (Claude Code) will build. The front-end already reads and writes the JSON schema below. Build the engine to **produce and consume exactly this shape** and the two halves will meet in the middle.

The product: a D&D-style character/creature forge. A user dumps stats *and* loose thoughts about how a creature looks; the engine (1) assembles a canonical statblock and (2) produces art prompts + images for four "states". Three front-end surfaces already exist — **Studio** (live-edit form), **Forge** (brain-dump → canon + art prompts), **Codex** (printable sheet with a cyclable portrait set).

---

## 1. The data contract — `Character` JSON

This is the single object the front-end loads, edits, and would POST back. Every field here is already used by the prototype.

```jsonc
{
  "id": "hane",                       // stable slug
  "schemaVersion": 1,
  "ruleset": "dnd5e-2014",            // see §4
  "kind": "monster",                  // monster | npc | creature | companion | pet | character

  // ---- Identity ----
  "name": "Hané Pathfinder",
  "size": "Medium",                   // Tiny|Small|Medium|Large|Huge|Gargantuan  (or free text)
  "type": "Wind-Kin (Path-Keeper)",   // a 5e creature type, optionally "(subtype)"; free text allowed
  "alignment": "Neutral",
  "flavour": "Hané Pathfinders are wise keepers of the wind-paths…",

  // ---- Defences ----
  "ac": "15 (aerial awareness)",      // STRING: number + optional parenthetical
  "hp": "110 (13d8 + 52)",            // STRING: average + dice formula
  "speed": "10 ft., fly 70 ft. (hover)",

  // ---- Abilities (integers) ----
  "abilities": { "STR": 10, "DEX": 18, "CON": 18, "INT": 14, "WIS": 20, "CHA": 16 },

  // ---- Proficiencies / summary lines (STRINGS today — see §3 decision) ----
  "saves": "Dex +8, Wis +9",
  "skills": "Perception +9, Insight +9, Survival +9, Acrobatics +8",
  "resist": "psychic; bludgeoning from non-magical attacks while airborne",
  "condImm": "prone (while flying), disoriented",
  "senses": "passive Perception 19",
  "languages": "Auran, Common, Wind-Sign",
  "challenge": "9 (5,000 XP)",        // "CR (XP)"; for PCs use "— (level 5)"  (Hané = CR 9, see §3.1)

  // ---- Features (ordered arrays of {name, text}) ----
  "traits":    [ { "name": "Path Stability (Aura)", "text": "Within 60 feet…" } ],
  "actions":   [ { "name": "Multiattack", "text": "The Pathfinder makes two Talon Strikes." } ],
  "reactions": [ { "name": "Course Correction", "text": "When a creature within 30 feet…" } ],

  // ---- Art brain-dump (drives image prompts) ----
  "dump": "A wise falcon-person who keeps the wind-paths…",   // freeform concept
  "art": {
    "appearance":  "Anthropomorphic falcon, slate-grey and cream plumage, amber eyes",
    "outfit":      "Layered blue travelling robes, rope belts",
    "pose":        "Hovering, wings spread",
    "environment": "Above misty island peaks, soft daylight",
    "personality": "Calm, watchful, never still",
    "style":       "Painterly high fantasy, soft natural light"
  },

  // ---- Portrait set: one image per state ----
  "portraits": {
    "at-rest":         { "prompt": "…", "imageUrl": null, "seed": null },
    "in-conversation": { "prompt": "…", "imageUrl": null, "seed": null },
    "in-battle":       { "prompt": "…", "imageUrl": null, "seed": null },
    "travelling":      { "prompt": "…", "imageUrl": null, "seed": null }
  }
}
```

### 1.1 Schema extensions (vA — non-breaking, all optional, `schemaVersion` stays 1)

Resolved per §3. All additive; absent = old behaviour.

```jsonc
  // Structured proficiencies — ENGINE SOURCE OF TRUTH when present.
  // saves/skills/senses strings above become DERIVED/read-only (computed via §2).
  "saveProfs":  ["DEX", "WIS"],
  "skillProfs": [ { "skill": "Perception", "expertise": false } ],

  // PC layer (kind:"character") — Prompt D resolved: EXTEND under these two optional keys.
  "pc": {
    "species": "elf", "subspecies": "high-elf",
    "class": "wizard", "subclass": "evocation", "level": 5, "background": "sage",
    "abilityMethod": "point_buy",
    "hitDice": { "die": "d6", "total": 5, "remaining": 5 },
    "deathSaves": { "successes": 0, "failures": 0 },
    "proficiencies": { "armor": [], "weapons": [], "tools": [] },
    "feats": [],
    "equipment": [ { "name": "Spellbook" }, { "name": "Potion of healing", "qty": 2 } ],
    "currency": { "cp": 0, "sp": 0, "ep": 0, "gp": 25, "pp": 0 },
    "personality": { "traits": [], "ideals": [], "bonds": [], "flaws": [] }
  },
  "spellcasting": {
    "ability": "int", "saveDc": 14, "attackBonus": 6,
    "slots": { "1": { "total": 4, "expended": 0 }, "2": { "total": 3, "expended": 0 } },
    "cantrips": ["fire-bolt", "light"],
    "prepared": ["magic-missile", "shield", "fireball"]
  },
  // feature items (traits/actions/reactions) gain an OPTIONAL "source" on PCs:
  //   "source": "class:Wizard" | "race:Elf" | "background:Sage" | "feat:…"
  // saveDc, attackBonus, saves/skills/initiative/PB are ENGINE-DERIVED from challenge "— (level N)"
  //   → render read-only in the PC view, same as statblock numbers.

  // Per-state character-specific scene beats — OPTIONAL, AI-authored at forge time from
  // class/alignment/race. build_prompt drops the matching beat in as the per-state ACTION
  // (keeping the generic camera/lighting + env reframe), so each character's four portraits
  // read as distinctly theirs (wizard meditates at-rest, warlock confers with a patron in-
  // conversation, rogue cases the road travelling). Absent → generic per-state action.
  "art": {
    "stateBeats": {
      "at-rest": "seated cross-legged in meditation, a half-formed spell hovering over one palm",
      "in-conversation": "…", "in-battle": "…", "travelling": "…"
    }
  },

  // Reserved (not built yet): extra named portrait states beyond the fixed four
  "portraits": { "custom": [] },

  // Origin/audit trail written by autofill
  "provenance": { /* source, model, extractedAt, … */ }
```

**Notes for the engine**
- `abilities` are integers; the front-end shows the modifier in parentheses and computes it itself, but the engine must use the same formula (§2) for any derived strings it writes into `saves`/`skills`/`senses`.
- The four portrait state keys are fixed: `at-rest`, `in-conversation`, `in-battle`, `travelling`. The front-end's image slots are keyed off these. (A `custom` array can be added later — flag if you want it now.)
- Treat the arrays as **ordered**; render order = array order.

---

## 2. Canonical 5e maths the engine should own

These are the rules the front-end deliberately does *not* hard-code, so the engine is the source of truth.

- **Ability modifier:** `floor((score − 10) / 2)`.
- **Proficiency bonus by CR** (also `ceil(level/4)+1` for PCs):

  | CR | 0–4 | 5–8 | 9–12 | 13–16 | 17–20 | 21–24 | 25–28 | 29–30 |
  |----|-----|-----|------|-------|-------|-------|-------|-------|
  | PB | +2  | +3  | +4   | +5    | +6    | +7    | +8    | +9    |

- **Saving throw:** `ability mod (+ PB if proficient)`.
- **Skill check:** `ability mod (+ PB if proficient, + 2×PB if expertise)`.
- **Passive Perception:** `10 + WIS mod (+ PB if proficient in Perception)`.
- **PC-only derived (read-only, like saves/skills):** Initiative = `DEX mod`. Spell save DC = `8 + PB + spell-ability mod`. Spell attack = `PB + spell-ability mod`. The engine WRITES `spellcasting.saveDc`/`attackBonus`; the front-end treats them (and PB/Initiative) as read-only and may recompute via these same formulas for display.
- **CR ↔ XP** (sample): CR 1/8 = 25, 1/4 = 50, 1/2 = 100, 1 = 200, 5 = 1,800, 8 = 3,900 … include the full table.
- **Ability bounds:** monsters/NPCs 1–30; point-buy PCs 8–15 pre-racial, 27-point budget. Standard array: 15,14,13,12,10,8.

---

## 3. Decisions — RESOLVED (vA)

1. **Structured proficiencies — ADOPTED.** Engine stores `saveProfs: ["DEX","WIS"]` and `skillProfs: [{skill,expertise}]` and **derives** `saves`/`skills`/`senses` via §2. When the structured fields are present those three strings are **computed/read-only** — the front-end displays them and the engine owns the maths.
2. **Validation — ADOPTED.** `validate(character) -> {ok, warnings[]}`. Warnings surface drift (e.g. the old Hané CR 8 ↔ PB +4 mismatch) rather than silently rewriting.
3. **Custom portrait states — RESERVED.** `portraits.custom` key added, not built. The four fixed keys are unchanged.
4. **Transport — local Flask.** `GET/POST /character`, `POST /forge`, `POST /art`, plus `GET /art/preview?id&state` (canonical prompt string, includes statblock cues) and `GET /art/{id}/{state}.png` (serves the image). `imageUrl` the engine writes = `http://localhost:5000/art/{id}/{state}.png`.

---

## 4. Prompts to paste into Claude Code

Copy these into Claude Code as separate tasks. They're ordered so the engine can come online incrementally while the front-end keeps evolving.

### Prompt A — Lock the schema + maths

```
You are building the backend "engine" for a D&D 5e character/creature forge.
A front-end already exists and reads/writes a Character JSON object (schema pasted
below). Your job in this task: (1) implement the canonical Character schema as a
typed model with validation, and (2) implement the 5e derivation maths
(ability modifier, proficiency bonus by CR, save/skill/passive-perception bonuses,
CR↔XP). Expose pure functions:  deriveModifiers(character),  validate(character) -> {ok, warnings[]}.
Do NOT change the field names or the four fixed portrait state keys; the front-end
depends on them exactly. Target: a small, dependency-light module + tests against the
sample "Hané Pathfinder" character.
[paste §1 schema + §2 maths here]
```

### Prompt B — The auto-fill agent (brain-dump → canon)

```
Build an agentic "auto-fill" step. Input: a user's freeform brain-dump (and optionally
an uploaded .docx character sheet or scheme-of-work). Output: a fully-populated Character
JSON matching the schema, with canonical 5e values. Requirements:
- Extract or infer: kind, size, type, alignment, AC/HP/speed, the six ability scores,
  saves/skills/resistances/immunities/senses/languages, CR (+XP), and ordered
  traits/actions/reactions written in proper 5e statblock prose.
- Use the canonical maths module (Prompt A) so derived numbers are internally consistent;
  return validate() warnings rather than silently fixing.
- Also populate the `art` brain-dump fields (appearance/outfit/pose/environment/
  personality/style) by separating "looks" from "rules" in the dump.
- AUTHOR `art.stateBeats` (§1.1) — one short character-specific action per state
  (at-rest/in-conversation/in-battle/travelling) drawn from class/alignment/race/role, so the
  four portraits are bespoke to this character. This is the only place an LLM touches the art
  prompt; build_prompt (Prompt C) consumes the beats DETERMINISTICALLY, so preview == generated.
- Keep content rules-clean: no emoji, no markdown inside statblock text.
- EMIT STRUCTURED PROFICIENCIES (§3.1): populate `saveProfs` / `skillProfs` and let the
  engine derive the `saves`/`skills`/`senses` strings — do not hand-write those strings.
- Honour the incoming `ruleset` slug; write a `provenance` block (source, model, extractedAt).
Provide a function  autofill(input) -> {character, warnings[]}.
```

### Prompt C — Art-prompt assembly + image generation

```
Build the portrait pipeline. For each of the four fixed states
(at-rest, in-conversation, in-battle, travelling), assemble a RICH image-generation
prompt from the character's `art` fields + the statblock context + a per-state scene
modifier, then generate an image and return its URL/path. Write results into
character.portraits[state] = {prompt, imageUrl, seed}. Requirements:
- The prompt must carry enough SETTING, PLACING and WORLD context to read as D&D, not a
  floating figure on a blank background. Compose from, at minimum:
  • subject framing: size + creature type + kind + name, explicitly "a Dungeons & Dragons …"
  • appearance + outfit/gear + characteristic pose (from `art`)
  • a PER-STATE scene: where the subject is, what they are doing, the energy/camera —
      at-rest = calm candid moment; in-conversation = expressive, eye-level, companion off-frame;
      in-battle = dynamic mid-action, dramatic light, high tension;
      travelling = on the move, distance + weather, landscape behind
  • the ENVIRONMENT/location described as a high-fantasy place (lighting, time of day,
      foreground/background placement), and mood/personality
  • art style + quality tags, and "consistent character design across the set"
- Optionally weave in relevant statblock cues (e.g. a flying speed → airborne framing;
  resistances/damage type → visual motif) — keep it tasteful, never a stat dump.
- Deterministic assembly so the front-end can PREVIEW the prompt before generating
  (the prototype already shows a live preview built this way — match its structure).
- Keep ONE consistent subject across all four states; only pose, setting and energy change.
- Support regenerate-with-adjustment (free-text tweak + optional fixed seed).
- v1 regenerate is PROMPT-DRIVEN, not pixel-locked: the Gemini Developer API exposes no image seed,
  so `seed` round-trips in the schema (forward-compat) but won't reproduce identical pixels.
  True pixel-lock (Vertex AI / Stability) is DEFERRED — do not build it for v1.

FRONT-END CONTRACT — match exactly so the live preview equals the generated prompt:
- `state` is the kebab key: buildPrompt(character, "at-rest"|"in-conversation"|"in-battle"|"travelling").
  Display label per key (prototype strings, SENTENCE CASE — not Title Case):
    at-rest→"At rest", in-conversation→"In conversation", in-battle→"In battle", travelling→"Travelling".
- Deterministic segment order (mirrors the prototype's computePrompt). Segments joined with ". ",
  wrapped in “ ”, suffixed ' — <label LOWERCASED> variant.' — the prototype lowercases the label, so:
    " — at rest variant.", " — in conversation variant.", " — in battle variant.", " — travelling variant.":
    1. "{size} {type} — a Dungeons & Dragons {kindWord} named “{name}”"
       kindWord: monster→monster, npc→NPC, creature→creature, companion→animal companion,
                 pet→pet familiar, character→hero adventurer
       PC OVERRIDE — for kind:"character" with a pc{} block, build the subject from PC identity,
       not size+type: "a Dungeons & Dragons player character, a {pc.subspecies||pc.species}
       {pc.class} ({pc.subclass}) named “{name}”" (e.g. "a high-elf wizard (evocation) named Lyra").
    2. appearance · "wearing {outfit}" · "characteristic pose: {pose}"
    3. PER-STATE scene = "{action}; {camera+lighting}". The action is `art.stateBeats[state]`
       when present (character-specific, §1.1), else the generic action below; the camera+lighting
       clause (after the ";") is ALWAYS the generic one, for set consistency. Generic strings:
         at-rest:         "calm and at ease in a quiet, unguarded moment, relaxed candid posture; intimate close framing, soft warm ambient light"
         in-conversation: "mid-conversation, expressive and gesturing toward a companion just off-frame; eye-level medium shot, warm even daylight"
         in-battle:         "in the thick of combat, caught mid-action with real weight and motion; dramatic low angle, harsh rim light, dust and embers, high tension"
         travelling:      "on the move and mid-stride, covering ground; wide establishing shot, big sky and shifting weather, long golden-hour light"
    4. PER-STATE environment reframe — same world `{environment}`, reframed so the four backgrounds differ:
       "{envPrefix} {environment}, a high-fantasy world" (fallback "{envPrefix} an evocative high-fantasy location").
       envPrefix per state: at-rest "in a sheltered, still corner of" · in-conversation "in a lived-in, occupied part of"
         · in-battle "amid the chaos and wreckage of" · travelling "crossing the open expanse of"
       Then · "mood: {personality}" · style (fallback "painterly high fantasy")
       · fixed tail "full-body fantasy character art, cinematic composition, consistent character design across the set, rich detail, dramatic natural light"
    Statblock cues (flying speed → airborne, etc.) go AFTER this base so the leading text stays stable.
- imageUrl MUST be usable directly as an <img src>: an absolute URL
  (http://localhost:5000/art/{id}/{state}.png) or a data URI — never a server-local filesystem path.
  Round-trip `seed` unchanged for regenerate.
Provide:  buildPrompt(character, state) -> string   and   generatePortrait(character, state) -> {imageUrl, seed}.
```

### Prompt D — Decide whether Player-Character mode needs a distinct layer

```
Assess whether "player character" sheets need a schema/layout DISTINCT from the
monster/NPC statblock, or whether they can extend the same Character object.
NOTE (resolved direction): §1.1 already reserved optional `pc{}` and `spellcasting{}`
keys on the Character object — i.e. the EXTEND path is the chosen default. Design the PC
delta UNDER those two keys; do not add new top-level fields and keep `schemaVersion` at 1
(additive). Only argue for a separate sub-schema if you find a concrete blocker.
A 5e PC carries data a monster doesn't: class + subclass, level, race/lineage,
background, proficiency bonus, ability saves with proficiency, a full skill list with
proficiency/expertise, hit dice + death saves, initiative, attacks/cantrips,
spellcasting (slots, prepared/known), inventory/equipment + currency, features &
traits by source, and personality/ideals/bonds/flaws.
Deliverable: (1) a recommendation — extend vs. separate sub-schema — with rationale;
(2) the proposed PC schema delta as JSON; (3) which existing front-end surfaces
(Studio/Forge/Codex) can be reused vs. need a PC-specific view. Do not over-build;
propose the minimum that makes a PC sheet usable at the table.
```

### Prompt E — Design the ruleset switch

```
Design a ruleset abstraction so the forge can support D&D 5e (2014), D&D 5e (2024),
and homebrew "adaptions". Identify what actually changes between rulesets and capture it
in config. MONSTER/NPC side: creature type list, conditions, size categories, CR/XP table,
statblock field labels/order, renamed mechanics (note: 2024 statblocks add an Initiative
line — drive via labels/order, don't add a schema field).
PC side (now that pc{}+spellcasting{} exist — the config must drive these too):
- Option lists for the PC dropdowns: class, subclass-by-class, species/subspecies, background,
  feats. Same job the creature-type list does for monsters.
- Field LABELS that differ: "Race" (2014) vs "Species" (2024); the schema key stays
  `pc.species`/`pc.subspecies`, only the displayed label changes per ruleset.
- Ability-score rules: 2014 racial ASIs vs 2024 background ASIs; point-buy budget (27),
  standard array, bounds — these feed validate() and the Studio ability editor.
- Prepared/known spell mechanics and any spell renames (2024 differs); the level→PB and
  spell-slot tables (stable in official 5e, overridable for homebrew).
Deliverable: a `ruleset` config (JSON) the engine loads and the front-end reads to drive
BOTH monster and PC dropdowns + labels, plus a default config for dnd5e-2014. Support
INHERITANCE: a homebrew adaption declares `extends: "dnd5e-2024"` and overrides deltas only,
so a ruleset is base + patch. The Character object already carries a `ruleset` slug — make
the engine honour it (and fall back to dnd5e-2014 when unknown).
```

---

## 5. The meeting point

- **Front-end owns:** all rendering, the three surfaces, live editing, the parchment look, image slots, print/PDF, dropdown choices (it can pull option lists from the ruleset config in Prompt E).
  - **Prompt preview** fetches `GET /art/preview` (canonical, == generated, includes statblock cues), falling back to the client-side `computePrompt()` when the engine is unreachable. The only offline delta is the trailing statblock-cue clause appended after the variant suffix.
- **Engine owns:** the schema + maths (A), auto-fill (B), art prompts + images (C), and the two open design calls (D, E).
- **Shared contract:** the `Character` JSON in §1. Keep it stable; version with `schemaVersion`. When the engine adds structured proficiencies (§3.1) or a PC delta (D), bump the version and tell the front-end what changed.

### 5.1 Bridge / Flask contract (settle before building the Flask layer)

The front-end is a standalone HTML file, NOT served by Flask — so:
1. **CORS is mandatory.** Enable `Access-Control-Allow-Origin` for the dev origin (or serve the HTML from Flask). Without it every fetch fails. Confirm which.
2. **Slow endpoints (`/forge`, `/art`) — sync or async?** Imagen can take 10–30s. State whether these block until done (front-end shows a spinner) or return a job id to poll. Front-end builds the loading UX to match — pick one.
3. **Live prompt preview stays client-side.** `computePrompt()` runs per-keystroke locally; `GET /art/preview` is called only at generate-time (canonical check), NOT per keystroke. Preview must accept the CURRENT (possibly unsaved) draft — so expose it as `POST /art/preview {character, state}` OR require a `POST /character` save first and document that. Don't assume an `id` exists at preview time.
4. **Exact JSON shapes** (please confirm/return):
   - `POST /forge {dump, ruleset?, kind?}` → `{character, warnings[]}`
   - `POST /art {id|character, state, tweak?, seed?}` → `{imageUrl, seed, prompt}` (one state per call? or all four?)
   - `GET/POST /character` → is there a LIST endpoint (`GET /character`) for the starter rail, plus `GET /character/{id}` and `POST /character`? id = slug.
   - `GET /ruleset/{slug}` → confirm top-level keys: `{labels, abilityRules, statblockOrder, initiativeLine, optionLists{class, subclassByClass, species, subspecies, background, feat, conditions, sizes, creatureTypes}}`. Add `GET /rulesets` (available slugs incl. homebrew) for the ruleset selector.
   - `warnings[]` element shape: plain strings, or `{level, message}`?
5. **Generated image vs drop-slot.** `portraits[state].imageUrl` (engine-served) and the manual `image-slot` drop zones are two different mechanisms. Front-end renders `imageUrl` as a plain `<img>` when present, drop-slot is the fallback — the engine just needs `GET /art/{id}/{state}.png` to be a stable, content-typed URL. No engine awareness of image-slot needed.

### 5.2 Bridge wiring — BUILT on the front-end (matches the locked contract)

The prototype is now wired to all nine endpoints via a thin bridge adapter with silent fallback:
- **Probe on mount:** `GET /rulesets`; success → "Bridge live", populates the ruleset selector, `loadRuleset(slug)`, and `GET /character` for the starter rail (merged after the local samples). Failure → "Local preview" and the original local-sample behaviour.
- **Studio:** option lists (sizes, creatureTypes, alignments) come from `ruleset.optionLists` when live; the PC strip becomes live dropdowns (class · subclass-by-class · species · background) with the **`labels.species`** flip ("Race" 2014 / "Species" 2024). Offline → the read-only strip.
- **Forge:** the button calls `POST /forge {dump, ruleset, kind}`, shows a "Forging…" busy state, swaps in the returned `character`, and renders `warnings[]` as a Validation panel coloured by `level` (error/warning/info).
- **Portraits:** each of the four slots renders `portraits[state].imageUrl` as a plain `<img>` when present (engine-served or freshly generated); a per-slot **Generate / Regenerate** button calls `POST /art {id, character, state}` (one state per call) with an independent spinner; the manual `image-slot` drop zone is the fallback when no URL exists. Codex shows the same image, drop-slot fallback.
- **Config / override:** base URL defaults to `http://localhost:5000`; override via `localStorage.forgeBridgeUrl` or `?bridge=<url>`. The probe only fires from a `file://`/localhost/override context, so a cloud-hosted copy stays in fallback without throwing. **Note for the engine side:** if the dashboard is ever served from a non-localhost origin over https, the browser blocks http://localhost as mixed content — serve the bridge over https or the HTML from Flask in that case (localhost-to-localhost is fine; Chrome treats localhost as secure).
- **Open items for the engine to confirm:** exact `GET /rulesets` payload shape (array of slugs vs objects — adapter handles both), and that `GET /character` returns a list of `{id|slug, name, kind, challenge, accent?}` summaries for the rail. `/art/preview` is reserved in the adapter (client `computePrompt()` is the live preview); wire it at generate-time if you want the canonical-cue check enforced.
