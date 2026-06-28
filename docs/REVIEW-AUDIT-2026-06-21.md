# Review & Audit — Forge front-end + art changes (session 2026-06-21)

**Purpose:** a complete, interlinked map of *everything changed this session* (plus the parallel-chat work merged
into the same files), so you can review **suitability** end-to-end. Grouped by feature; each entry lists **what it
does**, **where it lives** (file · function), **how it interlinks**, and **verified vs needs-your-test**.

Two files hold almost all of it: the front-end `web/frontend/Character Forge - Prototype.dc.html` and the bridge
`forge/web/app.py`; art logic is in `forge/agents/art.py`. Nothing is committed/pushed — all local.

---

## A. Forge UX (closes the create → sheet loop)
- **Confirm dialog before any forge** — gates BOTH entry points (brain-dump button + Surprise "Forge this").
  `requestForge(source)` → `forgeConfirm` state → dialog → `confirmForge()` routes to `doForge()` (block) or
  `forgeFromConcept()` (concept). Shows a "What you'll forge" summary + a **rules-mode reminder that names the
  selected edition** (`rulesModeHint`/`editionLabel`). Cancel spends nothing.
- **Full-screen loading lock** while `forgeBusy` — dark/blur scrim (z-index 320) + animated quill/scribble
  (`pf-scribble`/`pf-quill`/`pf-dots` CSS). Locks the whole UI during a forge.
- **Stay-in-Forge + progression strip** — after a forge it no longer auto-jumps to Studio; sets `forgeDone`,
  shows "Forged… open the character sheet" (+ the companion springboard button, see D).
- **Library "reconnecting" state** — `componentDidMount`→`probeBridge()` retries every 4s (`bridgeRetrying`);
  "My creations" distinguishes connecting/reconnecting vs local-preview vs genuinely-empty.
- **Verified:** dialog gating, edition in reminder, overlay render, all via Preview MCP. **Test:** the feel of the
  loading animation during a real forge; the reconnecting state (stop the bridge to see it).

## B. 5-kind picker + per-kind Surprise
- **Kind picker** Player / NPC / Monster / Companion / Pet (`forgeKind`, `pickForgeKind`→`setKind`, render array
  `forgeKinds`) — mirrors the library buckets. **Default now = Player.**
- **Surprise me** rolls a tailored recipe per kind (`this.SURPRISE` curated lists + `rollConcept`/`conceptLine`/
  `forgeFromConcept` all branch 5 ways): PC = class/subclass/species/bg/level · Monster = type/size/CR · **NPC =
  role-based** (ancestry+occupation+tier+hook) · Companion = beast+size+temperament · Pet = familiar+quirk.
  **Warlock roll** also rolls patron+boon (see F).
- **Verified:** all 5 recipes produce sensible concept lines; default-Player highlights. **Test:** roll several of
  each; do the concepts read well to you?

## C. Per-kind flavour fields + bonded-creature dropdown
- **Flavour panel adapts per kind** (`flavourFieldDefs(kind)` + render array `flavourFields` + `<sc-for>`): PC/NPC =
  age/origin/memory · Monster = nature/lair/hungers · Companion = met/moment/quirk · Pet = found/favourite/quirk.
  `flavourText()` reads the current kind's fields → sent to `/forge` as `details`.
- **Bonded-creature dropdown** (PC/NPC only): None / Companion / Pet / Familiar + a description + caster hint +
  the warlock **Pact & patron** line (see F). Woven into `flavourText()`.
- **Verified:** per-kind fields + dropdown + pact line render and weave. **Test:** does each kind's set of nudges
  feel right?

## D. Companion / familiar LINKING (the "build a team" thread, P2 complete)
This is the most interlinked feature — follow the chain:
1. **Capture:** the bonded dropdown + description live in `flavour.bonded`/`bondedDesc`; `flavourText()` adds
   "They have a <companion/pet/magical familiar>: …" to the forge brief.
2. **Owner's portraits:** on forge, `doForge` sets `ch.art.companion` (via `companionShortForm`, which strips a
   leading name) and weaves it into `art.appearance` with `applyCompanion()` — **a byte-for-byte mirror of the
   engine's `apply_companion`** ("accompanied by … always at their side") → the companion appears in ALL four
   portraits.
3. **Springboard:** `doForge` records `pendingCompanion`; the progression strip shows **"Forge <name> too →"**;
   `forgeCompanionFromOwner()` seeds a fresh Forge draft — kind (Companion→`companion`, Pet/Familiar→`pet`),
   pre-filled dump ("…of <owner>" + inherited world/art-style), and stores **`companionOf:{name,id}`** + **`bondType`**.
4. **Carry-through:** the engine returns a fresh character on forge, so `doForge` re-attaches `companionOf` +
   `bondType` onto it, then runs `applyCreatureGuard` (see E).
5. **Library:** `forge/web/app.py` `_char_summary` now returns **`companionOf` + `bondType`**; the front-end shows a
   **"Familiars" group** (split from Pets by `bondType==="Familiar"`) and a **"↳ <owner>'s familiar/companion/pet"**
   link line on each.
- **Verified:** springboard seeds correctly; Familiars group + owner link render with a mock. **Test:** the full
  loop live — forge a PC w/ familiar → "Forge it too" → save → confirm it appears under **Familiars** as
  "↳ <PC>'s familiar".
- **Note:** an existing pre-fix familiar (e.g. Soot/Ember) won't carry the `bondType` tag — only ones forged from now.

