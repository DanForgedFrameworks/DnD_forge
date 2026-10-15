# Forge — Issues & Open Work

**Status: EXECUTING — data redraw landed (both 2014 + 2024).** Hold lifted 2026-06-29. Capstone review
part 1 done: all data loads, 11/11 tests pass, no breakage. Now working the wiring tasks.

**Progress (backend mechanics done — all unit-verified, 11/11 tests, 18/18 saved chars re-derive clean):**
- ✅ Capstone review part 1 — load/coverage (all categories load both editions).
- ✅ **A.1 Foundation** — equipment/spells/trinkets accessors + endpoint routing (slug-gated, de-duped, OCR-flagged).
- ✅ **A.2 Feat-prereq gating fn** — `local_data.feat_prereq_status(feat, character)` (advisory; parses
  Level/Ability/Feature/feat-name; 9/9 test cases pass). UI picker still to build.
- ✅ **A.5 Firearm flag** — local equipment cards carry `firearm:True` (musket/pistol). UI gate still to apply.
- ✅ **A.6 Multiclass caster level** — edition-aware: half-casters round DOWN (2014) / UP (2024), third-casters
  (EK/AT) now counted. ⚠️ **CONFIRM:** the 2024 round-UP is from the owner's book-verified data — flag for sign-off.