## E. Art / portraits
- **"✦ Generate all 4 (one consistent character)"** button (Portrait-set panel) → `genArtSet()` → `POST /art/set`
  → fills all 4 slots + folds into draft + saves. (`artSetBusy` guard; 240s timeout.) Per-state ⟳ still regenerates one.
- **Consistency identity-lock** — `forge/agents/art.py` `openai_backend` now passes **`input_fidelity:"high"`** to
  `images.edit` (with a safe fallback if the API rejects it) — the main lever for "same person across the set".
- **Companion-in-portraits** — via `art.companion` + `applyCompanion` (see D2).
- **Thin-creature guard** — `applyCreatureGuard()` prepends "a small non-humanoid creature"/"a non-humanoid animal"
  to pet/companion/familiar appearance (idempotent) so anchors stop drifting humanoid (the "dragonborn" issue).
- **Bug fixes:** `companionShortForm` no longer mangles multi-word creature descriptions; `computePrompt`'s PC-subject
  title helper now **preserves hyphens** (Half-Elf/Half-Orc/High-Elf) to match the engine's `_title`.
- **INVARIANT (load-bearing):** front-end `computePrompt()` must equal engine `build_prompt()` **byte-for-byte** — the
  preview IS the generated prompt. All art changes above keep this; **verified equal across all 4 states** incl. the
  companion. ⚠️ Item ② (per-kind portrait scenes, still TODO) must preserve this too.
- **Test:** re-run "Generate all 4" — does the face/outfit hold across the set now?

## F. Warlock pacts
- **Surprise path** (parallel chat): rolling a Warlock rolls patron + boon (`SURPRISE.warlockPatrons`/`pactBoons`/
  `chainForms`); concept panel shows it; `forgeFromConcept` weaves it in; **Pact of the Chain auto-seeds a Familiar**
  (→ feeds the springboard, D3).
- **Manual path** (this session): an optional **"Pact & patron"** line in the flavour box for PC/NPC, woven into
  `flavourText()` ("Warlock pact & patron: …") — so typed warlocks get it too.
- **Test:** Surprise a warlock; type a warlock with a pact note — does the pact carry into the result?

## G. From-sheet upload
- The top-bar **"⚒ Auto-fill from sheet"** button is now a **real file picker** (`pickSheet`/`onSheetFile`, hidden
  `#ff-sheet-input`, `.docx/.pdf/.txt/.md`) → `POST /forge/sheet` (back-end already built) → lands the draft in the
  **Studio**. Shows the loading lock while reading; surfaces a clean warning on a scanned/empty PDF.
- **Verified:** wiring + endpoint present (not a live upload). **Test:** upload a real Word/PDF sheet.

## H. Engine / data (delegated + in-flight)
- **2024 data** (landed): 339 spells + 160 slot tables native; **a background agent is right now switching the 3
  engine call sites to use it** (per `docs/SRD-2024-DATA-HANDBACK.md`) — result pending; will be verified on return.
- **2014 data** (landed): subclasses 12→66, backgrounds 1→13, subraces 4→9, feats 1→57 → the Forge dropdowns +
  Surprise rolls are richer automatically. Remaining engine bits (subrace ability bonuses, feat prereqs) are queued.
- **Art engine** (landed): OpenAI `gpt-image-1.5`, set-conditioning, class beats, companion-in-states.
- **From-sheet** (landed): `sheet_extract.py` + `POST /forge/sheet`.

---

## Interlink / dependency map (what affects what)
- **Byte-for-byte chain:** ANY change to `computePrompt` (front-end) MUST be mirrored in `build_prompt` (`art.py`),
  and vice-versa. Touched by: companion weave, creature guard, hyphen fix — all kept equal. **Item ② will touch this.**
- **Bridge restart triggers:** any `forge/web/app.py` change (`_char_summary` bondType/companionOf, `/forge/sheet`,
  `/art/set`) or `art.py` change (`input_fidelity`) needs the bridge restarted to take effect.
- **`bondType` + `companionOf` flow:** set on the creature (springboard) → carried through `doForge` → surfaced by
  `_char_summary` → drives the library **Familiars group** + **owner link**. (If the summary lacks them, the library
  can't group/link — they were added this session.)
- **Familiar = `pet` + `bondType:"Familiar"`** (no new `kind`; keeps the locked 6-kind contract additive-only).

## Verified ✅ vs Needs your test 🔬
| Area | Verified (mechanism) | Needs your live test |
|---|---|---|
| Confirm dialog / overlay / strip | ✅ render + gating | feel of the loading anim |
| Reconnecting library | ✅ logic | stop bridge to see it |
| 5-kind Surprise | ✅ all 5 concepts | do they read well |
| Per-kind flavour + bonded + pact | ✅ render + weave | wording suitability |
| Springboard + Familiars group + link | ✅ via mock/instance | full live loop + a saved familiar |
| Generate-all set + identity-lock | ✅ wiring + invariant | **does the face hold** |
| Companion-in-portraits | ✅ invariant across 4 states | does it look right in images |
| Thin-creature guard | ✅ logic | fewer "dragonborn" first-rolls |
| From-sheet upload | ✅ wiring + endpoint | a real Word/PDF upload |
| 2024 native data switch | ⏳ agent in flight | (its own tests) |

## Still TODO (not in this audit's scope yet)
Front-end pack remaining: **② per-kind portrait scenes · ④ examples redesign · ⑤ Codex HTML export · ⑥ full Studio
editing.** Engine: 2014 subrace bonuses · feat prereqs · Monster Manual pass. Decisions: commit/push · retire v1 files.
(Full list = `HANDOVER.md` §11.)