- ✅ **A.7 Languages secret-filter** — Druidic/Thieves' Cant out of the picker (17 shown, still class-granted).
- ✅ **A.9 (2014) Subrace ability bonuses** — chosen subrace's bonuses now applied (Hill Dwarf +2 CON +1 WIS).
- ✅ **A.8 Weapon-mastery warrior gate** — RESOLVED (no data needed): warrior classes derived from the
  class-features data (barbarian/fighter/paladin/ranger/rogue have the Weapon Mastery feature). Non-warriors
  now have any mastery stripped (wield, don't apply); warriors keep it. Verified.
- ✅ **A.2 Feat picker UI** — new `/feats` endpoint (prereq-evaluated per character) + a Studio Feats
  section with the picker modal (grouped by type, locked feats greyed 🔒 but still addable). 74 feats,
  12 epic-boons correctly locked at L5; SRD returns 0. Live-verified.
- ✅ **A.3 Spell picker UI** — OCR-suspect spells flagged ⚠ (not hidden), `at_higher_levels` + level in
  the button tooltip. Live-verified (255 wizard spells, 10 flagged on -local).
- ✅ **A.4 Trinket item + randomiser action** — Trinket in the catalog; its + Action rolls the d100 table
  (fresh each press, reconcile-safe source). Engine-verified.
- ✅ **A.5 Musket/Pistol picker gate** — hidden unless DEX 13+ or Firearms proficiency; mastery shown on
  weapon cards; firearm flag now survives the SRD/local merge. Live-verified (flagged on -local, 0 on SRD).
- Front-end parses with ZERO console errors; app connects to the bridge and loads all three rulesets.
- ✅ **A.6 confirmed** by owner (2026-06-29) — 2024 half-caster round-up is correct.
- ✅ **A.10a (2014 feat prereqs)** — `/feats` now serves all editions (2014: 57, SRD-2024: 17, local: 74)
  with prereqs evaluated; the feat picker shows for any live PC. Robust to both feat data shapes.
- ✅ **A.10b (background choose-one tools)** — backgrounds carry `toolChoices`; a Studio input lets the
  player name the tool (`pc.bgTools`), applied to proficiencies by `grants.py`. Verified (folk-hero → Smith's Tools).
- ✅ **A.11 Barbarian Rage table** — hardcoded from the PHB (⚠️ owner to confirm the exact numbers);
  surfaced as a "Rage — at a glance" feature (L5 → 3 Rages · +2 dmg · 3 weapon masteries).
- ✅ Integration check: 18/18 saved chars derive clean, all companion links resolve (id+name), SRD clean, 11/11 tests.

**Cross-stage wiring audit (Forge→Studio→Codex→Play) — done, gaps fixed:**
- ✅ Audit confirmed: companion links solid (two-key id+name, self-heal sound, offer-gating correct); re-derive/save
  do NOT clobber editable pc subfields (feats/bgTools/boosts/languages all survive); edition handling follows the character.
- ✅ **FIXED — feats were a write-only dead-end.** Chosen `pc.feats` now surface as features via `derive_feats()`,
  so they render on the Codex AND Play sheets (and export). Verified both editions. (NB: feats DISPLAY everywhere
  now but are not yet auto-applied MECHANICALLY — most are situational; full mechanical application is a separate task.)
- ✅ **FIXED — owner-rename could sever a null-id companion link.** `_sync_companion_links()` on save cements a
  companion's null id from a name match, then propagates any rename by id. Verified: rename now propagates to all
  linked companions; the link can't break again once the owner's been saved.
- ✅ **FIXED (cosmetic):** stale "2024-local only" feat-picker message; ability-boost note no longer shows on a 2014
  sheet; owner-name matching is now case-insensitive in both link directions.
- ⏳ Minor remaining: `pc.bgTools` shows under Tools but isn't labelled "from background"; a derivePc race if you type
  during an in-flight re-derive (low frequency). Both low-priority.
- ⏳ Capstone review part 2 (horizontal content pass) — OWNER will run this.

_Last updated: 2026-06-29_

---

## Reported UI issues (ad-hoc, as reported)

- **[UI] Language "🌐 Browse" button clipped / misplaced.** In the Studio language editor the Add/Browse
  row is a single non-wrapping flex row — two inputs (`flex:1` + `flex:2`) plus the **Add** and
  **🌐 Browse** buttons — so on the narrow Studio column it overflows and the Browse button is cut off
  at the right edge. Fix: let the row wrap (`flex-wrap:wrap`) and/or move Browse onto its own line, or
  trim the input flex. Location: `web/frontend/Character Forge - Prototype.dc.html:462-466`.

- **[art] Companion portraits don't visually match the owner PC/NPC.** The companion forge inherits the
  owner's art *style string* correctly (e.g. Casimir Vael and his forged companion "Soot and Ember" share
  the identical style line), but two independently-generated portraits still don't match in palette/
  lighting/likeness — a shared style sentence isn't enough. Likely needs the owner's actual portrait fed
  in as a visual reference (image-to-image / reference seeding) or generating the set together. Secondary
  drift: the figure woven into the owner's portrait (`art.companion`, "playful and fierce brother") and
  the separately-forged companion identity ("Soot and Ember") aren't kept in sync. Examples:
  `casimir-vael-*.json`, `soot-and-ember.json`. Touches `build_prompt` (art.py) ⇄ `computePrompt()`.

- **[art] Static environment bleeds into state-specific portraits (travelling/battle). — DONE: `art.stateEnvs` implemented (engine + front-end fields).** The character's
  single `a.environment` is appended to all four scene lead-ins, including "Travelling" ("crossing the
  open expanse of …") and "In battle" ("amid the chaos and wreckage of …"). For a character whose home
  scene is a specific indoor place — Brindle the hearth cat's fireplace — the Travelling portrait reads
  "crossing the open expanse of a cosy fireplace," so a fireplace appears behind the travelling cat. Fix:
  per-state environment overrides (`art.stateEnvs`, mirroring the existing `art.stateBeats`) so
  travelling/battle use a fitting scene rather than the home environment, falling back to the generic
  scene env when none is set. MUST keep `build_prompt` (art.py) == `computePrompt()` byte-for-byte.
  Location: `computePrompt` ~`web/frontend/Character Forge - Prototype.dc.html:3287-3305` + `forge/agents/art.py`.

- **[design direction] Brain dump should be FREER than the concept sheet.** The quick brain dump is
  "go for it" — it should give the forge AI more creative, rule-of-cool latitude (rules-legal, but bold),
  which is what produced the benchmark Casimir Vael. The concept sheet is "I've got more of an idea and I
  want to guide it" — it should adhere more tightly to the user's specified fields. Implication: the two
  entry paths likely want different prompting/latitude rather than sharing one prompt. Not a bug — a
  product-direction note for when the forge prompt is next revisited.

- **[bug] Proficiencies (Weapons/Tools line) don't self-heal on load — can show stale on the Codex.**
  GET `/character` refreshes features, languages and actions on load (`_refresh_features` etc.) but does
  NOT run `resolve_pc_proficiencies`, which only runs on save. So a character whose class changed via a
  non-deriving path (or before the re-derive fix) keeps a stale `pc.proficiencies` Weapons/Tools line on
  the Codex until it's re-saved. (Borin Stonegrip's own line is actually CORRECT — wizard + criminal — so
  he's not the stale case, just where it was spotted.) Fix: run `resolve_pc_proficiencies` in the GET path
  too, mirroring how features/languages already self-heal. Location: `forge/web/app.py` GET handler
  (~528-536). Cosmetic note: "Crossbows, light" would read better as "Light Crossbows".

- **[principle/design] Preserve the "spirit of cool" generated content.** Older forges (e.g. Casimir
  Vael, Marquess of Hollowmere) generated rich, Rule-of-Cool material as AI free-text: flavoured
  **actions** ("Pact Blade — summoned blade of black glass", "Eldritch Blast — the air tasting of low
  static"), a flavoured **reaction** ("Opportunity Attack — lashes out with his pact blade"), narrative
  **items** ("Star-chart bound in violet leather", "Scroll of pedigree", "Signet ring of House Vael"),
  and **bonded elements** in the portrait ("playful and fierce brother"). These are valued but are NOT
  canon-backed, and the new structured tooling doesn't preserve/reproduce them. Want: the canon pickers
  (esp. reactions) should let you ADD/keep this flavour rather than offering canon-only, and the forge
  should keep generating it. Cross-links the two items below (reaction selector has no options to capture
  such flavour; bonded elements in `art.companion` have no forge path). Examples: `casimir-vael-*.json`,
  `borin-stonegrip.json`.

- **[data/wiring] Companion in `art.companion` only → no "Forge X too" button.** A companion described
  at forge time can end up solely in the portrait text (`art.companion`, e.g. Borin Stonegrip's badger
  "chocolate chops") with no structured `bonded` record. The named **"Forge <companion> too"** offer
  requires `bonded.type`, so it never appears — only the generic **+ Pet/+ Companion/+ Familiar**
  buttons (which don't pre-fill the existing companion). NOT caused by the recent offer-gating change
  (`bonded` is `None` there, so the gate never applies). Fix: synthesise an effective bonded offer from
  `art.companion` when `bonded` is missing (default type Pet, desc = the portrait companion line), so the
  springboard pre-fills the creature already on the sheet. Location: render `hasDeclaredBonded` /
  `declaredBondedLabel` / `onForgeDeclaredBonded` ~`web/frontend/Character Forge - Prototype.dc.html:583-588, 3850`.

- **[UI/data] No reaction selector options.** Reactions have no populated picker like spells/feats/
  equipment/languages do. The Studio offers only a blank manual **"+ Reaction"** row (free text) plus
  the **"⚑ Common actions"** picker — and `/actions/standard` defines just **2** reactions (Opportunity
  Attack, Ready). Needs a reaction catalog (class/subclass/feat reactions — Shield, Counterspell,
  Uncanny Dodge, Hellish Rebuke, etc.) feeding a searchable selector. Likely overlaps the 2024 data
  work (class/subclass features already carry reaction-kind entries). Location: editor at
  `web/frontend/Character Forge - Prototype.dc.html:654-665`; source `forge/engine` `standard_actions()`.

---

## H. Capstone — full mapping review once the data redraw lands (do FIRST)

20. **Full top-to-bottom + horizontal review against the redrawn 2014 & 2024 data.** Once the complete
    redraw of both editions is in, do a comprehensive review before tackling A–G:
    - **Top-to-bottom (per character/edition):** every class, subclass, species, background, feat, item,
      spell, action, reaction and trait maps to suitable, complete content — name + description +
      mechanics/outcome present, no blanks, no OCR cruft, no orphaned references.
    - **Horizontal (across the set):** consistency across all PCs/NPCs/creatures and across 2014 ⇄ 2024 —
      same shapes/fields (different titles OK), parity of coverage, descriptions/actions/reactions/traits
      all populated and edition-appropriate.
    - Output a coverage/gap report and feed any holes back into the relevant A–G items.

---

## G. Studio parity & non-PC customisation (new)

16. **Codex ⇄ Studio parity.** Things shown on the Codex but with no Studio editor feel "missing" from
    the Studio. Confirmed in data: all saved PCs DO have editable `pc.equipment` (Codex and Studio read
    the same field), so equipment is in sync — the actual gap is the **proficiencies (Weapons/Tools)
    line**, which renders on the Codex as lore but has no Studio editor. Rectify: give proficiencies a
    Studio view/editor (and audit for any other Codex-only fields). Confirm exact spots in the live
    click-through.
17. **Expand non-PC Studio customisation.** Non-PCs (monsters, NPCs, companions, pets, familiars)
    currently get a simpler statblock editor; the rich editor (class/species/background/level/features/
    languages/abilities) is PC-only. Add more Studio options for non-PCs — possibly a full Studio for
    customisation of any creature type.
18. **Party HTML — linked play sheet.** Export a whole team (a PC + their bonded companions/pets/
    familiars) as one self-contained, offline play sheet, with each member's play reference linked/
    navigable to the others. Today export is per-character only (`downloadHtml` + `playReferenceHtml`)
    and the Party tab (`teams`) is view-only — so this bundles the existing pieces into a single party
    document.
21. **Sidekick system for bonded creatures (Tasha's: Expert / Spellcaster / Warrior).** Wire the existing
    `data/srd/2014/5e-SRD-Sidekicks.json` (3 types, each with full `features` + `levels`; Spellcaster has
    `spellcasting_roles`) so a companion/pet/familiar/NPC can "become a sidekick" and level up alongside
    the party. Currently the data is extracted but NOTHING in the engine/UI references it. Sidekicks are
    a Tasha's optional rule and edition-agnostic (no separate 2024 system) — confirm the exact 2024
    treatment against the redrawn data. Decisions: (a) can only ever be one of the 3 types; (b) whether/
    how to allow a familiar to be a sidekick (RAW familiars are a distinct summoned-spirit mechanic — a
    design choice, not forbidden); (c) push rule-of-cool by flavouring the chosen type's features via the
    #12 enrichment pass. Ties to #17 (non-PC studio) and #19 (bonded creatures).

19. **Bonded creatures get equipment, coin & actions/attacks (not forced martial).** A pet/companion/
    familiar should support its own equipment & coin and derive actions/attacks from gear — extends the
    PC-only equipment/coin editor + weapon-action derivation to bonded non-PCs (ties to #17). A PC's
    bonded creature already can appear as an equipment entry with an action (Borin's "Chocolate Chops
    (pet badger)", `hasAction:true`) — make that consistent for all bonded creatures. IMPORTANT: don't
    force a martial/combat action on every pet (a non-combat badger needs none); for the ones that
    warrant it, offer an AI-drafted novel/flavourful action (Gemini), reusing the #12 enrichment pass.

---

## A. Backend tasks (data landed 2026-06-29 — executing)

_Collated from the data-extraction signpost (8 engine tasks) + the 2014 remaining items. Integration
check passed after A.1: shape parity 2014⇄2024 holds (0 divergent fields), all 18 saved chars derive
clean, SRD builds leak no local keys, 11/11 tests green._

- **A.1 ✅ Foundation — DONE.** `local_data.equipment()/spells()/trinkets()` accessors; equipment+spells
  routed through `/equipment` & `/spells` gated on the `-local` slug (de-duped, OCR-flagged); trinkets
  reachable. SRD-only builds verified clean.
- **A.2 Feat-prereq gating.** Function over `prerequisites_text` per type: origin → always; fighting-style
  → only if the character has that feature; epic-boon → L19+; general → parse free text (level / ability
  score / another feat) and evaluate vs character state. Backend gate fn + a feat picker (none exists yet).
- **A.3 Spell picker UI.** `classes[]` filter (data ready); `ocrSuspect` → small warning icon (don't
  hide); `at_higher_levels` → distinct block in the detail view (separate string, via `local_data.spell()`).
  Note: Divine Smite is a L1 Paladin spell in 2024 — don't also render it as a class feature.
- **A.4 ✅ Trinkets = item + randomiser action — DONE (a1eabe5).** Not a creation-step wizard — a **Trinket item**
  whose **+ Action** rolls the d100 table (`local_data.trinkets()`), same pattern as Bag of Holding (#4).
  Engine item-action + the catalog item.
- **A.5 Musket/Pistol gating.** Hide from the weapon picker unless DEX 13+ or a class/subclass granting
  Firearms proficiency. `eligibilityNote` is already surfaced on the local cards — add the gate.
- **A.6 Multiclassing.** Compound prereqs (Fighter STR OR DEX; Paladin STR AND CHA; Monk DEX AND WIS) +
  weighted-level slot formula (full / half-round-up / third-round-down; Warlock pact slots interchangeable),
  using `spellcaster_slot_table`. Verify against existing `progression.py` (slot table already correct).
- **A.7 Languages secret-filter.** Keep `secret:true` (Druidic, Thieves' Cant) out of the standard
  language picker — they're class-granted (Druid/Rogue), already routed via features.
- **A.8 Weapon masteries.** `warrior_classes` gating: non-warrior classes can wield a weapon but not apply
  its mastery. Mastery injection partly wired (`actions.py`); add the warrior-class check.
- **A.9 (2014) Subrace ability bonuses.** `builder.py` applies the race's bonuses but not the chosen
  subrace's — wire subspecies lookup into `apply_ability_bonuses` (2014 path).
- **A.10 (2014) Feat prereqs + background choice-tools.** 2014 feats are list-only (prereqs unread);
  background "choose one" tools in `starting_proficiency_options` are ignored by `grants.py` — decide
  surface/apply.
- **A.11 Barbarian per-level resource table** (Rages / Rage Damage) — not in the class-features JSON
  (OCR-garbled columns); hardcode from the PHB table only if the front-end needs the values. Low priority.

## B. Open feature requests (floated earlier, not started — lower priority)

4. **Bag of Holding** — plus a "used" variant that rolls randomised contents.
5. **Deck of Many Things** — full card list + mechanics, possibly its own tab.

## C. To confirm during the live click-through (status uncertain)

6. **PC XP editing** — PCs currently level via the Level control; the Challenge/XP box is for non-PC
   creatures only. Confirm whether XP tracking is wanted for PCs as a separate thing.
7. **"⚔ Attack" button clarity** — was flagged as confusing; confirm the current label/tooltip reads
   clearly now.
8. **Companion category lock** (e.g. Goliath as pet vs familiar) — confirm the bond type is editable
   and sticks.

## D. Deferred audit polish (non-breaking, cosmetic)

9. **Play attack lines** — the Play sheet parses attack text by pattern; a hand-written or oddly-phrased
   attack shows its name only, with no hit/damage line.
10. **Companion data cleanup** — deleting a companion now correctly hides the "Forge X too" offer, but
    the owner's stored bond record (`ch.bonded`) isn't wiped (invisible; the offer behaves correctly).

---

## F. Wonky Forge Homebrew — capture, enrichment & companion sync (proposals)

_Good news: the plumbing largely exists already — `data/srd/_homebrew/` overlay (equipment, item_actions,
standard_actions = actions+reactions, species_traits), a provider-aware Gemini client, and reference-image
art support in `art.py`. These are wiring jobs, not from-scratch builds._

11. **Wonky Forge Homebrew store + retrofit.** Save any fresh/novel item, action, reaction or trait
    (from either entry path) into the `_homebrew/` overlay so it persists, shows in pickers, and merges
    into canon. Retrofit: scan all saved PCs/NPCs, diff their elements against canon, harvest the novel
    ones (dedup by index) into the overlay files. Tag them homebrew.
12. **Optional AI enrichment ("make it table-ready").** For a novel / rule-of-cool element, offer a
    one-click pass that calls the existing Gemini client to generate a rules-suitable description +
    action/outcome grounded in the original, saved to the homebrew shelf. Opt-in (plain items stay plain).
13. **Concept-sheet novel elements — free text + homebrew, never omit (ADVISED).** Don't make the
    concept sheet canon-only. Novel elements from EITHER path are kept as free text by default and saved
    to the homebrew shelf; the strict/relaxed rules toggle governs rules-enforcement (flag-what's-invented,
    not delete-it). Brain-dump-vs-concept-sheet stays about AI latitude, not whether homebrew is allowed.
15. **"Back room" homebrew editor.** After the retrofit (#11), provide an editor UI to manage the Wonky
    Forge Homebrew entries — view/edit/delete novel items, actions, reactions, traits — **arranged by
    theme/utility/type** (e.g. martial · utility · flavour-only/"pointless" · etc., whatever buckets fit
    best). A back-of-house workshop for curating the harvested homebrew, separate from the per-character
    Studio.

14. **Companion ↔ owner sync (retro Soot and Ember into Casimir).** A forged companion should be written
    back into the owner's `art.companion` + portrait/description so they match. Casimir's portrait/text
    still references the stale "playful and fierce brother" rather than his actual forged companion
    "Soot and Ember"; retro-reconcile Casimir (prompts, concept, Studio) and keep owner art.companion in
    sync with the forged companion going forward. (Relates to the art reference-image item above.)

---

## E. Done (closed — listed so we don't reopen)

- Integration audit fixes: re-derive on class/species/background/subclass change; save re-syncs the
  engine's derived character; 2024 background panel shows for plain `dnd5e-2024` (not just `-local`);
  characters remember their edition (open switches ruleset); companion-link self-heals a null owner id.
- `test_grants` corrected (stale expectation, not an engine bug) — **full suite green (11/11)**.
- 2024 Common language auto-granted at creation (languages moved off species in 2024).
- Companion duplicate "Forge X too" offer suppressed once a linked companion exists.
- 2024 background ability-boost provenance shown on Codex, live Play, and the Play HTML export.
